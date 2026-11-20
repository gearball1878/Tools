"""Compact architecture details, explicit source navigation and comparison."""
from __future__ import annotations
import json
from nicegui import ui
from .technical_comparison import comparison_rows, connected_signal, ecad_key, actual_objects


def source_dialog(package, identifier):
    from .traceability import project_objects
    from .identity import show_sha_identity
    from .help_ui import HelpContext
    obj = next((o for group in project_objects(package).values() for i,o in group.items() if i == identifier), None)
    if not obj: return
    with ui.dialog() as dialog, ui.card().classes('w-[850px] max-w-[95vw] max-h-[90vh] overflow-auto'):
        dialog._isd_help_context=HelpContext('requirements' if type(obj).__name__=='EcadRequirement' else 'hardware',obj)
        ui.label(getattr(obj,'name',getattr(obj,'title','Quelle'))).classes('text-xl font-bold')
        show_sha_identity(obj.id)
        ui.label(getattr(obj,'description','') or getattr(obj,'text','')).classes('whitespace-pre-wrap')
        if type(obj).__name__ == 'EcadRequirement':
            ui.label('Akzeptanzkriterien: '+obj.acceptance_criteria).classes('whitespace-pre-wrap')
        from .object_properties import render_native_fields
        render_native_fields(package,obj)
        if hasattr(obj,'requirement_attributes'):
            from .property_schema import applicable
            for scope,title in [('requirement_attributes','Anforderung'),('realization_attributes','Realisierung')]:
                with ui.expansion(title,value=True).classes('w-full'):
                    for d in applicable(package.property_definitions,obj,scope):ui.label(d.label+': '+value_text(getattr(obj,scope).get(d.key),d.unit))
        legacy=getattr(obj,'attributes',{}).get('legacyPropertyValues',{})
        if legacy:
            with ui.expansion('Erhaltene Bestandswerte / bisherige Herkunft',value=False).classes('w-full'):
                for scope,values in legacy.items():
                    for key,value in values.items():ui.label(f'{scope} · {key}: {json.dumps(value,ensure_ascii=False)}').classes('text-xs break-all')
        ui.button('Schließen',on_click=dialog.close).props('flat')
    dialog.open()


def value_text(value, unit):
    if value is None or value=='' or value==[] or value=={}: return 'Offen'
    if isinstance(value,dict) and any(k in value for k in ('value','min','max')):
        unit = value.get('unit',unit)
        text = str(value['value']) if value.get('value') is not None else ' … '.join(str(value.get(k,'offen')) for k in ('min','max'))
    elif isinstance(value,(dict,list)): text = json.dumps(value,ensure_ascii=False)
    else: text = str(value)
    return text+((' '+unit) if unit else '')


def render_comparison(package, obj):
    rows = comparison_rows(package,obj)
    open_count = sum(r.status not in {'Passend','Abweichung'} for r in rows)
    mismatch = sum(r.status=='Abweichung' for r in rows)
    with ui.expansion(f'Technischer Vergleich · {len(rows)} Kennwerte · {open_count} offen · {mismatch} abweichend',icon='compare_arrows',value=False).classes('w-full border rounded'):
        if not rows:
            ui.label('Keine technischen Kennwerte aus zugeordneten Requirements oder Realisierungen.').classes('text-xs text-slate-500')
            return
        ui.label('Aktive Realisierungsvariante · Wertevergleich und Nachweisbewertung bleiben getrennt.').classes('text-xs text-slate-500')
        choice = ui.select(['Alle relevanten','Offen / prüfen','Abweichend'],value='Alle relevanten',label='Vergleich filtern').props('dense outlined').classes('w-full')
        table = ui.table(columns=[{'name':k,'label':v,'field':k,'align':'left'} for k,v in [('label','Kennwert'),('required','Soll'),('actual','Ist'),('status','Vergleich')]],
            rows=[],row_key='id',pagination=8).classes('w-full').props('dense wrap-cells')
        details = ui.column().classes('w-full gap-1')
        def refresh():
            table.rows = [{'id':i,'label':r.label,'required':value_text(r.required,r.unit),'actual':value_text(r.actual,r.unit),'status':r.status}
                for i,r in enumerate(rows) if choice.value=='Alle relevanten' or choice.value=='Abweichend' and r.status=='Abweichung'
                or choice.value=='Offen / prüfen' and r.status not in {'Passend','Abweichung'}]
            table.update(); details.clear()
        def select(event):
            row = next((v for v in event.args if isinstance(v,dict) and 'id' in v),None) if isinstance(event.args,list) else event.args
            if not row or 'id' not in row: return
            r = rows[int(row['id'])]; details.clear()
            with details:
                with ui.expansion(r.label+' · Quellen und Bedingungen',value=True).classes('w-full'):
                    for label,identifier in [('Requirement',r.requirement_id),('Realisierung',r.actual_id)]:
                        if label=='Requirement' and identifier and not package.find_requirement(identifier):label='Soll-Quelle'
                        if identifier: ui.button(label+' öffnen',on_click=lambda _,i=identifier:source_dialog(package,i)).props('flat dense no-caps')
                    if r.legacy: ui.label('Übernommener Bestandswert. Die bisherige Herkunft bleibt erhalten; Zuordnung fachlich prüfen.').classes('text-xs text-amber-800')
                    ui.label('Bedingungen: '+json.dumps(r.conditions,ensure_ascii=False)).classes('text-sm')
                    ui.label('Herkunft: '+(r.origin or 'Offen')+' · Revision: '+(r.revision or 'Offen')).classes('text-xs')
                    ui.label('Bewertung / Nachweis: '+r.evidence).classes('text-xs')
                    if r.rationale: ui.label(r.rationale).classes('text-sm')
                    for i in r.source_ids: ui.button('Quelle öffnen',on_click=lambda _,i=i:source_dialog(package,i)).props('flat dense')
                    if isinstance(r.required,(dict,list)): ui.label('Soll: '+json.dumps(r.required,ensure_ascii=False)).classes('text-xs break-all')
                    if isinstance(r.actual,(dict,list)): ui.label('Ist: '+json.dumps(r.actual,ensure_ascii=False)).classes('text-xs break-all')
        table.on('row-click',select); choice.on_value_change(lambda _:refresh()); refresh()


def render_architecture_details(package, obj, *, preferred='comparison', edit_object=None, _include_bus=True):
    from .netclasses import member_class
    from .requirement_graph import allocation_edges
    from .property_schema import applicable
    from .object_properties import render_native_fields
    render_native_fields(package,obj)
    for scope,title in [('requirement_attributes','Anforderungsattribute'),('realization_attributes','Realisierungsattribute')]:
        definitions=applicable(package.property_definitions,obj,scope)
        if not definitions:continue
        with ui.expansion(title,value=True).classes('w-full border rounded'):
            if preferred==scope:ui.badge('Aktiver Attributraum',color='blue-1').props('text-color=blue-9')
            for definition in definitions:
                value=getattr(obj,scope).get(definition.key)
                if definition.key=='ecadKey':value=ecad_key(obj)
                with ui.column().classes('w-full gap-0 border-b py-2'):
                    ui.label(definition.label+': '+value_text(value,definition.unit)).classes('text-sm break-all')
                    ui.label(definition.description).classes('text-xs text-slate-500')
    attached = connected_signal(package,obj)
    if type(obj).__name__=='InterfacePort':
        role = {'Host':'Host','Participant':'Teilnehmer'}.get(obj.role,'Offen')
        ui.label('Rolle: '+role+(' · aus Verbindungstopologie' if attached else ' · vorläufig')).classes('text-sm')
    if attached:
        if attached is not obj: ui.button('Netz / Bus: '+attached.name,on_click=lambda:source_dialog(package,attached.id)).props('flat dense no-caps')
        if edit_object:ui.button('Netzklasse bearbeiten',icon='edit',on_click=lambda:edit_object(attached.id)).props('outline dense no-caps')
        if type(obj).__name__=='Signal':
            ui.label('Wirksame Netzklasse: '+(', '.join(member_class(attached,obj)) or 'Offen')).classes('text-sm')
            if edit_object:ui.button('Mitglied bearbeiten',icon='edit',on_click=lambda:edit_object(obj.id)).props('outline dense no-caps')
        elif attached.bus_contents and _include_bus:
            effective = {tuple(member_class(attached,m)) for m in attached.bus_contents}
            summary = 'Gemischt' if len(effective)>1 else ', '.join(next(iter(effective),())) or 'Offen'
            ui.label('Netzklassen der Busmitglieder: '+summary).classes('text-sm')
            with ui.expansion('Businhalt / Mitgliedsdetails',value=False).classes('w-full border rounded'):
                for member in attached.bus_contents:
                    with ui.expansion(member.name+' · '+(', '.join(member_class(attached,member)) or 'Netzklasse offen'),value=False).classes('w-full').mark('member-details-'+member.id):
                        if member.description: ui.label(member.description).classes('text-xs')
                        ui.label('Eigene Klasse' if member_class(member) else 'Klasse vom Bus' if member_class(attached,member) else 'Klasse offen').classes('text-xs')
                        if edit_object:ui.button('Mitglied bearbeiten',icon='edit',on_click=lambda _,i=member.id:edit_object(i)).props('outline dense no-caps').mark('member-edit-'+member.id)
                        render_architecture_details(package,member,edit_object=edit_object,_include_bus=False)
        else: ui.label('Netzklasse: '+(', '.join(member_class(attached)) or 'Offen')).classes('text-sm')
    reqids = {r for r,_,i in allocation_edges(package) if i in {obj.id,attached.id if attached else obj.id}}
    actuals = actual_objects(package,obj)
    with ui.expansion(f'Zuordnungen · {len(reqids)} Requirements · {len(actuals)} Realisierungen',value=False).classes('w-full'):
        for req in package.requirements:
            if req.id in reqids: ui.button(req.title,on_click=lambda _,i=req.id:source_dialog(package,i)).props('flat dense no-caps')
        for actual in actuals: ui.button(actual.name,on_click=lambda _,i=actual.id:source_dialog(package,i)).props('flat dense no-caps')
    render_comparison(package,obj)
    from .integration import linked_interfaces
    for interface in linked_interfaces(package,obj.id):
        ui.button(interface.kind+' · '+interface.name,on_click=lambda _,i=interface.id:source_dialog(package,i)).props('flat dense no-caps')
