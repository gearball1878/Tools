"""Signal templates, project interface library and bus contents.

Explicit callbacks keep project state in the page controller.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from nicegui import ui
from .models import ConnectionType, Direction, InterfaceMemberDefinition, ProjectInterfaceTemplate, SignalType
from .requirements_service import clone_builtin_interface_template

@dataclass(frozen=True)
class CatalogUiViews:
    interface_template_dialog: Callable[..., Any]
    clone_template_dialog: Callable[..., Any]
    interface_template_library_dialog: Callable[..., Any]
    bus_contents_dialog: Callable[..., Any]


def create_catalog_ui(
    *,
    bus_templates,
    confirm_delete_object,
    edit_architecture_signal_dialog,
    edit_object_dialog,
    export_buscontents,
    focus_object,
    open_topology_drawer,
    save,
    state,
) -> CatalogUiViews:
    def interface_template_dialog(
        template: ProjectInterfaceTemplate | None = None,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        current = template or ProjectInterfaceTemplate(name="", members=[])
        member_text = "\n".join(
            f"{item.name_pattern} | {item.direction_from_host.value} | "
            f"{item.host_pin_type} | {item.participant_pin_type} | {item.description}"
            for item in current.members
        )
        with ui.dialog() as dialog, ui.card().classes("w-[760px] max-w-[96vw] p-6 gap-4"):
            ui.label(
                "Projektvorlage bearbeiten" if template else "Projektvorlage hinzufügen"
            ).classes("text-xl font-bold")
            with ui.row().classes("w-full gap-3"):
                name = ui.input(
                    "Name", value=current.name, placeholder="z. B. SPI Project Variant",
                ).classes("grow")
                port_type = ui.input(
                    "Fachlicher Port Type", value=current.port_type,
                ).classes("grow")
            with ui.row().classes("w-full gap-3"):
                signal_type = ui.select(
                    [item.value for item in SignalType],
                    value=current.signal_type.value,
                    label="Signal Type",
                ).classes("grow")
                connection_type = ui.select(
                    [item.value for item in ConnectionType],
                    value=current.connection_type.value,
                    label="Netz oder Bus",
                ).classes("grow")
            aliases = ui.input(
                "Aliase", value=", ".join(current.aliases),
                placeholder="SPI, Serial Peripheral Interface",
            ).classes("w-full")
            members = ui.textarea(
                "Mitgliedssignale",
                value=member_text,
                placeholder=(
                    "{interface}_SCLK | out | OUT | IN\n"
                    "{interface}_MISO | in | IN | OUT | Daten vom Teilnehmer zum Host"
                ),
            ).classes("w-full font-mono").props("outlined rows=8")
            ui.label(
                "Format: Namensmuster | Richtung aus Hostsicht | Host Pin Type | Participant Pin Type | Beschreibung (optional)"
            ).classes("text-xs text-slate-500")
            description = ui.textarea(
                "Beschreibung", value=current.description,
            ).classes("w-full").props("autogrow outlined")

            def apply() -> None:
                template_name = (name.value or "").strip()
                if not template_name:
                    ui.notify("Der Vorlagenname darf nicht leer sein.", type="warning")
                    return
                if any(
                    item.id != current.id and item.name.casefold() == template_name.casefold()
                    for item in state.package.interface_templates
                ):
                    ui.notify("Der Name der Interfacevorlage ist bereits vergeben.", type="warning")
                    return
                parsed: list[InterfaceMemberDefinition] = []
                try:
                    for line in (members.value or "").splitlines():
                        if not line.strip():
                            continue
                        fields = [item.strip() for item in line.split("|", 4)]
                        if len(fields) not in {4, 5}:
                            raise ValueError(f"Ungültige Zeile: {line}")
                        parsed.append(InterfaceMemberDefinition(
                            name_pattern=fields[0],
                            direction_from_host=Direction(fields[1].casefold()),
                            host_pin_type=fields[2],
                            participant_pin_type=fields[3],
                            active_low=fields[0].endswith("#") or fields[0].endswith("_N"),
                            description=fields[4] if len(fields) == 5 else "",
                        ))
                except ValueError as error:
                    ui.notify(str(error), type="negative")
                    return
                if not parsed:
                    ui.notify("Mindestens ein Mitgliedssignal ist erforderlich.", type="warning")
                    return
                target = template or ProjectInterfaceTemplate(name=template_name)
                if template:
                    target.version += 1
                target.name = template_name
                target.port_type = (port_type.value or template_name).strip()
                target.signal_type = SignalType(signal_type.value)
                target.connection_type = ConnectionType(connection_type.value)
                target.aliases = [
                    item.strip() for item in (aliases.value or "").split(",") if item.strip()
                ]
                target.members = parsed
                target.description = description.value or ""
                if template is None:
                    state.package.interface_templates.append(target)
                dialog.close()
                save("Projekt-Interfacevorlage gespeichert")
                if on_changed:
                    on_changed()

            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                ui.button("Speichern", icon="save", on_click=apply).props("no-caps")
        dialog.open()

    def clone_template_dialog(on_changed: Callable[[], None] | None = None) -> None:
        options = bus_templates.interface_templates()
        with ui.dialog() as dialog, ui.card().classes("w-[600px] max-w-[95vw] p-6 gap-4"):
            ui.label("Systemvorlage ins Projekt kopieren").classes("text-xl font-bold")
            source = ui.select(
                options, value=options[0] if options else None,
                label="Systemvorlage", with_input=True,
            ).classes("w-full")
            name = ui.input(
                "Name der Projektvorlage", placeholder="Leer = Name der Systemvorlage",
            ).classes("w-full")
            ui.label(
                "Die Kopie kann anschließend fachlich und hinsichtlich der Pin-Type-Zuordnung angepasst werden."
            ).classes("text-sm text-slate-600")

            def apply() -> None:
                try:
                    template = clone_builtin_interface_template(
                        bus_templates, source.value, (name.value or "").strip() or None,
                    )
                except ValueError as error:
                    ui.notify(str(error), type="negative")
                    return
                if any(
                    item.name.casefold() == template.name.casefold()
                    for item in state.package.interface_templates
                ):
                    ui.notify("Der Name der Interfacevorlage ist bereits vergeben.", type="warning")
                    return
                state.package.interface_templates.append(template)
                dialog.close()
                save("Interfacevorlage ins Projekt kopiert")
                if on_changed:
                    on_changed()

            with ui.row().classes("w-full justify-end"):
                ui.button("Abbrechen", on_click=dialog.close).props("flat no-caps")
                ui.button("Kopieren", icon="content_copy", on_click=apply).props("no-caps")
        dialog.open()

    def interface_template_library_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes(
            "w-[900px] max-w-[96vw] max-h-[90vh] p-6 gap-4"
        ):
            with ui.row().classes("w-full items-center gap-2"):
                with ui.column().classes("gap-0 grow"):
                    ui.label("Interface- und Signalvorlagen").classes("text-xl font-bold")
                    ui.label(
                        "Systemvorlagen bleiben unverändert; Projektvorlagen können ergänzt, angepasst und gelöscht werden."
                    ).classes("subtle")
                ui.button(icon="close", on_click=dialog.close).props("flat round")

            @ui.refreshable
            def template_list() -> None:
                with ui.column().classes("w-full gap-3"):
                    with ui.row().classes("w-full items-center gap-2"):
                        ui.badge(
                            f"{len(bus_templates.interface_templates())} Systemvorlagen",
                            color="blue-1",
                        ).props("text-color=blue-9")
                        ui.label(
                            "Eine Systemvorlage kann als editierbare Projektkopie übernommen werden."
                        ).classes("subtle grow")
                        ui.button(
                            "Systemvorlage kopieren", icon="content_copy",
                            on_click=lambda: clone_template_dialog(template_list.refresh),
                        ).props("outline no-caps")
                        ui.button(
                            "Neue Projektvorlage", icon="add",
                            on_click=lambda: interface_template_dialog(None, template_list.refresh),
                        ).props("no-caps")
                    ui.separator()
                    from .netclasses import template_audit
                    with ui.expansion('Signal- und Interfacevorlagen prüfen',icon='rule').classes('w-full border rounded'):
                        issues=template_audit(bus_templates.data)
                        for name,issue in issues:
                            ui.label(name).classes('font-medium');ui.label(issue).classes('text-sm')
                        if not issues:ui.label('Keine offenen Vorlagenhinweise.')
                    if not state.package.interface_templates:
                        ui.label(
                            "Noch keine projektspezifischen Vorlagen. Der Wizard kann weiterhin alle Systemvorlagen verwenden."
                        ).classes("subtle py-8 text-center")
                    for template in state.package.interface_templates:
                        usage_count = sum(
                            str(item.properties.get("template", "")) == template.name
                            for item in state.package.signals
                        )
                        with ui.card().classes("w-full p-4 gap-2 border shadow-none"):
                            with ui.row().classes("w-full items-center gap-2"):
                                ui.icon("dataset", color="primary")
                                ui.label(template.name).classes("font-bold grow")
                                ui.badge(f"v{template.version}", color="grey-3").props("text-color=grey-9")
                                ui.badge(template.port_type, color="teal-1").props("text-color=teal-9")
                                ui.button(
                                    icon="edit",
                                    on_click=lambda _, item=template: interface_template_dialog(
                                        item, template_list.refresh,
                                    ),
                                ).props("flat round dense")

                                def remove(item=template) -> None:
                                    state.package.interface_templates = [
                                        value for value in state.package.interface_templates
                                        if value.id != item.id
                                    ]
                                    save("Projekt-Interfacevorlage gelöscht")
                                    template_list.refresh()

                                ui.button(
                                    icon="delete_outline", on_click=remove,
                                ).props("flat round dense color=negative").tooltip(
                                    "Bestehende Signale bleiben unverändert"
                                )
                            ui.label(
                                f"{len(template.members)} Signale · {template.connection_type.value} · "
                                f"{usage_count} Verwendung(en)"
                            ).classes("subtle")
                            if template.description:
                                ui.label(template.description).classes("text-sm")

            with ui.scroll_area().classes("w-full h-[62vh]"):
                template_list()
        dialog.open()

    def bus_contents_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[920px] max-w-[96vw] max-h-[90vh]"):
            with ui.row().classes("w-full items-center"):
                with ui.column().classes("gap-0 grow"):
                    ui.label("Signale & Interfaces").classes("text-xl font-bold")
                    ui.label("Toolneutrale Definitionen nach Typ mit Mitgliedssignalen und Topologie.").classes("subtle")
                ui.button(
                    "Vorlagen", icon="view_list", on_click=interface_template_library_dialog,
                ).props("outline no-caps")
                ui.button("Xpedition-Adapterdatei", icon="download", on_click=export_buscontents).props("outline").tooltip("Optionaler Export als busconts.ini")
            with ui.scroll_area().classes("w-full h-[65vh]"):
                if not state.package.signals:
                    ui.label("Noch keine Signaldefinitionen vorhanden.").classes("subtle p-4")
                for signal_type in SignalType:
                    typed = sorted((signal for signal in state.package.signals if signal.signal_type == signal_type), key=lambda item: item.name.casefold())
                    if not typed:
                        continue
                    ui.label(signal_type.value).classes("panel-heading mt-4")
                    for architecture_signal in typed:
                        topology = f"1 Host · {len(architecture_signal.sinks)} Teilnehmer" if architecture_signal.source else "Topologie offen"
                        with ui.expansion(architecture_signal.name, icon="hub" if architecture_signal.connection_type == ConnectionType.BUS else "electrical_services").classes("w-full border rounded-lg mb-2"):
                            with ui.row().classes("w-full items-center"):
                                ui.badge(topology, color="purple-1").props("text-color=purple-9")
                                ui.badge(architecture_signal.connection_type.value, color="grey-3").props("text-color=grey-9")
                                ui.space()
                                ui.button(
                                    "Im Canvas zeigen", icon="visibility",
                                    on_click=lambda _, s=architecture_signal: (
                                        dialog.close(), focus_object(s.id),
                                    ),
                                ).props("flat no-caps")
                                ui.button(
                                    "Definition",
                                    icon="edit",
                                    on_click=lambda _, s=architecture_signal: edit_architecture_signal_dialog(s),
                                ).props("flat")
                                ui.button("Topologie", icon="account_tree", on_click=lambda _, s=architecture_signal: open_topology_drawer(s)).props("flat")
                                ui.button(
                                    icon="delete_outline",
                                    on_click=lambda _, object_id=architecture_signal.id: confirm_delete_object(
                                        object_id,
                                        after_delete=dialog.close,
                                    ),
                                ).props("flat round dense color=negative").tooltip("Signal- oder Interfacedefinition löschen")
                            if architecture_signal.bus_contents:
                                with ui.column().classes("w-full gap-0 border rounded-lg overflow-hidden"):
                                    with ui.grid(columns=6).classes("w-full items-center bg-slate-100 px-3 py-2 gap-2"):
                                        ui.label("Mitgliedssignal").classes("text-xs font-bold")
                                        ui.label("Richtung").classes("text-xs font-bold")
                                        ui.label("Pin Type").classes("text-xs font-bold")
                                        ui.label("Active Low").classes("text-xs font-bold")
                                        ui.label("")
                                        ui.label("")
                                    for member in architecture_signal.bus_contents:
                                        with ui.grid(columns=6).classes("w-full items-center px-3 py-2 gap-2 border-t"):
                                            ui.label(member.name).classes("text-sm truncate")
                                            ui.label(member.direction.value).classes("text-sm")
                                            ui.label(member.pin_type).classes("text-sm")
                                            ui.label("Ja" if member.active_low else "Nein").classes("text-sm")
                                            ui.button(
                                                icon="edit",
                                                on_click=lambda _, object_id=member.id: (
                                                    dialog.close(), edit_object_dialog(object_id),
                                                ),
                                            ).props("flat round dense").tooltip("Busmitglied bearbeiten")
                                            ui.button(
                                                icon="delete_outline",
                                                on_click=lambda _, object_id=member.id: confirm_delete_object(
                                                    object_id,
                                                    after_delete=dialog.close,
                                                ),
                                            ).props("flat round dense color=negative").tooltip("Mitgliedssignal löschen")
                            else:
                                ui.label("Keine untergeordneten Mitgliedssignale.").classes("subtle")
            with ui.row().classes("w-full justify-end"):
                ui.button("Schließen", on_click=dialog.close).props("flat")
        dialog.open()


    return CatalogUiViews(
        interface_template_dialog=interface_template_dialog,
        clone_template_dialog=clone_template_dialog,
        interface_template_library_dialog=interface_template_library_dialog,
        bus_contents_dialog=bus_contents_dialog,
    )
