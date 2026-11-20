"""A persistent selection with context-specific lists and a right-hand inspector."""
from nicegui import ui
from .realization_focus import CONTEXTS, RealizationFocus, focus_objects, focus_projection, scope_options, direct_requirements
from .identity import show_sha_identity


def create_realization_focus(package, save, refresh_shell, edit_realization, edit_component,
                             edit_fe, open_requirement, jump, component_details, ecad_dialog):
    focus = RealizationFocus()

    def current():
        focus.reconcile(package())
        return focus_objects(package()).get(focus.selected_id)

    def refresh():
        workspace.refresh()
        refresh_shell()

    def select(identifier):
        focus.select(identifier, package())
        refresh()

    def rows():
        focus.reconcile(package())
        data = focus_projection(package(), focus.scope_id, focus.focus_id)
        values = data['realizations'] if focus.context == 'ecad' else data[focus.context]
        query = focus.query.casefold().strip()
        return [o for o in values if not query or query in ' '.join(str(getattr(o, key, ''))
                for key in ('name', 'title', 'identifier', 'manufacturer', 'manufacturer_part_number')).casefold()]

    def name(obj):
        return getattr(obj, 'name', getattr(obj, 'title', 'Objekt'))

    def kind(obj):
        return {'Domain': 'Domäne', 'ArchitectureElement': 'AE', 'FunctionElement': 'FE',
                'TechnicalRealization': 'Implementierung', 'DesignComponent': 'Bauteil', 'EcadRequirement': 'Requirement'}.get(type(obj).__name__, type(obj).__name__)

    def value(title, text):
        ui.label(title).classes('text-xs text-slate-500')
        ui.label(str(text or 'Offen')).classes('text-sm break-words')

    def related_button(obj, prefix=''):
        ui.button(prefix + name(obj), on_click=lambda _, i=obj.id: select(i)).props('flat dense no-caps').classes('w-full justify-start')

    @ui.refreshable
    def workspace():
        p = package(); focus.reconcile(p)
        with ui.row().classes('w-full items-center gap-3'):
            ui.select(CONTEXTS, value=focus.context, label='Kontext', on_change=lambda e: (focus.change_context(e.value), refresh())).classes('w-48')
            ui.select(scope_options(p), value=focus.scope_id or '', label='Architekturbezug',
                      on_change=lambda e: (setattr(focus, 'scope_id', e.value or None), setattr(focus, 'focus_id', None), refresh())).props('use-input').classes('grow')
            ui.input('Im Kontext suchen', value=focus.query, on_change=lambda e: (setattr(focus, 'query', e.value or ''), refresh())).props('clearable').classes('w-64')
        if focus.focus_id:
            ui.button('Fokus zurücksetzen', on_click=lambda: (setattr(focus, 'focus_id', None), refresh())).props('flat dense no-caps')
        obj = current()
        ui.label('Auswahl: ' + (kind(obj) + ' · ' + name(obj) if obj else 'Offen') + ' · Details rechts').classes('text-sm text-slate-600')
        projection = focus_projection(p, focus.scope_id, focus.focus_id)
        objects = focus_objects(p)
        if focus.focus_id in objects:
            ui.label('Fokus: ' + name(objects[focus.focus_id])).classes('font-semibold text-teal-800')
        ui.label('Gemeinsamer Realisierungsbezug · Kontext bestimmt die Darstellung; Requirements sind direkt zugeordnet.').classes('text-xs text-slate-500')

        def render_section(context):
            visible = projection['realizations'] if context == 'ecad' else projection[context]
            query = focus.query.casefold().strip()
            visible = [o for o in visible if not query or query in ' '.join(str(getattr(o, key, '')) for key in
                       ('name', 'title', 'identifier', 'manufacturer', 'manufacturer_part_number')).casefold()]
            if context == 'parts':
                ui.label('Part View · Systembestimmende Bauteile').classes('text-xl font-semibold')
                columns = [{'name': k, 'label': label, 'field': k, 'align': 'left', 'sortable': True} for k, label in
                           [('name', 'Bauteil'), ('manufacturer', 'Hersteller'), ('mpn', 'MPN'), ('revision', 'Revision'), ('owner', 'AE / FE'), ('documents', 'Dokumente')]]
                part_projection = projection
                values = []
                for c in visible:
                    owner_ids = part_projection['owners'].get(c.id, set())
                    real_ids = part_projection['part_realizations'].get(c.id, set())
                    fe_ids = {i for r in real_ids for i in part_projection['realization_functions'].get(r, set())}
                    sources = [s for s in p.technical_sources if s.owner_id == c.id]
                    values.append({'id': c.id, 'name': c.name, 'manufacturer': c.manufacturer or 'Offen',
                                   'mpn': c.manufacturer_part_number or 'Offen', 'revision': c.part_revision or 'Offen',
                                   'owner': ', '.join(name(objects[i]) for i in sorted(owner_ids | fe_ids) if i in objects) or 'Zuordnung offen',
                                   'documents': ', '.join(s.title + ' · ' + (s.revision or 'Revision offen') for s in sources) or 'Offen'})
                table = ui.table(columns=columns, rows=values, row_key='id', selection='single',
                                 on_select=lambda e: select(e.selection[0]['id']) if e.selection else None,
                                 pagination=20).props('wrap-cells dense').classes('w-full max-w-full overflow-auto')
                table.selected = [r for r in values if r['id'] == focus.selected_id]
                ui.label('Eine Zeile auswählen. Die vollständige BOM bleibt über die ECAD-Anbindung verfügbar.').classes('text-xs text-slate-500')
            elif context == 'ecad':
                binding = p.properties.get('ecadConnectors', {}).get('kicad', {})
                value('Verknüpftes KiCad-Projekt', binding.get('projectPath'))
                if ecad_dialog: ui.button('ECAD Annotation', icon='sync', on_click=ecad_dialog).props('outline no-caps')
                for f in p.function_elements:
                    if f in projection['architecture']:
                        with ui.card().classes('w-full border shadow-none p-3'):
                            related_button(f, 'FE · ')
                            value('Schaltplanbezug', ' · '.join(v for v in [f.source_project, f.source_sheet, f.source_block_uuid, f.source_revision] if v))
                with ui.expansion('Implementierungen / Variantencontainer',value=False).classes('w-full border rounded'):
                    for obj in visible: related_button(obj, 'Implementierung · ')
            else:
                for obj in visible:
                    with ui.card().classes('w-full shadow-none border p-3 gap-1'):
                        related_button(obj, kind(obj) + ' · ')
                        ui.label(getattr(obj, 'description', '') or getattr(obj, 'text', '') or 'Beschreibung offen').classes('text-sm')
                if context == 'architecture':
                    with ui.expansion('Implementierungen / Variantencontainer', value=False).classes('w-full border rounded'):
                        for obj in projection['realizations']: related_button(obj)
            if not visible: ui.label('Keine passenden Objekte in diesem Kontext.').classes('text-sm text-slate-500')
    
        order = [focus.context] + [c for c in CONTEXTS if c != focus.context]
        for context in order:
            title = {'architecture': 'Architekturbezug', 'parts': 'Parts · Kernbauteile',
                     'requirements': 'Direkt verknüpfte Requirements', 'ecad': 'ECAD-Bezug'}[context]
            with ui.expansion(title, value=context == focus.context).classes('w-full border rounded'):
                render_section(context)

    def navigator():
        ui.label('HW / ECAD · ' + CONTEXTS[focus.context]).classes('font-semibold p-4')
        for obj in rows(): related_button(obj, kind(obj) + ' · ')
        if not rows(): ui.label('Keine passenden Objekte.').classes('p-4 text-sm')

    def inspector():
        p = package(); obj = current()
        with ui.column().classes('w-full p-4 gap-3'):
            ui.label('Details').classes('text-xl font-semibold')
            if obj is None:
                ui.label('Ein Objekt im gewählten Kontext auswählen.'); return
            ui.label(kind(obj) + ' · ' + name(obj)).classes('text-lg font-semibold')
            show_sha_identity(obj.id)
            value('Beschreibung', getattr(obj, 'description', '') or getattr(obj, 'generic_function', ''))
            object_kind = type(obj).__name__
            if object_kind == 'DesignComponent':
                for title, text in [('Hersteller', obj.manufacturer), ('MPN', obj.manufacturer_part_number),
                                    ('Bauteilrevision', obj.part_revision), ('Gehäuse', obj.package_name),
                                    ('Systembeitrag', obj.system_defining_reason)]: value(title, text)
                if edit_component: ui.button('Bauteil bearbeiten', icon='edit', on_click=lambda: edit_component(obj)).props('outline no-caps')
                projection = focus_projection(p); objects = focus_objects(p)
                with ui.expansion('Architektur und Realisierungen', value=True).classes('w-full border rounded'):
                    identifiers = projection['owners'].get(obj.id, set()) | projection['part_realizations'].get(obj.id, set())
                    for identifier in sorted(identifiers):
                        if identifier in objects: related_button(objects[identifier])
                    if not identifiers: ui.label('Zuordnung offen')
                with ui.expansion('Alternativen', value=False).classes('w-full border rounded'):
                    for identifier in obj.alternative_component_ids:
                        c = p.find_component(identifier)
                        if c: related_button(c, (c.manufacturer_part_number or 'MPN offen') + ' · ')
                    if not obj.alternative_component_ids: ui.label('Offen')
                with ui.expansion('Datenblätter / Application Notes / PLM / ERP', value=True).classes('w-full border rounded'):
                    sources = [s for s in p.technical_sources if s.owner_id == obj.id]
                    for source in sources:
                        value(source.title, ' · '.join([source.source_type.value, source.channel.value, source.revision or 'Revision offen', source.status.value]))
                        if source.url.startswith(('https://', 'http://')): ui.link('Dokument öffnen', source.url, new_tab=True)
                        if source.external_reference: value('Externe Referenz', source.external_reference)
                        if source.provider: value('Anbieter', source.provider)
                    if not sources: ui.label('Offen')
                from .realization_service import standard_comparison
                with ui.expansion('Normen und Standards', value=False).classes('w-full border rounded'):
                    claims = standard_comparison(p, obj)
                    for claim in claims:
                        value(claim['designation'] + ' · ' + (claim['edition'] or 'Ausgabe offen'), claim['result'])
                        value('Geltungsbereich', claim['scope'])
                        if claim['gap']: ui.label(claim['gap']).classes('text-xs text-amber-800')
                    if not claims: ui.label('Offen')
                if component_details: ui.button('Dokumente und Qualifikation verwalten', on_click=lambda: component_details(obj)).props('flat no-caps')
            elif object_kind == 'TechnicalRealization':
                projection = focus_projection(p)
                objects = focus_objects(p)
                for identifier in sorted(projection['realization_owners'].get(obj.id, set()) | projection['realization_functions'].get(obj.id, set())):
                    if identifier in objects: related_button(objects[identifier], 'Architektur · ')
                if edit_realization: ui.button('Realisierung bearbeiten', icon='edit', on_click=lambda: edit_realization(obj)).props('outline no-caps')
                value('Status', obj.status.value)
                active = next((v for v in obj.variants if v.id == obj.selected_variant_id), None)
                value('Aktive Variante', active.name if active else '')
                from .realization_service import core_component_ids
                for c in p.components:
                    if active and c.id in core_component_ids(p, active): related_button(c, 'Bauteil · ')
            elif object_kind == 'FunctionElement':
                if edit_fe: ui.button('FE bearbeiten', icon='edit', on_click=lambda: edit_fe(obj)).props('outline no-caps')
                value('ECAD-Projekt / Blatt / Revision', ' · '.join(v for v in [obj.source_project, obj.source_sheet, obj.source_revision] if v))
                with ui.expansion('Implementierungen und aktive Varianten',value=False).classes('w-full border rounded'):
                    for r in p.technical_realizations:
                        if r.id not in obj.realization_ids and r.function_element_id!=obj.id:continue
                        related_button(r,'Implementierung · ')
                        if edit_realization:ui.button('Implementierung bearbeiten',on_click=lambda _,r=r:edit_realization(r)).props('outline dense no-caps')
                        selected=next((v for v in r.variants if v.id==r.selected_variant_id),None)
                        value('Aktive Variante',selected.name if selected else '')
                        value('Status',r.status.value)
                    if not obj.realization_ids and not any(r.function_element_id==obj.id for r in p.technical_realizations):ui.label('Implementierung: Offen')
            elif object_kind == 'EcadRequirement':
                from .requirements_service import requirement_traceability_status
                from .requirements_presentation import COVERAGE_LABELS
                trace = requirement_traceability_status(p, obj)
                value('Abdeckung', COVERAGE_LABELS.get(trace.coverage.value, trace.coverage.value))
                value('Verifikation', trace.verification.value)
                value('Kennung', obj.identifier)
                value('Aussage', obj.text)
                if open_requirement: ui.button('Requirement anzeigen', on_click=lambda: open_requirement(obj.id)).props('outline no-caps')
            else:
                if jump: ui.button('In Hardwarearchitektur anzeigen', on_click=lambda: jump(obj.id)).props('outline no-caps')
            if object_kind in {'Domain', 'ArchitectureElement', 'FunctionElement'}:
                projected = focus_projection(p, obj.id)
                with ui.expansion('Implementierungen und Kernbauteile', value=False).classes('w-full border rounded'):
                    for r in projected['realizations']: related_button(r, 'Implementierung · ')
                    for c in projected['parts']: related_button(c, (c.manufacturer_part_number or 'MPN offen') + ' · ')
                    if not projected['realizations'] and not projected['parts']: ui.label('Umsetzung offen')
            with ui.expansion('Requirements und Abhängigkeiten', value=False).classes('w-full border rounded'):
                target_ids={obj.id}
                if object_kind=='FunctionElement':target_ids.update(r.id for r in p.technical_realizations if r.id in obj.realization_ids or r.function_element_id==obj.id)
                identifiers = {r.id for r in direct_requirements(p, target_ids)}
                for identifier in sorted(identifiers):
                    requirement = p.find_requirement(identifier)
                    if requirement: related_button(requirement, requirement.identifier + ' · ')
                if not identifiers: ui.label('Requirements: Offen')
            if hasattr(obj, 'requirement_attributes'):
                from .attribute_spaces import render_attribute_spaces
                with ui.expansion('Objektattribute', value=True).classes('w-full border rounded'):
                    render_attribute_spaces(obj, save, package=p)

    def activate(identifier=None):
        focus.reconcile(package())
        if identifier in scope_options(package()):
            focus.scope_id = identifier
            focus.selected_id = identifier
            focus.focus_id = identifier
        workspace.refresh()

    return {'activate': activate, 'workspace': workspace, 'navigator': navigator, 'inspector': inspector,
            'selected_object': current, 'context': lambda: CONTEXTS[focus.context], 'focus': focus, 'refresh': refresh}
