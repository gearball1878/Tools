from __future__ import annotations

from pathlib import Path
from typing import Any
import configparser
import html
import json
import math
import re
import xml.etree.ElementTree as ET

from .model import ArchitectureModel, ArchitectureLevel, PortType, ConnectionType, PowerDirection


def safe_name(name: str) -> str:
    n = re.sub(r"[^A-Za-z0-9_]", "_", name.strip())
    if not n:
        raise ValueError("Name must not be empty")
    if n[0].isdigit():
        n = "_" + n
    return n


def quote(value: Any) -> str:
    if isinstance(value, (list, dict, bool)):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(str(value), ensure_ascii=False)


class SysML2Exporter:
    def __init__(self, model: ArchitectureModel):
        self.model = model
        self.lines: list[str] = []

    def export_text(self) -> str:
        self.model.validate()
        package_name = safe_name(self.model.name)
        self.lines = []
        self._w(f"package {package_name} {{")
        self._emit_library()
        self._w("")
        self._w(f"part def {package_name}_Architecture {{")
        for block in self.model.blocks:
            self._emit_block(block, 1)
        if self.model.connections or self.model.net_references:
            self._w("")
            for con in self.model.connections:
                self._emit_connection(con, 1)
            for ref in self.model.net_references:
                self._emit_reference(ref, 1)
        self._w("}")
        self._w("}")
        return "\n".join(self.lines) + "\n"

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(self.export_text(), encoding="utf-8")
        return p

    def _emit_library(self) -> None:
        self._w("enum def ArchitectureLevel { enum Level1_Domain; enum Level2_ArchitectureElement; }")
        self._w("enum def PortType { enum In; enum Out; enum Bidi; enum Power; enum Ground; enum Analog; }")
        self._w("enum def ConnectionType { enum Net; enum Bus; }")
        self._w("enum def NetReferenceDirection { enum In; enum Out; enum Bidi; }")
        self._w("part def ArchitectureBlock { attribute blockId : ScalarValues::String; }")
        self._w("port def ArchitecturePort { attribute portId : ScalarValues::String; }")
        self._w("connection def ArchitectureConnection { attribute connectionId : ScalarValues::String; }")

    def _emit_block(self, block, indent: int) -> None:
        i = "    " * indent
        self._w(f"{i}part {safe_name(block.name)} : ArchitectureBlock {{")
        self._w(f"{i}    attribute blockId = {quote(block.id)};")
        self._w(f"{i}    attribute architectureLevel = {quote(block.level.value)};")
        self._w(f"{i}    attribute isHost = {quote(block.is_host)};")
        self._w(f"{i}    attribute color = {quote(block.color)};")
        for k, v in block.attributes.items():
            self._w(f"{i}    attribute {safe_name(k)} = {quote(v)};")
        for port in block.ports:
            self._emit_port(port, indent + 1)
        for child in block.children:
            self._emit_block(child, indent + 1)
        self._w(f"{i}}}")

    def _emit_port(self, port, indent: int) -> None:
        i = "    " * indent
        self._w(f"{i}port {safe_name(port.name)} : ArchitecturePort {{")
        self._w(f"{i}    attribute portId = {quote(port.id)};")
        self._w(f"{i}    attribute portType = {quote(port.port_type.value)};")
        for k, v in port.attributes.items():
            self._w(f"{i}    attribute {safe_name(k)} = {quote(v)};")
        self._w(f"{i}}}")

    def _emit_connection(self, con, indent: int) -> None:
        i = "    " * indent
        self._w(f"{i}connection {safe_name(con.name)} : ArchitectureConnection {{")
        self._w(f"{i}    attribute connectionId = {quote(con.id)};")
        self._w(f"{i}    attribute netId = {quote(con.net_id)};")
        self._w(f"{i}}}")

    def _emit_reference(self, ref, indent: int) -> None:
        i = "    " * indent
        self._w(f"{i}connection {safe_name(ref.name)}_Reference : ArchitectureConnection {{")
        self._w(f"{i}    attribute connectionId = {quote(ref.id)};")
        self._w(f"{i}    attribute netId = {quote(ref.net_id)};")
        self._w(f"{i}    attribute referenceName = {quote(ref.name)};")
        self._w(f"{i}    attribute referenceDirection = {quote(ref.direction.value)};")
        for k, v in ref.attributes.items():
            self._w(f"{i}    attribute {safe_name(k)} = {quote(v)};")
        self._w(f"{i}}}")

    def _w(self, line: str) -> None:
        self.lines.append(line)


class BusContentsIniExporter:
    """
    Export busconts.ini in the required plain format:

        <bus_or_group_name> <signal_1>,<signal_2>,...

    Important:
    - No sections and no equals signs.
    - Filename is always busconts.ini.
    - If several architectural net references share the same bus/group name,
      all subordinate signals are merged into one single bus line.
      This avoids creating the same bus n times with one signal each.
    """
    def __init__(self, model: ArchitectureModel):
        self.model = model

    def _bus_group_name(self, ref) -> str:
        family = str(ref.attributes.get("family", "")).lower()

        # Wizard-created buses/interfaces carry the original bus content name.
        # This is the preferred grouping key.
        bus_name = ref.attributes.get("busContentName")
        if bus_name:
            return str(bus_name)

        # Some templates may store a generic interface name.
        interface_name = ref.attributes.get("interfaceName")
        if interface_name and ref.attributes.get("signals"):
            return str(interface_name)

        # Single architecture signals can still belong to a common group.
        if family == "power":
            return "Power_Signals"
        if family == "control":
            return "Control_Signals"
        if family == "status":
            return "Status_Signals"
        if family == "analog":
            bus_content = ref.attributes.get("busContentName")
            return str(bus_content) if bus_content else "Analog_Signals"

        return ref.name

    def _signals_for_ref(self, ref) -> list[str]:
        signals = ref.attributes.get("signals", [])
        if signals:
            return [str(s) for s in signals]

        # Even a single architecture net is exported as signal content of its group.
        return [str(ref.name)]

    def export_text(self) -> str:
        grouped: dict[str, list[str]] = {}
        seen_per_group: dict[str, set[str]] = {}

        for ref in self.model.net_references:
            group = self._bus_group_name(ref)
            grouped.setdefault(group, [])
            seen_per_group.setdefault(group, set())

            for sig in self._signals_for_ref(ref):
                if sig not in seen_per_group[group]:
                    grouped[group].append(sig)
                    seen_per_group[group].add(sig)

        lines = [f"{group} {','.join(signals)}" for group, signals in grouped.items()]
        return "\n".join(lines) + ("\n" if lines else "")

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        if p.name != "busconts.ini":
            p = p.with_name("busconts.ini")
        p.write_text(self.export_text(), encoding="utf-8")
        return p


class DrawioExporter:
    def __init__(self, model: ArchitectureModel):
        self.model = model
        self.id_counter = 0
        self.block_cells: dict[str, str] = {}
        self.block_geom: dict[str, tuple[float, float, float, float]] = {}
        self.port_cells: dict[str, str] = {}
        self.port_abs: dict[str, tuple[float, float]] = {}
        self.port_side: dict[str, str] = {}
        self.proxy_ref_cells: dict[str, str] = {}
        self.proxy_ref_abs: dict[str, tuple[float, float]] = {}
        self.proxy_ref_side: dict[str, str] = {}
        self.proxy_refs_by_owner: dict[str, list[Any]] = {}

    def _page_id(self, name: str) -> str:
        return "page_" + safe_name(name)

    def _page_link(self, page_name: str) -> str:
        return "data:page/id," + self._page_id(page_name)

    def _page_link_alt(self, page_name: str) -> str:
        return "data:page/id," + self._page_id(page_name)

    def save(self, path: str | Path) -> Path:
        self.model.validate()
        mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "type": "device"})
        mxfile.append(self._make_page("01_Domains", [(b, b.name) for b in self.model.blocks]))
        for domain in self.model.blocks:
            children = [(c, f"{domain.name}.{c.name}") for c in domain.children if c.level == ArchitectureLevel.ARCH_ELEMENT]
            mxfile.append(self._make_page(f"02_{domain.name}", children))
        p = Path(path)
        p.write_text(ET.tostring(mxfile, encoding="unicode"), encoding="utf-8")
        return p

    def _make_page(self, name: str, blocks: list[tuple[Any, str]]) -> ET.Element:
        self.block_cells.clear()
        self.block_geom.clear()
        self.port_cells.clear()
        self.port_abs.clear()
        self.port_side.clear()
        self.proxy_ref_cells.clear()
        self.proxy_ref_abs.clear()
        self.proxy_ref_side.clear()

        visible_paths = set(path for _, path in blocks)
        self.proxy_refs_by_owner = self._collect_proxy_refs(visible_paths)

        diagram = ET.Element("diagram", {"id": self._page_id(name), "name": name[:80]})
        graph = ET.SubElement(diagram, "mxGraphModel", {
            "grid": "1", "gridSize": "10", "page": "1",
            "pageWidth": "12000", "pageHeight": "8000",
        })
        root = ET.SubElement(graph, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

        title = ET.SubElement(root, "mxCell", {
            "id": self._id("title"),
            "value": html.escape(name),
            "style": "text;html=1;fontSize=15;fontStyle=1;align=left;",
            "vertex": "1",
            "parent": "1",
        })
        ET.SubElement(title, "mxGeometry", {
            "x": "40", "y": "30", "width": "900", "height": "30", "as": "geometry",
        })

        self._layout_blocks(root, blocks)
        self._emit_net_references(root, visible_paths)
        return diagram

    def _collect_proxy_refs(self, visible_paths: set[str]) -> dict[str, list[Any]]:
        result: dict[str, list[Any]] = {p: [] for p in visible_paths}
        for ref in self.model.net_references:
            owner = self._visible_owner(ref.end.block_path, visible_paths)
            if not owner:
                continue

            # Only explicitly selected signals are propagated upward to collapsed
            # parent/domain pages. This models whether a signal has to travel
            # through all hierarchy levels.
            propagate = bool(ref.attributes.get("propagateToParent", False))
            if not propagate:
                continue

            if ref.end.block_path != owner:
                result.setdefault(owner, []).append(ref)
            else:
                block = self.model.find_block(owner)
                if block and not block.find_port(ref.end.port_name):
                    result.setdefault(owner, []).append(ref)
        for owner in list(result):
            result[owner] = sorted(result[owner], key=lambda r: (self._ref_order_key(r), r.name))
        return result


    def _layout_blocks(self, root: ET.Element, blocks: list[tuple[Any, str]]) -> None:
        """
        Host-centered non-overlap layout.

        If a visible block is marked as host, it is placed in the center and the
        remaining blocks are placed around it. This applies both to:
        - Level 1 domain diagram: only one host domain is allowed.
        - Level 2 architecture element diagrams: only one host per domain.

        If no host is set, a robust shelf/grid layout is used.
        """
        if not blocks:
            return

        margin_x = 160
        margin_y = 160
        col_gap = 820
        row_gap = 200
        max_col_height = 3600

        hosts = [(b, p) for b, p in blocks if getattr(b, "is_host", False)]
        if hosts and len(blocks) > 1:
            self._layout_around_host(root, hosts[0], [(b, p) for b, p in blocks if p != hosts[0][1]])
            return

        def weight(item):
            block, path = item
            return len(block.ports) + len(self.proxy_refs_by_owner.get(path, []))

        ordered = sorted(blocks, key=weight, reverse=True)
        self._layout_columns(root, ordered, margin_x, margin_y, col_gap, row_gap, max_col_height)

    def _layout_around_host(self, root, host_item, others):
        """
        Place host in the middle and distribute other blocks in left/right columns.
        Geometry is intentionally generous to avoid both block and connector overlap.
        """
        host_block, host_path = host_item
        host_w, host_h = self._block_size(host_block, host_path)

        center_x = 3000
        center_y = 1700
        host_x = int(center_x - host_w / 2)
        host_y = int(center_y - host_h / 2)
        self._emit_block(root, host_block, host_path, host_x, host_y)

        if not others:
            return

        row_gap = 200
        col_gap = 900
        max_col_height = 3600

        def weight(item):
            block, path = item
            return len(block.ports) + len(self.proxy_refs_by_owner.get(path, []))

        # Balance left/right columns by estimated height.
        left, right = [], []
        left_h = right_h = 0
        for item in sorted(others, key=weight, reverse=True):
            w, h = self._block_size(item[0], item[1])
            refs = self.proxy_refs_by_owner.get(item[1], [])
            left_score = sum(1 for r in refs if self._side_for_ref(r) == "left")
            right_score = sum(1 for r in refs if self._side_for_ref(r) == "right")

            if left_score > right_score:
                left.append(item); left_h += h + row_gap
            elif right_score > left_score:
                right.append(item); right_h += h + row_gap
            elif left_h <= right_h:
                left.append(item); left_h += h + row_gap
            else:
                right.append(item); right_h += h + row_gap

        # Place left columns to the left of host. Use wide x distance so host stubs have room.
        left_start_x = max(160, host_x - col_gap - 900)
        right_start_x = host_x + host_w + col_gap

        self._layout_columns(root, left, left_start_x, 160, col_gap, row_gap, max_col_height)
        self._layout_columns(root, right, right_start_x, 160, col_gap, row_gap, max_col_height)

    def _layout_columns(self, root, items, start_x, start_y, col_gap, row_gap, max_col_height):
        if not items:
            return

        columns = []
        current = []
        current_h = 0
        current_w = 0
        for item in items:
            w, h = self._block_size(item[0], item[1])
            if current and current_h + h + row_gap > max_col_height:
                columns.append((current, current_w))
                current = []
                current_h = 0
                current_w = 0
            current.append((item, w, h))
            current_h += h + row_gap
            current_w = max(current_w, w)
        if current:
            columns.append((current, current_w))

        x = start_x
        for col, max_w in columns:
            y = start_y
            for (block, path), w, h in col:
                self._emit_block(root, block, path, int(x), int(y))
                y += h + row_gap
            x += max_w + col_gap


    def _block_size(self, block, path: str | None = None) -> tuple[int, int]:
        # Wider blocks and larger vertical pitch keep port labels and net stubs readable.
        base_w, header_h, bottom_margin = 680, 98, 55
        left, right = self._split_ports(block.ports)
        if path:
            p_left, p_right = self._split_proxy_refs(self.proxy_refs_by_owner.get(path, []))
            left_count = len(left) + len(p_left)
            right_count = len(right) + len(p_right)
        else:
            left_count = len(left)
            right_count = len(right)

        def col_h(count: int) -> int:
            return count * 46

        return base_w, max(300, header_h + max(col_h(left_count), col_h(right_count), 90) + bottom_margin)


    def _port_order_key(self, port):
        fam = str(port.attributes.get("family", "")).lower()
        if port.port_type == PortType.POWER or fam == "power":
            return 0
        if fam in {"control", "status"} or port.port_type in {PortType.IN, PortType.OUT}:
            return 1
        if fam in {"interface", "memory"} or port.port_type == PortType.BIDI:
            return 2
        if fam == "analog" or port.port_type == PortType.ANALOG:
            return 3
        return 4

    def _ref_order_key(self, ref):
        fam = str(ref.attributes.get("family", "")).lower()
        if fam == "power":
            return 0
        if fam in {"control", "status"}:
            return 1
        if fam in {"interface", "memory"}:
            return 2
        if fam == "analog":
            return 3
        return 4

    def _side_for_port(self, port) -> str:
        override = port.attributes.get("sideOverride", "Auto")
        if override == "Left":
            return "left"
        if override == "Right":
            return "right"
        fam = str(port.attributes.get("family", "")).lower()
        if port.port_type == PortType.POWER:
            return "right" if port.attributes.get("powerDirection") == PowerDirection.OUT.value else "left"
        if port.port_type == PortType.IN:
            return "left"
        if port.port_type == PortType.OUT:
            return "right"
        if fam in {"interface", "memory"} or port.port_type == PortType.BIDI:
            return "right"
        if fam == "analog" or port.port_type == PortType.ANALOG:
            return "left"
        return "left"

    def _side_for_ref(self, ref) -> str:
        override = str(ref.attributes.get("sideOverride", "Auto"))
        if override == "Left":
            return "left"
        if override == "Right":
            return "right"
        family = str(ref.attributes.get("family", "")).lower()
        if family in {"interface", "memory"}:
            return "right"
        if family == "analog":
            return "left"
        if family == "power":
            return "right" if ref.attributes.get("powerDirection") == PowerDirection.OUT.value else "left"
        if ref.direction.value == "In":
            return "left"
        if ref.direction.value == "Out":
            return "right"
        return "right"

    def _split_ports(self, ports):
        sorted_ports = sorted(ports, key=lambda p: (self._port_order_key(p), p.name))
        left = [p for p in sorted_ports if self._side_for_port(p) == "left"]
        right = [p for p in sorted_ports if self._side_for_port(p) == "right"]
        return left, right

    def _split_proxy_refs(self, refs):
        sorted_refs = sorted(refs, key=lambda r: (self._ref_order_key(r), r.name))
        left = [r for r in sorted_refs if self._side_for_ref(r) == "left"]
        right = [r for r in sorted_refs if self._side_for_ref(r) == "right"]
        return left, right

    def _block_style(self, block) -> str:
        color = block.color or block.attributes.get("domainColor") or "#f5f5f5"
        stroke = "#3d6fb6" if getattr(block, "is_host", False) else "#666666"
        return (
            "rounded=1;whiteSpace=wrap;html=1;align=left;verticalAlign=top;"
            f"spacingLeft=10;spacingTop=8;fillColor={color};strokeColor={stroke};"
        )

    def _net_style(self, connection_type, family: str = "") -> str:
        fam = (family or "").lower()
        colors = {
            "interface": "#003f9e",
            "control": "#008c8c",
            "status": "#8a2be2",
            "analog": "#d79b00",
            "power": "#d00000",
            "memory": "#6a00a8",
            "manual": "#333333",
        }
        style = (
            "html=1;rounded=0;orthogonal=0;edgeStyle=none;fontSize=15;"
            f"labelBackgroundColor=#ffffff;strokeColor={colors.get(fam, '#333333')};"
        )
        style += "strokeWidth=4;dashed=1;" if connection_type == ConnectionType.BUS else "strokeWidth=2;"
        return style

    def _emit_block(self, root: ET.Element, block, path: str, x: int, y: int) -> None:
        w, h = self._block_size(block, path)
        cid = self._id(block.id)
        self.block_cells[path] = cid
        self.block_geom[path] = (float(x), float(y), float(w), float(h))

        host_label = " [HOST]" if getattr(block, "is_host", False) else ""
        label = (
            f"<b>{html.escape(block.name)}{host_label}</b>"
            f"<br><font style='font-size:15px'>ID: {html.escape(block.id)}</font>"
            f"<br><font style='font-size:15px'>{html.escape(block.level.value)}</font>"
        )

        # Direct block mxCell. Do not Object-wrap blocks here, because children with
        # parent=blockId are not rendered reliably when the parent is inside Object.
        cell_attrs = {
            "id": cid,
            "value": label,
            "style": self._block_style(block),
            "vertex": "1",
            "parent": "1",
            "objectType": "Block",
            "blockId": block.id,
            "blockPath": path,
            "architectureLevel": block.level.value,
            "isHost": str(getattr(block, "is_host", False)),
            "domainColor": block.color or block.attributes.get("domainColor", ""),
        }
        if block.level == ArchitectureLevel.DOMAIN and any(block.children):
            cell_attrs["link"] = self._page_link(f"02_{block.name}")
            cell_attrs["targetPage"] = f"02_{block.name}"
            cell_attrs["targetPageId"] = self._page_id(f"02_{block.name}")
        cell = ET.SubElement(root, "mxCell", cell_attrs)
        ET.SubElement(cell, "mxGeometry", {
            "x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry",
        })

        left, right = self._split_ports(block.ports)
        proxy_left, proxy_right = self._split_proxy_refs(self.proxy_refs_by_owner.get(path, []))
        self._emit_ports(root, cid, path, left, "left", w, x, y, start_index=0)
        self._emit_proxy_ports(root, cid, path, proxy_left, "left", w, x, y, start_index=len(left))
        self._emit_ports(root, cid, path, right, "right", w, x, y, start_index=0)
        self._emit_proxy_ports(root, cid, path, proxy_right, "right", w, x, y, start_index=len(right))



    def _port_net_info(self, block_path: str, port_name: str) -> tuple[str, str, str]:
        for ref in self.model.net_references:
            if ref.end.block_path == block_path and ref.end.port_name == port_name:
                return ref.net_id, ref.reference_type.value, ref.id
        for con in self.model.connections:
            if con.source.block_path == block_path and con.source.port_name == port_name:
                return con.net_id, con.connection_type.value, con.id
            if con.target.block_path == block_path and con.target.port_name == port_name:
                return con.net_id, con.connection_type.value, con.id
        return "", "", ""

    def _emit_ports(self, root, parent_id, block_path, ports, side, block_w, block_x, block_y, start_index=0):
        for offset, port in enumerate(ports):
            idx = start_index + offset
            label_h = 28
            y = 94 + idx * 46
            x_dot = -5 if side == "left" else block_w - 5
            x_label = 14 if side == "left" else block_w - 420
            align = "left" if side == "left" else "right"
            pid = self._id(port.id)
            key = f"{block_path}.{port.name}"
            self.port_cells[key] = pid
            self.port_side[key] = side
            self.port_abs[key] = (block_x + x_dot + 5, block_y + y + label_h / 2)

            net_id, connection_type, reference_id = self._port_net_info(block_path, port.name)
            family = str(port.attributes.get("family", "manual"))
            power_direction = str(port.attributes.get("powerDirection", ""))

            dot = ET.SubElement(root, "mxCell", {
                "id": pid,
                "value": "",
                "style": "ellipse;html=1;connectable=1;fillColor=#ffffff;strokeColor=#333333;",
                "vertex": "1",
                "parent": parent_id,
                "objectType": "Port",
                "portId": port.id,
                "portName": port.name,
                "portType": port.port_type.value,
                "connectionType": connection_type,
                "netId": net_id,
                "referenceId": reference_id,
                "family": family,
                "side": side,
                "powerDirection": power_direction,
            })
            ET.SubElement(dot, "mxGeometry", {
                "x": str(x_dot), "y": str(y + label_h / 2 - 5), "width": "10", "height": "10", "as": "geometry",
            })

            self._emit_clean_label(root, parent_id, port.id, port.name, port.port_type.value, net_id, connection_type, reference_id, x_label, y, align, label_h)

    def _emit_proxy_ports(self, root, parent_id, block_path, refs, side, block_w, block_x, block_y, start_index=0):
        for offset, ref in enumerate(refs):
            idx = start_index + offset
            label_h = 28
            y = 94 + idx * 46
            x_dot = -5 if side == "left" else block_w - 5
            x_label = 14 if side == "left" else block_w - 420
            align = "left" if side == "left" else "right"
            pid = self._id(ref.id + "_proxy_port")
            self.proxy_ref_cells[ref.id] = pid
            self.proxy_ref_side[ref.id] = side
            self.proxy_ref_abs[ref.id] = (block_x + x_dot + 5, block_y + y + label_h / 2)

            dot = ET.SubElement(root, "mxCell", {
                "id": pid,
                "value": "",
                "style": "ellipse;html=1;connectable=1;fillColor=#ffffff;strokeColor=#333333;",
                "vertex": "1",
                "parent": parent_id,
                "objectType": "ProxyPort",
                "portId": ref.end.port_name,
                "portName": ref.name,
                "sourceBlockPath": ref.end.block_path,
                "connectionType": ref.reference_type.value,
                "netId": ref.net_id,
                "referenceId": ref.id,
                "family": str(ref.attributes.get("family", "manual")),
                "side": side,
            })
            ET.SubElement(dot, "mxGeometry", {
                "x": str(x_dot), "y": str(y + label_h / 2 - 5), "width": "10", "height": "10", "as": "geometry",
            })

            self._emit_clean_label(root, parent_id, ref.id + "_proxy", ref.name, "", ref.net_id, ref.reference_type.value, ref.id, x_label, y, align, label_h)

    def _emit_clean_label(self, root, parent_id, id_seed, name, port_type, net_id, connection_type, reference_id, x_label, y, align, label_h):
        label = ET.SubElement(root, "mxCell", {
            "id": self._id(id_seed + "_label"),
            "value": f"<font style='font-size:15px'><b>{html.escape(name)}</b></font>",
            "style": (
                f"text;html=1;align={align};verticalAlign=middle;resizable=0;movable=0;"
                "spacing=0;overflow=hidden;"
            ),
            "vertex": "1",
            "parent": parent_id,
            "objectType": "PortLabel",
            "portId": id_seed,
            "portName": name,
            "portType": port_type,
            "connectionType": connection_type,
            "netId": net_id,
            "referenceId": reference_id,
        })
        ET.SubElement(label, "mxGeometry", {
            "x": str(x_label), "y": str(y), "width": "390", "height": str(label_h), "as": "geometry",
        })

    def _emit_net_references(self, root, visible_paths):
        # Separate lanes per side and per visible owner. This keeps connector ends
        # from stacking on top of each other, even for large propagated blocks.
        lane_by_key: dict[tuple[str, str], int] = {}

        for ref in self.model.net_references:
            owner = self._visible_owner(ref.end.block_path, visible_paths)
            if not owner:
                continue

            key = f"{owner}.{ref.end.port_name}"
            port_cell = self.port_cells.get(key)
            if port_cell:
                px, py = self.port_abs.get(key, (0, 0))
                side = self.port_side.get(key, "right")
            elif ref.id in self.proxy_ref_cells:
                port_cell = self.proxy_ref_cells[ref.id]
                px, py = self.proxy_ref_abs.get(ref.id, (0, 0))
                side = self.proxy_ref_side.get(ref.id, "right")
            else:
                continue

            sign = -1 if side == "left" else 1
            style = self._net_style(ref.reference_type, ref.attributes.get("family", "manual"))

            # Equal-length net-reference stubs.
            # Every arrow has exactly this length from the port/proxy-port anchor.
            # 680 px is enough for ~64 characters at 10 pt plus arrow head.
            stub_len = 680
            outside_x = px + sign * stub_len

            base_attrs = {
                "id": self._id(ref.id),
                "value": html.escape(ref.name),
                "edge": "1",
                "parent": "1",
                "objectType": "NetReference",
                "referenceId": ref.id,
                "referenceName": ref.name,
                "referenceType": ref.reference_type.value,
                "connectionType": ref.reference_type.value,
                "referenceDirection": ref.direction.value,
                "netId": ref.net_id,
                "portName": ref.end.port_name,
                "blockPath": ref.end.block_path,
                "visibleOwner": owner,
                "family": str(ref.attributes.get("family", "manual")),
            }

            if ref.direction.value == "In":
                attrs = dict(base_attrs)
                attrs.update({"style": style + "endArrow=block;", "target": port_cell})
                edge = ET.SubElement(root, "mxCell", attrs)
                geo = ET.SubElement(edge, "mxGeometry", {"relative": "1", "as": "geometry"})
                ET.SubElement(geo, "mxPoint", {"x": str(outside_x), "y": str(py), "as": "sourcePoint"})
            else:
                arrow = "startArrow=block;endArrow=block;" if ref.direction.value == "Bidi" else "endArrow=block;"
                attrs = dict(base_attrs)
                attrs.update({"style": style + arrow, "source": port_cell})
                edge = ET.SubElement(root, "mxCell", attrs)
                geo = ET.SubElement(edge, "mxGeometry", {"relative": "1", "as": "geometry"})
                ET.SubElement(geo, "mxPoint", {"x": str(outside_x), "y": str(py), "as": "targetPoint"})


    def _visible_owner(self, block_path, visible_paths):
        parts = block_path.split(".")
        for i in range(len(parts), 0, -1):
            cand = ".".join(parts[:i])
            if cand in visible_paths:
                return cand
        return None

    def _id(self, preferred: str) -> str:
        self.id_counter += 1
        return f"mx_{safe_name(preferred)}_{self.id_counter}"
