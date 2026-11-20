"""A focused complete chain from sources to architecture and evidence."""
from .traceability import trace_path, project_objects, evidence_status, verification_current, canonical_kind
from .requirements_layers import build_layer_view, LAYERS
from .requirement_graph import allocation_edges
from .property_schema import KIND_LABELS


def open_chain_dialog(package,requirement,select_requirement=None):
    from nicegui import ui
    view=build_layer_view(package,requirement.id)
    registry=project_objects(package);chain_ids={r.id for column in view.columns for r in column}
    path=trace_path(package,requirement.id,requirement_ids=chain_ids)
    architecture={'SystemDomain','SystemElement','SystemRelation','Domain','ArchitectureElement','Port','ArchitectureSignal','Connection',
                  'MechanicalArchitectureElement','SoftwareArchitectureElement','DisciplineRelation','FunctionElement','IntegrationInterface','Signal'}
    links={(rid,canonical_kind(kind),oid) for rid,kind,oid in allocation_edges(package) if rid in chain_ids}
    inherited_keys={'realizations':'Realization','components':'Component','mechanical_components':'MechanicalComponent','software_components':'SoftwareComponent',
        'system_elements':'SystemElement','system_domains':'SystemDomain','system_relations':'SystemRelation','architecture_elements':'ArchitectureElement',
        'mechanical_architecture_elements':'MechanicalArchitectureElement','software_architecture_elements':'SoftwareArchitectureElement',
        'signals':'ArchitectureSignal','ports':'Port','connections':'Connection','domains':'Domain','discipline_relations':'DisciplineRelation',
        'function_elements':'FunctionElement','technical_sources':'TechnicalSource','integration_interfaces':'IntegrationInterface','signal_members':'Signal'}
    with ui.dialog().props('maximized') as dialog,ui.card().classes('w-full h-full overflow-auto p-6 gap-4'):
        with ui.row().classes('w-full items-center'):
            ui.label('Requirementskette · '+requirement.title).classes('text-2xl font-bold grow')
            ui.button('Schließen',on_click=dialog.close)
        ui.label('Quelle → L1–L4 → Architekturverantwortung → konkrete Realisierung → Erfüllungsbewertung und Verifikation').classes('text-sm text-slate-600')
        ui.label('Quellen und Herkunft').classes('text-lg font-semibold')
        sources={r.source_document_id for r in package.requirements if r.id in chain_ids and r.source_document_id}
        for oid in sources:
            document=registry['SourceDocument'].get(oid)
            if document:ui.label(document.name)
        if not sources:ui.label('Keine Dokumentquelle zugeordnet. Manuelle Herkunft oder Bestandsbefund am Requirement prüfen.').classes('text-amber-800')
        for number,title,_ in LAYERS:
            index=int(number[1:])-1;column=view.columns[index]
            with ui.expansion(number+' · '+title,value=True).classes('w-full border rounded'):
                if not column:ui.label('Diese Ebene ist im gewählten Strang offen.').classes('text-amber-800')
                for req in column:
                    with ui.card().classes('w-full border shadow-none gap-2'):
                        ui.label(f'{req.identifier} · {req.title}').classes('font-semibold')
                        ui.label(req.text).classes('text-sm')
                        ui.label('Freigabe: '+req.maturity.value+' · Akzeptanz: '+(req.acceptance_criteria or 'Offen')).classes('text-sm')
                        evidence=evidence_status(package,req)
                        labels={'Verified':'Verifiziert','Stale':'Nachweis erneut prüfen','Failed':'Fehlgeschlagen','Blocked':'Blockiert','Test Defined':'Test definiert','No Test':'Kein Test definiert'}
                        ui.label(f'Zuordnung: {evidence.allocation} · Erfüllung: {evidence.fulfillment} · Verifikation: {labels[evidence.verification]}').classes('text-sm')
                        for gap in evidence.gaps:ui.label(gap).classes('text-xs text-amber-800')
                        if select_requirement:
                            def focus(_,rid=req.id):dialog.close();select_requirement(rid)
                            ui.button('Requirement öffnen',on_click=focus).props('flat dense no-caps')
        for title,kinds in [('Architekturverantwortung',architecture),('Konkrete Realisierung und Lösungen',set(registry)-architecture-{'Requirement','SourceDocument','Standard','Observation','VerificationCase'})]:
            ui.label(title).classes('text-lg font-semibold')
            rows=sorted({(kind,oid) for rid,kind,oid in links if kind in kinds}|{(kind,oid) for key,kind in inherited_keys.items() if kind in kinds for oid in path.get(key,[])})
            if not rows:ui.label('Zuordnung in diesem Strang offen.').classes('text-amber-800')
            for kind,oid in rows:
                obj=registry.get('Realization' if kind=='TechnicalRealization' else kind,{}).get(oid)
                if not obj:continue
                refs=[r.identifier or r.title for r in package.requirements if any(rid==r.id and k==kind and i==oid for rid,k,i in links)]
                with ui.row().classes('w-full border-b py-2 flex-wrap'):
                    ui.label(KIND_LABELS.get(kind,kind)).classes('w-64 font-medium')
                    ui.label(getattr(obj,'name',getattr(obj,'title',oid))).classes('grow')
                    ui.label(', '.join(refs) or 'Über gespeicherte Architektur-/Realisierungszuordnung').classes('text-sm')
        ui.label('Ergebnisbelege').classes('text-lg font-semibold')
        for case in package.verification_cases:
            if case.id not in path['tests']:continue
            ui.label(f'{case.identifier} · {case.title} · {case.execution_status.value} · '+('Aktueller Stand' if verification_current(package,case) else 'Gültigkeit prüfen')).classes('font-medium')
            ui.label(f'Geprüfte Revision: {case.verified_revision or "Offen"} · Beleg: {case.evidence_reference or "Offen"}').classes('text-sm')
        if not path['tests']:ui.label('Kein Verifikationsfall im gewählten Strang vorhanden.').classes('text-amber-800')
        if view.gaps:
            ui.label('Ableitungslücken').classes('text-lg font-semibold')
            for gap in view.gaps:ui.label(gap).classes('text-sm text-amber-800')
    dialog.open()
