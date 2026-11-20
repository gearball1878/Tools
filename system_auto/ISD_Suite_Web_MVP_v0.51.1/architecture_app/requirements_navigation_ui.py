"""Readable requirement navigation with references rather than copied objects."""
from nicegui import ui
from .requirements_layers import LAYERS, effective_layer, derivation_edges
from .models import RequirementLevel
from .traceability import project_objects
from .requirement_graph import allocation_edges


def decision_label(requirement):
    if effective_layer(requirement)==RequirementLevel.CUSTOMER:
        return {'Open':'Annahme offen','Accepted':'Angenommen','Rejected':'Abgelehnt'}[requirement.customer_decision]
    return {'Rejected':'Abgelehnt','Obsolete':'Obsolet','Approved':'Freigegeben',
            'Detected':'Erfasst / Entscheidung offen','In Review':'In Prüfung'}.get(requirement.maturity.value,requirement.maturity.value)


def navigation_groups(package, visible):
    lookup={r.id:r for r in visible};edges=derivation_edges(package)
    customers=[r for r in visible if effective_layer(r)==RequirementLevel.CUSTOMER]
    linked={child for parent,child in edges if parent in lookup and effective_layer(lookup[parent])==RequirementLevel.CUSTOMER}
    return customers,{r.id:[lookup[c] for a,c in sorted(edges) if a==r.id and c in lookup and effective_layer(lookup[c])==RequirementLevel.SYSTEM] for r in customers},[
        r for r in visible if effective_layer(r)==RequirementLevel.SYSTEM and r.id not in linked]


def render_navigation(package,visible,selected_id,select_requirement,select_architecture,select_realization):
    lookup={r.id:r for r in package.requirements};edges=derivation_edges(package)
    with ui.element('div').classes('w-full').style('display:grid;grid-template-columns: minmax(280px,1fr) minmax(300px,1fr);gap:20px'):
        with ui.column().classes('w-full gap-3'):
            ui.label('Anforderungen').classes('text-lg font-semibold')
            def entry(r,reference=False):
                with ui.row().classes('w-full items-start border-b py-2 gap-2'):
                    number=next(n for n,_,layer in LAYERS if effective_layer(r)==layer)
                    ui.badge(number,color='blue-1').props('text-color=blue-9')
                    with ui.column().classes('grow gap-1'):
                        ui.button((r.identifier or r.external_id or r.id[:9])+' · '+r.title,
                            on_click=lambda _,i=r.id:select_requirement(i)).props('flat no-caps align=left').classes('w-full text-left')
                        ui.label(r.classification.value+' · '+decision_label(r)+' · Prüfstand: '+r.maturity.value).classes('text-xs text-slate-500')
                        if reference:ui.label('Verweis · weitere Kundenursprünge im Zusammenhang').classes('text-xs text-blue-700')
            customers,children,other=navigation_groups(package,visible)
            if customers:
                with ui.expansion('L1 Kundenanforderungen und abgeleitete L2',value=True).classes('w-full border rounded'):
                    for customer in customers:
                        with ui.expansion((customer.identifier or 'L1')+' · '+customer.title,value=customer.id==selected_id).classes('w-full'):
                            entry(customer)
                            for child in children[customer.id]:entry(child,sum(c==child.id for _,c in edges)>1)
                            if not children[customer.id]:ui.label('L2-Ableitung: Offen').classes('text-xs text-amber-800')
            if other:
                with ui.expansion('Weitere Systemanforderungen (L2)',value=True).classes('w-full border rounded'):
                    for r in other:entry(r)
            for number,title,layer in LAYERS[2:]:
                group=[r for r in visible if effective_layer(r)==layer]
                if group:
                    with ui.expansion(number+' · '+title,value=True).classes('w-full border rounded'):
                        for r in group:entry(r)
            if not visible:ui.label('Keine Requirements für diese Filter.').classes('text-slate-500')
        with ui.column().classes('w-full gap-3 border rounded p-4'):
            ui.label('Zusammenhang der Auswahl').classes('text-lg font-semibold')
            selected=lookup.get(selected_id)
            if not selected:
                ui.label('Ein Requirement auswählen. Hier erscheinen seine gespeicherten Ableitungen und Zuordnungen.');return
            ui.label(selected.identifier+' · '+selected.title).classes('font-semibold')
            for label,identifiers in [('Abgeleitet aus',[a for a,c in edges if c==selected.id]),('Abgeleitete Requirements',[c for a,c in edges if a==selected.id])]:
                with ui.expansion(label,value=True).classes('w-full border rounded'):
                    for identifier in sorted(set(identifiers)):
                        r=lookup.get(identifier)
                        if r:ui.button(r.identifier+' · '+r.title,on_click=lambda _,i=r.id:select_requirement(i)).props('flat no-caps align=left')
                    if not identifiers:ui.label('Offen').classes('text-sm text-slate-500')
            registry=project_objects(package)
            allocated={(kind,i) for rid,kind,i in allocation_edges(package) if rid==selected.id}
            with ui.expansion('Architekturverantwortung und Umsetzung',value=True).classes('w-full border rounded'):
                seen=set()
                for kind,identifier in sorted(allocated):
                    obj=registry.get(kind,{}).get(identifier)
                    if not obj or identifier in seen:continue
                    seen.add(identifier)
                    handler=select_realization if kind=='Realization' else select_architecture
                    if kind in {'Component','MechanicalComponent','SoftwareComponent'}:
                        # Concrete details stay behind an explicit source action.
                        from .comparison_ui import source_dialog
                        handler=lambda i:source_dialog(package,i)
                    ui.badge(kind,color='teal-1').props('text-color=teal-9')
                    ui.button(getattr(obj,'name',getattr(obj,'title',identifier)),
                        on_click=lambda _,i=identifier,h=handler:h(i)).props('flat no-caps align=left').mark('target-open-'+identifier)
                if not seen:ui.label('Architektur-/Realisierungszuordnung: Offen').classes('text-amber-800')
            ui.label('Zuordnung ist keine Erfüllungsbewertung. Freigabe und Testnachweis stehen in den Details.').classes('text-xs text-slate-500')
