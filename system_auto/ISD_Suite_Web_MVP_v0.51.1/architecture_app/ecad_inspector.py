"""Project-wide searchable design index with logical-net properties."""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Callable

from .kicad_connector import KiCadConnector
from .kicad_rules import class_for, constraints_for
from .models import ArchitecturePackage


def design_rows(package: ArchitecturePackage, manifest: dict) -> list[dict]:
    rows: list[dict] = []
    for domain in package.domains:
        rows.append({"kind": "Domain", "id": domain.id, "name": domain.name, "object": domain})
        for element in domain.elements:
            rows.append({"kind": "AE", "id": element.id, "name": element.name,
                         "parent": domain.name, "object": element})
            for port in element.ports:
                rows.append({"kind": "Port", "id": port.id, "name": port.name,
                             "parent": element.name, "object": port})
    connections = {c.signal_id: c for c in package.connections if c.signal_id}
    signals = {s.id: s for s in package.signals}
    for signal in package.signals:
        rows.append({"kind": "Netz/Bus", "id": signal.id, "name": signal.name,
                     "object": signal, "connection": connections.get(signal.id)})
    for connection in package.connections:
        rows.append({"kind": "Verbindung", "id": connection.id, "name": connection.name,
                     "object": connection})
    for segment in manifest.get("segments", []):
        signal = signals[segment["signalId"]]
        rows.append({"kind": "Segment", "id": segment["uuid"], "name": signal.name,
                     "parent": segment["file"], "object": signal,
                     "connection": connections.get(signal.id), "segment": segment})
    return rows


def attribute_origin(obj, key: str) -> str:
    stored = obj.properties.get("attributeProvenance", {}).get(key)
    if stored in {"manual", "imported", "computed"}:
        return {"manual": "manuell", "imported": "importiert", "computed": "berechnet"}[stored]
    if obj.properties.get("generatedBy"):
        return "berechnet"
    if obj.properties.get("sourceDocumentId"):
        return "importiert"
    return "Herkunft offen"


def open_design_inspector(package: ArchitecturePackage,
                          commit: Callable[[ArchitecturePackage, str], bool]) -> None:
    from nicegui import ui
    try:
        _, manifest = KiCadConnector().generate(package)
    except ValueError as error:
        ui.notify(f"Designindex kann nicht aufgebaut werden: {error}", type="negative")
        return
    rows = design_rows(package, manifest)
    selected: dict = {"row": None, "limit": 100}
    with ui.dialog() as dialog, ui.card().classes("w-[1120px] max-w-[97vw] h-[90vh] p-5 gap-3"):
        ui.label("KiCad-Designindex · ISD-Eigenschaften").classes("text-xl font-bold")
        ui.label("Netz- und Busattribute gelten für alle Segmente desselben logischen Links. "
                 "Grafische Koordinaten bleiben segmentbezogen.").classes("text-sm")
        ui.label("KiCad zeigt an einem Leitungssegment nur Grafikwerte. Die ISD-Felder liegen "
                 "am zugehörigen Label; hier sind sie über den Segmentnamen oder die UUID auffindbar.") \
            .classes("text-xs text-slate-600")
        with ui.row().classes("w-full gap-4 min-h-0 grow"):
            with ui.column().classes("w-[40%] min-w-[270px] h-full"):
                search = ui.input("Objekte durchsuchen", placeholder="Name, Art, ID oder Seite").classes("w-full")
                count = ui.label().classes("text-xs text-slate-600")

                @ui.refreshable
                def object_list() -> None:
                    term = (search.value or "").casefold().strip()
                    matches = [row for row in rows if term in " ".join(
                        str(row.get(field, "")) for field in ("kind", "id", "name", "parent"))
                        .casefold()]
                    shown = matches[:selected["limit"]]
                    count.set_text(f"{len(shown)} angezeigt · {len(matches)} Treffer · "
                                   f"{len(matches) - len(shown)} weitere · {len(rows)} Objekte · "
                                   f"{len(manifest['layoutWarnings'])} Layoutkonflikte")
                    for row in shown:
                        ui.button(f"{row['kind']} · {row['name']}",
                                  on_click=lambda current=row: choose(current)).props("flat no-caps align=left") \
                            .classes("w-full text-left truncate")
                    if len(matches) > len(shown):
                        def show_more() -> None:
                            selected["limit"] += 100
                            object_list.refresh()
                        ui.button("Weitere 100 anzeigen", on_click=show_more).props("outline no-caps")

                with ui.scroll_area().classes("w-full grow border rounded-lg p-2"):
                    object_list()
                search.on("update:model-value", lambda _: object_list.refresh())
            with ui.scroll_area().classes("grow h-full border rounded-lg p-4"):
                @ui.refreshable
                def detail() -> None:
                    row = selected["row"]
                    if not row:
                        ui.label("Ein Objekt auswählen, um seine Eigenschaften zu sehen.")
                        return
                    obj = row["object"]

                    def section(title: str, values: dict) -> None:
                        ui.label(title).classes("font-bold text-base mt-3")
                        for key, value in values.items():
                            ui.label(f"{key}: {value}").classes("text-sm break-all")

                    section("Identität", {"Art": row["kind"], "Name": row["name"],
                                         "ISD-ID": getattr(obj, "id", row["id"]),
                                         "KiCad-UUID": row["id"] if row["kind"] == "Segment" else "siehe Mapping"})
                    section("Fachliche Eigenschaften", {
                        "Beschreibung": getattr(obj, "description", ""),
                        "Typ": getattr(getattr(obj, "signal_type", None), "value",
                                           getattr(obj, "port_type", getattr(obj, "role_type_id", ""))),
                    })
                    connection = row.get("connection")
                    if connection:
                        section("Beziehungen", {"Verbindung": connection.name,
                                                  "Verbindungs-ID": connection.id})
                    segment = row.get("segment")
                    if segment:
                        section("Grafische Darstellung", {"Seite": segment["file"],
                            "Segment-UUID": segment["uuid"], "Rolle": segment["role"],
                            "Von / nach": f"{segment['from']} / {segment['to']}"})
                    if row["kind"] in {"Netz/Bus", "Segment"}:
                        section("KiCad-Netzregeln", {
                            "Netzklasse": class_for(obj),
                            "Constraints aus SPOT": constraints_for(obj) or "noch keine Maße festgelegt",
                        })
                        if segment and connection:
                            endpoint = next((v for v in connection.endpoints
                                             if v.port_id == segment.get("portId")), None)
                            if endpoint:
                                section("Verbindungsendpunkt", {
                                    "Architektur-Port": endpoint.port_id,
                                    "Rolle": endpoint.role.value if endpoint.role else segment["role"],
                                    "Attribute": endpoint.attributes,
                                    "Eigenschaften": endpoint.properties,
                                })
                    section("Attribute · SPOT", {f"{key} [{attribute_origin(obj, key)}]": value
                                                   for key, value in obj.attributes.items()})
                    if connection and connection is not obj:
                        section("Verbindungsattribute · zentral", {
                            f"{key} [{attribute_origin(connection, key)}]": value
                            for key, value in connection.attributes.items()})
                    section("Herkunft / weitere Eigenschaften", obj.properties)
                    attributes = ui.textarea("Attribute als JSON bearbeiten",
                                             value=json.dumps(obj.attributes, ensure_ascii=False, indent=2)) \
                        .classes("w-full font-mono")

                    def save() -> None:
                        try:
                            value = json.loads(attributes.value or "{}")
                            if not isinstance(value, dict):
                                raise ValueError("Attribute müssen ein JSON-Objekt sein")
                            updated = deepcopy(package)
                            all_objects = [*updated.domains, *updated.signals, *updated.connections]
                            for domain in updated.domains:
                                all_objects.extend(domain.elements)
                                for element in domain.elements:
                                    all_objects.extend(element.ports)
                            target = next(v for v in all_objects if v.id == obj.id)
                            origins = target.properties.setdefault("attributeProvenance", {})
                            for key in list(origins):
                                if key not in value:
                                    del origins[key]
                            for key, item in value.items():
                                if obj.attributes.get(key) != item:
                                    origins[key] = "manual"
                            target.attributes = value
                            if commit(updated, "ECAD-Designattribute geändert"):
                                dialog.close()
                        except (ValueError, StopIteration) as error:
                            ui.notify(f"Attribute nicht übernommen: {error}", type="negative")

                    ui.button("Attribute in SPOT übernehmen", on_click=save).props("no-caps")

                detail()

        def choose(row: dict) -> None:
            selected["row"] = row
            detail.refresh()

        ui.button("Schließen", on_click=dialog.close).props("flat no-caps")
    dialog.open()
