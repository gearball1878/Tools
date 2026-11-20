"""Engineering properties with lossless legacy metadata and one object identity."""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

# These are connector/identity internals, never editable as engineering properties.
SYSTEM_KEYS = {
    'nativeScmUuid', 'nativeSheetName', 'kicadPinUuid', 'generatedBy',
    'architectureSignalId', 'nativeScmImport', 'nativeHostOverride',
    'hostAssignmentPending', 'technicalImplementations', 'attributeProvenance',
    'xpedArchId', 'xpedScmId', 'portNamingRule', 'portSignalsMaterialized',
    'manualDefinitionOverride', 'interfaceTemplateUnresolved',
    'legacyPropertyValues',
}


def is_system_key(key: str) -> bool:
    return key in SYSTEM_KEYS or key.lower() in {'id', 'uuid', 'sha256'} or key.startswith('native')


def compare_values(required: Any, realized: Any) -> str:
    """Only compare explicit values/ranges; never claim verified compliance."""
    if realized is None:
        return 'Realisierungswert fehlt'
    if isinstance(required, dict) and 'value' in required and isinstance(realized, dict) and 'value' in realized:
        if required.get('unit', '') != realized.get('unit', ''):
            return 'Einheiten prüfen'
        return 'Werte stimmen überein' if required['value'] == realized['value'] else 'Werte weichen ab'
    if isinstance(required, dict) and any(k in required for k in ('min', 'max')):
        value = realized.get('value') if isinstance(realized, dict) else realized
        if required.get('unit', '') != (realized.get('unit', '') if isinstance(realized, dict) else ''):
            return 'Einheiten prüfen'
        if isinstance(value, (float, int)) and not isinstance(value, bool):
            try:
                good = ('min' not in required or value >= required['min']) and ('max' not in required or value <= required['max'])
                return 'Innerhalb der Vorgabe' if good else 'Außerhalb der Vorgabe'
            except TypeError:
                pass
        return 'Manuell bewerten'
    return 'Werte stimmen überein' if required == realized else 'Werte weichen ab'


def render_attribute_spaces(obj, save, preferred='comparison', package=None, *, editable=False, edit_object=None) -> None:
    from nicegui import ui
    from .identity import show_sha_identity
    from .property_schema import applicable,system_definitions,validate_value,exchange_mode,selection_options,TYPE_LABELS
    from .netclasses import member_class,set_assignment
    from .technical_comparison import ARCHITECTURE_KINDS
    if package is not None and type(obj).__name__ in ARCHITECTURE_KINDS and not editable:
        from .comparison_ui import render_architecture_details
        render_architecture_details(package,obj,preferred=preferred,edit_object=edit_object)
        return
    if package is not None and not editable:
        from .object_properties import render_native_fields
        render_native_fields(package,obj)
    definitions=package.property_definitions if package is not None else system_definitions()
    ui.label('Eigenschaften').classes('font-semibold text-lg')
    ui.label('Werte bearbeiten · Attribute im Property Manager verwalten' if editable else 'Objektbezogene Attribute · Änderungen über Bearbeiten').classes('text-xs text-slate-600')

    def editor(scope,d):
        values=getattr(obj,scope);old=deepcopy(values.get(d.key))
        with ui.dialog() as dialog,ui.card().classes('w-[650px] max-w-[94vw] max-h-[90vh] overflow-auto'):
            ui.label(('Anforderung · ' if scope=='requirement_attributes' else 'Realisierung · ')+d.label).classes('text-xl font-bold')
            ui.label(d.description).classes('text-sm text-slate-600')
            ui.label(f'{TYPE_LABELS[d.data_type]} {d.unit} · {exchange_mode(d,scope)} · {"Systemattribut" if d.system else "Benutzerattribut"}')
            select_input=bool(d.choices or d.selection_source) and package is not None
            if d.data_type=='list' and old is not None and any(not isinstance(v,str) for v in old):
                select_input=False
                ui.label('Strukturierter Bestandswert: Die vorhandenen Angaben bleiben bearbeitbar und erhalten.').classes('text-xs')
            if select_input:
                options=selection_options(d,obj,package)
                for value in (old if isinstance(old,list) else [old]):
                    if value is not None and isinstance(value,str):options.setdefault(value,value+' (Bestandswert)')
                field=ui.select(options,value=old,label='Wert',multiple=d.data_type=='list',clearable=True).props('use-input use-chips' if d.data_type=='list' else 'use-input').classes('w-full')
                ui.label('Keine Auswahl = Offen. Die Auswahlquelle ist im Property Manager hinterlegt.').classes('text-xs')
            elif d.data_type in ('text','reference'):field=ui.textarea('Wert',value=old or '').classes('w-full')
            elif d.data_type=='number':
                field=ui.number('Wert'+(f' [{d.unit}]' if d.unit else ''),value=old.get('value') if isinstance(old,dict) else old).classes('w-full')
                with ui.row():
                    lo=ui.number('Minimum',value=old.get('min') if isinstance(old,dict) else None)
                    hi=ui.number('Maximum',value=old.get('max') if isinstance(old,dict) else None)
                ui.label('Wert oder Wertebereich eingeben. Leere Felder bleiben offen.').classes('text-xs')
            elif d.data_type=='enum':field=ui.select(d.choices,value=old,label='Wert',clearable=True).classes('w-full')
            elif d.data_type=='boolean':field=ui.select({'true':'Ja','false':'Nein'},value=('true' if old else 'false') if old is not None else None,label='Wert',clearable=True)
            else:field=ui.textarea('Wert als JSON (leer = offen)',value=json.dumps(old,ensure_ascii=False,indent=2) if old is not None else '').classes('w-full')
            def apply(clear=False):
                try:
                    if clear:value=None
                    elif select_input:value=field.value or None
                    elif d.data_type=='number':
                        if (lo.value is not None or hi.value is not None) and field.value is not None:raise ValueError('Wert oder Wertebereich wählen')
                        value={k:v for k,v in [('min',lo.value),('max',hi.value)] if v is not None} if lo.value is not None or hi.value is not None else field.value
                        if isinstance(value,dict) and d.unit:value['unit']=d.unit
                    elif d.data_type=='boolean':value=None if field.value is None else field.value=='true'
                    elif d.data_type in ('text','reference'):value=field.value or None
                    elif d.data_type=='enum':value=field.value
                    else:value=json.loads(field.value) if field.value else None
                    if package is not None and value!=old:
                        from .requirement_profiles import validate_selection
                        validate_selection(d,obj,package,value)
                    else:validate_value(d,value)
                    values[d.key]=value
                    if save('Eigenschaft gespeichert') is False:values[d.key]=old;return
                    dialog.close()
                except (ValueError,TypeError) as error:ui.notify(str(error),type='negative')
            ui.button('Wert speichern',icon='save',on_click=lambda:apply())
            ui.button('Wert leeren',on_click=lambda:apply(True)).props('flat')
            ui.button('Abbrechen',on_click=dialog.close).props('flat')
        dialog.open()

    def class_editor():
        current=obj.realization_attributes.get('netClass')
        with ui.dialog() as dialog,ui.card().classes('w-[650px] max-w-[94vw] max-h-[85vh] overflow-auto'):
            ui.label('Netzklasse wählen').classes('text-xl font-bold')
            choice=ui.select({c.name:c.name for c in package.net_classes},value=current,label='Standardklasse für Busmitglieder' if getattr(getattr(obj,'connection_type',None),'value',None)=='Bus' else 'Netzklasse',clearable=True).props('use-input input-debounce=0').classes('w-full')
            extra=ui.select([c.name for c in package.net_classes],value=obj.realization_attributes.get('netClasses') or [],multiple=True,label='Weitere ECAD-Klassen').props('use-chips use-input').classes('w-full')
            ui.label('Keine festen PCB-Maße werden aus der Auswahl berechnet.').classes('text-xs')
            def persist():
                before=deepcopy(obj.realization_attributes);metadata=deepcopy(obj.attributes)
                set_assignment(obj,choice.value);obj.realization_attributes['netClasses']=list(extra.value or []) or None
                if save('Netzklassenzuordnung gespeichert') is False:
                    obj.realization_attributes=before;obj.attributes=metadata;return
                dialog.close()
            ui.button('Zuordnung speichern',on_click=persist)
            ui.button('Abbrechen',on_click=dialog.close)
        dialog.open()

    if hasattr(obj,'requirement_attributes'):
        for scope,title,icon in [('requirement_attributes','Anforderung','fact_check'),('realization_attributes','Realisierung','build')]:
            if not applicable(definitions,obj,scope):continue
            with ui.expansion(title,icon=icon,value=preferred==scope).classes('w-full border rounded-lg'):
                for d in applicable(definitions,obj,scope):
                    value=getattr(obj,scope).get(d.key)
                    with ui.row().classes('w-full items-center flex-wrap border-b py-1'):
                        ui.label(d.label).classes('font-medium')
                        ui.label('Offen' if value is None else json.dumps(value,ensure_ascii=False)).classes('grow break-all text-sm text-slate-600')
                        if d.unit:ui.label(d.unit).classes('text-xs')
                        provenance=getattr(obj,'attributes',{}).get('attributeProvenance',{}).get(d.key,{})
                        if provenance.get('source'):ui.badge(provenance['source']).classes('text-xs')
                        if editable and not d.readonly:
                            if d.key in ('netClass','netClasses') and package is not None:
                                ui.button(icon='edit',on_click=class_editor).props('flat round dense').mark(f'property-edit-{scope}-{d.key}').tooltip(d.label)
                            else:ui.button(icon='edit',on_click=lambda _,s=scope,d=d:editor(s,d)).props('flat round dense').mark(f'property-edit-{scope}-{d.key}').tooltip(d.label)
                ui.label('Systemattribute sind dauerhaft vorhanden; eigene Definitionen im Property Manager verwalten.').classes('text-xs text-slate-500')
        if preferred=='comparison' and type(obj).__name__ not in ARCHITECTURE_KINDS:
            filled={k:v for k,v in obj.requirement_attributes.items() if v is not None}
            if filled:
                with ui.expansion('Soll / Realisierung vergleichen',icon='compare_arrows',value=False).classes('w-full'):
                    for k,v in filled.items():ui.label(f'{k}: {compare_values(v,obj.realization_attributes.get(k))}').classes('text-sm')
                    ui.label('Wertevergleich ist kein Verifikationsnachweis.').classes('text-xs')
        if package is not None and type(obj).__name__=='ArchitectureSignal' and obj.bus_contents:
            with ui.expansion('Netzklassen der Busmitglieder',icon='settings_ethernet').classes('w-full'):
                for member in obj.bus_contents:
                    with ui.row().classes('w-full items-center border-b'):
                        own=member_class(member);effective=member_class(obj,member)
                        ui.label(member.name).classes('grow')
                        ui.label(', '.join(effective) or 'Offen').classes('text-sm')
                        ui.badge('Direkt' if own else 'Vom Bus' if effective else 'Offen')
                        if editable:ui.button(icon='edit',on_click=lambda _,m=member:member_dialog(m)).props('flat round dense')
    def member_dialog(member):
        with ui.dialog() as dialog,ui.card().classes('w-[800px] max-w-[95vw] max-h-[90vh] overflow-auto'):
            ui.label(member.name).classes('text-xl font-bold')
            show_sha_identity(member.id)
            def save_member(reason):
                result=save(reason)
                if result is not False:dialog.close()
                return result
            render_attribute_spaces(member,save_member,'realization_attributes',package)
            ui.button('Schließen',on_click=dialog.close)
        dialog.open()
    if package is not None and type(obj).__name__=='InterfacePort':
        attached=next((s for s in package.signals if s.id==obj.attributes.get('architectureSignalId') or s.id==obj.properties.get('architectureSignalId')),None)
        if attached:
            ui.label('Netzklasse des angeschlossenen Netzes / Busses: '+(', '.join(member_class(attached)) or 'Offen')).classes('text-sm')
            ui.label('Die Zuweisung wird am Netz beziehungsweise an seinen Busmitgliedern bearbeitet.').classes('text-xs text-slate-600')
