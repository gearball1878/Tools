from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom
import json
import html

from model import Design, Block, Port, Connection


PORT_STYLE = {
    "in": "shape=ellipse;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=8;",
    "out": "shape=ellipse;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=8;",
    "bidi": "shape=ellipse;fillColor=#ffe6cc;strokeColor=#d79b00;fontSize=8;",
    "power": "shape=rectangle;fillColor=#ffcccc;strokeColor=#cc0000;fontSize=8;",
    "ground": "shape=rectangle;fillColor=#e6e6e6;strokeColor=#000000;fontSize=8;",
    "analog": "shape=ellipse;fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=8;",
}

BLOCK_STYLE = {
    1: "rounded=1;whiteSpace=wrap;html=1;fillColor=#f8f9fa;strokeColor=#333333;fontStyle=1;",
    2: "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#666666;fontStyle=1;",
    3: "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#999999;",
    4: "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#b3b3b3;",
}

EDGE_STYLE = {
    "net": "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeWidth=2;",
    "bus": "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;strokeWidth=4;dashed=1;",
}


def safe_id(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text)


def mx_block_id(block: Block) -> str:
    return f"BLOCK_{safe_id(block.id)}"


def mx_port_id(block: Block, port: Port) -> str:
    return f"PORT_{safe_id(block.id)}_{safe_id(port.id)}"


def mx_conn_id(conn: Connection) -> str:
    return f"CONN_{safe_id(conn.id)}"


def str_attr(value) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if value is None:
        return ""
    return str(value)


def object_attributes(kind: str, obj, extra: dict | None = None) -> dict[str, str]:
    """
    These attributes are stored on draw.io <object>.
    They are visible via:
      right click shape -> Edit Data
    or:
      Format Panel -> Data
    """
    attrs = {
        "label": obj.name,
        "kind": kind,
        "object_id": obj.id,
        "object_name": obj.name,
        "attributes_json": json.dumps(obj.attributes, ensure_ascii=False, separators=(",", ":")),
    }

    if hasattr(obj, "level"):
        attrs["level"] = str(obj.level)
    if hasattr(obj, "type"):
        attrs["type"] = str(obj.type)

    if extra:
        attrs.update({k: str_attr(v) for k, v in extra.items()})

    # Flatten proprietary attributes so they are immediately readable in draw.io Edit Data.
    for key, value in getattr(obj, "attributes", {}).items():
        attrs[f"attr_{key}"] = str_attr(value)

    return attrs


class DrawioRenderer:
    """
    Important:
    This renderer stores metadata on draw.io <object> wrappers, not only on mxCell.

    Result:
      - Open .drawio
      - Select object
      - Right click -> Edit Data
      - Proprietary attributes are visible as normal data fields
    """

    def __init__(self, design: Design):
        self.design = design

    def render(self, output_file: str | Path) -> Path:
        output_file = Path(output_file)

        mxfile = ET.Element("mxfile", {
            "host": "app.diagrams.net",
            "agent": "thor-readable-attribute-renderer",
            "version": "24.0.0",
            "type": "device",
        })

        self._add_page(mxfile, "L1_Domains", self.design.domains, parent_block=None)

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
            title = self._mxcell(root, f"TITLE_{safe_id(parent_block.id)}",
                                 f"{parent_block.name} / Drill-down",
                                 "text;html=1;strokeColor=none;fillColor=none;fontSize=18;fontStyle=1;",
                                 vertex=True)
            self._geometry(title, 40, 20, 900, 40)

        cols = 3
        w, h = 320, 190
        start_x, start_y = 80, 110
        gap_x, gap_y = 120, 120

        for idx, block in enumerate(blocks):
            x = start_x + (idx % cols) * (w + gap_x)
            y = start_y + (idx // cols) * (h + gap_y)
            self._render_block(root, block, x, y, w, h)

        visible = {b.id for b in blocks}
        for conn in self.design.connections:
            src_block_id, src_port_id = conn.source.split(".", 1)
            dst_block_id, dst_port_id = conn.target.split(".", 1)
            if src_block_id in visible and dst_block_id in visible:
                src_block, src_port = self.design.find_port_ref(conn.source)
                dst_block, dst_port = self.design.find_port_ref(conn.target)
                self._render_connection(root, conn, src_block, src_port, dst_block, dst_port)

    def _mxcell(self, parent, cid, value, style, vertex=False, edge=False, source=None, target=None):
        attrs = {"id": cid, "value": value, "style": style, "parent": "1"}
        if vertex:
            attrs["vertex"] = "1"
        if edge:
            attrs["edge"] = "1"
        if source:
            attrs["source"] = source
        if target:
            attrs["target"] = target
        return ET.SubElement(parent, "mxCell", attrs)

    def _object_cell(self, root, object_attrs: dict[str, str], cell_attrs: dict[str, str]):
        obj = ET.SubElement(root, "object", object_attrs)
        ET.SubElement(obj, "mxCell", cell_attrs)
        return obj

    def _geometry(self, cell_or_obj, x=None, y=None, w=None, h=None, relative=None):
        # Geometry is child of mxCell. If object wrapper was passed, get its mxCell.
        if cell_or_obj.tag == "object":
            cell = cell_or_obj.find("mxCell")
        else:
            cell = cell_or_obj

        attrs = {"as": "geometry"}
        if x is not None: attrs["x"] = str(x)
        if y is not None: attrs["y"] = str(y)
        if w is not None: attrs["width"] = str(w)
        if h is not None: attrs["height"] = str(h)
        if relative is not None: attrs["relative"] = str(relative)
        return ET.SubElement(cell, "mxGeometry", attrs)

    def _render_block(self, root, block: Block, x: int, y: int, w: int, h: int):
        has_children = bool(block.children)
        link = f"data:page/id,{block.id}" if has_children else ""
        details = self._visible_details(block.attributes)
        drill = "<br><font style='font-size:10px'>drill-down page available</font>" if has_children else ""
        value = (
            f"<b>{html.escape(block.name)}</b><br>"
            f"<font style='font-size:10px'>{html.escape(block.id)}</font>"
            f"{details}{drill}"
        )

        style = BLOCK_STYLE[block.level]
        if has_children:
            style += f"link={link};"

        obj_attrs = object_attributes("block", block, {"has_children": has_children})
        cell_attrs = {
            "id": mx_block_id(block),
            "value": value,
            "style": style,
            "vertex": "1",
            "parent": "1",
        }
        obj = self._object_cell(root, obj_attrs, cell_attrs)
        self._geometry(obj, x, y, w, h)

        self._render_ports(root, block)

    def _visible_details(self, attrs: dict) -> str:
        if not attrs:
            return ""
        keys = list(attrs.keys())[:4]
        lines = []
        for k in keys:
            lines.append(f"{html.escape(str(k))}: {html.escape(str_attr(attrs[k]))}")
        return "<br><font style='font-size:9px'>" + "<br>".join(lines) + "</font>"

    def _render_ports(self, root, block: Block):
        left_types = {"in", "power", "ground", "analog"}
        sides = {"left": [], "right": []}
        for port in block.ports:
            sides["left" if port.type in left_types else "right"].append(port)

        for side, ports in sides.items():
            for idx, port in enumerate(ports):
                total = len(ports)
                x_rel = 0 if side == "left" else 1
                y_rel = (idx + 1) / (total + 1)

                obj_attrs = object_attributes("port", port, {
                    "parent_block_id": block.id,
                    "fqid": f"{block.id}.{port.id}",
                })
                cell_attrs = {
                    "id": mx_port_id(block, port),
                    "value": port.name,
                    "style": PORT_STYLE[port.type],
                    "vertex": "1",
                    "parent": mx_block_id(block),
                }

                obj = self._object_cell(root, obj_attrs, cell_attrs)
                geom = self._geometry(obj, x=x_rel, y=y_rel, w=22, h=22, relative=1)
                ET.SubElement(geom, "mxPoint", {"x": "-11", "y": "-11", "as": "offset"})

    def _render_connection(self, root, conn: Connection, src_block: Block, src_port: Port, dst_block: Block, dst_port: Port):
        obj_attrs = object_attributes("connection", conn, {
            "source": conn.source,
            "target": conn.target,
        })
        cell_attrs = {
            "id": mx_conn_id(conn),
            "value": conn.name,
            "style": EDGE_STYLE[conn.type],
            "edge": "1",
            "parent": "1",
            "source": mx_port_id(src_block, src_port),
            "target": mx_port_id(dst_block, dst_port),
        }
        obj = self._object_cell(root, obj_attrs, cell_attrs)
        self._geometry(obj, relative=1)
