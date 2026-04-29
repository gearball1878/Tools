from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re


@dataclass
class InterfaceInstance:
    name: str
    signals: list[str]
    template_name: str
    index: int
    link_or_port: str
    family: str = "interface"

    @property
    def bc_line(self) -> str:
        return f"{self.name} {','.join(self.signals)}"


class BusContentTemplates:
    def __init__(self, template_path: str | Path):
        self.template_path = Path(template_path)
        self.data = json.loads(self.template_path.read_text(encoding="utf-8"))

    def families(self) -> list[str]:
        return ["Interface", "Control", "Status", "Analog", "Power", "Memory"]

    def interface_templates(self) -> list[str]:
        return list(self.data.get("Interface_Temp", {}).keys())

    def control_signal_templates(self) -> list[str]:
        return list(self.data.get("Control_Signal_Temp", {}).keys())

    def status_signal_templates(self) -> list[str]:
        return list(self.data.get("Status_Signal_Temp", {}).keys())

    def analog_bus_templates(self) -> list[str]:
        return list(self.data.get("Analog_Busses", {}).keys())

    def analog_signal_templates(self) -> list[str]:
        return list(self.data.get("Analog_Signal_Temp", {}).keys())

    def voltage_signal_templates(self) -> list[str]:
        return list(self.data.get("Voltage_Signal_Temp", {}).keys())

    def domains(self) -> list[str]:
        return list(self.data.get("TecDomains", {}).keys())

    def memory_technologies(self) -> list[str]:
        return list(self.data.get("Memory_Interface_Temp", {}).keys())

    def memory_subtechnologies(self, technology: str) -> list[str]:
        obj = self.data.get("Memory_Interface_Temp", {}).get(technology, {})
        return list(obj.keys()) if isinstance(obj, dict) else []

    def memory_configurations(self) -> list[str]:
        cfg = self.data.get("Memory_Configurations", {}).get("LPDDR_Config", {})
        return list(cfg.keys()) if isinstance(cfg, dict) else []

    def bus_templates_for_family(self, family: str) -> list[str]:
        if family == "Control":
            return [f"{d}_Control" for d in self.domains()]
        if family == "Status":
            return [f"{d}_Status" for d in self.domains()]
        if family == "Analog":
            return self.analog_bus_templates()
        if family == "Power":
            return ["Power_Signals"]
        return []

    def interface_signals(self, template_name: str, index: int, link_or_port: str) -> InterfaceInstance:
        replacement = f"{link_or_port}_{index}"
        interface_name = template_name.replace("[Link/Port]", replacement)
        raw_signals = list(self.data["Interface_Temp"][template_name].keys())
        signals = [s.replace("[Link/Port]", replacement) for s in raw_signals]
        return InterfaceInstance(interface_name, signals, template_name, index, link_or_port, "interface")

    def generate_interfaces(self, template_name: str, start_index: int, amount: int, link_or_port: str) -> list[InterfaceInstance]:
        return [self.interface_signals(template_name, idx, link_or_port) for idx in range(start_index, start_index + amount)]

    def control_status_instance(self, family: str, domain_bus: str, signal_type: str, additional_info: str, voltage: str = "", active_low: bool = False) -> InterfaceInstance:
        sensitivity = "#" if active_low else ""
        domain = domain_bus.split("_")[0]
        bus_name = domain_bus
        signal = f"{signal_type}{sensitivity}_{domain}_{additional_info}"
        if voltage:
            signal += f"_{voltage}"
        return InterfaceInstance(bus_name, [signal], signal_type, 0, "Net", family.lower())

    def analog_instance(self, analog_bus: str, signal_type: str, domain: str, additional_info: str, differential: bool = True, frequency: str = "") -> InterfaceInstance:
        tmpl = self.data.get("Analog_Signal_Temp", {}).get(signal_type)
        if tmpl is None:
            raise ValueError(f"Unknown analog signal type: {signal_type}")
        raw = list(tmpl.keys()) if isinstance(tmpl, dict) else [signal_type]
        signals = []
        for s in raw:
            sig = s.replace("[Domain]", f"{domain}_{additional_info}").replace("[frequency]", frequency).replace(".", "_")
            signals.append(sig)
        if not differential and signals:
            signals = [re.sub(r"_[PN]$", "", signals[0])]
        return InterfaceInstance(analog_bus, signals, signal_type, 0, "Net", "analog")

    def power_instance(self, voltage_type: str, domain: str, additional_info: str, voltage_level: str) -> InterfaceInstance:
        bus_name = "Power_Signals"
        signal = f"{voltage_type}_{domain}_{additional_info}_{voltage_level}"
        return InterfaceInstance(bus_name, [signal], voltage_type, 0, "Net", "power")

    def memory_instances(self, technology: str, subtechnology: str, domain: str, host_device: str, amount: int = 1, config: str = "") -> list[InterfaceInstance]:
        tech_data = self.data.get("Memory_Interface_Temp", {}).get(technology, {}).get(subtechnology)
        if not isinstance(tech_data, dict):
            raise ValueError(f"Unknown memory template: {technology}/{subtechnology}")
        raw_signals = list(tech_data.keys())
        channels = 1
        if "Dual-Channel" in config:
            channels = 2
        elif "Quad-Channel" in config:
            channels = 4
        result = []
        for dev in range(1, amount + 1):
            dev_suffix = f"_DEV{dev}" if amount > 1 else ""
            bus_name = f"{subtechnology}_{domain}_{host_device}{dev_suffix}"
            signals = []
            if technology == "DRAM":
                for ch in range(1, channels + 1):
                    for s in raw_signals:
                        signals.append(f"{bus_name}_CH{ch}_{s}")
            else:
                for s in raw_signals:
                    signals.append(f"{bus_name}_{s}")
            result.append(InterfaceInstance(bus_name, signals, subtechnology, dev, "Bus", "memory"))
        return result

    @staticmethod
    def next_index(existing_names: list[str], template_name: str, link_or_port: str) -> int:
        base = template_name.replace("[Link/Port]", link_or_port)
        max_idx = 0
        pattern = re.compile(re.escape(base) + r"_(\d+)$")
        for name in existing_names:
            m = pattern.search(name)
            if m:
                max_idx = max(max_idx, int(m.group(1)))
        return max_idx + 1
