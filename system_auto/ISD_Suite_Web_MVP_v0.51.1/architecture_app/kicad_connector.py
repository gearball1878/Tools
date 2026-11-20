"""SPOT architecture to a component-free, hierarchical KiCad schematic.

Only explicit annotation operations call this module.  IDs and the connector
manifest make a later reverse comparison independent of display names.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
import json
import re
import uuid
import unicodedata
from zipfile import ZipFile, ZIP_DEFLATED

from . import __version__
from .ecad_connector import AnnotationChange, AnnotationPreview, register
from .identity import sha_identity
from .kicad_rules import class_for, project_settings
from .property_schema import exchange_values
from .ecad_pin_mapping import hierarchical_mapping
from .models import ArchitecturePackage, ConnectionType
from .hardware_topology import is_global_ground, domain_role


def _uid(project_id: str, *parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "isd-suite/kicad/" + "/".join((project_id, *parts))))


def _q(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _num(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _at(x: float, y: float, angle: int = 0) -> str:
    return f"(at {_num(x)} {_num(y)} {angle})"


def _effects(size: float = 1.0, justify: str = "", hidden: bool = False) -> str:
    return (f'(effects (font (size {_num(size)} {_num(size)}))'
            f'{f" (justify {justify})" if justify else ""}'
            f'{" (hide yes)" if hidden else ""})')


def _text_width(value: str, size: float = 1.0) -> float:
    """Conservative KiCad vector-font envelope, in millimetres."""
    return max(size, len(value) * size * 0.78)


def _safe_filename(value: str) -> str:
    value = str(value).translate(str.maketrans({"Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
                                               "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    token = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_-")
    return (token or "design")[:64]


def _project_stem(value: str) -> str:
    # The model's revision belongs to its exported artifact, not the project file.
    bare = re.sub(r"\s+v\d+(?:\.\d+)*(?:\s*\(\d+\))?$", "", value, flags=re.I)
    return _safe_filename(bare)


def _sheet_files(package: ArchitecturePackage) -> tuple[dict[str, str], dict[str, str]]:
    domains, elements = {}, {}
    for di, domain in enumerate(package.domains, 1):
        match = re.match(r"DOM_(\d+)_", domain.technical_name)
        domain_prefix = f"D{int(match[1]) if match else di:02d}"
        domains[domain.id] = f"{domain_prefix}_{_safe_filename(domain.name)}.kicad_sch"
        for ei, element in enumerate(domain.elements, 1):
            match = re.match(r"AE_(\d+)_", element.technical_name)
            element_prefix = f"AE{int(match[1]) if match else ei:02d}"
            elements[element.id] = (f"{domain_prefix}_{element_prefix}_"
                                    f"{_safe_filename(element.name)}.kicad_sch")
    names = [*domains.values(), *elements.values()]
    if len(names) != len(set(name.casefold() for name in names)):
        raise ValueError("KiCad-Dateinamen sind nicht eindeutig; technische Nummerierung prüfen")
    return domains, elements


def _group(signal) -> str:
    return "{" + signal.name + "}" if signal.connection_type == ConnectionType.BUS else signal.name


def _color(signal) -> tuple[int, int, int]:
    if signal.connection_type == ConnectionType.BUS:
        return (238, 180, 24)
    category = signal.signal_type.value.casefold()
    if category == "power":
        return (212, 49, 49)
    if category in {"analog", "differential"}:
        return (37, 139, 76)
    if category in {"clock"}:
        return (123, 62, 180)
    if category in {"rf"}:
        return (222, 109, 32)
    return (50, 92, 186)


def _stroke(signal) -> str:
    r, g, b = _color(signal)
    width = 0.36 if signal.connection_type == ConnectionType.BUS else 0.18
    return f"(stroke (width {_num(width)}) (type default) (color {r} {g} {b} 1))"


def _wire(pid: str, key: str, x1: float, y1: float, x2: float, y2: float, signal) -> str:
    kind = 'bus' if signal.connection_type == ConnectionType.BUS else 'wire'
    return (f'({kind} (pts (xy {_num(x1)} {_num(y1)}) (xy {_num(x2)} {_num(y2)})) '
            f'{_stroke(signal)} (uuid {_q(_uid(pid, key, "wire"))}))')


def _label(pid: str, key: str, name: str, x: float, y: float, angle: int = 0,
           hierarchical: bool = False, shape: str = "passive",
           fields: dict[str, str] | None = None, hidden: bool = False,
           justify: str = "") -> str:
    kind = "hierarchical_label" if hierarchical else "label"
    extra = f"(shape {shape}) " if hierarchical else ""
    props = " ".join(_property(field, value, x, y + index * 1.27, True)
                     for index, (field, value) in enumerate((fields or {}).items()))
    return (f'({kind} {_q(name)} {extra}{_at(x, y, angle)} '
            f'{_effects(justify=justify, hidden=hidden)} '
            f'(uuid {_q(_uid(pid, key, kind))}) {props})')


def _text(pid: str, key: str, name: str, x: float, y: float, size: float = 1.2,
          justify: str = "") -> str:
    return (f'(text {_q(name)} {_at(x, y)} {_effects(size, justify)} '
            f'(uuid {_q(_uid(pid, key, "text"))}))')


def _legend_swatch(pid: str, key: str, x: float, y: float,
                   color: tuple[int, int, int]) -> str:
    r, g, b = color
    return (f'(polyline (pts (xy {_num(x)} {_num(y)}) '
            f'(xy {_num(x + 5.08)} {_num(y)})) '
            f'(stroke (width 2.0) (type solid) (color {r} {g} {b} 0.85)) '
            f'(uuid {_q(_uid(pid, "legend", key))}))')


def _inner_frame(pid: str, node_id: str, x: float, y: float, width: float,
                 height: float, color: str) -> str:
    # Keep the sheet-pin connection in the margin and its caption in the frame.
    inset_x, inset_y = 8.89, 5.08
    r, g, b = _rgb(color)
    corners = ((x + inset_x, y + inset_y), (x + width - inset_x, y + inset_y),
               (x + width - inset_x, y + height - inset_y),
               (x + inset_x, y + height - inset_y), (x + inset_x, y + inset_y))
    points = " ".join(f'(xy {_num(px)} {_num(py)})' for px, py in corners)
    return (f'(polyline (pts {points}) '
            f'(stroke (width 0.18) (type solid) (color {r} {g} {b} 0.7)) '
            f'(uuid {_q(_uid(pid, "inner-frame", node_id))}))')


def _header(pid: str, key: str, title: str, paper: str = "A1") -> list[str]:
    return [
        f'(kicad_sch (version 20260306) (generator "isd_suite") (generator_version "{__version__}")',
        f'(uuid {_q(_uid(pid, key, "screen"))})',
        f'(paper {_q(paper)})',
        f'(title_block (title {_q(title)}))',
        '(lib_symbols)',
    ]


def _property(name: str, value: str, x: float, y: float, hidden: bool = False) -> str:
    return (f'(property {_q(name)} {_q(value)} {_at(x, y)} '
            f'(effects (font (size 1 1)){" (hide yes)" if hidden else ""}))')


def _rgb(value: str) -> tuple[int, int, int]:
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value or ""):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    return (37, 99, 235)


def _technical_fields(package,obj):
    from .technical_comparison import comparison_rows
    rows=comparison_rows(package,obj)
    targets={(r.requirement_id,r.key):{'requirementId':r.requirement_id,'key':r.key,'value':r.required,'unit':r.unit,'conditions':r.conditions['Soll']} for r in rows if r.requirement_id}
    actuals={(r.actual_id,r.key,str(r.actual)):{'realizationId':r.actual_id,'key':r.key,'value':r.actual,'unit':r.unit,'conditions':r.conditions['Ist'],'revision':r.revision,'origin':r.origin,'sourceIds':r.source_ids} for r in rows if r.actual_id and r.actual is not None and not r.legacy}
    return {'ISD_TechnicalTargets':json.dumps(list(targets.values()),ensure_ascii=False,sort_keys=True),
            'ISD_TechnicalActuals':json.dumps(list(actuals.values()),ensure_ascii=False,sort_keys=True)}


def _meta_fields(signal, port, role: str, connection=None, endpoint=None, definitions=None, package=None) -> dict[str, str]:
    fields = {
        "ISD_SignalID": signal.id,
        "ISD_SignalSHA256": sha_identity(signal.id),
        "ISD_Role": role,
        "ISD_SignalType": signal.signal_type.value,
        "ISD_ConnectionType": signal.connection_type.value,
        "ISD_SourceAE": signal.source.element_id if signal.source else "",
        "ISD_SinkAEs": ",".join(v.element_id for v in signal.sinks),
        "ISD_Description": signal.description or "",
        "ISD_Attributes": json.dumps(signal.attributes, ensure_ascii=False, sort_keys=True),
        "ISD_Properties": json.dumps(signal.properties, ensure_ascii=False, sort_keys=True),
    }
    if package is not None:fields.update(_technical_fields(package,signal))
    if signal.connection_type == ConnectionType.BUS:
        fields["ISD_BusMembers"] = ",".join(member.name for member in signal.bus_contents)
    for source_key, field in (("designState", "ISD_DesignState"),
                              ("sourceDocumentId", "ISD_SourceDocumentID"),
                              ("sourceLocator", "ISD_SourceLocator"),
                              ("voltageFrequency", "ISD_VoltageFrequency")):
        value = signal.properties.get(source_key)
        if value is not None and value != "":
            fields[field] = str(value)
    fields["ISD_RealizationAttributes"] = json.dumps(exchange_values(signal,"realization_attributes","forward",definitions), ensure_ascii=False, sort_keys=True)
    fields['ISD_RequirementAttributes']=json.dumps(exchange_values(signal,'requirement_attributes','forward',definitions),ensure_ascii=False,sort_keys=True)
    if signal.connection_type == ConnectionType.BUS:
        fields['ISD_BusMemberRealizationAttributes']=json.dumps({m.name:exchange_values(m,'realization_attributes','forward',definitions) for m in signal.bus_contents},ensure_ascii=False,sort_keys=True)
    if port:
        fields["ISD_PortRealizationAttributes"] = json.dumps(exchange_values(port,"realization_attributes","forward",definitions), ensure_ascii=False, sort_keys=True)
    if connection:
        fields["ISD_ConnectionID"] = connection.id
        fields["ISD_ConnectionSHA256"] = sha_identity(connection.id)
        fields["ISD_ConnectionDescription"] = connection.description or ""
        fields["ISD_ConnectionAttributes"] = json.dumps(connection.attributes, ensure_ascii=False, sort_keys=True)
        fields["ISD_ConnectionProperties"] = json.dumps(connection.properties, ensure_ascii=False, sort_keys=True)
        if endpoint:
            fields["ISD_EndpointRole"] = endpoint.role.value if endpoint.role else role
            fields["ISD_EndpointAttributes"] = json.dumps(endpoint.attributes, ensure_ascii=False, sort_keys=True)
            fields["ISD_EndpointProperties"] = json.dumps(endpoint.properties, ensure_ascii=False, sort_keys=True)
    if port:
        fields.update({"ISD_PortID": port.id,
                       "ISD_PortSHA256": sha_identity(port.id),
                       "ISD_PortAlias": port.name,
                       "ISD_PortType": port.port_type,
                       "ISD_PortRole": port.role,
                       "ISD_PortDescription": port.description or "",
                       "ISD_PortAttributes": json.dumps(port.attributes, ensure_ascii=False, sort_keys=True),
                       "ISD_PortProperties": json.dumps({k:v for k,v in port.properties.items() if k not in {'kicadPinUuid','manualPortName'}}, ensure_ascii=False, sort_keys=True)})
    return fields


def _metadata(package: ArchitecturePackage) -> dict:
    def common(obj) -> dict:
        return {"name": obj.name, "sha256": sha_identity(obj.id),
                "description": obj.description,
                "attributes": obj.attributes, "properties": obj.properties,
                "requirement_attributes": getattr(obj, "requirement_attributes", {}),
                "realization_attributes": getattr(obj, "realization_attributes", {})}
    return {
        "project": {package.project.id: common(package.project)},
        "domains": {d.id: {**common(d), "color": d.color,
                           "technicalName": d.technical_name, "domainTypeId": d.domain_type_id}
                    for d in package.domains},
        "elements": {e.id: {**common(e), "domainId": d.id,
                            "color": d.color,
                            "technicalName": e.technical_name, "roleTypeId": e.role_type_id}
                     for d in package.domains for e in d.elements},
        "ports": {p.id: {**common(p), "elementId": e.id, "role": p.role,
                         "portType": p.port_type, "connectionType": p.connection_type.value}
                  for d in package.domains for e in d.elements for p in e.ports},
        "signals": {s.id: {**common(s), "signalType": s.signal_type.value,
                            "connectionType": s.connection_type.value,
                            "sourceId": s.source.element_id if s.source else None,
                            "sinkIds": [v.element_id for v in s.sinks],
                            "sourceEndpoint": s.source.model_dump() if s.source else None,
                            "sinkEndpoints": [v.model_dump() for v in s.sinks]}
                    for s in package.signals},
        "connections": {c.id: {**common(c), "signalId": c.signal_id,
                                "connectionType": c.connection_type.value,
                                "endpoints": [{"elementId": v.element_id, "portId": v.port_id,
                                               "role": v.role.value if v.role else None,
                                               "attributes": v.attributes, "properties": v.properties}
                                              for v in c.endpoints]}
                        for c in package.connections},
    }


def _lane_positions(pins: list[_Pin], start: float) -> list[tuple[_Pin, float]]:
    """Power, control/status, analog, then bus/interface on each block side."""
    ordered = _ordered(pins)
    result = []
    y = start
    previous = None
    for item in ordered:
        group = (_pin_group(item),
                 item.signal.catalog_family or item.signal.signal_type.value)
        if previous is not None and group != previous:
            y += 2.54
        result.append((item, y))
        y += 3.81
        previous = group
    return result


@dataclass
class _Pin:
    signal: object
    port: object | None
    role: str

    @property
    def name(self) -> str:
        return _group(self.signal)


def _ordered(pins: list[_Pin]) -> list[_Pin]:
    def natural(value: str) -> tuple:
        return tuple(int(s) if s.isdigit() else s.casefold() for s in re.split(r"(\d+)", value))
    return sorted(pins, key=lambda item: (
        _pin_group(item),
        str(item.signal.catalog_family or item.signal.signal_type.value),
        natural(item.signal.name),
    ))


def _pin_group(pin: _Pin) -> int:
    if pin.signal.connection_type == ConnectionType.BUS:
        return 3
    family = str(pin.signal.catalog_family or "").casefold()
    kind = pin.signal.signal_type.value.casefold()
    if kind == "power" or family == "power":
        return 0
    if kind in {"analog", "differential", "rf"} or family == "analog":
        return 2
    return 1


def _layout_order(ids: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Stable source-to-sink ordering, weighted by the number of shared links."""
    outputs = defaultdict(int)
    inputs = defaultdict(int)
    neighbors = defaultdict(set)
    for source, sink in edges:
        if source == sink:
            continue
        outputs[source] += 1
        inputs[sink] += 1
        neighbors[source].add(sink)
        neighbors[sink].add(source)
    return sorted(ids, key=lambda key: (
        -(outputs[key] - inputs[key]), -len(neighbors[key]), ids.index(key)))


def _snapshot(package: ArchitecturePackage) -> dict:
    return {
        "domains": {d.id: d.name for d in package.domains},
        "elements": {e.id: e.name for d in package.domains for e in d.elements},
        "signals": {s.id: {"name": s.name,
                            "source": s.source.element_id if s.source else None,
                            "sinks": sorted(v.element_id for v in s.sinks),
                            "members": [v.name for v in s.bus_contents],
                            "kind": s.connection_type.value}
                    for s in package.signals},
    }


class KiCadConnector:
    name = "kicad"

    def forward_preview(self, package: ArchitecturePackage) -> AnnotationPreview:
        preview = AnnotationPreview("forward")
        baseline = package.properties.get("ecadConnectors", {}).get("kicad", {}).get("snapshot")
        old_metadata = package.properties.get("ecadConnectors", {}).get("kicad", {}).get("metadataSnapshot")
        now = _snapshot(package)
        if baseline is None:
            preview.changes.append(AnnotationChange(package.project.id, "project", None,
                                                    f'{len(package.domains)} Domains, {len(now["elements"])} AEs, {len(now["signals"])} Links'))
        else:
            for section, items in now.items():
                for item_id in sorted(set(items) | set(baseline.get(section, {}))):
                    old, new = baseline.get(section, {}).get(item_id), items.get(item_id)
                    if old != new:
                        preview.changes.append(AnnotationChange(item_id, section, old, new))
        metadata = _metadata(package)
        if old_metadata is not None:
            for section, items in metadata.items():
                for item_id, value in items.items():
                    old = old_metadata.get(section, {}).get(item_id)
                    if old != value:
                        preview.changes.append(AnnotationChange(item_id, f"metadata.{section}", old, value))
        dangling = [s.name for s in package.signals if not s.source or not s.sinks]
        if dangling:
            preview.warnings.append(f"{len(dangling)} unvollständige Links bleiben ohne Verdrahtung.")
        else:
            try:
                _, layout = self.generate(package)
                pending=sum(m["status"].startswith("Offen") for m in layout.get("pinMappings",{}).values())
                if pending:preview.warnings.append(f"{pending} Signalrichtungen offen: passive Hierarchieanschlüsse fachlich prüfen.")
                preview.warnings.extend(layout["layoutWarnings"][:20])
                if len(layout["layoutWarnings"]) > 20:
                    preview.warnings.append(f"{len(layout['layoutWarnings']) - 20} weitere Layoutkonflikte")
            except ValueError as error:
                preview.warnings.append(f"KiCad-Layout: {error}")
        return preview

    def forward_archive(self, package: ArchitecturePackage) -> bytes:
        files, manifest = self.generate(package)
        target = BytesIO()
        with ZipFile(target, "w", ZIP_DEFLATED) as archive:
            for path, content in sorted(files.items()):
                archive.writestr(path, content)
            archive.writestr("isd_kicad_bindings.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr("PRUEFUNG.txt", (
                "ISD Suite / KiCad-Verbindungsschaltplan\n"
                f"KiCad-Projekt: {manifest['root']}\n"
                "Alle .kicad_sch-Dateien und isd_kicad_bindings.json im selben Ordner behalten.\n"
                "Prüfung auf einem Rechner mit KiCad 10:\n"
                f'  kicad-cli sch erc "{manifest["root"]}" -o erc.txt\n'
                f'  kicad-cli sch export pdf "{manifest["root"]}" -o Schaltplan.pdf\n'
                "PDF in KiCad direkt exportieren; A4-Druck skaliert die A1/A2/A3-Seiten herunter.\n"
                f"Layoutkonflikte nach Text-Geometrieprüfung: {len(manifest['layoutWarnings'])}\n"
                "Netzklassen und explizite Maße stehen in der .kicad_pro; ISD-Attribute an Labels.\n"
                "Label anwählen und Eigenschaften öffnen: Beschreibung, Rolle und Architekturkennungen.\n"
                "Die Segmenteigenschaften zeigen nur Geometrie; Buslinien sind doppelt so breit.\n"
                "Seitenverbinder tragen den Netznamen; Blockpin-Beschriftungen stehen im Innenrahmen.\n"
                "Busmitglieder erhalten beim späteren Auffächern passende Klassenmuster.\n"
                "Die Anfangsversion enthält keine physikalischen Bauteile.\n"
            ))
        return target.getvalue()

    def generate(self, package: ArchitecturePackage, topology_policy: str = "global-ground-host-priority-v1", legend_policy: str = "split-bottom-right-v1") -> tuple[dict[str, str], dict]:
        """Generate a deterministic schematic hierarchy from one validated SPOT object."""
        package_id = package.project.id
        global_ground = topology_policy != "legacy"
        signals = [s for s in package.signals if s.source and s.sinks and not (global_ground and is_global_ground(s))]
        grounds = [s for s in package.signals if global_ground and is_global_ground(s)]
        by_ae = {e.id: (d, e) for d in package.domains for e in d.elements}
        port_by_signal: dict[tuple[str, str], object] = {}
        connection_by_signal = {c.signal_id: c for c in package.connections if c.signal_id}
        for d in package.domains:
            for e in d.elements:
                for port in e.ports:
                    sid = port.interface_link_id or port.properties.get("architectureSignalId")
                    if sid:
                        port_by_signal[(e.id, sid)] = port
        for s in signals:
            ids = [s.source.element_id, *(v.element_id for v in s.sinks)]
            if any(ae not in by_ae for ae in ids):
                raise ValueError(f"Link {s.name} enthält ein unbekanntes AE")
            if s.connection_type == ConnectionType.BUS and not s.bus_contents:
                raise ValueError(f"Bus {s.name} hat keine Mitgliedssignale")
            if any((ae, s.id) not in port_by_signal for ae in ids):
                raise ValueError(f"Link {s.name} hat keinen zugeordneten AE-Port")
        if len(connection_by_signal) != sum(bool(c.signal_id) for c in package.connections):
            raise ValueError("Mehrere Verbindungsobjekte referenzieren denselben Architektur-Link")

        stem = _project_stem(package.project.name)
        root = stem + ".kicad_sch"
        root_uuid = _uid(package_id, "root", "screen")
        files: dict[str, str] = {
            stem + ".kicad_pro": project_settings([*signals, *grounds], stem + ".kicad_pro", package.net_classes)
        }
        manifest: dict = {"format": "isd-kicad/v1", "projectId": package_id,
                          "root": root, "snapshot": _snapshot(package),
                          "metadata": _metadata(package),
                          "referenceRegistry": deepcopy(package.properties.get("ecadConnectors", {})
                                                        .get("kicad", {}).get("references", {})),
                          "bindings": [], "labelBindings": [], "segments": [], "files": []}
        manifest["blockTopologyPolicy"] = topology_policy
        manifest["legendPolicy"] = legend_policy
        manifest["globalSignalIds"] = [s.id for s in grounds]
        manifest["pinMappings"]={s.id:{"hostShape":hierarchical_mapping(package,s,"Host")[0],"participantShape":hierarchical_mapping(package,s,"Participant")[0],"status":hierarchical_mapping(package,s,"Host")[1]} for s in signals}
        domain_files, ae_files = _sheet_files(package)
        root_pins: dict[str, list[_Pin]] = defaultdict(list)
        ae_pins: dict[str, list[_Pin]] = defaultdict(list)
        for s in signals:
            members = [(s.source.element_id, "Host"), *((v.element_id, "Participant") for v in s.sinks)]
            involved_domains = {by_ae[ae][0].id for ae, _ in members}
            for ae, role in members:
                ae_pins[ae].append(_Pin(s, port_by_signal[(ae, s.id)], role))
            if len(involved_domains) > 1:
                for domain_id in sorted(involved_domains):
                    roles = {role for ae, role in members if by_ae[ae][0].id == domain_id}
                    role = domain_role(package, domain_id, s) if topology_policy != "legacy" else ("Mixed" if len(roles) > 1 else next(iter(roles)))
                    root_pins[domain_id].append(_Pin(s, None, role))

        # A domain has one sheet pin per cross-domain link.  On its own page,
        # each AE endpoint may carry the matching hierarchical connector.
        boundary_role: dict[tuple[str, str], str] = {}
        for domain_id, pins in root_pins.items():
            for boundary in pins:
                boundary_role[(domain_id, boundary.signal.id)] = boundary.role

        # All bus aliases have their original SPOT member names, with no KiCad prefix.
        aliases = [f'(bus_alias {_q(s.name)} (members {" ".join(_q(m.name) for m in s.bus_contents)}))'
                   for s in sorted(signals, key=lambda v: v.name) if s.connection_type == ConnectionType.BUS]
        project_name = stem
        def sheet_node(parent_file: str, parent_path: str, node, filename: str,
                       pins: list[_Pin], x: float, y: float, page: int,
                       kind: str, color: str, domain_id: str | None = None) -> tuple[str, list[str]]:
            node_id, display_name = node.id, node.name
            node_uuid = _uid(package_id, "sheet", node_id)
            path = parent_path + "/" + node_uuid
            left = _lane_positions([v for v in pins if v.role != "Host"], 22.86)
            right = _lane_positions([v for v in pins if v.role == "Host"], 22.86)
            height = max(43.18, max((values[-1][1] + 10.16 for values in (left, right) if values), default=43.18))
            left_width = max((_text_width(v.name) for v, _ in left), default=0)
            right_width = max((_text_width(v.name) for v, _ in right), default=0)
            width = max(127.0, 45.72 + left_width + right_width,
                        27.94 + _text_width(display_name, 2.8))
            r, g, b = _rgb(color)
            # KiCad's sheet placement has no rotation field: (at X Y).
            parts = [f'(sheet (at {_num(x)} {_num(y)}) (size {_num(width)} {_num(height)})',
                     f'(stroke (width 0.254) (type solid) (color {r} {g} {b} 0.85))',
                     f'(fill (color {r} {g} {b} {"0.13" if kind == "ae" else "0.18"}))',
                     f'(uuid {_q(node_uuid)})',
                     _property("Sheetname", display_name, x, y - 2.54, True),
                     _property("Sheetfile", filename, x, y + height + 2.54, True),
                     _property("ISD_ID", node_id, x, y + height + 5.08, True),
                     _property("ISD_SHA256", sha_identity(node_id), x, y + height + 7.62, True),
                     _property("ISD_KIND", kind, x, y + height + 10.16, True),
                     _property("ISD_COLOR", color, x, y + height + 12.7, True),
                     _property("ISD_DESCRIPTION", node.description, x, y + height + 15.24, True),
                     _property("ISD_TECHNICAL_NAME", node.technical_name, x, y + height + 17.78, True),
                     _property("ISD_TYPE", node.domain_type_id if kind == "domain" else node.role_type_id,
                               x, y + height + 20.32, True)]
            parts.append(_property("ISD_REALIZATION_ATTRIBUTES",
                                   json.dumps(exchange_values(node,"realization_attributes","forward",package.property_definitions), ensure_ascii=False, sort_keys=True),
                                   x, y + height + 27.94, True))
            parts.append(_property('ISD_REQUIREMENT_ATTRIBUTES',json.dumps(exchange_values(node,'requirement_attributes','forward',package.property_definitions),ensure_ascii=False,sort_keys=True),x,y+height+29.21,True))
            for key,value in _technical_fields(package,node).items():parts.append(_property(key,value,x,y+height+30.48,True))
            if node.attributes:
                parts.append(_property("ISD_ATTRIBUTES",
                                       json.dumps(node.attributes, ensure_ascii=False, sort_keys=True),
                                       x, y + height + 25.4, True))
            if domain_id:
                parts.append(_property("ISD_PARENT_ID", domain_id, x, y + height + 22.86, True))
            connections: list[str] = [
                _inner_frame(package_id, node_id, x, y, width, height, color),
                _text(package_id, f'{node_id}:heading', display_name, x + width / 2, y + 11.43, 2.8),
            ]
            for side, values in (("left", left), ("right", right)):
                for item, offset in values:
                    py = y + offset
                    px = x if side == "left" else x + width
                    angle = 180 if side == "left" else 0
                    pin_key = f'{node_id}:{item.signal.id}:{side}'
                    pin_uuid = _uid(package_id, "pin", pin_key)
                    # KiCad has no independent sheet-pin name offset. Keep its
                    # electrical pin/shape and hide only the native caption;
                    # draw that caption once inside the inner frame instead.
                    parts.append(f'(pin {_q(item.name)} {hierarchical_mapping(package,item.signal,item.role)[0]} {_at(px, py, angle)} '
                                 f'{_effects(1.0, "left" if side == "left" else "right", True)} '
                                 f'(uuid {_q(pin_uuid)}))')
                    caption_x = x + 11.43 if side == "left" else x + width - 11.43
                    connections.append(_text(package_id, pin_key + ":caption", item.name,
                                             caption_x, py, 1.0,
                                             "left" if side == "left" else "right"))
                    wire_length = 20.32
                    outer_x = px - wire_length if side == "left" else px + wire_length
                    connections.append(_wire(package_id, pin_key, px, py, outer_x, py, item.signal))
                    connection = connection_by_signal.get(item.signal.id)
                    endpoint = next((v for v in connection.endpoints
                                     if item.port and v.port_id == item.port.id), None) if connection else None
                    label_fields = _meta_fields(item.signal, item.port, item.role, connection, endpoint,package.property_definitions,package)
                    label_fields["ISD_PinMappingStatus"]=hierarchical_mapping(package,item.signal,item.role)[1]
                    boundary = (kind == "ae" and domain_id is not None
                                and (domain_id, item.signal.id) in boundary_role)
                    label_kind = "hierarchical_label" if boundary else "label"
                    connections.append(_label(
                        package_id, pin_key, item.name, outer_x, py,
                        180 if side == "left" else 0, boundary,
                        hierarchical_mapping(package,item.signal,boundary_role[(domain_id, item.signal.id)] if boundary else item.role)[0],
                        label_fields if item.signal.connection_type==ConnectionType.BUS and any(m.realization_attributes.get("netClass") or m.realization_attributes.get("netClasses") for m in item.signal.bus_contents) else {**label_fields, "Netclass": class_for(item.signal)},
                        hidden=False,
                        justify="right" if side == "left" else "left"))
                    if boundary:
                        manifest["labelBindings"].append({
                            "file": parent_file,
                            "uuid": _uid(package_id, pin_key, label_kind),
                            "signalId": item.signal.id,
                            "name": item.name,
                            "fields": label_fields,
                            "netClass": class_for(item.signal),
                        })
                    manifest["segments"].append({
                        "uuid": _uid(package_id, pin_key, "wire"), "file": parent_file,
                        "signalId": item.signal.id,
                        "connectionId": connection.id if connection else None,
                        "portId": item.port.id if item.port else None,
                        "role": item.role, "kind": "bus" if item.signal.connection_type == ConnectionType.BUS else "wire",
                        "netClass": class_for(item.signal),
                        "from": [px, py], "to": [outer_x, py],
                        "labelUuid": _uid(package_id, pin_key, label_kind),
                        "labelKind": label_kind,
                    })
                    manifest["bindings"].append({"spotId": item.port.id if item.port else item.signal.id,
                        "signalId": item.signal.id, "role": "aePort" if item.port else "domainBoundary",
                        "alias": item.port.name if item.port else item.signal.name,
                        "sheetPath": path, "parentFile": parent_file, "uuid": pin_uuid,
                        "netLabel": item.name, "endpointRole": item.role,
                        "labelUuid": _uid(package_id, pin_key, label_kind),
                        "labelKind": label_kind,
                        "netClass": class_for(item.signal),
                        "labelFields": label_fields})
            parts.append(f'(instances (project {_q(project_name)} (path {_q(parent_path)} (page {_q(page)}))))')
            parts.append(')')
            manifest["bindings"].append({"spotId": node_id, "role": kind,
                "sheetPath": path, "parentFile": parent_file, "uuid": node_uuid,
                "file": filename})
            return "\n".join(parts), connections

        root_lines = _header(package_id, "root", package.project.name) + aliases
        root_lines.append(_text(package_id, "root:title", package.project.name + " · Domainübersicht",
                                420.0, 22.0, 2.4))
        root_path = "/" + root_uuid
        domain_edges = [(by_ae[s.source.element_id][0].id, by_ae[v.element_id][0].id)
                        for s in signals for v in s.sinks]
        domain_order = _layout_order([d.id for d in package.domains], domain_edges)
        domain_positions = {key: (65.0 + (i // 2) * 255.0, 48.26 + (i % 2) * 245.0)
                            for i, key in enumerate(domain_order)}
        ae_pages = {e.id: 2 + len(package.domains) + sum(len(previous.elements) for previous in package.domains[:di]) + ei
                    for di, d in enumerate(package.domains) for ei, e in enumerate(d.elements)}
        sheet_boxes: list[tuple[float, float, float, float]] = []
        for index, d in enumerate(package.domains):
            x, y = domain_positions[d.id]
            sheet, wires = sheet_node(root, root_path, d, domain_files[d.id],
                                      root_pins[d.id], x, y, index + 2, "domain", d.color)
            root_lines.append(sheet)
            root_lines.extend(wires)
            size = re.search(r"\(size ([0-9.]+) ([0-9.]+)\)", sheet)
            if size is None:
                raise ValueError("Ungültige KiCad-Sheet-Abmessung")
            sheet_boxes.append((x, y, x + float(size[1]), y + float(size[2])))
        # Legend is generated from this architecture's actual domain palette.
        legend_rows = [(d.name, _rgb(d.color)) for d in package.domains]
        legend_rows.extend((name, rgb) for name, rgb in (
            ("Bus / Interface", (238, 180, 24)),
            ("Versorgung", (212, 49, 49)),
            ("Analog / Differenziell", (37, 139, 76)),
            ("Steuerung / Status / Daten", (50, 92, 186)),
            ("Takt", (123, 62, 180)),
            ("HF / RF", (222, 109, 32)),
        ) if name == "Bus / Interface" or any(
            (s.connection_type == ConnectionType.BUS if name == "Bus / Interface" else
             s.signal_type.value in {
                 "Versorgung": {"Power"}, "Analog / Differenziell": {"Analog", "Differential"},
                 "Steuerung / Status / Daten": {"Control", "Status", "Digital", "Reset"},
                 "Takt": {"Clock"}, "HF / RF": {"RF"},
             }[name]) for s in signals))
        if legend_policy == 'legacy':
            legend_height = 18.0 + 5.5 * len(legend_rows)
            legend_pos = None
            for lx, ly in ((575, 300), (65, 470), (320, 470), (575, 470), (65, 400)):
                if lx + 190 > 826 or ly + legend_height > 565:
                    continue
                if all(lx + 190 < x0 or lx > x1 or ly + legend_height < y0 or ly > y1
                       for x0, y0, x1, y1 in sheet_boxes):
                    legend_pos = (lx, ly)
                    break
            if legend_pos is None:
                raise ValueError("Kein freier Bereich für die Legende auf der Wurzelseite")
            lx, ly = legend_pos
            root_lines.append(_text(package_id, "legend:title", "Legende · Domänen und Signale",
                                    lx, ly, 1.8, "left"))
            for row, (name, color) in enumerate(legend_rows):
                ry = ly + 7.62 + row * 5.5
                root_lines.append(_legend_swatch(package_id, f"{row}:{name}", lx, ry, color))
                root_lines.append(_text(package_id, f"legend:{row}", name, lx + 8.89, ry,
                                        1.0, "left"))
        else:
            blocks = legend_rows[:len(package.domains)]
            signal_rows = legend_rows[len(package.domains):]
            height = 16 + 5.5 * max(len(blocks), len(signal_rows))
            lx, ly = 416.0, 525.0 - height
            right, bottom = 816.0, 525.0
            if any(not (right < x0 or lx > x1 or bottom < y0 or ly > y1)
                   for x0, y0, x1, y1 in sheet_boxes):
                # Keep the requested corner; enlarge the page instead of covering blocks.
                root_lines = [line.replace('(paper "A1")', '(paper "A0")') for line in root_lines]
                right, bottom = 1164.0, 772.0
                lx, ly = right - 400, bottom - height
            if ly < 40 or any(not (right < x0 or lx > x1 or bottom < y0 or ly > y1)
                              for x0, y0, x1, y1 in sheet_boxes):
                raise ValueError('Der Bereich unten rechts für die Legenden ist auch auf A0 belegt. Architektur aufteilen oder Blockbelegung reduzieren.')
            manifest['legendBounds'] = [lx, ly, right, bottom]
            for column, (title, entries) in enumerate((('Blocklegende · Domänen', blocks), ('Signallegende · Netze / Busse', signal_rows))):
                x = lx + column * 210
                root_lines.append(_text(package_id, f'legend:{column}:title', title, x, ly, 1.5, 'left'))
                for row, (name, color) in enumerate(entries):
                    y = ly + 9 + row * 5.5
                    key = f'{column}:{row}:{name}'
                    if column == 0:
                        r, g, b = color
                        root_lines.append(f'(polyline (pts (xy {x} {y-1.5}) (xy {x+5} {y-1.5}) (xy {x+5} {y+1.5}) (xy {x} {y+1.5}) (xy {x} {y-1.5})) (stroke (width 0.25) (type solid) (color {r} {g} {b} 1)) (uuid {_q(_uid(package_id, "legend", key))}))')
                    else:
                        swatch = _legend_swatch(package_id, key, x, y, color)
                        root_lines.append(swatch.replace('(width 2.0)', '(width 0.65)' if name == 'Bus / Interface' else '(width 0.3)'))
                    root_lines.append(_text(package_id, f'legend:{column}:{row}', name, x+8.89, y, 1.0, 'left'))
        root_lines.append('(sheet_instances (path "/" (page "1")))')
        root_lines.append(')')
        files[root] = "\n".join(root_lines) + "\n"

        for di, d in enumerate(package.domains):
            domain_path = root_path + "/" + _uid(package_id, "sheet", d.id)
            domain_lines = _header(package_id, "domain:" + d.id, d.name, "A2") + aliases
            domain_lines.append(_text(package_id, f"domain:{d.id}:title", "Domain: " + d.name,
                                      297.0, 24.0, 2.2))
            domain_lines.append(_text(package_id, f"domain:{d.id}:identity",
                                      "ISD SHA-256: " + sha_identity(d.id)[:16] + "…",
                                      297.0, 30.0, 1.0))
            # Boundary labels are attached to AE wires by sheet_node below.
            local_ids = [e.id for e in d.elements]
            local_edges = [(s.source.element_id, v.element_id)
                           for s in signals for v in s.sinks
                           if s.source.element_id in local_ids and v.element_id in local_ids]
            local_order = _layout_order(local_ids, local_edges)
            local_positions = {key: 101.6 + i * 254.0 for i, key in enumerate(local_order)}
            for ei, e in enumerate(d.elements):
                x = local_positions[e.id]
                y = 65.0
                sheet, wires = sheet_node(domain_files[d.id], domain_path, e, ae_files[e.id],
                                         ae_pins[e.id], x, y, ae_pages[e.id], "ae", d.color, d.id)
                domain_lines.append(sheet)
                domain_lines.extend(wires)
            domain_lines.append(f'(sheet_instances (path {_q(domain_path)} (page {_q(di + 2)})))')
            domain_lines.append(')')
            files[domain_files[d.id]] = "\n".join(domain_lines) + "\n"

            for e in d.elements:
                lines = _header(package_id, "ae:" + e.id, e.name, "A3") + aliases
                lines.append(_text(package_id, f"ae:{e.id}:title", "AE: " + e.name,
                                   210.0, 24.0, 2.2))
                lines.append(_text(package_id, f"ae:{e.id}:context",
                                   "Domain: " + d.name + " · ISD SHA-256: " + sha_identity(e.id)[:16] + "…",
                                   210.0, 30.0, 1.0))
                left = _lane_positions([v for v in ae_pins[e.id] if v.role != "Host"], 58.42)
                right = _lane_positions([v for v in ae_pins[e.id] if v.role == "Host"], 58.42)
                for side, values in (("left", left), ("right", right)):
                    for item, y in values:
                        x = 45.72 if side == "left" else 365.76
                        # The free connection end faces the centre of this AE page.
                        angle = 180 if side == "left" else 0
                        key = f'ae:{e.id}:{item.signal.id}'
                        connection = connection_by_signal.get(item.signal.id)
                        endpoint = next((v for v in connection.endpoints
                                         if item.port and v.port_id == item.port.id), None) if connection else None
                        fields = _meta_fields(item.signal, item.port, item.role, connection, endpoint,package.property_definitions,package)
                        fields["ISD_PinMappingStatus"]=hierarchical_mapping(package,item.signal,item.role)[1]
                        lines.append(_label(package_id, key, item.name, x, y, angle,
                                            True, hierarchical_mapping(package,item.signal,item.role)[0],
                                            fields if item.signal.connection_type==ConnectionType.BUS and any(m.realization_attributes.get("netClass") or m.realization_attributes.get("netClasses") for m in item.signal.bus_contents) else {**fields, "Netclass": class_for(item.signal)},
                                            justify="right" if side == "left" else "left"))
                        manifest["labelBindings"].append({"file": ae_files[e.id],
                            "uuid": _uid(package_id, key, "hierarchical_label"),
                            "signalId": item.signal.id, "name": item.name, "fields": fields,
                            "netClass": class_for(item.signal)})
                # Global ground labels live on the functional page, with no sheet pins.
                local_grounds = [s for s in grounds if any(endpoint.element_id == e.id
                    for endpoint in ([s.source] if s.source else []) + s.sinks)]
                for index, ground in enumerate(local_grounds):
                    key = f'ground:{e.id}:{ground.id}'
                    fields = _meta_fields(ground, None, 'Global', definitions=package.property_definitions, package=package)
                    label = _label(package_id, key, ground.name, 200.66, 190.5 + index * 5.08,
                                   hierarchical=True, fields={**fields, 'Netclass': class_for(ground)})
                    label = label.replace('(hierarchical_label ', '(global_label ', 1)
                    lines.append(label)
                ae_path = domain_path + "/" + _uid(package_id, "sheet", e.id)
                lines.append(f'(sheet_instances (path {_q(ae_path)} (page {_q(ae_pages[e.id])})))')
                lines.append(')')
                files[ae_files[e.id]] = "\n".join(lines) + "\n"

        manifest["files"] = sorted(files)
        from .kicad_layout import audit_page_bounds, audit_text_collisions
        manifest["layoutWarnings"] = audit_text_collisions(files) + audit_page_bounds(files)
        from .kicad_project_readback import embed_project_binding
        embed_project_binding(files, manifest, package)
        return files, manifest

    def backward_preview(self, package: ArchitecturePackage, archive: bytes) -> AnnotationPreview:
        """Compatibility path for legacy ZIP consumers; project UI uses v2 reader."""
        if not isinstance(archive, bytes):
            return self.backward_project_preview(package, archive)
        from .kicad_readback import inspect_archive
        return inspect_archive(package, archive)

    def backward_project_preview(self, package, project_file, build_architecture=False, hierarchy="auto"):
        from .kicad_project_readback import inspect_project
        return inspect_project(package, project_file, build_architecture, hierarchy)

    def backward_project_archive_preview(self, package, archive, build_architecture=False, hierarchy="auto"):
        from .kicad_project_readback import inspect_project_archive
        return inspect_project_archive(package, archive, build_architecture, hierarchy)

    def backward_apply(self, package: ArchitecturePackage, preview: AnnotationPreview) -> ArchitecturePackage:
        if preview.direction != "backward" or not preview.can_apply:
            raise ValueError("Offene Konflikte müssen vor der Backward Annotation gelöst werden")
        if hasattr(preview, "back_annotation_state"):
            from .kicad_project_readback import apply_project_changes
            candidate = apply_project_changes(package, preview)
            binding = candidate.properties.setdefault("ecadConnectors", {}).setdefault("kicad", {})
            binding["snapshot"] = _snapshot(candidate)
            binding["metadataSnapshot"] = _metadata(candidate)
            return candidate
        candidate = deepcopy(package)
        domains = {d.id: d for d in candidate.domains}
        elements = {e.id: e for d in candidate.domains for e in d.elements}
        signals = {s.id: s for s in candidate.signals}
        changed_signals = []
        for change in preview.changes:
            if change.field == "name":
                target = domains.get(change.object_id) or elements.get(change.object_id)
                if target is None:
                    raise ValueError("Unbekanntes Architekturobjekt")
                target.name = str(change.after)
            elif change.field == "sinks":
                from .models import SignalEndpoint
                signal = signals[change.object_id]
                signal.sinks = [SignalEndpoint(element_id=ae) for ae in change.after]
                changed_signals.append(signal)
            elif change.field == "description":
                target = domains.get(change.object_id) or elements.get(change.object_id)
                if target is None:
                    raise ValueError("Unbekanntes Architekturobjekt")
                target.description = str(change.after)
            elif change.field == "color":
                if change.object_id not in domains or not re.fullmatch(r"#[0-9a-fA-F]{6}", str(change.after)):
                    raise ValueError("Ungültige Domainfarbe")
                domains[change.object_id].color = str(change.after)
        if changed_signals:
            from pathlib import Path
            from .bus_content import BusContentTemplates
            from .topology import synchronize_signal_topology
            templates = BusContentTemplates(Path(__file__).resolve().parents[1] / "Interface_Template_File.json")
            for signal in changed_signals:
                synchronize_signal_topology(candidate, signal, templates)
        candidate = ArchitecturePackage.model_validate(candidate.export_dict())
        binding = candidate.properties.setdefault("ecadConnectors", {}).setdefault("kicad", {})
        binding["snapshot"] = _snapshot(candidate)
        binding["metadataSnapshot"] = _metadata(candidate)
        return candidate


register(KiCadConnector())
