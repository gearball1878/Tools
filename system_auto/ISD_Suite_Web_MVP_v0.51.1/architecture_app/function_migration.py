"""Attach retained implementations to stable leading functions; safe to repeat."""
import hashlib
from .models import FunctionElement


def migrate_function_elements(package):
    byid={f.id:f for f in package.function_elements}
    for real in package.technical_realizations:
        if not real.function_element_id and real.attributes.get('feAssignmentOpen'):continue
        if real.function_element_id:
            fe=byid.get(real.function_element_id)
            if fe is None:raise ValueError('FE-Zuordnung verweist auf ein fehlendes Objekt')
        else:
            candidates=[f for f in package.function_elements if f.discipline=='hardware' and real.id in f.realization_ids]
            candidates += [byid[r.source_id] for r in package.model_relations
                if r.kind=='realized_by' and r.target_id==real.id and r.source_id in byid and byid[r.source_id].discipline=='hardware']
            candidates={f.id:f for f in candidates}
            if len(candidates)>1:
                # Shared historical implementations retain all owners; no arbitrary ownership.
                for f in candidates.values():
                    if real.id not in f.realization_ids:f.realization_ids.append(real.id)
                continue
            fe=next(iter(candidates.values()),None)
            if fe is None:
                identifier=hashlib.sha256(('isd-fe-from-implementation:'+real.id).encode()).hexdigest()
                fe=byid.get(identifier)
                if fe is None:
                    names={f.name.casefold() for f in package.function_elements}
                    name=real.name;index=2
                    while name.casefold() in names:name=real.name+' (FE '+str(index)+')';index+=1
                    fe=FunctionElement(id=identifier,name=name,description=real.generic_function or real.attributes.get('legacyPropertyValues',{}).get('requirement_attributes',{}).get('function') or '',
                        architecture_element_id=real.architecture_element_id,
                        attributes={'migrationOrigin':{'implementationId':real.id,'version':'0.49.0'}})
                    package.function_elements.append(fe);byid[identifier]=fe
            real.function_element_id=fe.id
        if fe.discipline!='hardware':raise ValueError('HW-Implementierung benötigt ein Hardware-FE')
        if real.id not in fe.realization_ids:fe.realization_ids.append(real.id)
    # SW and mechanical implementations already have explicit AE/FE references.
    # Group only AE allocations; unallocated components remain visible as open implementations.
    for discipline,elements in [('software',package.software_architecture_elements),('mechanical',package.mechanical_architecture_elements)]:
        linked={i for f in package.function_elements if f.discipline==discipline for i in f.realization_ids}
        for ae in elements:
            ids=[i for i in ae.realization_ids if i not in linked]
            if not ids:continue
            identifier=hashlib.sha256(('isd-fe-from-allocation:'+discipline+':'+ae.id).encode()).hexdigest()
            fe=byid.get(identifier)
            if fe is None:
                names={f.name.casefold() for f in package.function_elements};name=ae.name;index=2
                while name.casefold() in names:name=ae.name+' (FE '+str(index)+')';index+=1
                fe=FunctionElement(id=identifier,discipline=discipline,name=name,description=ae.description,
                    architecture_element_id=ae.id,attributes={'migrationOrigin':{'architectureElementId':ae.id,'version':'0.49.0'}})
                package.function_elements.append(fe);byid[identifier]=fe
            fe.realization_ids=list(dict.fromkeys([*fe.realization_ids,*ids]));linked.update(ids)
