"""One graph-based engineering context for every AI operation."""
from .traceability import project_objects, evidence_status
from .requirement_graph import derivation_edges, allocation_edges

def compact(value):
    if isinstance(value,dict):return {k:compact(v) for k,v in value.items() if v is not None and v not in ('',[],{})}
    if isinstance(value,list):return [compact(v) for v in value]
    return value

def engineering_context(package,selected_object_id='',economy=False):
    registry=project_objects(package);objects={o.id:(kind,o) for kind,group in registry.items() for o in group.values()}
    edges={(a,b,'derived_from') for a,b in derivation_edges(package)}
    edges.update((rid,oid,'allocated_to') for rid,kind,oid in allocation_edges(package))
    edges.update((r.source_id,r.target_id,r.kind) for r in package.model_relations)
    for domain in package.domains:
        edges.update((domain.id,e.id,'contains') for e in domain.elements)
        for element in domain.elements:
            edges.update((element.id,p.id,'port') for p in element.ports)
            for port in element.ports:
                sid=port.interface_link_id or port.properties.get('architectureSignalId') or port.attributes.get('architectureSignalId')
                if sid:edges.add((sid,port.id,'signal_port'))
    for signal in package.signals:
        endpoints=([signal.source] if signal.source else [])+signal.sinks
        edges.update((ep.element_id,signal.id,'signal') for ep in endpoints)
    for link in package.architecture_allocations:edges.add((link.system_element_id,link.target_id,'allocated_to'))
    for collection in (package.mechanical_architecture_elements,package.software_architecture_elements):
        for element in collection:
            edges.update((element.id,i,'realizes') for i in element.realization_ids)
            if element.parent_id:edges.add((element.parent_id,element.id,'contains'))
    for r in package.technical_realizations:
        if r.architecture_element_id:edges.add((r.architecture_element_id,r.id,'realizes'))
        if r.function_element_id:edges.add((r.function_element_id,r.id,'realizes'))
        for v in r.variants:
            if r.selected_variant_id and r.selected_variant_id!=v.id:continue
            from .realization_service import core_component_ids
            cores=core_component_ids(package,v)
            edges.update((r.id,role.component_id,'core_technology' if role.component_id in cores else 'support_part') for role in v.component_roles)
            edges.update((r.id,i,'implementation') for i in v.mechanical_component_ids+v.software_component_ids)
    for f in package.function_elements:
        edges.update((rid,f.id,'allocated_to') for rid in f.requirement_ids)
        if f.architecture_element_id:edges.add((f.architecture_element_id,f.id,'function'))
        edges.update((f.id,i,'dependency') for i in f.dependency_ids)
        edges.update((f.id,i,'functional_interface') for i in f.interface_signal_ids)
    for source in package.technical_sources:edges.add((source.owner_id,source.id,'evidence'))
    for component in package.components:edges.update((component.id,i,'alternative') for i in component.alternative_component_ids)
    for link in package.requirement_standard_links:edges.add((link.requirement_id,link.standard_id,'governed_by'))
    from .integration import REFERENCE_COLLECTIONS
    for interface in package.integration_interfaces:
        edges.update((interface.id,i,'technical_interface') for field in REFERENCE_COLLECTIONS for i in getattr(interface,field))
    for value in package.technical_values:edges.add((value.owner_id,value.id,'actual_value'))
    for f in package.function_elements:
        edges.update((f.id,i,'realizes') for i in f.realization_ids)
        edges.update((f.id,i,'technical_interface') for i in f.interface_requirement_ids)
    for c in package.software_components:
        edges.update((c.id,i,'dependency') for i in c.dependency_ids)
        edges.update((c.id,i,'contains') for i in c.included_component_ids)
    selected=set(objects)
    if selected_object_id in objects:
        from .requirements_layers import focused_graph
        selected=focused_graph(objects,{(a,b) for a,b,kind in edges},selected_object_id)
        # A norm/evidence child of a relevant requirement accompanies that
        # requirement, without bringing unrelated derivation siblings along.
        selected.update(link.standard_id for link in package.requirement_standard_links if link.requirement_id in selected)
        selected.update(claim.standard_id for c in package.components if c.id in selected for claim in c.standard_claims)
        # Sources belonging to any relevant object accompany its graph context.
        selected.update(s.id for s in package.technical_sources if s.owner_id in selected)
    priority={'Requirement':0,'SystemElement':1,'SystemDomain':1,'Domain':2,'ArchitectureElement':2,
              'FunctionElement':2,'MechanicalArchitectureElement':2,'SoftwareArchitectureElement':2,
              'Realization':3,'Standard':4,'InterfaceRequirement':4,'TechnicalSource':6,'Component':7}
    from .realization_service import core_component_ids
    cores={i for r in package.technical_realizations for v in r.variants
           if not r.selected_variant_id or r.selected_variant_id==v.id for i in core_component_ids(package,v)}
    ordered=sorted(selected,key=lambda i:(i!=selected_object_id,5 if i in cores else priority.get(objects[i][0],8),objects[i][0],i))
    budget=100 if economy and not selected_object_id else 250 if economy else len(ordered)
    chosen=ordered[:budget]
    records=[]
    for identifier in chosen:
        kind,obj=objects[identifier];payload=compact(obj.model_dump(mode='json'))
        payload.pop('reviewed_revisions',None)
        if kind=='TechnicalSource':
            text=obj.extracted_content;limit=12000 if economy else 50000
            payload['extracted_content']=text[:limit];payload['contentAvailable']=bool(text);payload['contentTruncated']=len(text)>limit
            payload['evidenceLocator']=obj.evidence_locator
        records.append({'objectType':kind,'object':payload})
    from .requirement_profiles import allowed_dependency_types,category_options
    definitions=[compact(d.model_dump(mode='json')) for d in package.property_definitions]
    return {'selectedObjectId':selected_object_id,'objects':records,
        'relations':[{'sourceId':a,'targetId':b,'kind':kind} for a,b,kind in sorted(edges) if a in chosen and b in chosen],
        'propertyDefinitions':definitions,'netClasses':[{'name':c.name,'description':c.description} for c in package.net_classes],
        'dependencyTargetTypes':{kind:allowed_dependency_types(obj) for kind,obj in objects.values() if hasattr(obj,'requirement_attributes')},
        'requirementCategories':{d:list(category_options(d)) for d in ('System','Hardware','Mechanik','Software','Firmware')},
        'requirementEvidence':{r.id:evidence_status(package,r).__dict__ for r in package.requirements if r.id in chosen},
        'completeness':{'totalObjects':len(objects),'relevantObjects':len(ordered),'suppliedObjects':len(chosen),'truncated':len(chosen)<len(ordered)},
        'workflowRules':{'layers':['L1 Kunde','L2 System','L3 Technik','L4 Disziplin'],
            'functionElement':'Abstract function, interfaces and core dependencies. Parts belong to realization.',
            'coreComponents':'Several system-defining parts may implement a function; no automatic full BOM expansion.',
            'hwPorts':'Every HW port uses its connected net or bus name. *_Port_* names are internal functional-block interfaces.',
            'verification':'Use stored current evidence status. Never invent passed tests or standards compliance.'}}
