from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom
import json
import html
from statistics import mean

from model import Design, Block, Port, Signal


PORT_STYLE = {
    "in": "shape=ellipse;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=8;",
    "out": "shape=ellipse;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=8;",
    "bidi": "shape=ellipse;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;fontSize=8;",
    "power": "shape=rectangle;html=1;fillColor=#ffcccc;strokeColor=#cc0000;fontSize=8;",
    "ground": "shape=rectangle;html=1;fillColor=#e6e6e6;strokeColor=#000000;fontSize=8;",
    "analog": "shape=ellipse;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=8;",
}

SIGNAL_STYLE = {
    "net": "rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;fontSize=10;",
    "bus": "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=10;fontStyle=1;",
}

WIRE_STYLE = {
    "net": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=none;strokeWidth=2;",
    "bus": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=none;strokeWidth=4;dashed=1;",
}

PORT_SIDE = {
    "in": "left",
    "power": "left",
    "ground": "left",
    "analog": "left",
    "out": "right",
    "bidi": "right",
}

PORT_PREFIX = {
    "in": "in",
    "out": "out",
    "bidi": "bidi",
    "power": "pwr",
    "ground": "gnd",
    "analog": "ana",
}


def safe_id(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text)


def mx_block_id(block: Block) -> str:
    return f"UML_BLOCK_{safe_id(block.id)}"


def mx_port_id(block: Block, port: Port) -> str:
    return f"UML_PORT_{safe_id(block.id)}_{safe_id(port.id)}"


def mx_signal_id(signal: Signal) -> str:
    return f"SIGNAL_{safe_id(signal.id)}"


def mx_wire_id(signal: Signal, endpoint: str) -> str:
    return f"WIRE_{safe_id(signal.id)}_{safe_id(endpoint)}"


def str_attr(value) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if value is None:
        return ""
    return str(value)


def object_attributes(kind: str, obj, extra: dict | None = None) -> dict[str, str]:
    attrs = {
        "label": getattr(obj, "name", ""),
        "kind": kind,
        "object_id": getattr(obj, "id", ""),
        "object_name": getattr(obj, "name", ""),
        "stereotype": getattr(obj, "stereotype", ""),
        "attributes_json": json.dumps(getattr(obj, "attributes", {}), ensure_ascii=False, separators=(",", ":")),
    }
    if hasattr(obj, "level"):
        attrs["level"] = str(obj.level)
    if hasattr(obj, "type"):
        attrs["type"] = str(obj.type)
    if extra:
        attrs.update({k: str_attr(v) for k, v in extra.items()})
    for key, value in getattr(obj, "attributes", {}).items():
        attrs[f"attr_{key}"] = str_attr(value)
    return attrs


class DrawioSignalFlowRenderer:
    """
    Signal-flow renderer:
      - Blocks are UML-like objects.
      - Ports are separate objects with attributes.
      - Nets/buses are separate visible objects with attributes.
      - Edges only represent attachment from Port -> Signal object.
      - This makes signal flow and hierarchy visible and machine-readable.
    """

    def __init__(self, design: Design):
        self.design = design
        self.current_block_pos: dict[str, tuple[int, int, int, int]] = {}

    def render(self, output_file: str | Path) -> Path:
        output_file = Path(output_file)
        mxfile = ET.Element("mxfile", {
            "host": "app.diagrams.net",
            "agent": "thor-signalflow-object-renderer",
            "version": "24.0.0",
            "type": "device",
        })

        self._add_page(mxfile, "L1_Domains", parent_block=None)
        for block in self.design.walk_blocks():
            if block.children:
                self._add_page(mxfile, block.id, parent_block=block)

        raw = ET.tostring(mxfile, encoding="utf-8")
        pretty = minidom.parseString(raw).toprettyxml(indent="  ")
        output_file.write_text(pretty, encoding="utf-8")
        return output_file

    def _add_page(self, mxfile, page_name: str, parent_block: Block | None):
        blocks = self.design.direct_children_of(parent_block)
        self.current_block_pos = {}

        diagram = ET.SubElement(mxfile, "diagram", {"name": page_name})
        model = ET.SubElement(diagram, "mxGraphModel", {
            "dx": "1900", "dy": "1200", "grid": "1", "gridSize": "10",
            "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
            "fold": "1", "page": "1", "pageScale": "1", "pageWidth": "2100",
            "pageHeight": "1400", "math": "0", "shadow": "0",
        })
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

        self._title(root, f"{self.design.name}" if parent_block is None else f"Drill-down: {parent_block.name} ({parent_block.id})")

        cols = 3
        w, h = 380, 250
        start_x, start_y = 100, 150
        gap_x, gap_y = 220, 190

        visible = {}
        for idx, block in enumerate(blocks):
            x = start_x + (idx % cols) * (w + gap_x)
            y = start_y + (idx // cols) * (h + gap_y)
            visible[block.id] = block
            self.current_block_pos[block.id] = (x, y, w, h)
            self._render_uml_block(root, block, x, y, w, h)
            self._render_ports(root, block)

        self._render_visible_signals(root, visible)

    def _title(self, root, text):
        cell = ET.SubElement(root, "mxCell", {
            "id": f"TITLE_{safe_id(text)}",
            "value": html.escape(text),
            "style": "text;html=1;strokeColor=none;fillColor=none;fontSize=18;fontStyle=1;align=left;",
            "vertex": "1",
            "parent": "1",
        })
        ET.SubElement(cell, "mxGeometry", {"x": "40", "y": "30", "width": "1500", "height": "40", "as": "geometry"})

    def _object_cell(self, root, object_attrs: dict[str, str], cell_attrs: dict[str, str]):
        obj = ET.SubElement(root, "object", object_attrs)
        ET.SubElement(obj, "mxCell", cell_attrs)
        return obj

    def _geometry(self, obj_or_cell, x=None, y=None, w=None, h=None, relative=None):
        cell = obj_or_cell.find("mxCell") if obj_or_cell.tag == "object" else obj_or_cell
        attrs = {"as": "geometry"}
        if x is not None: attrs["x"] = str(x)
        if y is not None: attrs["y"] = str(y)
        if w is not None: attrs["width"] = str(w)
        if h is not None: attrs["height"] = str(h)
        if relative is not None: attrs["relative"] = str(relative)
        return ET.SubElement(cell, "mxGeometry", attrs)

    def _uml_value(self, block: Block) -> str:
        attrs = "<br>".join(
            f"{html.escape(str(k))} = {html.escape(str_attr(v))}"
            for k, v in block.attributes.items()
        ) or "&nbsp;"

        port_summary = "<br>".join(
            f"{html.escape(p.id)} : {html.escape(p.type)}"
            for p in block.ports
        ) or "&nbsp;"

        drill = "<br><font style='font-size:10px'>linked drill-down page</font>" if block.children else ""

        return (
            f"<div style='font-size:11px'>&lt;&lt;{html.escape(block.stereotype)}&gt;&gt;</div>"
            f"<b><u>{html.escape(block.name)}</u></b><br>"
            f"<font style='font-size:10px'>ID: {html.escape(block.id)} | Level: {block.level}</font>{drill}"
            f"<hr size='1'>"
            f"<b>ports</b><br><font style='font-size:10px'>{port_summary}</font>"
            f"<hr size='1'>"
            f"<b>attributes</b><br><font style='font-size:10px'>{attrs}</font>"
        )

    def _render_uml_block(self, root, block: Block, x: int, y: int, w: int, h: int):
        has_children = bool(block.children)
        link = f"link=data:page/id,{block.id};" if has_children else ""
        style = (
            "rounded=0;whiteSpace=wrap;html=1;align=center;verticalAlign=top;"
            "spacingTop=8;fillColor=#ffffff;strokeColor=#333333;fontSize=12;"
            + link
        )
        obj_attrs = object_attributes("uml_block", block, {"has_children": has_children})
        cell_attrs = {
            "id": mx_block_id(block),
            "value": self._uml_value(block),
            "style": style,
            "vertex": "1",
            "parent": "1",
        }
        obj = self._object_cell(root, obj_attrs, cell_attrs)
        self._geometry(obj, x, y, w, h)

    def _render_ports(self, root, block: Block):
        left_ports = [p for p in block.ports if PORT_SIDE[p.type] == "left"]
        right_ports = [p for p in block.ports if PORT_SIDE[p.type] == "right"]

        for side, ports in [("left", left_ports), ("right", right_ports)]:
            for idx, port in enumerate(ports):
                total = len(ports)
                y_rel = (idx + 1) / (total + 1)
                x_rel = 0 if side == "left" else 1

                obj_attrs = object_attributes("uml_port", port, {
                    "parent_block_id": block.id,
                    "fqid": f"{block.id}.{port.id}",
                    "port_type": port.type,
                })
                style = PORT_STYLE[port.type]
                label = f"{PORT_PREFIX[port.type]}<br>{html.escape(port.id)}"

                cell_attrs = {
                    "id": mx_port_id(block, port),
                    "value": label,
                    "style": style,
                    "vertex": "1",
                    "parent": mx_block_id(block),
                }
                obj = self._object_cell(root, obj_attrs, cell_attrs)
                g = self._geometry(obj, x=x_rel, y=y_rel, w=62, h=32, relative=1)
                ET.SubElement(g, "mxPoint", {"x": "-31", "y": "-16", "as": "offset"})

    def _render_visible_signals(self, root, visible: dict[str, Block]):
        signal_index = 0
        for signal in self.design.signals:
            visible_endpoints = []
            for endpoint in signal.endpoints:
                block_id, port_id = endpoint.split(".", 1)
                if block_id in visible:
                    block, port = self.design.find_port_ref(endpoint)
                    visible_endpoints.append((endpoint, block, port))

            # Need at least one visible endpoint to show the signal object on this page.
            # With 2+ endpoints it also shows actual signal flow.
            if not visible_endpoints:
                continue

            sx, sy = self._signal_position(signal_index, visible_endpoints)
            signal_index += 1
            self._render_signal_object(root, signal, sx, sy)

            for endpoint, block, port in visible_endpoints:
                self._render_wire(root, signal, endpoint, block, port)

    def _signal_position(self, index: int, endpoints):
        # Position near the average of connected blocks, shifted to avoid overlap.
        centers = []
        for _, block, _ in endpoints:
            x, y, w, h = self.current_block_pos[block.id]
            centers.append((x + w / 2, y + h / 2))

        cx = mean([p[0] for p in centers])
        cy = mean([p[1] for p in centers])

        offset_x = 80 * ((index % 3) - 1)
        offset_y = 60 * (index // 3)
        return int(cx + offset_x - 90), int(cy + offset_y - 35)

    def _render_signal_object(self, root, signal: Signal, x: int, y: int):
        endpoint_text = "<br>".join(html.escape(ep) for ep in signal.endpoints)
        attrs = "<br>".join(
            f"{html.escape(str(k))} = {html.escape(str_attr(v))}"
            for k, v in signal.attributes.items()
        ) or "&nbsp;"

        value = (
            f"&lt;&lt;{html.escape(signal.stereotype)}&gt;&gt;<br>"
            f"<b>{html.escape(signal.name)}</b><br>"
            f"<font style='font-size:9px'>ID: {html.escape(signal.id)}</font>"
            f"<hr size='1'>"
            f"<font style='font-size:9px'>{endpoint_text}</font>"
            f"<hr size='1'>"
            f"<font style='font-size:9px'>{attrs}</font>"
        )

        obj_attrs = object_attributes("uml_signal", signal, {
            "endpoint_count": len(signal.endpoints),
            "endpoints": ",".join(signal.endpoints),
        })
        cell_attrs = {
            "id": mx_signal_id(signal),
            "value": value,
            "style": SIGNAL_STYLE[signal.type],
            "vertex": "1",
            "parent": "1",
        }
        obj = self._object_cell(root, obj_attrs, cell_attrs)
        self._geometry(obj, x, y, 180, 90)

    def _render_wire(self, root, signal: Signal, endpoint: str, block: Block, port: Port):
        obj_attrs = {
            "label": f"{endpoint} -> {signal.name}",
            "kind": "wire",
            "object_id": mx_wire_id(signal, endpoint),
            "object_name": f"{endpoint} -> {signal.name}",
            "signal_id": signal.id,
            "signal_name": signal.name,
            "signal_type": signal.type,
            "endpoint": endpoint,
            "block_id": block.id,
            "port_id": port.id,
        }

        cell_attrs = {
            "id": mx_wire_id(signal, endpoint),
            "value": "",
            "style": WIRE_STYLE[signal.type],
            "edge": "1",
            "parent": "1",
            "source": mx_port_id(block, port),
            "target": mx_signal_id(signal),
        }
        obj = self._object_cell(root, obj_attrs, cell_attrs)
        self._geometry(obj, relative=1)
