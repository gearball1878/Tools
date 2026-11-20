"""Shared architecture views; HW remains the ECAD contract, allocations are explicit."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from html import escape
import re

from nicegui import ui

from .attribute_spaces import render_attribute_spaces
from .integration_ui import render_integration_panel
from .identity import show_sha_identity
from .models import ArchitectureAllocation, ArchitecturePackage, SystemDomain, SystemElement, SystemRelation, MechanicalArchitectureElement, SoftwareArchitectureElement, DisciplineRelation
from .discipline_architecture import elements as discipline_elements, RELATION_KINDS, discipline_svg, remove_element, adopt_realizations


def allocation_targets(package):
    return {
        **{('hw_element', e.id): e for d in package.domains for e in d.elements},
        **{('hw_realization', r.id): r for r in package.technical_realizations},
        **{('mechanical', c.id): c for c in package.mechanical_components},
        **{('software', c.id): c for c in package.software_components},
        **{('mechanical_element',c.id):c for c in package.mechanical_architecture_elements},
        **{('software_element',c.id):c for c in package.software_architecture_elements},
    }


def related_ids(package, selected):
    result = {selected} if selected else set()
    for a in package.architecture_allocations:
        if selected in {a.system_element_id, a.target_id}:
            result.update((a.system_element_id, a.target_id))
    return result


def system_svg(package, selected=None, kinds=None, collapsed=None):
    """Escaped SVG with selectable nodes, external boundary and typed edges."""
    kinds = set(['Information', 'Energie', 'Material', 'Abhängigkeit'] if kinds is None else kinds)
    collapsed = set(collapsed or [])
    domains = {d.id: d for d in package.system_domains}
    groups = [(d.name, d.id, [e for e in package.system_elements if e.domain_id == d.id and not e.external]) for d in package.system_domains]
    groups += [('Systemelemente', None, [e for e in package.system_elements if e.domain_id is None and not e.external]),
               ('Externe Systeme / Akteure', 'external', [e for e in package.system_elements if e.external])]
    groups = [(name, gid, items) for name, gid, items in groups if items or gid in domains]
    highlighted = related_ids(package, selected)
    pos = {}; blocks = []; backgrounds = []; y = 60; internal_bottom = None
    for title, gid, elements in groups:
        if gid == "external": internal_bottom = y - 12
        hidden = gid in collapsed
        height = 52 if hidden else 60 + max(1, (len(elements)+2)//3)*110
        color = domains[gid].color if gid in domains else '#64748B'
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color): color = '#2563EB'
        data = f' data-system-id="{escape(gid, quote=True)}"' if gid in domains else ''
        backgrounds.append(f'<g{data}><rect x="25" y="{y}" width="950" height="{height}" rx="12" fill="#f8fafc" stroke="{color}"/><text x="42" y="{y+28}" fill="{color}" font-size="17">{escape(title)}{" · eingeklappt" if hidden else ""}</text></g>')
        if not hidden:
            for i, e in enumerate(elements):
                x = 45+(i%3)*305; ey=y+48+(i//3)*110
                pos[e.id] = (x+140, ey+40)
                labels = sorted({{'hw_element':'HW', 'hw_realization':'HW', 'mechanical':'MECH', 'software':'SW/FW', 'mechanical_element':'MECH', 'software_element':'SW/FW'}[a.target_kind]
                                 for a in package.architecture_allocations if a.system_element_id == e.id})
                badge = 'Realisierung: ' + ', '.join(labels) if labels else 'Realisierung fehlt'
                if e.external: badge = 'Externer Bezug'
                stroke = '#f59e0b' if e.id in highlighted else color
                blocks.append(f'<g data-system-id="{escape(e.id, quote=True)}" style="cursor:pointer"><rect x="{x}" y="{ey}" width="280" height="82" rx="7" fill="white" stroke="{stroke}" stroke-width="{3 if e.id in highlighted else 1.5}"/><text x="{x+12}" y="{ey+23}" font-size="11" fill="#475569">Anforderung · Systemelement</text><text x="{x+12}" y="{ey+47}" font-size="15">{escape(e.name[:32])}</text><text x="{x+12}" y="{ey+67}" font-size="11" fill="#475569">{escape(badge)}</text><title>{escape(e.description)}</title></g>')
        y+=height+25
    lines=[]
    colors={'Information':'#2563eb','Energie':'#d97706','Material':'#0f9f77','Abhängigkeit':'#7c3aed'}
    for relation in package.system_relations:
        if relation.kind not in kinds or relation.source_id not in pos or relation.target_id not in pos: continue
        x1,y1=pos[relation.source_id]; x2,y2=pos[relation.target_id]
        lines.append(f'<g data-system-id="{escape(relation.id, quote=True)}" style="cursor:pointer"><path d="M{x1} {y1+43} L{x2} {y2-43}" stroke="{colors[relation.kind]}" stroke-width="{4 if relation.id == selected else 2}" fill="none" marker-end="url(#arrow)"/><text x="{(x1+x2)/2+5}" y="{(y1+y2)/2}" font-size="11" fill="{colors[relation.kind]}" stroke="white" stroke-width="3" paint-order="stroke">{escape(relation.name[:32])}</text><title>{escape(relation.kind+': '+relation.description)}</title></g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {max(y+15,240)}" style="width:100%;min-width:650px"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#475569"/></marker></defs><rect x="8" y="8" width="984" height="{max(internal_bottom or y,220)}" fill="white" stroke="#94a3b8" rx="14"/><text x="28" y="36" font-size="20">{escape(package.project.name)} · Systemarchitektur</text>{"".join(backgrounds+lines+blocks)}</svg>'


@dataclass
class ArchitectureViews:
    workspace: object
    navigator: object
    inspector: object
    hardware_realizations: object
    refresh: object
    is_hardware: object
    show_hardware: object
    attribute_space: object
    show_system: object
    current_discipline: object
    edit_object: object
    selected_object: object
    realization_navigator: object
    realization_inspector: object
    realization_selected: object
    realization_context: object
    realization_activate: object


def create_architecture_views(state, save, hw_canvas, hw_select, refresh_shell, open_hw_realization, ecad_dialog=None, open_discipline=None, open_requirement=None, open_component=None, open_fe=None, select_architecture=None, edit_component=None):
    view = {'discipline':'hardware', 'space':'comparison', 'selected':None, 'kinds':['Information','Energie','Material','Abhängigkeit']}
    collapsed = set()
    project_token = {'id': state.package.project.id}

    def package():
        if project_token['id'] != state.package.project.id:
            project_token['id'] = state.package.project.id
            view['selected'] = None; collapsed.clear()
        return state.package

    def apply(action, message):
        previous = state.package
        candidate = deepcopy(previous)
        try:
            action(candidate)
            state.package = ArchitecturePackage.model_validate(candidate.export_dict())
            if save(message) is False:
                state.package = previous; return False
            return True
        except ValueError as error:
            state.package = previous
            ui.notify(str(error), type='negative', close_button=True)
            return False

    def choose(identifier):
        view['selected'] = identifier
        refresh(); refresh_shell()

    def objects():
        p=package()
        if view['discipline']=='system':
            return [*p.system_domains,*p.system_elements,*p.system_relations,*allocation_targets(p).values()]
        return [*discipline_elements(p,view['discipline']),*(r for r in p.discipline_relations if r.discipline==view['discipline']),*(f for f in p.function_elements if f.discipline==view['discipline'])]

    def current():
        return next((o for o in objects() if o.id == view['selected']),None)

    def object_dialog(kind, obj=None):
        p=package()
        with ui.dialog() as dialog, ui.card().classes('w-[650px] max-w-[94vw] max-h-[90vh] overflow-auto'):
            from .help_ui import mask_help
            mask_help(dialog,'architecture',obj,mask='Systemobjekt bearbeiten')
            ui.label('Systemobjekt bearbeiten' if obj else 'Systemobjekt anlegen').classes('text-xl font-bold')
            name=ui.input('Name',value=obj.name if obj else '').classes('w-full')
            task=ui.textarea('Aufgabe / Verantwortung',value=obj.requirement_attributes.get('function') or '' if obj else '').classes('w-full')
            description=ui.textarea('Beschreibung',value=obj.description if obj else '').classes('w-full')
            if kind=='element':
                element_kind=ui.select(['Systemteil','Funktion','Schnittstelle'],value=obj.kind if obj else 'Systemteil',label='Elementtyp').classes('w-full')
                domain=ui.select({'':'Ohne Domäne',**{d.id:d.name for d in p.system_domains}},value=obj.domain_id or '' if obj else '',label='Systemdomäne').classes('w-full')
                external=ui.checkbox('Externes System / Akteur',value=obj.external if obj else False)
                requirements=ui.select({r.id:f'{r.identifier} · {r.title}' for r in p.requirements},value=obj.requirement_ids if obj else [],multiple=True,label='Anforderungen').props('use-chips').classes('w-full')
            if kind=='relation':
                options={e.id:e.name for e in p.system_elements}
                source=ui.select(options,value=obj.source_id if obj else None,label='Quelle').classes('w-full')
                target=ui.select(options,value=obj.target_id if obj else None,label='Ziel').classes('w-full')
                relation_kind=ui.select(['Information','Energie','Material','Abhängigkeit'],value=obj.kind if obj else 'Information',label='Beziehungstyp').classes('w-full')
            from .property_inputs import custom_inputs
            seed=obj or ({'domain':SystemDomain,'element':SystemElement,'relation':SystemRelation}[kind].model_construct(name=''))
            apply_custom=custom_inputs(p,seed,include_system=True,exclude_keys=('function',))
            def commit():
                def mutate(candidate):
                    if not (name.value or '').strip(): raise ValueError('Bitte einen Namen eingeben.')
                    data={'name':name.value.strip(),'description':description.value or ''}
                    if kind!='relation':data['requirement_attributes']={**(obj.requirement_attributes if obj else {}),'function':task.value or None}
                    if kind=='domain': cls=SystemDomain; collection=candidate.system_domains
                    elif kind=='element':
                        cls=SystemElement; collection=candidate.system_elements
                        data.update(kind=element_kind.value,domain_id=domain.value or None,external=external.value,requirement_ids=list(requirements.value or []))
                    else:
                        cls=SystemRelation; collection=candidate.system_relations
                        if not source.value or not target.value: raise ValueError('Quelle und Ziel auswählen.')
                        data.update(source_id=source.value,target_id=target.value,kind=relation_kind.value)
                    if obj:
                        item=next(i for i in collection if i.id==obj.id)
                        for k,v in data.items(): setattr(item,k,v)
                    else: item=cls(**data);collection.append(item)
                    apply_custom(item)
                if apply(mutate,'Systemarchitektur gespeichert'): dialog.close()
            ui.button('Speichern',on_click=commit)
            ui.button('Abbrechen',on_click=dialog.close).props('flat')
        dialog.open()

    def allocation_dialog(element):
        p=package(); targets=allocation_targets(p)
        old={a.target_kind+':'+a.target_id for a in p.architecture_allocations if a.system_element_id==element.id}
        labels={'hw_element':'HW-AE','hw_realization':'HW-Realisierung','mechanical':'Mechanik-Realisierung','software':'SW/FW-Realisierung',
                'mechanical_element':'Mechanik-Architektur','software_element':'SW/FW-Architektur'}
        with ui.dialog() as dialog, ui.card().classes('w-[750px] max-w-[94vw]'):
            ui.label(f'Realisierungen für {element.name}').classes('text-xl font-bold')
            selected=ui.select({k+':'+oid:f'{labels[k]} · {o.name}' for (k,oid),o in targets.items()},
                               value=sorted(old & {k+':'+oid for k,oid in targets}),multiple=True,label='Zugeordnete Objekte').props('use-chips use-input').classes('w-full')
            def commit():
                def mutate(candidate):
                    chosen=set(selected.value or [])
                    # Keep dangling associations until explicitly removed, so imported deletions remain reviewable.
                    candidate.architecture_allocations=[a for a in candidate.architecture_allocations if a.system_element_id!=element.id or a.target_kind+':'+a.target_id in chosen or (a.target_kind,a.target_id) not in targets]
                    existing={(a.target_kind,a.target_id) for a in candidate.architecture_allocations if a.system_element_id==element.id}
                    for key in chosen:
                        kind,oid=key.split(':',1)
                        if (kind,oid) not in existing:
                            candidate.architecture_allocations.append(ArchitectureAllocation(system_element_id=element.id,target_kind=kind,target_id=oid))
                if apply(mutate,'Realisierungszuordnungen gespeichert'): dialog.close()
            ui.button('Speichern',on_click=commit)
            ui.button('Abbrechen',on_click=dialog.close).props('flat')
        dialog.open()

    def discipline_dialog(obj=None,relation=False):
        p=package();discipline=getattr(obj,'discipline',view['discipline']);nodes=discipline_elements(p,discipline)
        cls=DisciplineRelation if relation else MechanicalArchitectureElement if discipline=='mechanical' else SoftwareArchitectureElement
        with ui.dialog() as dialog,ui.card().classes('w-[760px] max-w-[95vw] max-h-[92vh] overflow-auto p-6 gap-3'):
            from .help_ui import mask_help
            mask_help(dialog,'architecture',obj,mask='Facharchitekturobjekt bearbeiten')
            ui.label(('Beziehung' if relation else 'Architekturelement')+(' bearbeiten' if obj else ' anlegen')).classes('text-xl font-bold')
            ui.label('Mechanikarchitektur' if discipline=='mechanical' else 'Software-/Firmwarearchitektur').classes('text-sm text-slate-600')
            name=ui.input('Name',value=obj.name if obj else '').classes('w-full')
            task=ui.textarea('Aufgabe / Verantwortung',value=obj.requirement_attributes.get('function') or '' if obj else '').classes('w-full')
            description=ui.textarea('Beschreibung',value=obj.description if obj else '').props('autogrow').classes('w-full')
            if relation:
                options={n.id:n.name for n in nodes}
                source=ui.select(options,value=obj.source_id if obj else None,label='Quelle').classes('w-full')
                target=ui.select(options,value=obj.target_id if obj else None,label='Ziel').classes('w-full')
                kind=ui.select(RELATION_KINDS[discipline],value=obj.kind if obj else RELATION_KINDS[discipline][0],label='Beziehungstyp').classes('w-full')
            else:
                kind=ui.select(list(cls.model_fields['kind'].annotation.__args__),value=obj.kind if obj else cls.model_fields['kind'].default,label='Elementtyp').classes('w-full')
                parent=ui.select({n.id:n.name for n in nodes if not obj or n.id!=obj.id},value=obj.parent_id if obj else None,label='Übergeordnetes Element',clearable=True).classes('w-full')
                realizations=p.mechanical_components if discipline=='mechanical' else p.software_components
                realization=ui.select({n.id:n.name for n in realizations},value=[i for i in obj.realization_ids if i in {n.id for n in realizations}] if obj else [],label='Konkrete Realisierungen',multiple=True).props('use-chips use-input').classes('w-full')
            requirements=ui.select({r.id:f'{r.identifier} · {r.title}' for r in p.requirements},value=obj.requirement_ids if obj else [],label='Anforderungen',multiple=True).props('use-chips use-input').classes('w-full')
            systems=ui.select({e.id:e.name for e in p.system_elements},value=[a.system_element_id for a in p.architecture_allocations if obj and a.target_id==obj.id],label='Systemelemente',multiple=True).props('use-chips').classes('w-full') if not relation else None
            if obj:show_sha_identity(obj.id)
            from .property_inputs import custom_inputs
            seed=obj or cls.model_construct(name='',discipline=discipline)
            apply_custom=custom_inputs(p,seed,include_system=True,exclude_keys=('function',))
            def persist():
                def mutate(candidate):
                    data={'name':(name.value or '').strip(),'description':description.value or '', 'kind':kind.value,'requirement_ids':list(requirements.value or [])}
                    if not relation:data['requirement_attributes']={**(obj.requirement_attributes if obj else {}),'function':task.value or None}
                    if relation:data.update(discipline=discipline,source_id=source.value,target_id=target.value)
                    else:
                        # Preserve missing old realizations so their absence remains reviewable.
                        dangling=[i for i in obj.realization_ids if i not in {n.id for n in realizations}] if obj else []
                        data.update(parent_id=parent.value,realization_ids=list(realization.value or [])+dangling)
                    collection=candidate.discipline_relations if relation else discipline_elements(candidate,discipline)
                    if obj:
                        item=next(n for n in collection if n.id==obj.id)
                        for k,v in data.items():setattr(item,k,v)
                    else:item=cls(**data);collection.append(item)
                    apply_custom(item)
                    if systems is not None:
                        candidate.architecture_allocations=[a for a in candidate.architecture_allocations if a.target_id!=item.id]
                        for sid in systems.value or []:
                            candidate.architecture_allocations.append(ArchitectureAllocation(system_element_id=sid,target_kind=discipline+'_element',target_id=item.id))
                if apply(mutate,'Facharchitektur gespeichert'):
                    dialog.close();dialog.delete();refresh();refresh_shell()
            with ui.row().classes('w-full justify-end'):
                ui.button('Abbrechen',on_click=dialog.close).props('flat')
                ui.button('Speichern',on_click=persist,icon='save')
        dialog.open()

    def discipline_remove(obj):
        with ui.dialog() as dialog,ui.card():
            ui.label(f'„{obj.name}“ löschen?').classes('font-bold')
            ui.label('Architekturbeziehungen und Zuordnungen werden entfernt. Konkrete Realisierungen bleiben erhalten.')
            def persist():
                def mutate(candidate):
                    if isinstance(obj,DisciplineRelation):
                        candidate.discipline_relations=[r for r in candidate.discipline_relations if r.id!=obj.id]
                        candidate.model_relations=[r for r in candidate.model_relations if obj.id not in {r.source_id,r.target_id}]
                    else:remove_element(candidate,view['discipline'],obj.id)
                if apply(mutate,'Facharchitekturobjekt gelöscht'):
                    view['selected']=None;dialog.close();refresh();refresh_shell()
            ui.button('Abbrechen',on_click=dialog.close).props('flat')
            ui.button('Löschen',on_click=persist,color='negative')
        dialog.open()

    def remove(obj):
        with ui.dialog() as dialog, ui.card():
            ui.label(f'„{obj.name}“ löschen?')
            ui.label('Zugehörige Systembeziehungen und Zuordnungen werden entfernt; Realisierungsobjekte bleiben erhalten.')
            def commit():
                def mutate(p):
                    removed={obj.id}
                    if isinstance(obj,SystemDomain):
                        p.system_domains=[o for o in p.system_domains if o.id!=obj.id]
                        for e in p.system_elements:
                            if e.domain_id==obj.id:e.domain_id=None
                    elif isinstance(obj,SystemElement):
                        removed.update(r.id for r in p.system_relations if obj.id in {r.source_id,r.target_id})
                        p.system_elements=[o for o in p.system_elements if o.id!=obj.id]
                        p.system_relations=[o for o in p.system_relations if obj.id not in {o.source_id,o.target_id}]
                        p.architecture_allocations=[a for a in p.architecture_allocations if a.system_element_id!=obj.id]
                    else:p.system_relations=[o for o in p.system_relations if o.id!=obj.id]
                    p.model_relations=[r for r in p.model_relations if r.source_id not in removed and r.target_id not in removed]
                    p.requirement_links=[r for r in p.requirement_links if r.target_id not in removed]
                if apply(mutate,'Systemobjekt gelöscht'): view['selected']=None;dialog.close()
            ui.button('Löschen',on_click=commit).props('color=negative')
            ui.button('Abbrechen',on_click=dialog.close).props('flat')
        dialog.open()

    @ui.refreshable
    def workspace():
        p=package()
        with ui.row().classes('w-full items-center gap-3 p-3 bg-white border-b flex-wrap'):
            def change_discipline(event):
                view['discipline']=event.value;view['selected']=None;refresh();refresh_shell()
            ui.select({'system':'Systemarchitektur','hardware':'Hardware / ECAD','mechanical':'Mechanik / CAD','software':'Software / Firmware'},
                      value=view['discipline'],label='Architektursicht',on_change=change_discipline).classes('w-64')
            def change_space(event):
                view['space']=event.value;refresh();refresh_shell()
            ui.toggle({'requirement_attributes':'Anforderung','realization_attributes':'Realisierung','comparison':'Vergleich'},
                      value=view['space'],on_change=change_space).props('no-caps')
        if view['discipline']=='hardware':
            if view['space']!='requirement_attributes' and p.function_elements:
                with ui.expansion('Funktions Elemente (FE) · funktionale Architektur',icon='widgets',value=True).classes('w-full px-4 border-b'):
                    for fe in (f for f in p.function_elements if f.discipline=='hardware'):
                        with ui.card().classes('w-full shadow-none border p-3'):
                            ui.button(fe.name,icon='widgets',on_click=lambda _,oid=fe.id:select_architecture(oid) if select_architecture else None).props('flat no-caps')
                            ui.label(fe.description or 'Funktionsbeschreibung offen.').classes('text-sm')
                            names=[s.name for s in p.signals if s.id in fe.interface_signal_ids]
                            ui.label('Schnittstellen: '+(', '.join(names) or 'Offen')).classes('text-xs')
                            ui.label('Abhängigkeiten: '+(', '.join(f.name for f in p.function_elements if f.id in fe.dependency_ids) or 'Keine angegeben')).classes('text-xs')
            render_integration_panel(package,save,'hardware')
            hw_canvas();return
        with ui.column().classes('w-full p-4 gap-3'):
            render_integration_panel(package,save,view['discipline'])
            if view['discipline']=='system':
                with ui.row().classes('flex-wrap'):
                    ui.button('Domäne',icon='add',on_click=lambda:object_dialog('domain')).props('outline no-caps')
                    ui.button('Systemelement',icon='add',on_click=lambda:object_dialog('element')).props('outline no-caps')
                    ui.button('Schnittstelle / Beziehung',icon='add_link',on_click=lambda:object_dialog('relation')).props('outline no-caps')
                    def change_kinds(e):view['kinds']=e.value;workspace.refresh()
                    ui.select(['Information','Energie','Material','Abhängigkeit'],value=view['kinds'],multiple=True,label='Verbindungen',on_change=change_kinds).props('use-chips').classes('grow')
                if not p.system_elements:
                    ui.label('Systemelemente anlegen und vorhandene HW-, Mechanik- und SW/FW-Objekte zuordnen. Die HW-Architektur bleibt eigenständig.').classes('text-slate-600')
                if view['space'] != 'realization_attributes':
                    with ui.scroll_area().classes('w-full h-[55vh]'):
                        ui.html(system_svg(p,view['selected'],view['kinds'],collapsed),sanitize=False).classes('w-full').on('click',
                            lambda e: choose(e.args['id']) if isinstance(e.args, dict) and e.args.get('id') else None,
                            js_handler="(event) => emit({id: event.target.closest('[data-system-id]')?.dataset.systemId || ''})")
                if view['space'] != 'requirement_attributes':
                    targets = allocation_targets(p)
                    selected_systems = related_ids(p, view['selected']) if view['selected'] else {e.id for e in p.system_elements}
                    ui.label('Realisierung · zugeordnete technische Objekte').classes('font-semibold')
                    for element in p.system_elements:
                        if element.id not in selected_systems or element.external: continue
                        with ui.card().classes('w-full'):
                            ui.button('Anforderung: '+element.name, icon='fact_check', on_click=lambda _, oid=element.id: choose(oid)).props('flat no-caps')
                            allocations = [a for a in p.architecture_allocations if a.system_element_id == element.id]
                            if not allocations: ui.label('Realisierung fehlt').classes('text-amber-800')
                            for a in allocations:
                                target = targets.get((a.target_kind, a.target_id))
                                if target:
                                    ui.button('Realisierung: '+target.name, icon='build', on_click=lambda _, oid=target.id: choose(oid)).props('outline no-caps')
                                else: ui.label('Realisierungsobjekt fehlt · '+a.target_id).classes('text-red-700 break-all')
            else:
                with ui.row().classes('w-full flex-wrap gap-3'):
                    ui.button('Element hinzufügen',icon='add',on_click=lambda:discipline_dialog()).props('no-caps')
                    if open_fe:ui.button('Funktions Element anlegen',icon='widgets',on_click=lambda:open_fe(None)).props('outline no-caps')
                    ui.button('Beziehung hinzufügen',icon='add_link',on_click=lambda:discipline_dialog(relation=True)).props('outline no-caps')
                    def adopt():
                        if apply(lambda c:adopt_realizations(c,view['discipline']),'Architekturelemente aus Realisierungen übernommen'):refresh();refresh_shell()
                    ui.button('Aus Realisierungen übernehmen',icon='content_copy',on_click=adopt).props('flat no-caps').tooltip('Eigenständige Architekturelemente mit Verweis auf vorhandene Realisierungen anlegen')
                if view['space']!='realization_attributes':
                    with ui.scroll_area().classes('w-full h-[48vh]'):
                        ui.html(discipline_svg(p,view['discipline'],view['selected']),sanitize=False).classes('w-full').on('click',
                            lambda e:choose(e.args['id']) if isinstance(e.args,dict) and e.args.get('id') else None,
                            js_handler="(event) => emit({id: event.target.closest('[data-system-id]')?.dataset.systemId || ''})")
                ui.label('Architekturelemente und Beziehungen').classes('font-semibold')
                for obj in objects():
                    with ui.card().classes('w-full '+('border-2 border-amber-500' if obj.id in related_ids(p,view['selected']) else '')):
                        ui.button(obj.name,icon='build',on_click=lambda _,oid=obj.id:choose(oid)).props('flat no-caps')
                        ui.label('Beziehung' if isinstance(obj,DisciplineRelation) else 'Funktions Element' if type(obj).__name__=='FunctionElement' else 'Architekturelement').classes('text-xs text-teal-700')
                        ui.label(obj.description).classes('text-sm')
                        parent = next((n for n in objects() if n.id == getattr(obj,'parent_id',None)), None)
                        if parent: ui.label('Übergeordnet: '+parent.name).classes('text-sm')
                        names=[e.name for a in p.architecture_allocations if a.target_id==obj.id for e in p.system_elements if e.id==a.system_element_id]
                        ui.label('Systembezug: '+(', '.join(names) or 'noch nicht zugeordnet')).classes('text-sm')
                        if view['space']!='requirement_attributes' and not isinstance(obj,DisciplineRelation):
                            realizations=p.mechanical_components if view['discipline']=='mechanical' else p.software_components
                            for rid in obj.realization_ids:
                                real=next((n for n in realizations if n.id==rid),None)
                                if real and open_discipline:ui.button('Realisierung: '+real.name,on_click=lambda _,rid=rid:open_discipline(view['discipline'],rid)).props('outline no-caps')
                                elif not real:ui.label('Realisierungsobjekt fehlt: '+rid).classes('text-red-700')
                            if not obj.realization_ids:ui.label('Realisierungszuordnung offen').classes('text-amber-800')
                if not objects():ui.label('Hier Elemente anlegen und bei Bedarf vorhandene Realisierungen zuordnen.')

    @ui.refreshable
    def navigator():
        ui.label('Architektur · '+({'system':'System','hardware':'HW','mechanical':'Mechanik','software':'SW/FW'}[view['discipline']])).classes('font-semibold')
        ui.label({'requirement_attributes':'Anforderung','realization_attributes':'Realisierung','comparison':'Vergleich'}[view['space']]).classes('text-sm')
        for obj in objects():
            is_system = isinstance(obj, (SystemDomain, SystemElement, SystemRelation))
            if view['discipline']=='system' and view['space']=='requirement_attributes' and not is_system: continue
            if view['discipline']=='system' and view['space']=='realization_attributes' and is_system: continue
            ui.button(obj.name,icon='fact_check' if is_system else 'build',on_click=lambda _,oid=obj.id:choose(oid)).props('flat dense no-caps align=left').classes('w-full')

    @ui.refreshable
    def inspector():
        obj=current()
        if not obj:ui.label('Architekturobjekt auswählen.').classes('text-slate-500');return
        ui.label(obj.name).classes('text-xl font-bold break-words')
        ui.label('Systemarchitektur' if isinstance(obj, (SystemDomain, SystemElement, SystemRelation)) else 'Facharchitektur' if isinstance(obj,(MechanicalArchitectureElement,SoftwareArchitectureElement,DisciplineRelation)) else 'Funktions Element' if type(obj).__name__=='FunctionElement' else 'Realisierung').classes('text-sm font-semibold')
        show_sha_identity(obj.id)
        if open_discipline and not isinstance(obj, (SystemDomain, SystemElement, SystemRelation)):
            kind = next((kind for (kind, oid) in allocation_targets(package()) if oid == obj.id), None)
            if kind == 'hw_element':
                ui.button('In Hardwarearchitektur öffnen',icon='open_in_new',on_click=lambda:hw_select(obj.id)).props('outline no-caps')
            elif kind == 'hw_realization':
                ui.button('Realisierung bearbeiten',icon='edit',on_click=lambda:open_hw_realization(obj)).props('outline no-caps')
            elif kind in {'mechanical','software'}:
                ui.button('Im Realisierungsreiter öffnen',icon='open_in_new',on_click=lambda:open_discipline(kind,obj.id)).props('outline no-caps')
        ui.label(obj.description).classes('text-sm')
        if isinstance(obj,(SystemDomain,SystemElement,SystemRelation)):
            kind='domain' if isinstance(obj,SystemDomain) else 'element' if isinstance(obj,SystemElement) else 'relation'
            ui.button('Bearbeiten',icon='edit',on_click=lambda:object_dialog(kind,obj)).props('outline no-caps')
            ui.button('Löschen',icon='delete_outline',on_click=lambda:remove(obj)).props('flat color=negative no-caps')
        if isinstance(obj,(MechanicalArchitectureElement,SoftwareArchitectureElement,DisciplineRelation)):
            ui.label('Facharchitektur · Anforderung und Realisierung').classes('font-semibold text-sm')
            ui.button('Bearbeiten',icon='edit',on_click=lambda:discipline_dialog(obj,isinstance(obj,DisciplineRelation))).props('outline no-caps')
            ui.button('Löschen',icon='delete_outline',on_click=lambda:discipline_remove(obj)).props('flat color=negative no-caps')
        if type(obj).__name__=='FunctionElement' and open_fe:ui.button('FE bearbeiten',icon='edit',on_click=lambda:open_fe(obj)).props('outline no-caps')
        if isinstance(obj,SystemDomain):
            def toggle():
                if obj.id in collapsed:collapsed.remove(obj.id)
                else:collapsed.add(obj.id)
                workspace.refresh()
            ui.button('Aufklappen / Einklappen',on_click=toggle).props('flat no-caps')
        if isinstance(obj,SystemElement):
            ui.button('Realisierungen zuordnen',icon='link',on_click=lambda:allocation_dialog(obj)).props('outline no-caps')
            if not obj.requirement_ids: ui.label('Anforderungsbezug offen').classes('text-amber-800 text-sm')
            for rid in obj.requirement_ids:
                req=next((r for r in package().requirements if r.id==rid),None)
                if req:
                    if open_requirement: ui.button('Anforderung: '+req.title,on_click=lambda _,rid=req.id:open_requirement(rid)).props('flat dense no-caps')
                    else: ui.label('Anforderung: '+req.title).classes('text-sm')
        targets=allocation_targets(package())
        for a in package().architecture_allocations:
            if obj.id not in {a.system_element_id,a.target_id}:continue
            target=targets.get((a.target_kind,a.target_id))
            system=next((e for e in package().system_elements if e.id==a.system_element_id),None)
            ui.label(f'{system.name if system else "Systemelement fehlt"} → {target.name if target else "Realisierungsobjekt fehlt"}').classes('text-sm '+('text-red-700' if not target else ''))
            if target and a.target_kind=='hw_element':
                def jump(_,oid=target.id):
                    view['discipline']='hardware';refresh();refresh_shell();hw_select(oid)
                ui.button('HW-AE anzeigen',on_click=jump).props('flat dense no-caps')
            def unassign(_,aid=a.id):apply(lambda p:setattr(p,'architecture_allocations',[x for x in p.architecture_allocations if x.id!=aid]),'Zuordnung entfernt')
            ui.button('Zuordnung entfernen',on_click=unassign).props('flat dense no-caps')
        render_attribute_spaces(obj,save,view['space'],package())

    from .realization_focus_ui import create_realization_focus
    def focus_jump(identifier): show_hardware(); hw_select(identifier)
    focus_views = create_realization_focus(package, save, refresh_shell, open_hw_realization,
        edit_component, open_fe, open_requirement, focus_jump, open_component, ecad_dialog)

    @ui.refreshable
    def hardware_realizations():
        with ui.column().classes('w-full p-4 gap-3'):
            with ui.row().classes('items-center w-full'):
                ui.label('HW / ECAD · Realisierungen').classes('text-2xl font-bold grow')
                if open_fe:ui.button('Funktions Element anlegen',icon='widgets',on_click=lambda:open_fe(None)).props('no-caps')
                ui.button('Implementierung anlegen',icon='add',on_click=lambda:open_hw_realization(None)).props('outline no-caps')
                ui.button('Hardwarearchitektur anzeigen', icon='account_tree', on_click=lambda:hw_select(None)).props('outline no-caps')
                if ecad_dialog: ui.button('ECAD Annotation',icon='sync',on_click=ecad_dialog).props('outline no-caps')
                if edit_component:ui.button('Kernbauteil anlegen',icon='memory',on_click=lambda:edit_component(None)).props('outline no-caps')
                if edit_component and package().components:
                    def classify_existing():
                        with ui.dialog() as dialog,ui.card().classes('w-[800px] max-w-[95vw] p-5 gap-3'):
                            ui.label('Vorhandenes Bauteil zuordnen').classes('text-xl font-bold')
                            choice=ui.select({c.id:c.name+' · '+(c.manufacturer_part_number or 'MPN offen') for c in package().components},label='Bauteil aus Projektkatalog').props('use-input clearable').classes('w-full')
                            def edit():
                                component=package().find_component(choice.value or '')
                                if component:dialog.close();edit_component(component)
                            ui.button('Einordnung und Eigenschaften bearbeiten',icon='edit',on_click=edit).props('no-caps')
                            ui.button('Schließen',on_click=dialog.close).props('flat')
                        dialog.open()
                    ui.button('Bauteil aus Katalog',icon='manage_search',on_click=classify_existing).props('outline no-caps')
            focus_views['workspace']()
            with ui.expansion('Disziplinübergreifende Schnittstellen',value=False).classes('w-full'):
                render_integration_panel(package,save,'hardware')

    def refresh(*, include_details: bool = True):
        workspace.refresh()
        hardware_realizations.refresh()
        if include_details:
            navigator.refresh()
            inspector.refresh()

    def show_hardware():view['discipline']='hardware';refresh();refresh_shell()
    def show_system(object_id=None):view['discipline']='system';view['selected']=object_id;refresh();refresh_shell()
    def edit_object(identifier):
        from .architecture_editing import find_architecture_object
        obj=find_architecture_object(package(),identifier)
        if isinstance(obj,(SystemDomain,SystemElement,SystemRelation)):
            object_dialog('domain' if isinstance(obj,SystemDomain) else 'element' if isinstance(obj,SystemElement) else 'relation',obj)
        elif isinstance(obj,(MechanicalArchitectureElement,SoftwareArchitectureElement,DisciplineRelation)):
            discipline_dialog(obj,isinstance(obj,DisciplineRelation))
        elif type(obj).__name__=='FunctionElement' and open_fe:open_fe(obj)
    return ArchitectureViews(workspace,navigator,inspector,hardware_realizations,refresh,
                             lambda:view['discipline']=='hardware',show_hardware,lambda:view['space'],show_system,lambda:view['discipline'],edit_object,current,
                             focus_views['navigator'],focus_views['inspector'],focus_views['selected_object'],focus_views['context'],focus_views['activate'])
