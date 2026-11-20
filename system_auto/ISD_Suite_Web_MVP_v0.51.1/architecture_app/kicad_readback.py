"""Read-only KiCad comparison used by explicit Backward Annotation."""
from __future__ import annotations

from io import BytesIO
import json
import re
from zipfile import ZipFile

from .ecad_connector import AnnotationChange, AnnotationPreview


_TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+')


def parse_sexpr(content: str) -> list:
    """Parse KiCad's plain S-expressions without evaluating any file content."""
    stack: list[list] = []
    root: list = []
    current = root
    for match in _TOKENS.finditer(content):
        token = match.group()
        if token == "(":
            child: list = []
            current.append(child)
            stack.append(current)
            current = child
        elif token == ")":
            if not stack:
                raise ValueError("KiCad-Datei hat eine überzählige schließende Klammer")
            current = stack.pop()
        else:
            current.append(json.loads(token) if token.startswith('"') else token)
    if stack or len(root) != 1 or not isinstance(root[0], list):
        raise ValueError("Ungültige KiCad-S-Expression")
    return root[0]


def _children(node: list, key: str) -> list[list]:
    return [item for item in node if isinstance(item, list) and item and item[0] == key]


def _value(node: list, key: str, default: str = "") -> str:
    values = _children(node, key)
    return str(values[0][1]) if values and len(values[0]) > 1 else default


def _value_from_property(node: list, name: str) -> str | None:
    return next((str(item[2]) for item in _children(node, "property")
                 if len(item) > 2 and item[1] == name), None)


def _xy(node: list) -> tuple[float, float] | None:
    at = _children(node, "at")
    return (float(at[0][1]), float(at[0][2])) if at and len(at[0]) >= 3 else None


def _attached_labels(tree: list, point: tuple[float, float]) -> set[str]:
    """Names on the wire component attached to a sheet pin in one page."""
    wires: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for wire in (*_children(tree, "wire"), *_children(tree, "bus")):
        pts = _children(wire, "pts")
        coords = _children(pts[0], "xy") if pts else []
        if len(coords) == 2:
            wires.append(((float(coords[0][1]), float(coords[0][2])),
                          (float(coords[1][1]), float(coords[1][2]))))
    labels = [(str(label[1]), _xy(label))
              for label in (*_children(tree, "label"), *_children(tree, "hierarchical_label"))]
    positions = {point} | {p for _, p in labels if p is not None}
    positions.update(p for pair in wires for p in pair)
    positions.update(p for j in _children(tree, "junction") if (p := _xy(j)) is not None)
    parent = {p: p for p in positions}

    def find(p):
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    def on_segment(p, a, b):
        return (abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])) < 0.00001
                and min(a[0], b[0])-0.00001 <= p[0] <= max(a[0], b[0])+0.00001
                and min(a[1], b[1])-0.00001 <= p[1] <= max(a[1], b[1])+0.00001)

    for a, b in wires:
        for p in positions:
            if on_segment(p, a, b):
                parent[find(p)] = find(a)
    root = find(point)
    return {name for name, p in labels if p is not None and find(p) == root}


def inspect_archive(package, archive: bytes) -> AnnotationPreview:
    preview = AnnotationPreview("backward")
    if len(archive) > 40_000_000:
        raise ValueError("Das KiCad-Archiv ist zu groß")
    try:
        with ZipFile(BytesIO(archive)) as zf:
            names = set(zf.namelist())
            if "isd_kicad_bindings.json" not in names:
                raise ValueError("ISD-Binding-Datei fehlt; Projektzuordnung nicht sicher möglich")
            manifest = json.loads(zf.read("isd_kicad_bindings.json"))
            if manifest.get("format") != "isd-kicad/v1" or manifest.get("projectId") != package.project.id:
                raise ValueError("KiCad-Projekt gehört nicht zu diesem SPOT-Projekt")
            missing = [f for f in manifest.get("files", []) if f not in names]
            if missing:
                raise ValueError(f"KiCad-Dateien fehlen: {', '.join(missing[:3])}")
            trees = {name: parse_sexpr(zf.read(name).decode("utf-8"))
                     for name in manifest["files"] if name.endswith(".kicad_sch")}
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"KiCad-Projekt kann nicht gelesen werden: {error}") from error

    snapshot = manifest["snapshot"]
    current = {
        "domains": {d.id: d.name for d in package.domains},
        "elements": {e.id: e.name for d in package.domains for e in d.elements},
    }
    current_objects = {d.id: d for d in package.domains}
    current_objects.update({e.id: e for d in package.domains for e in d.elements})
    seen: set[str] = set()
    attached: dict[str, dict[str, str | None]] = {}
    bindings_by_pin = {b["uuid"]: b for b in manifest["bindings"]
                       if b["role"] in {"aePort", "domainBoundary"}}
    known_net_names = {("{" + sid["name"] + "}" if sid["kind"] == "Bus" else sid["name"]): key
                       for key, sid in snapshot["signals"].items()}
    for label_binding in manifest.get("labelBindings", []):
        tree = trees.get(label_binding["file"])
        matches = ([label for label in _children(tree, "hierarchical_label")
                    if _value(label, "uuid") == label_binding["uuid"]] if tree else [])
        if len(matches) != 1:
            preview.changes.append(AnnotationChange(label_binding["signalId"], "labelBinding",
                label_binding["uuid"], None, "unsupported", "Hierarchisches Label entfernt oder UUID geändert"))
            continue
        actual = {str(p[1]): str(p[2]) for p in _children(matches[0], "property")
                  if len(p) > 2 and str(p[1]).startswith("ISD_")}
        net_class = _value_from_property(matches[0], "Netclass")
        if (matches[0][1] != label_binding["name"] or actual != label_binding["fields"]
                or (label_binding.get("netClass") is not None
                    and net_class != label_binding["netClass"])):
            preview.changes.append(AnnotationChange(label_binding["signalId"], "labelMetadata",
                {**label_binding["fields"], "Netclass": label_binding.get("netClass")},
                {**actual, "Netclass": net_class}, "unsupported",
                "Hierarchisches Label oder seine Architekturattribute geändert"))
    for binding in manifest["bindings"]:
        if binding["role"] not in {"domain", "ae", "aePort", "domainBoundary"}:
            continue
        parent = trees.get(binding["parentFile"])
        if parent is None:
            raise ValueError("Eine referenzierte KiCad-Seite fehlt")
        if binding["role"] in {"domain", "ae"}:
            matches = [s for s in _children(parent, "sheet") if _value(s, "uuid") == binding["uuid"]]
            if len(matches) != 1:
                preview.changes.append(AnnotationChange(binding["spotId"], "sheet", binding["uuid"],
                    None, "unsupported", "Sheet entfernt oder UUID verändert"))
                continue
            sheet = matches[0]
            properties = {str(v[1]): str(v[2]) for v in _children(sheet, "property") if len(v) > 2}
            if properties.get("ISD_ID") != binding["spotId"] or properties.get("Sheetfile") != binding["file"]:
                preview.changes.append(AnnotationChange(binding["spotId"], "binding",
                    binding["file"], properties.get("Sheetfile"), "unsupported",
                    "Objektbindung oder Sheet-Datei geändert"))
                continue
            obj_id = binding["spotId"]
            baseline_meta = manifest.get("metadata", {}).get(
                "domains" if binding["role"] == "domain" else "elements", {}).get(obj_id)
            if baseline_meta:
                if properties.get("ISD_SHA256") != baseline_meta["sha256"]:
                    preview.changes.append(AnnotationChange(obj_id, "identity", baseline_meta["sha256"],
                        properties.get("ISD_SHA256"), "unsupported", "Geschützte Architekturkennung verändert"))
                    continue
                protected = {
                    "ISD_KIND": binding["role"],
                    "ISD_TECHNICAL_NAME": baseline_meta.get("technicalName", ""),
                    "ISD_TYPE": baseline_meta.get("domainTypeId" if binding["role"] == "domain" else "roleTypeId", ""),
                }
                if binding["role"] == "ae":
                    protected["ISD_PARENT_ID"] = baseline_meta["domainId"]
                    protected["ISD_COLOR"] = baseline_meta["color"]
                if baseline_meta.get("attributes"):
                    protected["ISD_ATTRIBUTES"] = json.dumps(baseline_meta["attributes"],
                                                              ensure_ascii=False, sort_keys=True)
                for field, expected in protected.items():
                    if properties.get(field) != expected:
                        preview.changes.append(AnnotationChange(obj_id, field, expected,
                            properties.get(field), "unsupported", "Geschütztes Architekturfeld verändert"))
                expected_color = baseline_meta.get("color")
                fills = _children(sheet, "fill")
                colors = _children(fills[0], "color") if fills else []
                fill_color = ("#{:02X}{:02X}{:02X}".format(*(int(float(v)) for v in colors[0][1:4]))
                              if colors and len(colors[0]) >= 4 else None)
                if expected_color and fill_color and fill_color.casefold() != expected_color.casefold():
                    if binding["role"] == "ae":
                        preview.changes.append(AnnotationChange(obj_id, "fillColor", expected_color,
                            fill_color, "unsupported", "AE-Farbe wird von der Domain geerbt"))
                    elif properties.get("ISD_COLOR", expected_color).casefold() != expected_color.casefold() and (
                            properties["ISD_COLOR"].casefold() != fill_color.casefold()):
                        preview.changes.append(AnnotationChange(obj_id, "color", properties["ISD_COLOR"],
                            fill_color, "unsupported", "Sheet-Füllung und ISD_COLOR widersprechen sich"))
                    else:
                        properties["ISD_COLOR"] = fill_color
                editable_fields = [("description", "ISD_DESCRIPTION")]
                if binding["role"] == "domain":
                    editable_fields.append(("color", "ISD_COLOR"))
                for field, key in editable_fields:
                    old = str(baseline_meta.get(field, ""))
                    value = properties.get(key)
                    if value is None:
                        preview.changes.append(AnnotationChange(obj_id, field, old, None, "unsupported",
                            f"KiCad-Feld {key} fehlt"))
                        continue
                    if value != old:
                        now = str(getattr(current_objects[obj_id], field))
                        if field == "color" and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                            status, detail = "unsupported", "Farbe muss #RRGGBB sein"
                        else:
                            status = "ready" if now == old else "conflict"
                            detail = "In SPOT und KiCad geändert" if status == "conflict" else "KiCad-Feld geändert"
                        preview.changes.append(AnnotationChange(obj_id, field, now, value, status, detail))
            prop = next((v for v in _children(sheet, "property") if len(v) > 2 and v[1] == "Sheetname"), None)
            name = str(prop[2]) if prop else ""
            kind = "domains" if binding["role"] == "domain" else "elements"
            old = snapshot[kind].get(obj_id)
            now = current[kind].get(obj_id)
            if not name:
                preview.changes.append(AnnotationChange(obj_id, "name", old, name,
                                                        "unsupported", "Leerer Sheet-Name"))
            elif name != old and name != now and obj_id not in seen:
                preview.changes.append(AnnotationChange(obj_id, "name", now, name,
                    "ready" if now == old else "conflict",
                    "SPOT und KiCad wurden beide geändert" if now != old else "Sheet umbenannt"))
            seen.add(obj_id)
        else:
            if binding.get("labelUuid"):
                label_kind = binding.get("labelKind", "label")
                matching_labels = [label for label in _children(parent, label_kind)
                                   if _value(label, "uuid") == binding["labelUuid"]]
                if len(matching_labels) != 1:
                    preview.changes.append(AnnotationChange(binding["spotId"], "labelBinding",
                        binding["labelUuid"], None, "unsupported", "ISD-Netzlabel entfernt oder UUID geändert"))
                    continue
                actual_fields = {str(p[1]): str(p[2]) for p in _children(matching_labels[0], "property")
                                 if len(p) > 2 and str(p[1]).startswith("ISD_")}
                expected_fields = binding.get("labelFields", {})
                net_class = _value_from_property(matching_labels[0], "Netclass")
                if (actual_fields != expected_fields
                        or (binding.get("netClass") is not None
                            and net_class != binding["netClass"])):
                    preview.changes.append(AnnotationChange(binding["spotId"], "labelMetadata",
                        {**expected_fields, "Netclass": binding.get("netClass")},
                        {**actual_fields, "Netclass": net_class}, "unsupported",
                        "KiCad-Labelattribute geändert; fachliche Rückzuordnung erforderlich"))
                    continue
            sheets = [s for s in _children(parent, "sheet")
                      if _value(s, "uuid") == binding["sheetPath"].split("/")[-1]]
            pins = [p for s in sheets for p in _children(s, "pin") if _value(p, "uuid") == binding["uuid"]]
            if len(pins) != 1 or len(pins[0]) < 2 or pins[0][1] != binding["netLabel"]:
                preview.changes.append(AnnotationChange(binding["spotId"], "portConnectivity",
                    binding["netLabel"], pins[0][1] if pins else None, "unsupported",
                    "Hierarchischer Pin geändert: Zuordnung und elektrische Verbindung prüfen"))
                continue
            if binding["role"] == "aePort":
                point = _xy(pins[0])
                labels = _attached_labels(parent, point) if point else set()
                if len(labels) > 1:
                    preview.changes.append(AnnotationChange(binding["spotId"], "portConnectivity",
                        binding["netLabel"], sorted(labels), "conflict", "Mehrere Netzbezeichnungen am selben Port"))
                    continue
                label = next(iter(labels), None)
                if label and label not in known_net_names:
                    preview.changes.append(AnnotationChange(binding["spotId"], "portConnectivity",
                        binding["netLabel"], label, "unsupported", "Neuer Link benötigt eine fachliche Zuordnung"))
                    continue
                ae_id = binding["sheetPath"].split("/")[-1]
                # Resolve the AE from its sheet UUID, not the user-visible name.
                ae = next((b["spotId"] for b in manifest["bindings"]
                           if b["role"] == "ae" and b["uuid"] == ae_id), None)
                if ae:
                    attached.setdefault(ae, {})[binding["spotId"]] = label

    # A sheet pin without a stored binding is a newly introduced interface.
    for filename, tree in trees.items():
        for sheet in _children(tree, "sheet"):
            for pin in _children(sheet, "pin"):
                pin_id = _value(pin, "uuid")
                if pin_id not in bindings_by_pin:
                    preview.changes.append(AnnotationChange(pin_id, "portConnectivity", None,
                        pin[1] if len(pin) > 1 else None, "unsupported",
                        "Neuen AE-Port zuerst einem SPOT-Link und einer Rolle zuordnen"))

    current_signals = {s.id: s for s in package.signals}
    for signal_id, base in snapshot["signals"].items():
        if signal_id in manifest.get("globalSignalIds", []):
            continue
        if signal_id not in current_signals:
            continue
        signal = current_signals[signal_id]
        expected_label = "{" + base["name"] + "}" if base["kind"] == "Bus" else base["name"]
        connected = {ae for ae, ports in attached.items()
                     for port_id, label in ports.items() if label == expected_label}
        baseline = set(base["sinks"])
        changed = connected != baseline | {base["source"]}
        if not changed:
            continue
        if signal.connection_type.value == "Bus":
            preview.changes.append(AnnotationChange(signal_id, "topology", sorted(baseline), sorted(connected),
                "unsupported", "Bus-Topologie und Mitgliedszuordnung benötigen eine gesonderte Prüfung"))
            continue
        if base["source"] not in connected:
            preview.changes.append(AnnotationChange(signal_id, "source", base["source"], sorted(connected),
                "conflict", "Quelle getrennt oder geändert; Host-Rolle nicht eindeutig"))
            continue
        new_sinks = sorted(connected - {base["source"]})
        now_sinks = sorted(v.element_id for v in signal.sinks)
        if now_sinks == new_sinks:
            continue
        preview.changes.append(AnnotationChange(signal_id, "sinks", now_sinks, new_sinks,
            "ready" if (signal.source and signal.source.element_id == base["source"]
                        and now_sinks == sorted(baseline)) else "conflict",
            "Teilnehmer in KiCad geändert" if now_sinks == sorted(baseline)
            else "Teilnehmer in SPOT und KiCad geändert"))

    preview.warnings.append(
        "Neue Links, neue Ports, Bus-Umverdrahtung und unklare Host-Wechsel werden "
        "angezeigt, aber noch nicht automatisch zurückübernommen."
    )
    return preview
