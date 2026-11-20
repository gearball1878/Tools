"""Shared editors for HSI and hardware/mechanical contracts in both views."""
from __future__ import annotations
from .help_ui import mask_help
from nicegui import ui
from .models import ArchitecturePackage, IntegrationInterface
from .integration import REFERENCE_COLLECTIONS
from .traceability import project_objects, remove_deleted_references

LABELS = {'hardware_element_ids':'HW-Architekturelemente','signal_ids':'HW-Netze / Busse',
    'component_ids':'Konkrete HW-Bauteile','software_element_ids':'SW/FW-Architekturelemente',
    'software_component_ids':'Treiber / Firmware / SW-Komponenten','software_interface_ids':'Software-Schnittstellen',
    'mechanical_element_ids':'Mechanik-Architekturelemente','mechanical_component_ids':'CAD-Teile / Baugruppen',
    'mechanical_interface_ids':'Mechanische Schnittstellen','requirement_ids':'Requirements'}
HSI_KEYS = ['Peripherieinstanz','Adresse','Chip Select','IRQ','Pinmux','Protokoll','Timing']
MECH_KEYS = ['Befestigung','Bauraum','Kontaktfläche','Wärmeweg','Lastfall','Montage','Referenzsystem']


def interface_dialog(get_package, save, kind='HSI', existing=None):
    p = get_package(); current = existing.model_copy(deep=True) if existing else IntegrationInterface(name='',kind=kind)
    registry = project_objects(p)
    with ui.dialog() as dialog, ui.card().classes('w-[1050px] max-w-[96vw] max-h-[92vh] overflow-auto p-6 gap-3'):
        mask_help(dialog,'architecture',current,mask='Integrationsschnittstelle bearbeiten')
        ui.label(current.kind+' · Schnittstelle '+('bearbeiten' if existing else 'anlegen')).classes('text-xl font-bold')
        name = ui.input('Name',value=current.name).classes('w-full')
        description = ui.textarea('Schnittstellenbeschreibung',value=current.description).props('autogrow').classes('w-full')
        controls = {}
        for field, target in REFERENCE_COLLECTIONS.items():
            if field.startswith('mechanical_') and current.kind=='HSI' or field.startswith('software_') and current.kind=='HW-Mechanik': continue
            objects = registry[target].values()
            if field=='software_interface_ids': objects = [o for o in objects if o.interface_class.value in {'SW_IF','FW_IF'}]
            if field=='mechanical_interface_ids': objects = [o for o in objects if o.interface_class.value=='MECH_IF']
            options = {o.id:getattr(o,'name',getattr(o,'title',o.id)) for o in objects}
            controls[field] = ui.select(options,value=getattr(current,field),multiple=True,label=LABELS[field]).props('use-input use-chips outlined dense').classes('w-full')
        config = {}
        with ui.expansion('Konkrete Implementierung / Konfiguration',value=False).classes('w-full border rounded'):
            revision = ui.input('Implementierungsrevision',value=current.revision).classes('w-full')
            for key in dict.fromkeys((HSI_KEYS if current.kind=='HSI' else MECH_KEYS)+list(current.configuration)):
                config[key] = ui.input(key,value=current.configuration.get(key,'')).classes('w-full')
            ui.label('Offene Zuordnungen sind erlaubt. Auswahl und Kennwerte sind keine Erfüllungsbewertung.').classes('text-xs')
        def commit():
            current.name = (name.value or '').strip(); current.description = description.value or ''
            current.revision = revision.value or ''
            current.configuration = {k:c.value for k,c in config.items() if c.value}
            for field,c in controls.items(): setattr(current,field,list(c.value or []))
            candidate = get_package().model_copy(deep=True)
            candidate.integration_interfaces = [i for i in candidate.integration_interfaces if i.id!=current.id]+[current]
            try: candidate = ArchitecturePackage.model_validate(candidate.model_dump())
            except ValueError as e: ui.notify(str(e),type='negative');return
            target = get_package(); before = target.integration_interfaces; target.integration_interfaces = candidate.integration_interfaces
            if save('Disziplinübergreifende Schnittstelle gespeichert') is False: target.integration_interfaces=before;return
            dialog.close()
        ui.button('Schnittstelle speichern',icon='save',on_click=commit)
        ui.button('Abbrechen',on_click=dialog.close).props('flat')
    dialog.open()


def render_integration_panel(get_package, save, discipline='hardware', object_id=None):
    p = get_package(); registry = project_objects(p)
    kinds = ['HSI','HW-Mechanik'] if discipline in {'hardware','system'} else ['HSI'] if discipline=='software' else ['HW-Mechanik']
    with ui.expansion('Disziplinübergreifende Schnittstellen',icon='hub',value=False).classes('w-full border rounded'):
        with ui.row().classes('w-full flex-wrap'):
            for kind in kinds: ui.button(kind+' anlegen',icon='add_link',on_click=lambda _,k=kind:interface_dialog(get_package,save,k)).props('outline dense no-caps')
        for interface in p.integration_interfaces:
            if interface.kind not in kinds: continue
            if object_id and not any(object_id in getattr(interface,field) for field in REFERENCE_COLLECTIONS): continue
            with ui.expansion(interface.kind+' · '+interface.name,value=False).classes('w-full'):
                ui.label(interface.description).classes('text-sm')
                from .comparison_ui import source_dialog
                for field,target in REFERENCE_COLLECTIONS.items():
                    for identifier in getattr(interface,field):
                        obj = registry[target].get(identifier)
                        if obj: ui.button(LABELS[field]+': '+getattr(obj,'name',getattr(obj,'title',identifier)),on_click=lambda _,i=identifier:source_dialog(p,i)).props('flat dense no-caps')
                ui.label('Implementierungsrevision: '+(interface.revision or 'Offen')).classes('text-xs')
                with ui.expansion('Implementierungsdetails',value=False).classes('w-full'):
                    for key,value in interface.configuration.items(): ui.label(key+': '+value).classes('text-sm')
                from .technical_values_ui import render_technical_values
                render_technical_values(get_package,save,interface)
                ui.button('Bearbeiten',icon='edit',on_click=lambda _,i=interface:interface_dialog(get_package,save,existing=i)).props('outline dense')
                def delete(_,identifier=interface.id):
                    with ui.dialog() as confirmation,ui.card():
                        ui.label('Schnittstellenzuordnung löschen?')
                        def accept():
                            candidate = get_package().model_copy(deep=True); remove_deleted_references(candidate,{identifier})
                            candidate = ArchitecturePackage.model_validate(candidate.model_dump())
                            target=get_package(); before=target.model_copy(deep=True)
                            for field in ArchitecturePackage.model_fields: setattr(target,field,getattr(candidate,field))
                            if save('Schnittstellenzuordnung entfernt') is False:
                                for field in ArchitecturePackage.model_fields:setattr(target,field,getattr(before,field))
                                return
                            confirmation.close()
                        ui.button('Löschen',on_click=accept).props('color=negative')
                        ui.button('Abbrechen',on_click=confirmation.close).props('flat')
                    confirmation.open()
                ui.button('Löschen',icon='delete_outline',on_click=delete).props('flat dense color=negative')
