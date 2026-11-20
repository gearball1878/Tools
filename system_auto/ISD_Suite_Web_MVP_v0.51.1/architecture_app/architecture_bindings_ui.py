"""Object-specific responsibility and realization selectors inside edit masks."""
from __future__ import annotations
from nicegui import ui
from .traceability import project_objects, canonical_kind
from .requirement_graph import allocation_edges
from .models import RequirementLink, RequirementTargetType, ModelRelation


def binding_inputs(package,obj,discipline='hardware'):
    kind=canonical_kind(type(obj).__name__);registry=project_objects(package)
    labels={'hardware':{'Hardware','System'},'software':{'Software','Firmware','System'},'mechanical':{'Mechanik','System'}}
    reqs={r.id:r.identifier+' · '+r.title for r in package.requirements if r.classification.value in labels[discipline]}
    oldreq={r for r,_,i in allocation_edges(package) if i==obj.id}
    for r in package.requirements:
        if r.id in oldreq:reqs.setdefault(r.id,r.identifier+' · '+r.title+' (Bestand)')
    realkind={'hardware':['Realization','Component','InterfaceRequirement'],'software':['SoftwareComponent','InterfaceRequirement'],
        'mechanical':['MechanicalComponent','InterfaceRequirement']}[discipline]
    reals={}
    for group in realkind:
        for identifier,real in registry[group].items():
            if group=='InterfaceRequirement' and real.interface_class.value not in {'hardware':{'EHW_IF'},'software':{'SW_IF','FW_IF'},'mechanical':{'MECH_IF'}}[discipline]:continue
            reals[identifier]=group,real
    oldreal={r.target_id for r in package.model_relations if r.source_id==obj.id and r.kind=='realized_by'}
    with ui.expansion('Requirements und konkrete Umsetzung zuordnen',value=False).classes('w-full border rounded'):
        requirements=ui.select(reqs,value=sorted(oldreq),multiple=True,label='Verantwortete Requirements').props('use-input use-chips').classes('w-full')
        actual=ui.select({i:r.name for i,(_,r) in reals.items()},value=sorted(oldreal & reals.keys()),multiple=True,label='Kennwertquellen / konkrete Realisierungen').props('use-input use-chips').classes('w-full')
        ui.label('Die Zuordnung bestätigt keine Erfüllung. Vorhandene direkte FE-/AE-Realisierungen bleiben gültig.').classes('text-xs')
    from .property_inputs import custom_inputs
    apply_custom=custom_inputs(package,obj,include_system=True,exclude_keys={'function','ecadKey','netClass'})
    def apply(candidate):
        selected=set(requirements.value or [])
        candidate.requirement_links=[r for r in candidate.requirement_links if r.target_id!=obj.id or r.requirement_id in selected or r.relation.value=='Verified By']
        candidate.model_relations=[r for r in candidate.model_relations if not (r.target_id==obj.id and r.kind=='allocated_to' and r.source_type=='Requirement' and r.source_id not in selected)]
        target=next((o for group in project_objects(candidate).values() for i,o in group.items() if i==obj.id),None)
        if target:apply_custom(target)
        if target and hasattr(target,'requirement_ids'):target.requirement_ids=list(selected)
        allocated={r for r,_,i in allocation_edges(candidate) if i==obj.id}
        for rid in selected-allocated:candidate.requirement_links.append(RequirementLink(requirement_id=rid,target_type=RequirementTargetType(kind),target_id=obj.id))
        wanted=set(actual.value or [])
        candidate.model_relations=[r for r in candidate.model_relations if r.source_id!=obj.id or r.kind!='realized_by' or r.target_id in wanted or r.target_id not in reals]
        current={r.target_id for r in candidate.model_relations if r.source_id==obj.id and r.kind=='realized_by'}
        for identifier in wanted-current:
            candidate.model_relations.append(ModelRelation(kind='realized_by',source_type=kind,source_id=obj.id,target_type=reals[identifier][0],target_id=identifier,rationale='Explizite Zuordnung in der Objekt-Eingabemaske'))
        return candidate
    return apply
