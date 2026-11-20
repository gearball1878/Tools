"""Core technology, revision-specific qualification and abstract functional blocks."""
from __future__ import annotations
from copy import deepcopy
from .models import ArchitecturePackage, TechnicalRealization, ComponentRoleInRealization
import hashlib
import json

def part_fingerprint(component):
    identity={key:getattr(component,key) for key in ('manufacturer','manufacturer_part_number','part_revision','package_name')}
    return hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()

def source_fingerprint(source):
    evidence={key:getattr(source,key) for key in ('url','external_reference','revision','evidence_locator','checksum_sha256','status')}
    return hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest()

def record_qualification(package,component,claim):
    claim.reviewed_part_fingerprint=part_fingerprint(component)
    sources={s.id:s for s in package.technical_sources}
    claim.reviewed_source_fingerprints={i:source_fingerprint(sources[i]) for i in claim.evidence_source_ids if i in sources}
    standard=package.find_standard(claim.standard_id)
    if standard:claim.reviewed_standard_fingerprint=standard_fingerprint(standard)
    return claim

def standard_fingerprint(standard):
    return hashlib.sha256(json.dumps([standard.designation,standard.edition]).encode()).hexdigest()

def core_component_ids(package,variant):
    parts={c.id:c for c in package.components}
    return {r.component_id for r in variant.component_roles if r.component_id in parts and
            (parts[r.component_id].system_defining is True or
             parts[r.component_id].system_defining is None and r.role.value=='A-Part')}

def standard_comparison(package,component,requirement_ids=()):
    standards={s.id:s for s in package.standards};sources={s.id:s for s in package.technical_sources}
    requirements=set(requirement_ids)|set(component.requirement_ids)
    realization_ids=set();required=set()
    for realization in package.technical_realizations:
        variants=[v for v in realization.variants if any(r.component_id==component.id for r in v.component_roles)]
        if not variants:continue
        realization_ids.add(realization.id);requirements.update(realization.requirement_ids)
        required.update(sid for v in variants for sid in v.standard_ids)
        fe=next((f for f in package.function_elements if f.id==realization.function_element_id),None)
        if fe:requirements.update(fe.requirement_ids)
    requirements.update(link.requirement_id for link in package.requirement_links if link.target_id in realization_ids|{component.id})
    from .requirement_graph import derivation_edges
    edges=derivation_edges(package);pending=list(requirements)
    while pending:
        child=pending.pop();parents={a for a,b in edges if b==child}-requirements
        requirements.update(parents);pending.extend(parents)
    required.update(link.standard_id for link in package.requirement_standard_links if link.requirement_id in requirements)
    required.update(c.standard_id for c in component.standard_claims)
    rows=[]
    for sid in sorted(required):
        norm=standards[sid];claim=next((c for c in component.standard_claims if c.standard_id==sid),None)
        evidence=[sources[i] for i in claim.evidence_source_ids if i in sources] if claim else []
        current=bool(claim and claim.reviewed_part_fingerprint==part_fingerprint(component)
                     and claim.reviewed_standard_fingerprint==standard_fingerprint(norm)
                     and all(claim.reviewed_source_fingerprints.get(s.id)==source_fingerprint(s) for s in evidence))
        complete=bool(current and component.manufacturer.strip() and component.manufacturer_part_number.strip()
                      and claim and claim.scope.strip() and claim.rationale.strip() and evidence and norm.edition.strip()
                      and all(s.owner_id==component.id and s.revision.strip() and s.evidence_locator.strip() and s.status.value in {'Available','Verified'} for s in evidence))
        rows.append({'standard_id':sid,'designation':norm.designation,'edition':norm.edition,
                     'result':claim.result if complete else 'Offen','scope':claim.scope if claim else '',
                     'evidence_source_ids':[s.id for s in evidence],'rationale':claim.rationale if claim else '',
                     'gap':'' if complete else 'Bauteil-/Dokumentstand erneut prüfen oder Ausgabe, Geltungsbereich und Beleg ergänzen'})
    return rows

def delete_function_element(package,identifier):
    package.function_elements=[f for f in package.function_elements if f.id!=identifier]
    for f in package.function_elements:f.dependency_ids=[i for i in f.dependency_ids if i!=identifier]
    from .requirements_service import delete_technical_realization
    for r in list(package.technical_realizations):
        if r.function_element_id==identifier:
            if r.requirement_ids:
                r.function_element_id=None
                r.attributes['feAssignmentOpen']=True
            else:
                delete_technical_realization(package, r.id)
    from .traceability import remove_deleted_references
    remove_deleted_references(package,{identifier})

def save_function_element(package,element):
    from .models import ArchitecturePackage
    candidate=deepcopy(package)
    candidate.function_elements=[f for f in candidate.function_elements if f.id!=element.id]+[element]
    return ArchitecturePackage.model_validate(candidate.export_dict())


def synchronize_realization_architecture_attribute(
    package: ArchitecturePackage,
    realization: TechnicalRealization,
) -> None:
    """Store only stable references on the generic Architecture Element."""
    for domain in package.domains:
        for element in domain.elements:
            implementations = element.attributes.get("technicalImplementations", [])
            if isinstance(implementations, list):
                remaining = [
                    item for item in implementations
                    if not isinstance(item, dict) or item.get("realizationId") != realization.id
                ]
                if remaining:
                    element.attributes["technicalImplementations"] = remaining
                else:
                    element.attributes.pop("technicalImplementations", None)
            legacy = element.attributes.get("technicalImplementation")
            if isinstance(legacy, dict) and legacy.get("realizationId") == realization.id:
                element.attributes.pop("technicalImplementation", None)
    if not realization.architecture_element_id:
        return
    element_result = package.find_element(realization.architecture_element_id)
    if element_result is None:
        return
    selected = next(
        (item for item in realization.variants if item.id == realization.selected_variant_id),
        None,
    )
    selected_a_part_id = ""
    if selected:
        selected_a_part_id = next(
            (
                item.component_id for item in selected.component_roles
                if item.role == ComponentRoleInRealization.A_PART
            ),
            "",
        )
    implementation = {
        "realizationId": realization.id,
        "selectedVariantId": realization.selected_variant_id or "",
        "selectedAPartId": selected_a_part_id,
        "status": realization.status.value,
    }
    element_result[1].attributes.setdefault("technicalImplementations", []).append(implementation)

