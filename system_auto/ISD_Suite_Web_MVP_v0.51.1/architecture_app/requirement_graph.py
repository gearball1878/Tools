"""One read model for existing relationships; storage and IDs remain unchanged."""


def derivation_edges(package):
    edges={(d.source_requirement_id,d.derived_requirement_id) for d in package.requirement_derivations}
    edges.update((parent,r.id) for r in package.requirements for parent in r.parent_requirement_ids)
    edges.update((r.target_id,r.source_id) for r in package.model_relations
                 if r.kind=='derived_from' and r.source_type==r.target_type=='Requirement')
    return edges


def allocation_edges(package):
    """Requirement → typed object, excluding evidence and unrelated relations."""
    from .traceability import project_objects
    edges={(link.requirement_id,link.target_type.value,link.target_id) for link in package.requirement_links
           if link.relation.value!='Verified By' and link.target_type.value!='VerificationCase'}
    edges.update((r.source_id,r.target_type,r.target_id) for r in package.model_relations
                 if r.kind=='allocated_to' and r.source_type=='Requirement' and r.target_type!='VerificationCase')
    for kind,items in project_objects(package).items():
        if kind in {'Requirement','VerificationCase','SourceDocument','Standard'}:continue
        edges.update((rid,kind,obj.id) for obj in items.values() for rid in getattr(obj,'requirement_ids',[]))
    return edges


def test_requirement_ids(package,case):
    result=set(case.requirement_ids)
    result.update(r.source_id for r in package.model_relations if r.kind=='verified_by'
                  and r.source_type=='Requirement' and r.target_type=='VerificationCase' and r.target_id==case.id)
    result.update(r.requirement_id for r in package.requirement_links if r.target_id==case.id
                  and r.target_type.value=='VerificationCase' and r.relation.value=='Verified By')
    return result


def validate_graph(package):
    """All stored derivation representations participate in cycle detection."""
    ids={r.id for r in package.requirements};children={}
    for parent,child in derivation_edges(package):
        if parent not in ids or child not in ids:raise ValueError('Ableitung verweist auf unbekannte Anforderung')
        children.setdefault(parent,set()).add(child)
    visiting=set();done=set()
    def walk(node):
        if node in visiting:raise ValueError('Zyklus in Requirement-Ableitungen')
        if node in done:return
        visiting.add(node)
        for child in children.get(node,()):walk(child)
        visiting.remove(node);done.add(node)
    for node in ids:walk(node)
