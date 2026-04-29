from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom
import json
import html

from model import Design, Block, Port, Connection


PORT_STYLE = {
    "in": "shape=ellipse;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=8;",
    "out": "shape=ellipse;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=8;",
    "bidi": "shape=ellipse;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;fontSize=8;",
    "power": "shape=rectangle;html=1;fillColor=#ffcccc;strokeColor=#cc0000;fontSize=8;",
    "ground": "shape=rectangle;html=1;fillColor=#e6e6e6;strokeColor=#000000;fontSize=8;",
    "analog": "shape=ellipse;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=8;",
}

EDGE_STYLE = {
    "net": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;strokeWidth=2;",
    "bus": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;strokeWidth=4;dashed=1;",
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


def mx_conn_id(conn: Connection) -> str:
    return f"UML_CONN_{safe_id(conn.id)}"


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


class DrawioUmlRenderer:
    """
    UML-like top-down renderer with real visible port objects.

    - Blocks are UML-like object/class boxes.
    - Ports are separate draw.io objects attached to block borders.
    - Connections terminate on port objects, not only on blocks.
    - All proprietary data is visible via Right click -> Edit Data.
    """

    def __init__(self, design: Design):
        self.design = design

    def render(self, output_file: str | Path) -> Path:
        output_file = Path(output_file)
        mxfile = ET.Element("mxfile", {
            "host": "app.diagrams.net",
            "agent": "thor-uml-complete-port-connection-renderer",
            "version": "24.0.0",
            "type": "device",
        })

        self._add_page(mxfile, "L1_UML_Domains", parent_block=None)

        for block in self.design.walk_blocks():
            if block.children:
                self._add_page(mxfile, block.id, parent_block=block)

        raw = ET.tostring(mxfile, encoding="utf-8")
        pretty = minidom.parseString(raw).toprettyxml(indent="  ")
        output_file.write_text(pretty, encoding="utf-8")
        return output_file

    def _add_page(self, mxfile, page_name: str, parent_block: Block | None):
        blocks = self.design.direct_children_of(parent_block)
        diagram = ET.SubElement(mxfile, "diagram", {"name": page_name})
        model = ET.SubElement(diagram, "mxGraphModel", {
            "dx": "1800", "dy": "1100", "grid": "1", "gridSize": "10",
            "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
            "fold": "1", "page": "1", "pageScale": "1", "pageWidth": "1900",
            "pageHeight": "1200", "math": "0", "shadow": "0",
        })
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

        if parent_block:
            self._title(root, f"UML Drill-down: {parent_block.name} ({parent_block.id})")
        else:
            self._title(root, self.design.name)

        cols = 3
        w, h = 360, 250
        start_x, start_y = 100, 130
        gap_x, gap_y = 150, 140

        visible = {}
        for idx, block in enumerate(blocks):
            x = start_x + (idx % cols) * (w + gap_x)
            y = start_y + (idx // cols) * (h + gap_y)
            visible[block.id] = block
            self._render_uml_block(root, block, x, y, w, h)
            self._render_ports(root, block)

        self._render_visible_connections(root, visible)

    def _title(self, root, text):
        cell = ET.SubElement(root, "mxCell", {
            "id": f"TITLE_{safe_id(text)}",
            "value": html.escape(text),
            "style": "text;html=1;strokeColor=none;fillColor=none;fontSize=18;fontStyle=1;align=left;",
            "vertex": "1",
            "parent": "1",
        })
        ET.SubElement(cell, "mxGeometry", {"x": "40", "y": "30", "width": "1200", "height": "40", "as": "geometry"})

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
                g = self._geometry(obj, x=x_rel, y=y_rel, w=54, h=30, relative=1)
                ET.SubElement(g, "mxPoint", {"x": "-27", "y": "-15", "as": "offset"})

    def _render_visible_connections(self, root, visible: dict[str, Block]):
        for conn in self.design.connections:
            src_block_id, src_port_id = conn.source.split(".", 1)
            dst_block_id, dst_port_id = conn.target.split(".", 1)

            if src_block_id not in visible or dst_block_id not in visible:
                continue

            src_block, src_port = self.design.find_port_ref(conn.source)
            dst_block, dst_port = self.design.find_port_ref(conn.target)

            label = (
                f"&lt;&lt;{html.escape(conn.stereotype)}&gt;&gt;<br>"
                f"{html.escape(conn.name)}<br>"
                f"<font style='font-size:9px'>{html.escape(conn.id)}</font>"
            )

            obj_attrs = object_attributes("uml_connection", conn, {
                "source": conn.source,
                "target": conn.target,
                "source_port": src_port_id,
                "target_port": dst_port_id,
            })
            cell_attrs = {
                "id": mx_conn_id(conn),
                "value": label,
                "style": EDGE_STYLE[conn.type],
                "edge": "1",
                "parent": "1",
                "source": mx_port_id(src_block, src_port),
                "target": mx_port_id(dst_block, dst_port),
            }
            obj = self._object_cell(root, obj_attrs, cell_attrs)
            self._geometry(obj, relative=1)
