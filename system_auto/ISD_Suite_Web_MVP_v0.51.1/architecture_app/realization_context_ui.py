"""Architecture -> realization -> selected variant -> core parts, once per ID."""
from nicegui import ui
from .realization_service import core_component_ids
from .traceability import canonical_kind


def realization_context(package,realization):
    aes={realization.architecture_element_id} if realization.architecture_element_id else set()
    functions=[f for f in package.function_elements if f.discipline=='hardware' and
               (f.id==realization.function_element_id or realization.id in f.realization_ids)]
    for relation in package.model_relations:
        if relation.kind=='realized_by' and relation.target_id==realization.id:
            if canonical_kind(relation.source_type)=='ArchitectureElement':aes.add(relation.source_id)
            if canonical_kind(relation.source_type)=='FunctionElement':
                f=next((f for f in package.function_elements if f.id==relation.source_id and f.discipline=='hardware'),None)
                if f and f.id not in {v.id for v in functions}:functions.append(f)
    aes.update(f.architecture_element_id for f in functions if f.architecture_element_id)
    return sorted(aes),functions


def render_hardware_context(package,save,edit_realization,open_component,select_architecture,edit_fe,jump):
    p=package();groups={};seen=set()
    for r in p.technical_realizations:
        aes,functions=realization_context(p,r)
        key=next((identifier for identifier in aes if p.find_element(identifier)),None)
        groups.setdefault(key,[]).append((r,aes,functions))
    for identifier,entries in groups.items():
        owner=p.find_element(identifier) if identifier else None
        title=('Domäne '+owner[0].name+' · AE '+owner[1].name) if owner else 'Architekturzuordnung offen'
        with ui.expansion(title,value=True).classes('w-full border rounded p-2'):
            if owner:
                ui.button('Architekturbezug: '+owner[1].name,on_click=lambda _,i=identifier:jump(i)).props('flat no-caps')
                ui.label('Aufgabe: '+str(owner[1].requirement_attributes.get('function') or 'Offen')).classes('text-sm')
            for r,aes,functions in entries:
                seen.add(r.id)
                with ui.card().classes('w-full shadow-none border gap-2'):
                    ui.label('Realisiert: '+r.name).classes('text-lg font-semibold')
                    ui.label(r.generic_function or 'Funktionsbeschreibung: Offen').classes('text-sm')
                    ui.button('Realisierung bearbeiten',icon='edit',on_click=lambda _,obj=r:edit_realization(obj)).props('outline no-caps')
                    for other in aes:
                        found=p.find_element(other)
                        if found and other!=identifier:ui.button('Weiterer Architekturbezug: '+found[1].name,on_click=lambda _,i=other:jump(i)).props('flat dense no-caps')
                    for f in functions:
                        ui.button('Realisiert FE: '+f.name,on_click=lambda _,i=f.id:select_architecture(i) if select_architecture else None).props('flat no-caps')
                    selected=next((v for v in r.variants if v.id==r.selected_variant_id),None)
                    ui.label('Aktive Variante: '+(selected.name if selected else 'Offen')).classes('font-semibold text-sm')
                    with ui.expansion('Umsetzung und Varianten',value=False).classes('w-full border rounded'):
                        for v in r.variants:ui.label(('Aktiv · ' if v.id==r.selected_variant_id else 'Alternative · ')+v.name+' · '+v.status.value)
                        if not r.variants:ui.label('Varianten: Offen')
                        with ui.expansion('Systemdefinierende Bestandteile',value=False).classes('w-full border rounded'):
                            ids=core_component_ids(p,selected) if selected else set()
                            for c in p.components:
                                if c.id in ids:
                                    ui.button('Verwendet: '+c.name+' · '+(c.manufacturer_part_number or 'MPN offen'),on_click=lambda _,c=c:open_component(c) if open_component else None).props('flat no-caps')
                            if not ids:ui.label('Kernbauteile: Offen')
                    with ui.expansion('Requirements, Kennwerte und Nachweise',value=False).classes('w-full border rounded'):
                        for rid in r.requirement_ids:
                            req=p.find_requirement(rid)
                            if req:ui.label('Setzt um: '+req.identifier+' · '+req.title)
                        from .technical_values_ui import render_technical_values
                        render_technical_values(package,save,r)
    functions=[f for f in p.function_elements if f.discipline=='hardware' and not any(f.id==r.function_element_id or r.id in f.realization_ids for r in p.technical_realizations)]
    if functions:
        with ui.expansion('FE ohne konkrete Umsetzung',value=False).classes('w-full border rounded'):
            for f in functions:
                ui.label(f.name+' · Umsetzung: Offen')
                if edit_fe:ui.button('FE bearbeiten',on_click=lambda _,f=f:edit_fe(f)).props('outline no-caps')
    if not seen:ui.label('Noch keine technischen HW-Realisierungen angelegt.')
