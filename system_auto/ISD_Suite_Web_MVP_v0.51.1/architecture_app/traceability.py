"""Shared relationship reads and revision-bound engineering evidence."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from .models import ProjectWorkflow, RequirementLevel, TestExecutionStatus, utc_now
from .requirement_graph import derivation_edges, allocation_edges, test_requirement_ids

RELATION_KINDS={'derived_from','observed_at','inferred_from','allocated_to','assessed_by',
                'technical_interface','dependency','governed_by','verified_by','contains','realized_by'}


def project_objects(package):
    mapping={'Requirement':package.requirements,'Observation':package.observations,'Realization':package.technical_realizations,
        'Component':package.components,'ArchitectureElement':[e for d in package.domains for e in d.elements],
        'Domain':package.domains,'VerificationCase':package.verification_cases,'Standard':package.standards,
        'MechanicalComponent':package.mechanical_components,'MechanicalConstraint':package.mechanical_constraints,
        'SoftwareComponent':package.software_components,'SoftwareWorkItem':package.software_work_items,
        'InterfaceRequirement':package.interface_requirements,'Connection':package.connections,'ArchitectureSignal':package.signals,
        'SourceDocument':package.source_documents,'Port':[p for d in package.domains for e in d.elements for p in e.ports],
        'SystemDomain':package.system_domains,'SystemElement':package.system_elements,'SystemRelation':package.system_relations,
        'MechanicalArchitectureElement':package.mechanical_architecture_elements,
        'SoftwareArchitectureElement':package.software_architecture_elements,'DisciplineRelation':package.discipline_relations,
        'FunctionElement':package.function_elements,'TechnicalSource':package.technical_sources,
        'IntegrationInterface':package.integration_interfaces,'TechnicalValue':package.technical_values,
        'Signal':[m for s in package.signals for m in s.bus_contents]}
    return {kind:{o.id:o for o in values} for kind,values in mapping.items()}


def canonical_kind(kind):
    return {'TechnicalRealization':'Realization','InterfacePort':'Port'}.get(kind,kind)


def remove_deleted_references(package,object_ids):
    """Remove current graph references together with explicitly deleted objects.

    Repository revisions retain the previous objects and their evidence. An
    assessment of an existing object remains intact and becomes stale instead.
    """
    ids=set(object_ids)
    from .integration import remove_references
    remove_references(package,ids)
    package.model_relations=[r for r in package.model_relations if r.source_id not in ids and r.target_id not in ids]
    package.requirement_links=[r for r in package.requirement_links if r.requirement_id not in ids and r.target_id not in ids]
    package.fulfillment_assessments=[a for a in package.fulfillment_assessments
                                    if a.requirement_id not in ids and a.realization_id not in ids]
    package.architecture_allocations=[a for a in package.architecture_allocations
                                      if a.system_element_id not in ids and a.target_id not in ids]
    for conflict in package.engineering_conflicts:
        if conflict.target_id in ids:conflict.target_type=None;conflict.target_id=None


def validate_relation(package,relation):
    if relation.kind not in RELATION_KINDS:raise ValueError(f'Unbekannter Beziehungstyp: {relation.kind}')
    objects=project_objects(package)
    for kind,identifier in ((relation.source_type,relation.source_id),(relation.target_type,relation.target_id)):
        if identifier not in objects.get(canonical_kind(kind),{}):raise ValueError(f'Unbekanntes Beziehungsziel: {kind} {identifier}')
    if relation.source_type==relation.target_type and relation.source_id==relation.target_id:raise ValueError('Selbstbeziehungen sind nicht zulässig')
    if relation.kind=='derived_from':
        if relation.source_type!=relation.target_type or relation.source_type!='Requirement':raise ValueError('Ableitungen verbinden zwei Requirements')
        from .requirements_layers import _rank
        child=objects['Requirement'][relation.source_id];parent=objects['Requirement'][relation.target_id]
        if _rank(child)<=_rank(parent):raise ValueError('Ableitung muss zu einer tieferen Ebene führen')
        if _rank(child)!=_rank(parent)+1 and not relation.rationale.strip():raise ValueError('Ebenensprung benötigt eine Begründung')
        children={}
        for a,b in derivation_edges(package)|{(parent.id,child.id)}:children.setdefault(a,set()).add(b)
        pending=[child.id];seen=set()
        while pending:
            node=pending.pop()
            if node==parent.id:raise ValueError('Ableitung erzeugt einen Zyklus')
            if node in seen:continue
            seen.add(node);pending.extend(children.get(node,()))
    if relation.kind in {'technical_interface','dependency'} and not relation.rationale.strip():raise ValueError('Technische Beziehungen benötigen eine Begründung')
    if relation.kind=='realized_by':
        if canonical_kind(relation.source_type) not in {'ArchitectureElement','FunctionElement','SystemElement','SystemDomain','MechanicalArchitectureElement','SoftwareArchitectureElement','Domain','ArchitectureSignal','Signal','Port','Connection'} or canonical_kind(relation.target_type) not in {'Realization','Component','MechanicalComponent','SoftwareComponent','InterfaceRequirement','IntegrationInterface'}:raise ValueError('Realisierungsbeziehung benötigt Architektur und konkrete Umsetzung')
        source=objects[canonical_kind(relation.source_type)][relation.source_id]
        target=objects[canonical_kind(relation.target_type)][relation.target_id]
        source_kind=canonical_kind(relation.source_type);target_kind=canonical_kind(relation.target_type)
        discipline=getattr(source,'discipline','software' if source_kind=='SoftwareArchitectureElement' else 'mechanical' if source_kind=='MechanicalArchitectureElement' else 'hardware')
        allowed={'hardware':{'Realization','Component','InterfaceRequirement','IntegrationInterface'},
                 'software':{'SoftwareComponent','InterfaceRequirement','IntegrationInterface'},
                 'mechanical':{'MechanicalComponent','InterfaceRequirement','IntegrationInterface'}}[discipline]
        if source_kind not in {'SystemElement','SystemDomain'}:
            if target_kind not in allowed:raise ValueError('Realisierungsquelle passt nicht zur Disziplin; Fachschnittstelle zuordnen')
            if target_kind=='InterfaceRequirement' and target.interface_class.value not in {'hardware':{'EHW_IF'},'software':{'SW_IF','FW_IF'},'mechanical':{'MECH_IF'}}[discipline]:raise ValueError('Realisierungsschnittstelle passt nicht zur Disziplin')
            if target_kind=='IntegrationInterface' and (discipline=='software' and target.kind!='HSI' or discipline=='mechanical' and target.kind!='HW-Mechanik'):raise ValueError('Fachschnittstelle passt nicht zur Disziplin')
    if relation.kind=='dependency':
        from .requirement_profiles import dependency_target_applies
        source=objects[canonical_kind(relation.source_type)][relation.source_id]
        target=objects[canonical_kind(relation.target_type)][relation.target_id]
        if not dependency_target_applies(source,target):raise ValueError('Abhängigkeit passt nicht zum Quellobjekt')
    if relation.kind=='verified_by' and (relation.source_type!='Requirement' or relation.target_type!='VerificationCase'):
        raise ValueError('Verifikation verbindet ein Requirement mit einem Verifikationsfall')


def add_relation(package,relation):
    validate_relation(package,relation)
    if any(r.id==relation.id for r in package.model_relations):raise ValueError('Beziehungs-ID bereits vergeben')
    relation.history.append({'at':utc_now(),'status':relation.status,'rationale':relation.rationale})
    package.model_relations.append(relation);return relation


def object_fingerprint(obj):
    from .attribute_spaces import is_system_key
    payload=obj.model_dump(mode='json')
    for space in ('attributes','properties'):
        payload[space]={k:v for k,v in payload.get(space,{}).items() if not is_system_key(k)}
    # All open schema fields are equivalent to an absent field during migration.
    for space in ('requirement_attributes','realization_attributes'):
        if space in payload:payload[space]={k:v for k,v in payload[space].items() if v is not None}
    # Newly introduced empty fields do not change an already reviewed v0.42
    # object. Once filled, they participate in the reviewed object stand.
    introduced={
        'DesignComponent':('requirement_attributes','realization_attributes','system_defining','system_defining_reason','part_revision','alternative_component_ids','standard_claims'),
        'EcadRequirement':('requirement_attributes','realization_attributes'),
        'TechnicalRealization':('function_element_id',),
        'TechnicalSource':('document_date','release_status','extracted_content'),
    }
    introduced.update({'SoftwareComponent':('code_path','commit','package_id','artifact_url','build_id','dependency_ids','included_component_ids','configuration'),
        'MechanicalComponent':('part_number','manufacturer','revision','cad_reference','cad_revision','plm_reference','alternative_component_ids','analysis_references'),
        'FunctionElement':('realization_ids','interface_requirement_ids')})
    if type(obj).__name__=='SystemElement' and payload.get('kind')=='Systemteil':payload.pop('kind',None)
    if type(obj).__name__=='EcadRequirement' and payload.get('customer_decision')=='Open':payload.pop('customer_decision',None)
    if type(obj).__name__=='FunctionElement' and payload.get('discipline')=='hardware':payload.pop('discipline',None)
    for key in introduced.get(type(obj).__name__,()):
        if payload.get(key) is None or payload.get(key) in ('',[],{}):payload.pop(key,None)
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def criteria(requirement):
    return [v.strip() for line in requirement.acceptance_criteria.splitlines() for v in line.split(';') if v.strip()]


def _dependencies(package,kind,obj,variant_id=None):
    """Follow explicit selected implementation, hierarchy and dependency references."""
    registry=project_objects(package);seen={};pending=[(canonical_kind(kind),obj,variant_id)]
    while pending:
        typ,current,chosen=pending.pop();key=typ+':'+current.id
        if key in seen:continue
        seen[key]=object_fingerprint(current)
        refs=[]
        if typ=='Realization':
            selected=chosen or current.selected_variant_id
            variants=[v for v in current.variants if v.id==selected] if selected else current.variants
            if selected and not variants:seen['MissingVariant:'+selected]='missing'
            if current.architecture_element_id:refs.append(('ArchitectureElement',current.architecture_element_id))
            if current.function_element_id:refs.append(('FunctionElement',current.function_element_id))
            for v in variants:
                seen['Variant:'+v.id]=object_fingerprint(v)
                refs.extend(('Component',r.component_id) for r in v.component_roles)
                refs.extend(('MechanicalComponent',i) for i in v.mechanical_component_ids)
                refs.extend(('SoftwareComponent',i) for i in v.software_component_ids)
                refs.extend(('ArchitectureElement',i) for i in v.architecture_element_ids)
        if typ=='ArchitectureElement':
            refs.extend(('Realization',r.id) for r in package.technical_realizations
                        if r.architecture_element_id==current.id)
            refs.extend(('FunctionElement',f.id) for f in package.function_elements if f.architecture_element_id==current.id)
        if typ=='TechnicalValue':refs.extend(('TechnicalSource' if i in registry['TechnicalSource'] else 'SourceDocument',i) for i in current.source_ids)
        if typ=='IntegrationInterface':
            from .integration import REFERENCE_COLLECTIONS
            refs.extend((target,i) for field,target in REFERENCE_COLLECTIONS.items() for i in getattr(current,field))
        refs.extend(('TechnicalValue',v.id) for v in package.technical_values if v.owner_id==current.id)
        if typ=='FunctionElement':
            real_kind={'hardware':'Realization','software':'SoftwareComponent','mechanical':'MechanicalComponent'}[current.discipline]
            refs.extend((real_kind,i) for i in current.realization_ids)
            refs.extend(('InterfaceRequirement',i) for i in current.interface_requirement_ids)
            refs.extend(('Realization',r.id) for r in package.technical_realizations if r.function_element_id==current.id)
            refs.extend(('FunctionElement',i) for i in current.dependency_ids)
            refs.extend(('ArchitectureSignal',i) for i in current.interface_signal_ids)
        if typ=='Component':
            refs.extend(('TechnicalSource',s.id) for s in package.technical_sources if s.owner_id==current.id)
        for scope in ('requirement_attributes','realization_attributes'):
            for oid in getattr(current,scope,{}).get('dependencies') or []:
                refs.extend((k,oid) for k,group in registry.items() if oid in group)
        if typ in {'MechanicalArchitectureElement','SoftwareArchitectureElement'}:
            target='MechanicalComponent' if typ.startswith('Mechanical') else 'SoftwareComponent'
            refs.extend((target,i) for i in current.realization_ids)
        if typ=='SoftwareComponent':refs.extend(('SoftwareComponent',i) for i in current.dependency_ids+current.included_component_ids)
        for field in ('parent_component_id','parent_id'):
            if getattr(current,field,None):refs.append((typ,getattr(current,field)))
        for rel in package.model_relations:
            if rel.kind in {'dependency','realized_by','technical_interface'} and rel.source_id==current.id:
                seen['Relation:'+rel.id]=object_fingerprint(rel);refs.append((canonical_kind(rel.target_type),rel.target_id))
        if typ=='SystemElement':
            kinds={'hw_element':'ArchitectureElement','hw_realization':'Realization','mechanical':'MechanicalComponent','software':'SoftwareComponent',
                   'mechanical_element':'MechanicalArchitectureElement','software_element':'SoftwareArchitectureElement'}
            refs.extend((kinds[a.target_kind],a.target_id) for a in package.architecture_allocations if a.system_element_id==current.id)
        for target,oid in refs:
            other=registry.get(target,{}).get(oid)
            if other:pending.append((target,other,None))
            else:seen[target+':'+oid]='missing'
    return seen


def assessment_snapshot(package,assessment):
    registry=project_objects(package);req=registry['Requirement'].get(assessment.requirement_id);real=registry['Realization'].get(assessment.realization_id)
    if not req or not real:return {}
    snapshot={'Requirement':object_fingerprint(req),'Realization':object_fingerprint(real)}
    snapshot.update(_dependencies(package,'Realization',real,assessment.variant_id))
    return snapshot


def assessment_current(package,assessment):
    expected=assessment_snapshot(package,assessment)
    return bool(expected and expected==assessment.reviewed_revisions)


def review_assessment(package,assessment):
    req=package.find_requirement(assessment.requirement_id);real=package.find_technical_realization(assessment.realization_id)
    if not req or not real:raise ValueError('Requirement oder Realisierung fehlt')
    if assessment.result=='Passed':
        if not criteria(req) or any(assessment.criteria_results.get(c)!='Passed' for c in criteria(req)) or not assessment.rationale.strip() or not assessment.evidence_reference.strip():
            raise ValueError('Positive Bewertung benötigt alle Akzeptanzkriterien, Begründung und Ergebnisbeleg')
    if assessment.result not in {'Passed','Failed','Draft'}:raise ValueError('Ungültiges Bewertungsergebnis')
    if assessment.variant_id and not any(v.id==assessment.variant_id for v in real.variants):raise ValueError('Variante fehlt')
    assessment.reviewed_revisions=assessment_snapshot(package,assessment);assessment.status='Reviewed';assessment.assessed_at=utc_now()


def test_has_evidence(case,package=None):
    complete=bool(case.execution_status==TestExecutionStatus.PASSED and case.actual_result.strip() and case.evidence_reference.strip()
                  and case.verified_revision.strip() and case.executed_at)
    return complete and (package is None or verification_current(package,case))


def verification_snapshot(package,case):
    registry=project_objects(package);snapshot={}
    requirements=test_requirement_ids(package,case)
    for rid in sorted(requirements):
        req=registry['Requirement'].get(rid)
        if not req:return {}
        snapshot['Requirement:'+rid]=object_fingerprint(req)
    for rid,kind,oid in allocation_edges(package):
        if rid not in requirements:continue
        typ=canonical_kind(kind);obj=registry.get(typ,{}).get(oid)
        if obj:snapshot.update(_dependencies(package,typ,obj))
    definition={k:getattr(case,k) for k in ('objective','procedure','expected_result','configuration_reference')}
    definition['method']=case.method.value;definition['requirements']=sorted(requirements)
    snapshot['Testdefinition']=hashlib.sha256(json.dumps(definition,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return snapshot if requirements else {}


def verification_current(package,case):
    expected=verification_snapshot(package,case)
    return bool(expected and case.reviewed_revisions==expected)


def record_verification(package,case):
    if not test_has_evidence(case):raise ValueError('Nachweis benötigt Ergebnis, Beleg, geprüfte Revision und Zeitpunkt')
    snapshot=verification_snapshot(package,case)
    if not snapshot:raise ValueError('Requirements-Zuordnung für den Nachweis fehlt')
    case.reviewed_revisions=snapshot


def verification_status(package,req):
    from .requirements_service import is_test_defined
    tests=[c for c in package.verification_cases if req.id in test_requirement_ids(package,c) and c.execution_status!=TestExecutionStatus.OBSOLETE]
    if any(c.execution_status==TestExecutionStatus.FAILED for c in tests):return 'Failed'
    if any(c.execution_status==TestExecutionStatus.BLOCKED for c in tests):return 'Blocked'
    if tests and all(test_has_evidence(c,package) for c in tests):return 'Verified'
    if any(test_has_evidence(c) and not verification_current(package,c) for c in tests):return 'Stale'
    if any(is_test_defined(c) for c in tests):return 'Test Defined'
    return 'No Test'


@dataclass(frozen=True)
class EvidenceStatus:
    allocation:str
    fulfillment:str
    verification:str
    gaps:tuple[str,...]


def evidence_status(package,req):
    from .requirements_layers import effective_layer
    allocated=any(rid==req.id for rid,kind,oid in allocation_edges(package))
    assessments=[a for a in package.fulfillment_assessments if a.requirement_id==req.id]
    passed=any(a.result=='Passed' and a.status=='Reviewed' and assessment_current(package,a) for a in assessments)
    stale=any(a.result=='Passed' and not assessment_current(package,a) for a in assessments)
    failed=any(a.result=='Failed' and a.status=='Reviewed' and assessment_current(package,a) for a in assessments)
    ver=verification_status(package,req);gaps=[]
    observed=bool(req.observation_ids) or any(r.source_id==req.id and r.kind in {'observed_at','inferred_from'} for r in package.model_relations)
    if effective_layer(req)!=RequirementLevel.CUSTOMER and not any(b==req.id for a,b in derivation_edges(package)) and not observed:
        profile=package.project.workflow_mode
        gaps.append('Herkunft oder Beobachtung prüfen' if profile==ProjectWorkflow.REDESIGN else 'Hypothese prüfen' if profile==ProjectWorkflow.STUDY else 'Ableitung aus höherer Ebene fehlt')
    if not allocated:gaps.append('Architektur oder technische Lösung zuordnen')
    if not passed:gaps.append('Erfüllung erneut bewerten' if stale else 'Erfüllung bewerten')
    if ver!='Verified':gaps.append('Testnachweis erneut prüfen' if ver=='Stale' else 'Test definieren' if ver=='No Test' else 'Test ausführen und Ergebnis belegen')
    return EvidenceStatus('Zuordnung vorhanden' if allocated else 'Keine Zuordnung','Erfüllt' if passed else 'Erneut prüfen' if stale else 'Nicht erfüllt' if failed else 'Nicht bewertet',ver,tuple(gaps))


def trace_path(package,requirement_id,*,requirement_ids=None):
    registry=project_objects(package)
    seen=set(requirement_ids) if requirement_ids is not None else {requirement_id}
    queue=[] if requirement_ids is not None else [requirement_id]
    edges=derivation_edges(package)
    while queue:
        parent=queue.pop();children={b for a,b in edges if a==parent}
        for child in children-seen:seen.add(child);queue.append(child)
    keys={'Realization':'realizations','Component':'components','MechanicalComponent':'mechanical_components','SoftwareComponent':'software_components',
          'ArchitectureElement':'architecture_elements','SystemElement':'system_elements','SystemDomain':'system_domains','SystemRelation':'system_relations',
          'MechanicalArchitectureElement':'mechanical_architecture_elements','SoftwareArchitectureElement':'software_architecture_elements',
          'DisciplineRelation':'discipline_relations','Signal':'signal_members','ArchitectureSignal':'signals','Port':'ports','Domain':'domains',
          'InterfaceRequirement':'interfaces','Connection':'connections','FunctionElement':'function_elements','TechnicalSource':'technical_sources','IntegrationInterface':'integration_interfaces','TechnicalValue':'technical_values'}
    result={key:set() for key in keys.values()};reached=[]
    for rid,kind,oid in allocation_edges(package):
        typ=canonical_kind(kind)
        if rid in seen and typ in keys:result[keys[typ]].add(oid);reached.append((typ,oid))
    processed=set()
    while reached:
        kind,oid=reached.pop()
        if (kind,oid) in processed:continue
        processed.add((kind,oid));obj=registry.get(kind,{}).get(oid)
        if obj:
            for key in _dependencies(package,kind,obj):
                if ':' not in key:continue
                typ,rid=key.split(':',1)
                if typ in keys and rid not in result[keys[typ]]:result[keys[typ]].add(rid);reached.append((typ,rid))
    result.update(requirements=seen,assessments={a.id for a in package.fulfillment_assessments if a.requirement_id in seen},
        tests={c.id for c in package.verification_cases if test_requirement_ids(package,c)&seen},
        standards={l.standard_id for l in package.requirement_standard_links if l.requirement_id in seen},
        sources={r.source_document_id for r in package.requirements if r.id in seen and r.source_document_id})
    allids=set().union(*result.values())
    result['relations']={r.id for r in package.model_relations if r.source_id in allids or r.target_id in allids}
    return {k:sorted(v) for k,v in result.items()}
