from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from model import Design, Block, Port, Connection


PORT_STYLE = {
    "power": "shape=rectangle;fillColor=#ffcccc;strokeColor=#cc0000;fontSize=8;",
    "ground": "shape=rectangle;fillColor=#e6e6e6;strokeColor=#000000;fontSize=8;",
    "input": "shape=ellipse;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=8;",
    "output": "shape=ellipse;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=8;",
    "bidirectional": "shape=ellipse;fillColor=#ffe6cc;strokeColor=#d79b00;fontSize=8;",
    "analog": "shape=ellipse;fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=8;",
}

BLOCK_STYLE = (
    "rounded=1;whiteSpace=wrap;html=1;fillColor=#f8f9fa;"
    "strokeColor=#666666;fontStyle=1;"
)

CHILD_BLOCK_STYLE = (
    "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;"
    "strokeColor=#999999;"
)

EDGE_STYLE = {
    "net": (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
        "jettySize=auto;html=1;endArrow=block;strokeWidth=2;"
    ),
    "bus": (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
        "jettySize=auto;html=1;endArrow=block;strokeWidth=4;dashed=1;"
    ),
}


def safe_id(text: str) -> str:
    return (
        text.replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
        .replace("[", "_")
        .replace("]", "_")
    )


def block_id(path: str) -> str:
    return f"BLOCK_{safe_id(path)}"


def port_id(block_path: str, port_name: str) -> str:
    return f"PORT_{safe_id(block_path)}_{safe_id(port_name)}"


class DrawioRenderer:
    def __init__(self, design: Design):
        self.design = design
        self.root = None
        self.block_positions: dict[str, tuple[int, int, int, int]] = {}

    def render(self, output_file: str | Path) -> Path:
        output_file = Path(output_file)

        mxfile = ET.Element("mxfile", {
            "host": "app.diagrams.net",
            "agent": "python-object-model-renderer",
            "version": "24.0.0",
            "type": "device",
        })

        diagram = ET.SubElement(mxfile, "diagram", {"name": self.design.name})
        model = ET.SubElement(diagram, "mxGraphModel", {
            "dx": "1600",
            "dy": "1000",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "1800",
            "pageHeight": "1100",
            "math": "0",
            "shadow": "0",
        })

        self.root = ET.SubElement(model, "root")
        ET.SubElement(self.root, "mxCell", {"id": "0"})
        ET.SubElement(self.root, "mxCell", {"id": "1", "parent": "0"})

        self._layout_and_render_blocks()
        self._render_connections()

        raw = ET.tostring(mxfile, encoding="utf-8")
        pretty = minidom.parseString(raw).toprettyxml(indent="  ")
        output_file.write_text(pretty, encoding="utf-8")
        return output_file

    def _cell(self, cid, value="", style="", vertex=False, edge=False, parent="1", source=None, target=None):
        attrs = {"id": cid, "value": value, "style": style, "parent": parent}
        if vertex:
            attrs["vertex"] = "1"
        if edge:
            attrs["edge"] = "1"
        if source:
            attrs["source"] = source
        if target:
            attrs["target"] = target
        return ET.SubElement(self.root, "mxCell", attrs)

    def _geometry(self, parent, x=None, y=None, w=None, h=None, relative=None):
        attrs = {"as": "geometry"}
        if x is not None:
            attrs["x"] = str(x)
        if y is not None:
            attrs["y"] = str(y)
        if w is not None:
            attrs["width"] = str(w)
        if h is not None:
            attrs["height"] = str(h)
        if relative is not None:
            attrs["relative"] = str(relative)
        return ET.SubElement(parent, "mxGeometry", attrs)

    def _layout_and_render_blocks(self):
        # Simple deterministic layout for top-level blocks.
        x = 80
        y = 120
        gap = 80

        for i, block in enumerate(self.design.root_blocks):
            w = 520 if block.children else 220
            h = 420 if block.children else 170
            bx = x + i * (w + gap)
            by = y
            self._render_block(block, block.name, bx, by, w, h, parent="1", is_child=False)

    def _render_block(self, block: Block, path: str, x: int, y: int, w: int, h: int, parent: str, is_child: bool):
        bid = block_id(path)
        label = block.label or block.name
        style = CHILD_BLOCK_STYLE if is_child else BLOCK_STYLE

        c = self._cell(bid, label, style, vertex=True, parent=parent)
        self._geometry(c, x, y, w, h)
        self.block_positions[path] = (x, y, w, h)

        self._render_ports(path, block)

        if block.children:
            child_w = 190
            child_h = 105
            cols = 2
            margin_x = 40
            margin_y = 60
            dx = 260
            dy = 160

            for idx, child in enumerate(block.children):
                col = idx % cols
                row = idx // cols
                cx = margin_x + col * dx
                cy = margin_y + row * dy
                child_path = f"{path}.{child.name}"
                self._render_block(
                    child,
                    child_path,
                    cx,
                    cy,
                    child_w,
                    child_h,
                    parent=bid,
                    is_child=True,
                )

    def _render_ports(self, block_path: str, block: Block):
        grouped = {"left": [], "right": [], "top": [], "bottom": []}
        for port in block.ports:
            grouped[port.side].append(port)

        for side, ports in grouped.items():
            total = len(ports)
            for idx, port in enumerate(ports):
                self._render_port(block_path, port, side, idx, total)

    def _render_port(self, block_path: str, port: Port, side: str, idx: int, total: int):
        pid = port_id(block_path, port.name)

        if side in ("left", "right"):
            x_rel = 0 if side == "left" else 1
            y_rel = (idx + 1) / (total + 1)
        else:
            x_rel = (idx + 1) / (total + 1)
            y_rel = 0 if side == "top" else 1

        dx = -10
        dy = -10

        attrs = [
            f"type={port.type}",
            f"fqid={block_path}.{port.name}",
        ]
        if port.voltage:
            attrs.append(f"voltage={port.voltage}")
        if port.protocol:
            attrs.append(f"protocol={port.protocol}")
        if port.constraint_class:
            attrs.append(f"constraint_class={port.constraint_class}")

        tooltip = "&#10;".join(attrs)
        style = PORT_STYLE[port.type] + f"tooltip={tooltip};"

        c = self._cell(pid, port.name, style, vertex=True, parent=block_id(block_path))
        g = self._geometry(c, x=x_rel, y=y_rel, w=20, h=20, relative=1)
        ET.SubElement(g, "mxPoint", {"x": str(dx), "y": str(dy), "as": "offset"})

    def _render_connections(self):
        for conn in self.design.connections:
            source_block, source_port = self.design.find_port(conn.source)
            target_block, target_port = self.design.find_port(conn.target)

            eid = f"LINK_{safe_id(conn.name)}"
            source_id = port_id(source_block, source_port.name)
            target_id = port_id(target_block, target_port.name)

            attrs = [
                f"type={conn.type}",
                f"source={conn.source}",
                f"target={conn.target}",
            ]
            if conn.protocol:
                attrs.append(f"protocol={conn.protocol}")
            if conn.width is not None:
                attrs.append(f"width={conn.width}")
            if conn.constraint_class:
                attrs.append(f"constraint_class={conn.constraint_class}")

            tooltip = "&#10;".join(attrs)
            style = EDGE_STYLE[conn.type] + f"tooltip={tooltip};"

            e = self._cell(
                eid,
                conn.name,
                style,
                edge=True,
                parent="1",
                source=source_id,
                target=target_id,
            )
            self._geometry(e, relative=1)
