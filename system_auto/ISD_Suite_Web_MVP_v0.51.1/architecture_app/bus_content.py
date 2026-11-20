from __future__ import annotations

from dataclasses import dataclass, field
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
    member_keys: list[str] = field(default_factory=list)

    @property
    def bc_line(self) -> str:
        return f"{self.name} {','.join(self.signals)}"


class BusContentTemplates:
    def __init__(self, template_path: str | Path):
        self.template_path = Path(template_path)
        self.data = json.loads(self.template_path.read_text(encoding="utf-8"))

    def families(self) -> list[str]:
        return ["Interface", "Control", "Status", "Analog", "Power", "Memory"]

    @staticmethod
    def _name_token(value: str, fallback: str = "UNSPEC") -> str:
        token = str(value or "").strip().replace(".", "_")
        token = re.sub(r"\s+", "_", token)
        token = re.sub(r"[^A-Za-z0-9#\[\]_:-]+", "_", token)
        token = re.sub(r"_+", "_", token).strip("_")
        return token or fallback

    @staticmethod
    def _compact_name(*parts: str) -> str:
        value = "_".join(str(part or "").strip(" _") for part in parts if str(part or "").strip(" _"))
        return re.sub(r"_+", "_", value).strip("_")

    def signal_templates(self, family: str) -> list[str]:
        return {
            "Control": self.control_signal_templates,
            "Status": self.status_signal_templates,
            "Analog": self.analog_signal_templates,
            "Power": self.voltage_signal_templates,
        }.get(str(family), lambda: [])()

    def resolve_signal_template(self, family: str, value: str) -> str | None:
        query = str(value or "").strip().casefold()
        if not query:
            return None
        return next((item for item in self.signal_templates(family) if item.casefold() == query), None)

    def is_catalog_binding(self, family: str, template_name: str) -> bool:
        if family == "Interface":
            return self.resolve_interface_template(template_name) is not None
        if family == "Memory":
            return any(
                template_name in self.memory_subtechnologies(technology)
                for technology in self.memory_technologies()
            )
        return self.resolve_signal_template(family, template_name) is not None

    def ai_catalog_context(self) -> dict[str, object]:
        return {
            "families": {
                "Interface": self.interface_templates(),
                "Control": self.control_signal_templates(),
                "Status": self.status_signal_templates(),
                "Analog": self.analog_signal_templates(),
                "Power": self.voltage_signal_templates(),
                "Memory": {
                    technology: self.memory_subtechnologies(technology)
                    for technology in self.memory_technologies()
                },
            },
            "technicalDomains": self.domains(),
            "rules": [
                "Choose catalog_family and interface_template exactly from this catalog.",
                "Interface and Memory are buses; Control, Status, Analog and Power create individual NET signals.",
                "The compiler generates final names; observed schematic net names are evidence only.",
                "Ports for individual NET signals use the generated signal name one-to-one.",
            ],
        }

    def interface_templates(self) -> list[str]:
        return list(self.data.get("Interface_Temp", {}).keys())

    def interface_aliases(self) -> dict[str, str]:
        aliases = self.data.get("Interface_Aliases", {})
        return dict(aliases) if isinstance(aliases, dict) else {}

    @staticmethod
    def _normalized_interface_token(value: str) -> str:
        token = str(value or "").strip().casefold()
        token = token.removeprefix("builtin:")
        token = token.translate(str.maketrans({"²": "2", "³": "3"}))
        token = re.sub(r"\[link/port\]", "", token)
        token = re.sub(r"[_\s-]+(?:link|port)(?:[_\s-]*\d+)?$", "", token)
        token = re.sub(r"[_\s-]+\d+$", "", token)
        return re.sub(r"[^a-z0-9]+", "", token)

    @staticmethod
    def template_base(template_name: str) -> str:
        return str(template_name or "").replace("_[Link/Port]", "").replace("[Link/Port]", "").strip(" _-")

    @classmethod
    def canonical_instance_name(cls, template_name: str, kind: str, index: int) -> str:
        normalized_kind = "Port" if str(kind).casefold() == "port" else "Link"
        if "[Link/Port]" in template_name:
            return template_name.replace("[Link/Port]", f"{normalized_kind}_{int(index)}")
        return f"{template_name.strip(' _-')}_{normalized_kind}_{int(index)}"

    def resolve_interface_template(self, value: str) -> str | None:
        """Resolve exact names, canonical instances and explicit aliases deterministically."""
        raw_query = str(value or "").strip()
        query = raw_query.casefold()
        if not query:
            return None
        templates = self.interface_templates()
        exact = next((item for item in templates if item.casefold() == query), None)
        if exact:
            return exact
        alias_target = next((
            target for alias, target in self.interface_aliases().items()
            if alias.casefold() == query
        ), None)
        if alias_target in templates:
            return alias_target
        normalized_query = self._normalized_interface_token(raw_query)
        matches = [
            item for item in templates
            if self._normalized_interface_token(item) == normalized_query
        ]
        if len(matches) == 1:
            return matches[0]
        alias_matches = [
            target for alias, target in self.interface_aliases().items()
            if self._normalized_interface_token(alias) == normalized_query and target in templates
        ]
        alias_matches = list(dict.fromkeys(alias_matches))
        if len(alias_matches) == 1:
            return alias_matches[0]
        suffix_matches = [
            item for item in templates
            if self._normalized_interface_token(item).endswith(normalized_query)
            and normalized_query
        ]
        if len(suffix_matches) == 1:
            return suffix_matches[0]
        return matches[0] if len(matches) == 1 else None

    def raw_interface_members(self, template_name: str) -> list[str]:
        resolved = self.resolve_interface_template(template_name)
        if resolved is None:
            raise ValueError(f"Unknown interface template: {template_name}")
        return list(self.data["Interface_Temp"][resolved].keys())

    @staticmethod
    def _replacement_from_instance(template_name: str, instance_name: str) -> str | None:
        if "[Link/Port]" not in template_name:
            return None
        prefix, suffix = template_name.split("[Link/Port]", 1)
        match = re.fullmatch(
            re.escape(prefix) + r"(.+?)" + re.escape(suffix),
            instance_name,
            flags=re.IGNORECASE,
        )
        return match.group(1) if match else None

    @staticmethod
    def _vector_members(raw: list[str], count: int) -> tuple[list[str], list[str]]:
        if not 1 <= count <= 256:
            raise ValueError("Die Anzahl der Mitgliedssignale muss zwischen 1 und 256 liegen")
        if len(raw) != 1 or count == 1:
            return raw, raw
        seed = raw[0]
        match = re.search(r"\d+$", seed)
        prefix = seed[:match.start()] if match else seed
        start = int(match.group()) if match else 0
        names = [f"{prefix}{start + index}" for index in range(count)]
        return names, names

    def named_interface_signals(self, template_name: str, instance_name: str,
                                member_count: int = 1) -> InterfaceInstance:
        """Instantiate a built-in interface while retaining the requested instance name."""
        resolved = self.resolve_interface_template(template_name)
        if resolved is None:
            raise ValueError(f"Unknown interface template: {template_name}")
        raw_signals, member_keys = self._vector_members(
            list(self.data["Interface_Temp"][resolved].keys()), member_count)
        replacement = self._replacement_from_instance(resolved, instance_name)
        signals: list[str] = []
        for raw_signal in raw_signals:
            if replacement is not None:
                value = raw_signal.replace("[Link/Port]", replacement)
            else:
                marker = "__ISD_INTERFACE_INSTANCE__"
                template_prefix = resolved.replace("[Link/Port]", marker)
                value = raw_signal.replace("[Link/Port]", marker)
                if template_prefix in value:
                    value = value.replace(template_prefix, instance_name, 1)
                else:
                    value = value.replace(marker, instance_name)
            signals.append(value)
        return InterfaceInstance(
            instance_name, signals, resolved, 0, "Named", "interface", member_keys,
        )

    def control_signal_templates(self) -> list[str]:
        return list(self.data.get("Control_Signal_Temp", {}).keys())

    def status_signal_templates(self) -> list[str]:
        return list(self.data.get("Status_Signal_Temp", {}).keys())

    def analog_bus_templates(self) -> list[str]:
        return list(self.data.get("Analog_Busses", {}).keys())

    def analog_signal_templates(self) -> list[str]:
        # A null value is a vocabulary placeholder, not a generatable naming
        # template. Do not advertise it to the AI or accept it as a binding.
        return [
            name for name, definition in self.data.get("Analog_Signal_Temp", {}).items()
            if isinstance(definition, dict) and definition
        ]

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

    def interface_signals(self, template_name: str, index: int, link_or_port: str,
                          member_count: int = 1) -> InterfaceInstance:
        resolved = self.resolve_interface_template(template_name)
        if resolved is None:
            raise ValueError(f"Unknown interface template: {template_name}")
        replacement = f"{'Port' if str(link_or_port).casefold() == 'port' else 'Link'}_{int(index)}"
        interface_name = self.canonical_instance_name(resolved, link_or_port, index)
        raw_signals, member_keys = self._vector_members(
            list(self.data["Interface_Temp"][resolved].keys()), member_count)
        signals = [s.replace("[Link/Port]", replacement) for s in raw_signals]
        return InterfaceInstance(
            interface_name, signals, resolved, int(index), link_or_port, "interface", member_keys,
        )

    def generate_interfaces(self, template_name: str, start_index: int, amount: int, link_or_port: str) -> list[InterfaceInstance]:
        return [self.interface_signals(template_name, idx, link_or_port) for idx in range(start_index, start_index + amount)]

    def control_status_instance(self, family: str, domain_bus: str, signal_type: str, additional_info: str, voltage: str = "", active_low: bool = False) -> InterfaceInstance:
        sensitivity = "#" if active_low else ""
        domain = self._name_token(domain_bus.split("_")[0], "Other")
        bus_name = domain_bus
        signal = self._compact_name(
            f"{self._name_token(signal_type, 'Other')}{sensitivity}",
            domain,
            self._name_token(additional_info, "Signal"),
        )
        if voltage:
            signal = self._compact_name(signal, self._name_token(voltage))
        return InterfaceInstance(bus_name, [signal], signal_type, 0, "Net", family.lower())

    def analog_instance(self, analog_bus: str, signal_type: str, domain: str, additional_info: str, differential: bool = True, frequency: str = "") -> InterfaceInstance:
        tmpl = self.data.get("Analog_Signal_Temp", {}).get(signal_type)
        if tmpl is None:
            raise ValueError(f"Unknown analog signal type: {signal_type}")
        raw = list(tmpl.keys()) if isinstance(tmpl, dict) else [signal_type]
        signals = []
        for s in raw:
            domain_info = self._compact_name(
                self._name_token(domain, "Other"),
                self._name_token(additional_info, "Signal"),
            )
            sig = s.replace("[Domain]", domain_info).replace(
                "[frequency]", self._name_token(frequency) if "[frequency]" in s else frequency
            ).replace(".", "_")
            sig = self._compact_name(sig)
            signals.append(sig)
        if not differential and signals:
            signals = [re.sub(r"_[PN]$", "", signals[0])]
        return InterfaceInstance(analog_bus, signals, signal_type, 0, "Net", "analog")

    def power_instance(self, voltage_type: str, domain: str, additional_info: str, voltage_level: str) -> InterfaceInstance:
        bus_name = "Power_Signals"
        signal = self._compact_name(
            self._name_token(voltage_type, "Other"),
            self._name_token(domain, "Other"),
            self._name_token(additional_info, "Signal"),
            self._name_token(voltage_level),
        )
        return InterfaceInstance(bus_name, [signal], voltage_type, 0, "Net", "power")

    def architecture_signal_instances(
        self,
        family: str,
        template_name: str,
        technical_domain: str = "Other",
        additional_info: str = "Signal",
        voltage_frequency: str = "",
        active_low: bool = False,
        differential: bool = False,
    ) -> list[InterfaceInstance]:
        """Generate deterministic catalog instances for architecture-level connections."""
        if family in {"Control", "Status"}:
            resolved = self.resolve_signal_template(family, template_name)
            if resolved is None:
                raise ValueError(f"Unknown {family} signal template: {template_name}")
            return [self.control_status_instance(
                family,
                f"{self._name_token(technical_domain, 'Other')}_{family}",
                resolved,
                additional_info,
                voltage_frequency,
                active_low,
            )]
        if family == "Analog":
            resolved = self.resolve_signal_template(family, template_name)
            if resolved is None:
                raise ValueError(f"Unknown analog signal template: {template_name}")
            return [self.analog_instance(
                "Analog_Signals",
                resolved,
                self._name_token(technical_domain, "Other"),
                additional_info,
                differential,
                voltage_frequency,
            )]
        if family == "Power":
            resolved = self.resolve_signal_template(family, template_name)
            if resolved is None:
                raise ValueError(f"Unknown power signal template: {template_name}")
            return [self.power_instance(
                resolved,
                self._name_token(technical_domain, "Other"),
                additional_info,
                voltage_frequency,
            )]
        raise ValueError(f"{family} is not an individual-signal catalog family")

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

    def next_index(self, existing_names: list[str], template_name: str, link_or_port: str) -> int:
        resolved = self.resolve_interface_template(template_name) or template_name
        normalized_kind = "Port" if str(link_or_port).casefold() == "port" else "Link"
        max_idx = 0
        if "[Link/Port]" in resolved:
            prefix, suffix = resolved.split("[Link/Port]", 1)
            pattern = re.compile(
                r"^" + re.escape(prefix + normalized_kind + "_") + r"(\d+)" + re.escape(suffix) + r"$",
                flags=re.IGNORECASE,
            )
        else:
            pattern = re.compile(
                r"^" + re.escape(resolved.strip(" _-") + f"_{normalized_kind}_") + r"(\d+)$",
                flags=re.IGNORECASE,
            )
        for name in existing_names:
            m = pattern.match(name)
            if m:
                max_idx = max(max_idx, int(m.group(1)))
        return max_idx + 1
