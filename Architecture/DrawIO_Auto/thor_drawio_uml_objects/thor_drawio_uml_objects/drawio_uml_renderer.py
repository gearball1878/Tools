from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom
import json
import html

from model import Design, Block, Port, Connection


EDGE_STYLE = {
    "net": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;strokeWidth=2;",
    "bus": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;strokeWidth=4;dashed=1;",
}

PORT_PREFIX = {
    "in": "+",
    "out": "-",
    "bidi": "~",
    "power": "#",
    "ground": "#",
    "analog": "~",
}


def safe_id(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text)


def mx_block_id(block: Block) -> str:
    return f"UML_BLOCK_{safe_id(block.id)}"


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
        "label": obj.name,
        "kind": kind,
        "object_id": obj.id,
        "object_name": obj.name,
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
    Renders each architecture block as a UML-like class/object box.

    UML compartments:
      1. stereotype + name
      2. identity / level
      3. ports
      4. proprietary attributes

    Metadata is still stored in draw.io <object> wrappers,
    so it is readable via Right click -> Edit Data.
    """

    def __init__(self, design: Design):
        self.design = design

    def render(self, output_file: str | Path) -> Path:
        output_file = Path(output_file)
        mxfile = ET.Element("mxfile", {
            "host": "app.diagrams.net",
            "agent": "thor-uml-object-renderer",
            "version": "24.0.0",
            "type": "device",
        })

        self._add_page(mxfile, "L1_UML_Domains", self.design.domains, parent_block=None)

        for block in self.design.walk_blocks():
            if block.children:
                self._add_page(mxfile, block.id, block.children, parent_block=block)

        raw = ET.tostring(mxfile, encoding="utf-8")
        pretty = minidom.parseString(raw).toprettyxml(indent="  ")
        output_file.write_text(pretty, encoding="utf-8")
        return output_file

    def _add_page(self, mxfile, page_name: str, blocks: list[Block], parent_block: Block | None):
        diagram = ET.SubElement(mxfile, "diagram", {"name": page_name})
        model = ET.SubElement(diagram, "mxGraphModel", {
            "dx": "1600", "dy": "1000", "grid": "1", "gridSize": "10",
            "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
            "fold": "1", "page": "1", "pageScale": "1", "pageWidth": "1800",
            "pageHeight": "1100", "math": "0", "shadow": "0",
        })
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", {"id": "0"})
        ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

        if parent_block:
            title = ET.SubElement(root, "mxCell", {
                "id": f"TITLE_{safe_id(parent_block.id)}",
                "value": f"UML Drill-down: {parent_block.name}",
                "style": "text;html=1;strokeColor=none;fillColor=none;fontSize=18;fontStyle=1;",
                "vertex": "1",
                "parent": "1",
            })
            ET.SubElement(title, "mxGeometry", {"x": "40", "y": "20", "width": "1000", "height": "40", "as": "geometry"})

        cols = 3
        w, h = 340, 260
        start_x, start_y = 80, 110
        gap_x, gap_y = 120, 120

        for idx, block in enumerate(blocks):
            x = start_x + (idx % cols) * (w + gap_x)
            y = start_y + (idx // cols) * (h + gap_y)
            self._render_uml_block(root, block, x, y, w, h)

        visible = {b.id for b in blocks}
        for conn in self.design.connections:
            src_block_id, _ = conn.source.split(".", 1)
            dst_block_id, _ = conn.target.split(".", 1)
            if src_block_id in visible and dst_block_id in visible:
                self._render_connection(root, conn)

    def _uml_value(self, block: Block) -> str:
        ports = "<br>".join(
            f"{PORT_PREFIX[p.type]} {html.escape(p.name)} : {html.escape(p.type)}"
            for p in block.ports
        ) or "&nbsp;"

        attrs = "<br>".join(
            f"{html.escape(str(k))} = {html.escape(str_attr(v))}"
            for k, v in block.attributes.items()
        ) or "&nbsp;"

        drill = "<br><font style='font-size:10px'>linked drill-down page</font>" if block.children else ""

        return (
            f"<div style='font-size:11px'>&lt;&lt;{html.escape(block.stereotype)}&gt;&gt;</div>"
            f"<b><u>{html.escape(block.name)}</u></b><br>"
            f"<font style='font-size:10px'>{html.escape(block.id)}</font>{drill}"
            f"<hr size='1'>"
            f"<b>ports</b><br>{ports}"
            f"<hr size='1'>"
            f"<b>attributes</b><br>{attrs}"
        )

    def _render_uml_block(self, root, block: Block, x: int, y: int, w: int, h: int):
        has_children = bool(block.children)
        link = f"link=data:page/id,{block.id};" if has_children else ""

        # UML/class-like shape. Compartments are rendered in HTML inside the object.
        style = (
            "rounded=0;whiteSpace=wrap;html=1;align=center;verticalAlign=top;"
            "spacingTop=8;fillColor=#ffffff;strokeColor=#333333;fontSize=12;"
            + link
        )

        obj_attrs = object_attributes("uml_block", block, {"has_children": has_children})
        obj = ET.SubElement(root, "object", obj_attrs)
        cell = ET.SubElement(obj, "mxCell", {
            "id": mx_block_id(block),
            "value": self._uml_value(block),
            "style": style,
            "vertex": "1",
            "parent": "1",
        })
        ET.SubElement(cell, "mxGeometry", {
            "x": str(x), "y": str(y), "width": str(w), "height": str(h), "as": "geometry"
        })

    def _render_connection(self, root, conn: Connection):
        src_block_id, src_port_id = conn.source.split(".", 1)
        dst_block_id, dst_port_id = conn.target.split(".", 1)
        src_block = self.design.find_block(src_block_id)
        dst_block = self.design.find_block(dst_block_id)

        label = (
            f"&lt;&lt;{html.escape(conn.stereotype)}&gt;&gt;<br>"
            f"{html.escape(conn.name)}<br>"
            f"<font style='font-size:9px'>{html.escape(conn.source)} → {html.escape(conn.target)}</font>"
        )

        obj_attrs = object_attributes("uml_connection", conn, {
            "source": conn.source,
            "target": conn.target,
            "source_port": src_port_id,
            "target_port": dst_port_id,
        })

        obj = ET.SubElement(root, "object", obj_attrs)
        cell = ET.SubElement(obj, "mxCell", {
            "id": mx_conn_id(conn),
            "value": label,
            "style": EDGE_STYLE[conn.type],
            "edge": "1",
            "parent": "1",
            "source": mx_block_id(src_block),
            "target": mx_block_id(dst_block),
        })
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
