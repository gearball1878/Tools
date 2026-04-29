from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom
import html
import json

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
    result = []
    for ch in text:
        if ch.isalnum() or ch == "_":
            result.append(ch)
        else:
            result.append("_")
    return "".join(result)


def mx_block_id(block: Block) -> str:
    return f"BLOCK_{safe_id(block.id)}"


def mx_port_id(block: Block, port: Port) -> str:
    return f"PORT_{safe_id(block.id)}_{safe_id(port.id)}"


def mx_conn_id(conn: Connection) -> str:
    return f"CONN_{safe_id(conn.id)}"


def data_attrs(kind: str, obj) -> str:
    payload = {
        "kind": kind,
        "id": obj.id,
        "name": obj.name,
        "type": getattr(obj, "type", None),
        "level": getattr(obj, "level", None),
        "attributes": getattr(obj, "attributes", {}),
    }
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    label = html.escape(obj.name)
    tooltip = html.escape(json.dumps(payload, ensure_ascii=False, indent=2))
    return compact, label, tooltip


class DrawioRenderer:
    """
    Multi-page renderer:
      Page 1: Level-1 domains
      One page per block with children: drill-down page
      Each block that has children contains a link to its page.

    Metadata is embedded as draw.io custom object data in attributes:
      data_kind, data_id, data_name, data_type, data_level, data_json
    """

    def __init__(self, design: Design):
        self.design = design

    def render(self, output_file: str | Path) -> Path:
        output_file = Path(output_file)

        mxfile = ET.Element("mxfile", {
            "host": "app.diagrams.net",
            "agent": "thor-4level-python-renderer",
            "version": "24.0.0",
            "type": "device",
        })

        # Overview page
        self._add_page(mxfile, "L1_Domains", self.design.domains, level=1, parent_block=None)

        # Drill-down pages for every block with children
        for block in self.design.walk_blocks():
            if block.children:
                self._add_page(mxfile, f"{block.id}", block.children, level=block.level + 1, parent_block=block)

        raw = ET.tostring(mxfile, encoding="utf-8")
        pretty = minidom.parseString(raw).toprettyxml(indent="  ")
        output_file.write_text(pretty, encoding="utf-8")
        return output_file

    def _add_page(self, mxfile, page_name: str, blocks: list[Block], level: int, parent_block: Block | None):
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

        if parent_block is not None:
            title = self._cell(root, f"TITLE_{safe_id(parent_block.id)}", f"{parent_block.name}  /  Level {parent_block.level} → {level}",
                               "text;html=1;strokeColor=none;fillColor=none;fontSize=18;fontStyle=1;",
                               vertex=True, parent="1")
            self._geometry(title, 40, 20, 900, 40)

        block_pos = {}
        cols = 3
        w, h = 300, 180
        start_x, start_y = 80, 100
        gap_x, gap_y = 120, 120

        for idx, block in enumerate(blocks):
            x = start_x + (idx % cols) * (w + gap_x)
            y = start_y + (idx // cols) * (h + gap_y)
            block_pos[block.id] = (x, y, w, h)
            self._render_block(root, block, x, y, w, h)

        # Render only connections whose endpoints are visible on this page
        visible = {b.id for b in blocks}
        for conn in self.design.connections:
            src_block_id, src_port_id = conn.source.split(".", 1)
            dst_block_id, dst_port_id = conn.target.split(".", 1)
            if src_block_id in visible and dst_block_id in visible:
                src_block = self.design.find_block(src_block_id)
                dst_block = self.design.find_block(dst_block_id)
                src_port = next(p for p in src_block.ports if p.id == src_port_id)
                dst_port = next(p for p in dst_block.ports if p.id == dst_port_id)
                self._render_connection(root, conn, src_block, src_port, dst_block, dst_port)

    def _cell(self, root, cid, value="", style="", vertex=False, edge=False, parent="1", source=None, target=None, extra=None):
        attrs = {"id": cid, "value": value, "style": style, "parent": parent}
        if vertex:
            attrs["vertex"] = "1"
        if edge:
            attrs["edge"] = "1"
        if source:
            attrs["source"] = source
        if target:
            attrs["target"] = target
        if extra:
            attrs.update(extra)
        return ET.SubElement(root, "mxCell", attrs)

    def _geometry(self, cell, x=None, y=None, w=None, h=None, relative=None):
        attrs = {"as": "geometry"}
        if x is not None: attrs["x"] = str(x)
        if y is not None: attrs["y"] = str(y)
        if w is not None: attrs["width"] = str(w)
        if h is not None: attrs["height"] = str(h)
        if relative is not None: attrs["relative"] = str(relative)
        return ET.SubElement(cell, "mxGeometry", attrs)

    def _render_block(self, root, block: Block, x: int, y: int, w: int, h: int):
        compact, label, tooltip = data_attrs("block", block)
        has_children = bool(block.children)
        link = f"data:page/id,{block.id}" if has_children else ""
        suffix = "<br><font style='font-size:10px'>double-click / link: drill-down</font>" if has_children else ""
        value = f"<b>{label}</b><br><font style='font-size:10px'>{html.escape(block.id)}</font>{suffix}"

        extra = {
            "data_kind": "block",
            "data_id": block.id,
            "data_name": block.name,
            "data_level": str(block.level),
            "data_json": compact,
        }
        style = BLOCK_STYLE[block.level]
        if has_children:
            style += f"link={link};"

        c = self._cell(root, mx_block_id(block), value, style, vertex=True, parent="1", extra=extra)
        self._geometry(c, x, y, w, h)

        self._render_ports(root, block)

    def _render_ports(self, root, block: Block):
        sides = {"left": [], "right": []}
        for port in block.ports:
            # Simple deterministic placement by port type
            if port.type in ("in", "power", "ground", "analog"):
                sides["left"].append(port)
            else:
                sides["right"].append(port)

        for side, ports in sides.items():
            for idx, port in enumerate(ports):
                total = len(ports)
                x_rel = 0 if side == "left" else 1
                y_rel = (idx + 1) / (total + 1)

                compact, label, tooltip = data_attrs("port", port)
                extra = {
                    "data_kind": "port",
                    "data_id": port.id,
                    "data_name": port.name,
                    "data_type": port.type,
                    "data_parent_block_id": block.id,
                    "data_json": compact,
                }
                style = PORT_STYLE[port.type] + f"tooltip={tooltip};"
                p = self._cell(root, mx_port_id(block, port), label, style, vertex=True, parent=mx_block_id(block), extra=extra)
                g = self._geometry(p, x=x_rel, y=y_rel, w=22, h=22, relative=1)
                ET.SubElement(g, "mxPoint", {"x": "-11", "y": "-11", "as": "offset"})

    def _render_connection(self, root, conn: Connection, src_block: Block, src_port: Port, dst_block: Block, dst_port: Port):
        compact, label, tooltip = data_attrs("connection", conn)
        extra = {
            "data_kind": "connection",
            "data_id": conn.id,
            "data_name": conn.name,
            "data_type": conn.type,
            "data_source": conn.source,
            "data_target": conn.target,
            "data_json": compact,
        }
        style = EDGE_STYLE[conn.type] + f"tooltip={tooltip};"
        e = self._cell(root, mx_conn_id(conn), label, style, edge=True, parent="1",
                       source=mx_port_id(src_block, src_port),
                       target=mx_port_id(dst_block, dst_port),
                       extra=extra)
        self._geometry(e, relative=1)
