from __future__ import annotations

import base64
import hashlib
import json
from html import escape
from typing import Any

from .models import ArchitecturePackage
from .hardware_topology import is_global_ground, block_port_visible


SIGNAL_COLORS = {
    "Power": "#C2410C",
    "Analog": "#0E7490",
    "Digital": "#2563EB",
    "Clock": "#7C3AED",
    "Reset": "#DC3D62",
    "Control": "#B45309",
    "Status": "#15803D",
    "Differential": "#4F46E5",
    "Interface": "#0F766E",
    "Memory": "#6D28D9",
}


def _resolved_side(package: ArchitecturePackage, port: object) -> str:
    # Connection semantics take precedence over imported or manually retained
    # side values: sources leave on the right, every sink is entered from left.
    for connection in package.connections:
        for index, endpoint in enumerate(connection.endpoints):
            if endpoint.port_id == port.id:
                return "Right" if index == 0 else "Left"
    if str(port.role).casefold() == "host":
        return "Right"
    if str(port.role).casefold() == "participant":
        return "Left"
    return "Left" if str(port.role).casefold() in {"peripheral", "sink", "peer"} else "Right"


def _root_layout_options() -> dict[str, str]:
    return {
        "elk.algorithm": "layered",
        "elk.direction": "RIGHT",
        "elk.edgeRouting": "ORTHOGONAL",
        "elk.hierarchyHandling": "INCLUDE_CHILDREN",
        "elk.padding": "[top=48,left=48,bottom=48,right=48]",
        "elk.spacing.nodeNode": "96",
        "elk.spacing.edgeEdge": "28",
        "elk.spacing.edgeNode": "42",
        "elk.layered.spacing.nodeNodeBetweenLayers": "150",
        "elk.layered.spacing.edgeNodeBetweenLayers": "40",
        "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
        "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
        "elk.layered.mergeEdges": "true",
        "elk.layered.mergeHierarchyCrossingEdges": "true",
        "elk.layered.feedbackEdges": "true",
        "elk.layered.compaction.postCompaction.strategy": "EDGE_LENGTH",
        "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
        "elk.separateConnectedComponents": "true",
    }


def _architecture_maps(package: ArchitecturePackage) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    elements_by_id: dict[str, Any] = {}
    ports_by_id: dict[str, Any] = {}
    element_domain: dict[str, str] = {}
    for domain in package.domains:
        for element in domain.elements:
            elements_by_id[element.id] = element
            element_domain[element.id] = domain.id
            for port in element.ports:
                ports_by_id[port.id] = port
    return elements_by_id, ports_by_id, element_domain


def _filtered_connections(package: ArchitecturePackage, signal_types: set[str] | None) -> list[Any]:
    ground_ids = {signal.id for signal in package.signals if is_global_ground(signal)}
    signal_type_by_id = {signal.id: signal.signal_type.value for signal in package.signals}
    return [connection for connection in package.connections
            if connection.signal_id not in ground_ids and
            (signal_types is None or signal_type_by_id.get(connection.signal_id, 'Interface') in signal_types)]



def _focus_scope(
    package: ArchitecturePackage,
    selected_id: str | None,
    candidates: list[Any],
) -> tuple[set[str] | None, set[str] | None]:
    """Return connection and element IDs for a one-hop selection view."""
    if not selected_id:
        return None, None
    selected_connection_ids: set[str] = set()
    selected_element_ids: set[str] = set()
    if package.find_domain(selected_id):
        selected_element_ids = {element.id for element in package.find_domain(selected_id).elements}
        selected_connection_ids = {
            connection.id for connection in candidates
            if any(endpoint.element_id in selected_element_ids for endpoint in connection.endpoints)
        }
    else:
        element_result = package.find_element(selected_id)
        port_result = package.find_port(selected_id)
        signal = package.find_architecture_signal(selected_id)
        connection = next((item for item in candidates if item.id == selected_id), None)
        if element_result:
            selected_element_ids.add(element_result[1].id)
            selected_connection_ids = {
                item.id for item in candidates
                if any(endpoint.element_id == element_result[1].id for endpoint in item.endpoints)
            }
        elif port_result:
            selected_element_ids.add(port_result[1].id)
            selected_connection_ids = {
                item.id for item in candidates
                if any(endpoint.port_id == port_result[2].id for endpoint in item.endpoints)
            }
        elif signal:
            selected_connection_ids = {item.id for item in candidates if item.signal_id == signal.id}
            if signal.source:
                selected_element_ids.add(signal.source.element_id)
            selected_element_ids.update(endpoint.element_id for endpoint in signal.sinks)
        elif connection:
            selected_connection_ids.add(connection.id)
    for connection in candidates:
        if connection.id in selected_connection_ids:
            selected_element_ids.update(endpoint.element_id for endpoint in connection.endpoints)
    return selected_connection_ids, selected_element_ids


def _overview_graph(
    package: ArchitecturePackage,
    selected_id: str | None,
    signal_types: set[str] | None,
) -> dict[str, Any]:
    """Create a domain-only view with one aggregated edge per domain pair."""
    _, _, element_domain = _architecture_maps(package)
    candidates = _filtered_connections(package, signal_types)
    aggregates: dict[tuple[str, str], set[str]] = {}
    internal_counts: dict[str, int] = {domain.id: 0 for domain in package.domains}
    for connection in candidates:
        if len(connection.endpoints) < 2:
            continue
        source_domain = element_domain.get(connection.endpoints[0].element_id)
        sink_domains = {element_domain.get(endpoint.element_id) for endpoint in connection.endpoints[1:]}
        for sink_domain in sink_domains:
            if not source_domain or not sink_domain:
                continue
            if source_domain == sink_domain:
                internal_counts[source_domain] += 1
            else:
                aggregates.setdefault((source_domain, sink_domain), set()).add(connection.id)

    incoming: dict[str, list[tuple[str, int]]] = {domain.id: [] for domain in package.domains}
    outgoing: dict[str, list[tuple[str, int]]] = {domain.id: [] for domain in package.domains}
    domain_by_id = {domain.id: domain for domain in package.domains}
    for (source_id, sink_id), connection_ids in aggregates.items():
        outgoing[source_id].append((sink_id, len(connection_ids)))
        incoming[sink_id].append((source_id, len(connection_ids)))

    domains: dict[str, dict[str, Any]] = {}
    ports: dict[str, dict[str, Any]] = {}
    graph_children: list[dict[str, Any]] = []
    for domain in package.domains:
        left = sorted(incoming[domain.id], key=lambda item: domain_by_id[item[0]].name.casefold())
        right = sorted(outgoing[domain.id], key=lambda item: domain_by_id[item[0]].name.casefold())
        rows = max(len(left), len(right), 1)
        width = 370
        height = max(170, 112 + rows * 38)
        elk_ports: list[dict[str, Any]] = []
        for side, entries in (("Left", left), ("Right", right)):
            for index, (other_domain_id, count) in enumerate(entries):
                port_id = f"overview:{domain.id}:{other_domain_id}:{side}"
                other = domain_by_id[other_domain_id]
                ports[port_id] = {
                    "name": f"{other.name} · {count}",
                    "portType": "Domain-Verbindung",
                    "role": "Participant" if side == "Left" else "Host",
                    "side": side,
                    "domainId": domain.id,
                    "color": domain.color,
                    "selectable": False,
                    "aggregateCount": count,
                }
                elk_ports.append({
                    "id": port_id,
                    "width": 12,
                    "height": 12,
                    "x": -6 if side == "Left" else width - 6,
                    "y": 104 + index * 38,
                    "layoutOptions": {"elk.port.side": "WEST" if side == "Left" else "EAST"},
                })
        domains[domain.id] = {
            "name": domain.name,
            "color": domain.color,
            "collapsed": True,
            "elementCount": len(domain.elements),
            "incomingCount": sum(count for _, count in left),
            "outgoingCount": sum(count for _, count in right),
            "internalCount": internal_counts[domain.id],
        }
        graph_children.append({
            "id": domain.id,
            "width": width,
            "height": height,
            "ports": elk_ports,
            "layoutOptions": {"elk.portConstraints": "FIXED_POS"},
        })

    graph_edges: list[dict[str, Any]] = []
    connections: dict[str, dict[str, Any]] = {}
    for (source_id, sink_id), connection_ids in aggregates.items():
        aggregate_id = f"aggregate:{source_id}:{sink_id}"
        edge_id = f"edge:{aggregate_id}"
        source_port = f"overview:{source_id}:{sink_id}:Right"
        sink_port = f"overview:{sink_id}:{source_id}:Left"
        graph_edges.append({"id": edge_id, "sources": [source_port], "targets": [sink_port]})
        connections[aggregate_id] = {
            "name": f"{len(connection_ids)} Domain-Verbindung(en)",
            "connectionType": "Aggregate",
            "edgeIds": [edge_id],
            "sourcePortId": source_port,
            "sinkPortIds": [sink_port],
            "selectable": False,
            "aggregateCount": len(connection_ids),
        }

    return {
        "graph": {
            "id": "xped-architecture-root",
            "layoutOptions": _root_layout_options(),
            "children": graph_children,
            "edges": graph_edges,
        },
        "meta": {
            "domains": domains,
            "elements": {},
            "ports": ports,
            "connections": connections,
            "selectedId": selected_id,
            "viewMode": "system",
        },
    }


def architecture_graph(
    package: ArchitecturePackage,
    selected_id: str | None = None,
    view_mode: str = "architecture",
    focus_domain_id: str | None = None,
    collapsed_domain_ids: set[str] | None = None,
    collapsed_element_ids: set[str] | None = None,
    signal_types: set[str] | None = None,
) -> dict[str, Any]:
    """Translate the SPOT package into a scalable ELK graph and render metadata."""
    if view_mode == "system":
        return _overview_graph(package, selected_id, signal_types)

    elements_by_id, _, element_domain = _architecture_maps(package)
    candidates = _filtered_connections(package, signal_types)
    collapsed = set(collapsed_domain_ids or set())
    collapsed_elements = set(collapsed_element_ids or set())
    visible_element_ids: set[str] | None = None
    if view_mode == "domain" and focus_domain_id:
        collapsed = {domain.id for domain in package.domains if domain.id != focus_domain_id}
        focus_elements = {element.id for element in package.find_domain(focus_domain_id).elements} if package.find_domain(focus_domain_id) else set()
        candidates = [
            connection for connection in candidates
            if any(endpoint.element_id in focus_elements for endpoint in connection.endpoints)
        ]
        visible_element_ids = {endpoint.element_id for connection in candidates for endpoint in connection.endpoints} | focus_elements
    elif view_mode == "selection":
        connection_scope, visible_element_ids = _focus_scope(package, selected_id, candidates)
        if connection_scope is not None:
            candidates = [connection for connection in candidates if connection.id in connection_scope]

    visible_domain_ids = {
        element_domain[element_id] for element_id in visible_element_ids or elements_by_id
        if element_id in element_domain
    }
    included_connections = [
        connection for connection in candidates
        if len(connection.endpoints) >= 2
        and all(endpoint.element_id in elements_by_id for endpoint in connection.endpoints)
        and all(element_domain[endpoint.element_id] in visible_domain_ids for endpoint in connection.endpoints)
    ]

    proxy_ports: dict[str, dict[str, dict[str, Any]]] = {domain.id: {} for domain in package.domains}
    element_proxy_ports: dict[str, dict[str, dict[str, Any]]] = {
        element.id: {} for domain in package.domains for element in domain.elements
    }
    domain_names = {domain.id: domain.name for domain in package.domains}
    remapped_connections: list[tuple[Any, str, list[str]]] = []
    for connection in included_connections:
        source = connection.endpoints[0]
        source_domain_id = element_domain[source.element_id]
        if source_domain_id in collapsed and all(element_domain[v.element_id] == source_domain_id for v in connection.endpoints):
            continue
        source_port_id = source.port_id
        if source_domain_id in collapsed:
            source_port_id = f"proxy:{connection.id}:{source_domain_id}:source"
            proxy_ports[source_domain_id][source_port_id] = {
                "name": connection.name,
                "side": "Right",
                "role": "Host",
                "targetId": connection.id,
                "targetType": "connection",
            }
        elif source.element_id in collapsed_elements:
            source_port_id = f"element-proxy:{source.element_id}:source"
            proxy = element_proxy_ports[source.element_id].setdefault(source_port_id, {
                "name": "Ausgänge",
                "side": "Right",
                "role": "Host",
                "targetId": source.element_id,
                "targetType": "element",
                "count": 0,
            })
            proxy["count"] += 1
        sink_port_ids: list[str] = []
        collapsed_sink_counts: dict[str, int] = {}
        ordered_sinks = sorted(
            connection.endpoints[1:],
            key=lambda endpoint: (
                domain_names.get(element_domain.get(endpoint.element_id, ""), "").casefold(),
                getattr(elements_by_id.get(endpoint.element_id), "name", "").casefold(),
                endpoint.port_id,
            ),
        )
        for sink in ordered_sinks:
            sink_domain_id = element_domain[sink.element_id]
            if sink_domain_id == source_domain_id and source_domain_id in collapsed:
                continue
            if sink_domain_id in collapsed:
                collapsed_sink_counts[sink_domain_id] = collapsed_sink_counts.get(sink_domain_id, 0) + 1
                proxy_id = f"proxy:{connection.id}:{sink_domain_id}:sink"
                if proxy_id not in sink_port_ids:
                    sink_port_ids.append(proxy_id)
                proxy_ports[sink_domain_id][proxy_id] = {
                    "name": connection.name,
                    "side": "Left",
                    "role": "Participant",
                    "targetId": connection.id,
                    "targetType": "connection",
                }
            elif sink.element_id in collapsed_elements:
                proxy_id = f"element-proxy:{sink.element_id}:sink"
                if proxy_id not in sink_port_ids:
                    sink_port_ids.append(proxy_id)
                proxy = element_proxy_ports[sink.element_id].setdefault(proxy_id, {
                    "name": "Eingänge",
                    "side": "Left",
                    "role": "Participant",
                    "targetId": sink.element_id,
                    "targetType": "element",
                    "count": 0,
                })
                proxy["count"] += 1
            else:
                sink_port_ids.append(sink.port_id)
        for sink_domain_id, count in collapsed_sink_counts.items():
            proxy = proxy_ports[sink_domain_id][f"proxy:{connection.id}:{sink_domain_id}:sink"]
            if count > 1:
                proxy["name"] = f"{connection.name} · {count}"
        if not (source_domain_id in collapsed and all(element_domain[sink.element_id] == source_domain_id for sink in connection.endpoints[1:])):
            remapped_connections.append((connection, source_port_id, sink_port_ids))

    graph_children: list[dict[str, Any]] = []
    domains: dict[str, dict[str, Any]] = {}
    elements: dict[str, dict[str, Any]] = {}
    ports: dict[str, dict[str, Any]] = {}
    allowed_signal_ids = {
        signal.id for signal in package.signals
        if signal_types is None or signal.signal_type.value in signal_types
    }
    focus_port_ids = {
        endpoint.port_id for connection in included_connections for endpoint in connection.endpoints
    } if view_mode == "selection" else None
    if focus_port_ids is not None and selected_id and package.find_port(selected_id):
        focus_port_ids.add(selected_id)

    for domain in package.domains:
        if domain.id not in visible_domain_ids:
            continue
        is_collapsed = domain.id in collapsed
        domain_children: list[dict[str, Any]] = []
        domain_ports: list[dict[str, Any]] = []
        if is_collapsed:
            proxy_list = list(proxy_ports[domain.id].items())
            left = [(port_id, data) for port_id, data in proxy_list if data["side"] == "Left"]
            right = [(port_id, data) for port_id, data in proxy_list if data["side"] == "Right"]
            width = 350
            height = max(160, 112 + max(len(left), len(right), 1) * 38)
            for side, entries in (("Left", left), ("Right", right)):
                for index, (port_id, data) in enumerate(sorted(entries, key=lambda item: item[1]["name"].casefold())):
                    ports[port_id] = {
                        **data,
                        "portType": "Domain-Grenze",
                        "domainId": domain.id,
                        "color": domain.color,
                    }
                    domain_ports.append({
                        "id": port_id,
                        "width": 12,
                        "height": 12,
                        "x": -6 if side == "Left" else width - 6,
                        "y": 104 + index * 38,
                        "layoutOptions": {"elk.port.side": "WEST" if side == "Left" else "EAST"},
                    })
            domain_node: dict[str, Any] = {
                "id": domain.id,
                "width": width,
                "height": height,
                "ports": domain_ports,
                "layoutOptions": {"elk.portConstraints": "FIXED_POS"},
            }
        else:
            for element in domain.elements:
                if visible_element_ids is not None and element.id not in visible_element_ids:
                    continue
                is_element_collapsed = element.id in collapsed_elements
                if is_element_collapsed:
                    element_width = 300
                    element_height = 126
                    elk_ports: list[dict[str, Any]] = []
                    for port_id, data in sorted(
                        element_proxy_ports[element.id].items(),
                        key=lambda item: (item[1]["side"], item[0]),
                    ):
                        side = data["side"]
                        count = int(data.get("count", 0))
                        singular = "Eingang" if side == "Left" else "Ausgang"
                        plural = "Eingänge" if side == "Left" else "Ausgänge"
                        data["name"] = f"{count} {singular if count == 1 else plural}"
                        ports[port_id] = {
                            **data,
                            "portType": "Portgruppe",
                            "elementId": element.id,
                            "domainId": domain.id,
                            "color": domain.color,
                        }
                        elk_ports.append({
                            "id": port_id,
                            "width": 12,
                            "height": 12,
                            "x": -6 if side == "Left" else element_width - 6,
                            "y": 82,
                            "layoutOptions": {"elk.port.side": "WEST" if side == "Left" else "EAST"},
                        })
                    elements[element.id] = {
                        "name": element.name,
                        "kind": element.kind,
                        "domainId": domain.id,
                        "color": domain.color,
                        "collapsed": True,
                        "portCount": sum(block_port_visible(package, p) for p in element.ports),
                        "inputCount": sum(1 for port in element.ports if block_port_visible(package, port) and _resolved_side(package, port) == "Left"),
                        "outputCount": sum(1 for port in element.ports if block_port_visible(package, port) and _resolved_side(package, port) == "Right"),
                    }
                    domain_children.append({
                        "id": element.id,
                        "width": element_width,
                        "height": element_height,
                        "ports": elk_ports,
                        "layoutOptions": {"elk.portConstraints": "FIXED_POS"},
                    })
                    continue
                visible_ports = []
                for port in element.ports:
                    if not block_port_visible(package, port):
                        continue
                    generated_signal_id = str(port.properties.get("architectureSignalId") or "")
                    if generated_signal_id and generated_signal_id not in allowed_signal_ids:
                        continue
                    if focus_port_ids is not None and port.id not in focus_port_ids:
                        continue
                    visible_ports.append(port)
                left_ports = [port for port in visible_ports if _resolved_side(package, port) == "Left"]
                right_ports = [port for port in visible_ports if _resolved_side(package, port) == "Right"]
                port_rows = max(len(left_ports), len(right_ports))
                element_width = 300
                element_height = max(160, 118 + port_rows * 36)
                left_port_index = {port.id: index for index, port in enumerate(left_ports)}
                right_port_index = {port.id: index for index, port in enumerate(right_ports)}
                elk_ports: list[dict[str, Any]] = []
                for port in [*left_ports, *right_ports]:
                    side = _resolved_side(package, port)
                    side_index = left_port_index[port.id] if side == "Left" else right_port_index[port.id]
                    port_center_y = 94 + side_index * 36
                    ports[port.id] = {
                        "name": port.name,
                        "portType": port.port_type,
                        "role": port.role,
                        "side": side,
                        "elementId": element.id,
                        "domainId": domain.id,
                        "color": domain.color,
                    }
                    elk_ports.append({
                        "id": port.id,
                        "width": 12,
                        "height": 12,
                        "x": -6 if side == "Left" else element_width - 6,
                        "y": port_center_y - 6,
                        "layoutOptions": {"elk.port.side": "WEST" if side == "Left" else "EAST"},
                    })
                elements[element.id] = {
                    "name": element.name,
                    "kind": element.kind,
                    "domainId": domain.id,
                    "color": domain.color,
                    "collapsed": False,
                    "portCount": sum(block_port_visible(package, p) for p in element.ports),
                    "inputCount": len(left_ports),
                    "outputCount": len(right_ports),
                }
                domain_children.append({
                    "id": element.id,
                    "width": element_width,
                    "height": element_height,
                    "ports": elk_ports,
                    "layoutOptions": {"elk.portConstraints": "FIXED_POS", "elk.spacing.portPort": "22"},
                })
            domain_node = {
                "id": domain.id,
                "children": domain_children,
                "layoutOptions": {
                    "elk.algorithm": "layered",
                    "elk.direction": "RIGHT",
                    "elk.edgeRouting": "ORTHOGONAL",
                    "elk.hierarchyHandling": "INHERIT",
                    "elk.padding": "[top=78,left=86,bottom=42,right=86]",
                    "elk.spacing.nodeNode": "64",
                    "elk.layered.spacing.nodeNodeBetweenLayers": "110",
                    "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
                    "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
                    "elk.layered.mergeEdges": "true",
                    "elk.layered.feedbackEdges": "true",
                },
            }
            if not domain_children:
                domain_node.update({"width": 330, "height": 132})
        domains[domain.id] = {
            "name": domain.name,
            "color": domain.color,
            "collapsed": is_collapsed,
            "elementCount": len(domain.elements),
            "incomingCount": sum(1 for connection in included_connections for endpoint in connection.endpoints[1:] if element_domain[endpoint.element_id] == domain.id),
            "outgoingCount": sum(1 for connection in included_connections if element_domain[connection.endpoints[0].element_id] == domain.id),
            "internalCount": sum(1 for connection in included_connections if all(element_domain[endpoint.element_id] == domain.id for endpoint in connection.endpoints)),
        }
        graph_children.append(domain_node)

    graph_edges: list[dict[str, Any]] = []
    connections: dict[str, dict[str, Any]] = {}
    signals_by_id = {signal.id: signal for signal in package.signals}
    for connection, source_port_id, sink_port_ids in remapped_connections:
        edge_ids: list[str] = []
        for index, sink_port_id in enumerate(sink_port_ids):
            edge_id = f"edge-{connection.id}-{index}"
            edge_ids.append(edge_id)
            graph_edges.append({"id": edge_id, "sources": [source_port_id], "targets": [sink_port_id]})
        managed_signal = signals_by_id.get(connection.signal_id or "")
        signal_type = managed_signal.signal_type.value if managed_signal else "Interface"
        connections[connection.id] = {
            "name": connection.name,
            "connectionType": connection.connection_type.value,
            "signalId": connection.signal_id,
            "signalType": signal_type,
            "color": SIGNAL_COLORS.get(signal_type, "#48637F"),
            "sourceElementId": connection.endpoints[0].element_id,
            "sinkElementIds": [endpoint.element_id for endpoint in connection.endpoints[1:]],
            "sinkCount": len(connection.endpoints) - 1,
            "edgeIds": edge_ids,
            "sourcePortId": source_port_id,
            "sinkPortIds": sink_port_ids,
            "selectable": True,
        }

    return {
        "graph": {
            "id": "xped-architecture-root",
            "layoutOptions": _root_layout_options(),
            "children": graph_children,
            "edges": graph_edges,
        },
        "meta": {
            "domains": domains,
            "elements": elements,
            "ports": ports,
            "connections": connections,
            "selectedId": selected_id,
            "viewMode": view_mode,
        },
    }


def architecture_svg(
    package: ArchitecturePackage,
    selected_id: str | None = None,
    view_mode: str = "architecture",
    focus_domain_id: str | None = None,
    collapsed_domain_ids: set[str] | None = None,
    collapsed_element_ids: set[str] | None = None,
    signal_types: set[str] | None = None,
    assignment: dict[str, Any] | None = None,
) -> str:
    """Return the NiceGUI host for the client-side ELK SVG canvas."""
    if not package.domains:
        return """
        <div class="xped-interactive-canvas empty-canvas">
          <div class="empty-icon">◇</div><strong>Schritt 1: Domain anlegen</strong>
          <span>Danach kannst du Architecture Elements und Interfaces ergänzen.</span>
        </div>"""

    graph_data = architecture_graph(
        package,
        selected_id,
        view_mode=view_mode,
        focus_domain_id=focus_domain_id,
        collapsed_domain_ids=collapsed_domain_ids,
        collapsed_element_ids=collapsed_element_ids,
        signal_types=signal_types,
    )
    graph_data["meta"]["assignment"] = assignment or {"active": False}
    structural_payload = json.dumps(
        graph_data["graph"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    graph_data["layoutKey"] = hashlib.sha256(structural_payload).hexdigest()
    payload = json.dumps(graph_data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(payload).decode("ascii")
    styles = """<style>
      .xped-interactive-canvas{height:100%;min-height:680px;display:flex;flex-direction:column;background:#edf2f7;position:relative}
      .canvas-tools{position:relative;flex:0 0 auto;display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:8px;background:#fffffff2;border-bottom:1px solid #d4deea}
      .canvas-tools > span{min-width:0;overflow-wrap:anywhere}
      .canvas-tools button{border:1px solid #c8d5e3;background:white;border-radius:7px;padding:5px 10px;font-weight:700;color:#304861;cursor:pointer}
      .canvas-tools button:hover{background:#e8f1ff}
      .canvas-viewport{flex:1;overflow:auto;min-height:630px;padding:18px}
      .canvas-stage{width:max-content;min-width:100%;min-height:100%}
      .elk-canvas{min-width:100%;min-height:630px;display:flex;align-items:center;justify-content:center}
      .elk-loading,.elk-error{padding:28px;color:#64748b;font-size:14px}
      .canvas-object{cursor:pointer}
      .canvas-toggle{cursor:pointer}
      .canvas-toggle rect{transition:.14s ease}
      .canvas-toggle:hover rect{fill:#e8f1ff;stroke:#1769c2;stroke-width:1.8}
      .domain-object .domain-surface,.element-object .element-surface,.port-object .port-surface,.connection-object .connection-line{transition:.14s ease}
      .domain-object:hover .domain-surface,.element-object:hover .element-surface{stroke:#1769c2;stroke-width:2.5}
      .port-object:hover .port-surface{fill:#dcecff;stroke:#1769c2;stroke-width:2}
      .connection-object{opacity:.78;transition:opacity .14s ease}
      .connection-object:hover{opacity:1}
      .connection-object:hover .connection-line{stroke:#087d66;stroke-width:5}
      .connection-line-back{opacity:.2}
      .connection-junction{stroke:#fff;stroke-width:1.5}
      .dimmed-connection{opacity:.13!important}
      .connection-focus .selected-object.connection-object{opacity:1}
      .selected-object .domain-surface,.selected-object .element-surface,.selected-object .port-surface,.selected-object .port-circle{stroke:#ef8d00!important;stroke-width:3.5!important}
      .selected-object .connection-line{stroke:#ef8d00!important;stroke-width:6!important}
      .selected-object .connection-line-back{stroke:#ef8d00!important;opacity:.18}
      .assignment-mode .element-object .element-surface{stroke-dasharray:5 4;stroke-width:2}
      .assignment-mode .element-object:hover .element-surface{stroke:#d97706;stroke-width:4;stroke-dasharray:none}
      .assignment-host .element-surface{stroke:#7c3aed!important;stroke-width:4!important;stroke-dasharray:none!important}
      .assignment-participant .element-surface{stroke:#0f9f77!important;stroke-width:4!important;stroke-dasharray:none!important}
      .assignment-badge{font-size:10px;font-weight:800;letter-spacing:.05em}
      .domain-summary{font-size:12px;fill:#60758c;font-weight:650}
      .aggregate-connection .connection-line{stroke:#738ba3;stroke-width:5}
      .semantic-medium .element-kind{display:none}
      .semantic-overview .element-kind,.semantic-overview .port-label,.semantic-overview .port-surface{display:none}
      .semantic-overview .element-name{font-size:18px;font-weight:800}
      .canvas-minimap{position:absolute;right:22px;bottom:20px;width:190px;height:124px;padding:7px;background:#fffffff0;border:1px solid #b9c8d7;border-radius:10px;box-shadow:0 4px 16px #24364d22;z-index:3;cursor:pointer}
      .canvas-minimap svg{width:100%;height:100%;display:block}
      .canvas-minimap-title{position:absolute;left:10px;top:5px;font-size:9px;font-weight:800;color:#62758a;letter-spacing:.08em}
    </style>"""
    view_labels = {"system": "Systemübersicht", "architecture": "Architektur", "domain": "Domain-Fokus", "selection": "Auswahlfokus"}
    assignment_data = assignment or {}
    assignment_active = bool(assignment_data.get("active"))
    assignment_phase = assignment_data.get("phase")
    assignment_label = "Host anklicken" if assignment_phase == "host" else "Teilnehmer anklicken"
    assignment_controls = (
        f'<span class="assignment-help" style="align-self:center;margin-left:8px;padding:4px 9px;font-size:12px;font-weight:750">'
        f'Canvas-Zuweisung · {escape(assignment_label)}</span>'
        '<button onclick="xpedCanvasAssignmentDone(this)" title="Canvas-Zuweisung beenden">Fertig</button>'
        if assignment_active else ""
    )
    selected_connection = graph_data["meta"]["connections"].get(selected_id or "")
    connection_focus = (
        f'<span style="align-self:center;color:#0f766e;font-size:12px;font-weight:750">'
        f'· {escape(selected_connection["name"])} · {selected_connection.get("sinkCount", len(selected_connection.get("sinkPortIds", [])))} Teilnehmer</span>'
        if selected_connection and view_mode == "selection" else ""
    )
    controls = f"""<div class="canvas-tools">
      <button onclick="xpedCanvasZoom(this,1.2)" title="Vergrößern">＋</button>
      <button onclick="xpedCanvasZoom(this,0.833333)" title="Verkleinern">−</button>
      <button onclick="xpedCanvasFit(this)" title="Alles einpassen">Einpassen</button>
      <button onclick="xpedCanvasRelayout(this)" title="Layout vollständig neu berechnen">Neu anordnen</button>
      <span style="align-self:center;margin-left:8px;color:#284d75;font-size:12px;font-weight:750">{escape(view_labels.get(view_mode, view_mode))}</span>
      {connection_focus}
      <span style="align-self:center;color:#6a7c90;font-size:12px">· semantischer Zoom · Strg + Mausrad · Scrollbars</span>
      {assignment_controls}
    </div>"""
    return (
        styles
        + '<div class="xped-interactive-canvas">'
        + controls
        + '<div class="canvas-viewport" onwheel="xpedCanvasWheel(event,this)">'
        + '<div class="canvas-stage" data-scale="1">'
        + f'<div class="elk-canvas" data-elk-payload="{escape(encoded)}"><div class="elk-loading">Architektur wird automatisch angeordnet …</div></div>'
        + '</div></div><div class="canvas-minimap" onclick="xpedCanvasFit(this)"><span class="canvas-minimap-title">ÜBERSICHT</span></div></div>'
    )
