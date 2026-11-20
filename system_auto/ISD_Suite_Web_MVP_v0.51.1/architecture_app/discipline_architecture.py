"""Independent mechanical/software architecture nodes with explicit realizations."""
from __future__ import annotations
from html import escape

RELATION_KINDS = {
    'mechanical':['Befestigung','Einbau','Kontaktfläche','Wärmeweg','Abhängigkeit'],
    'software':['API','Datenfluss','Ereignis','Kommunikation','Abhängigkeit'],
}


def elements(package,discipline):
    return package.mechanical_architecture_elements if discipline=='mechanical' else package.software_architecture_elements


def validate_discipline_architecture(package,ids):
    requirement_ids={r.id for r in package.requirements}
    for discipline in RELATION_KINDS:
        nodes=elements(package,discipline);lookup={n.id:n for n in nodes};names=set()
        for node in nodes:
            if node.id in ids:raise ValueError('Doppelte Facharchitektur-ID')
            ids.add(node.id)
            if not node.name.strip() or node.name.strip().casefold() in names:raise ValueError('Facharchitekturelemente benötigen eindeutige Namen')
            names.add(node.name.strip().casefold())
            if set(node.requirement_ids)-requirement_ids:raise ValueError('Facharchitekturelement verweist auf unbekannte Anforderung')
            if node.parent_id and node.parent_id not in lookup:raise ValueError('Übergeordnetes Facharchitekturelement fehlt')
            visited={node.id};parent=node.parent_id
            while parent:
                if parent in visited:raise ValueError('Zyklus in Facharchitektur-Hierarchie')
                if parent not in lookup:raise ValueError('Übergeordnetes Facharchitekturelement fehlt')
                visited.add(parent);parent=lookup[parent].parent_id
            if len(node.realization_ids)!=len(set(node.realization_ids)):raise ValueError('Doppelte Realisierungszuordnung')
        for relation in package.discipline_relations:
            if relation.discipline!=discipline:continue
            if relation.id in ids:raise ValueError('Doppelte Beziehungs-ID')
            ids.add(relation.id)
            if relation.source_id not in lookup or relation.target_id not in lookup:raise ValueError('Fachbeziehung verweist auf unbekanntes Architekturelement')
            if relation.source_id==relation.target_id:raise ValueError('Selbstbeziehung ist nicht zulässig')
            if relation.kind not in RELATION_KINDS[discipline]:raise ValueError('Ungültiger Fachbeziehungstyp')
            if not relation.name.strip():raise ValueError('Beziehungsname fehlt')
            if set(relation.requirement_ids)-requirement_ids:raise ValueError('Fachbeziehung verweist auf unbekannte Anforderung')


def remove_element(package,discipline,identifier):
    collection=elements(package,discipline)
    collection[:]=[n for n in collection if n.id!=identifier]
    for n in collection:
        if n.parent_id==identifier:n.parent_id=None
    related={r.id for r in package.discipline_relations if identifier in {r.source_id,r.target_id}}
    package.discipline_relations=[r for r in package.discipline_relations if r.id not in related]
    package.architecture_allocations=[a for a in package.architecture_allocations if a.target_id!=identifier]
    removed=related|{identifier}
    package.model_relations=[r for r in package.model_relations if r.source_id not in removed and r.target_id not in removed]
    package.requirement_links=[r for r in package.requirement_links if r.target_id not in removed]
    from .traceability import remove_deleted_references
    remove_deleted_references(package,removed)


def adopt_realizations(package,discipline):
    """Explicit user action; identities and actual realization objects are retained."""
    from .models import MechanicalArchitectureElement,SoftwareArchitectureElement
    cls=MechanicalArchitectureElement if discipline=='mechanical' else SoftwareArchitectureElement
    collection=elements(package,discipline)
    realizations=package.mechanical_components if discipline=='mechanical' else package.software_components
    linked={rid for n in collection for rid in n.realization_ids};names={n.name.casefold() for n in collection};mapping={}
    for real in realizations:
        if real.id in linked:continue
        base=real.name;name=base;index=2
        while name.casefold() in names:name=f'{base} {index}';index+=1
        node=cls(name=name,description=real.description,requirement_ids=list(real.requirement_ids),realization_ids=[real.id])
        collection.append(node);mapping[real.id]=node;names.add(name.casefold())
    for real in realizations:
        if real.id in mapping and real.parent_component_id in mapping:mapping[real.id].parent_id=mapping[real.parent_component_id].id
    return len(mapping)


def discipline_svg(package,discipline,selected=None):
    nodes=[*elements(package,discipline),*(f for f in package.function_elements if f.discipline==discipline)];edges=[r for r in package.discipline_relations if r.discipline==discipline]
    height=max(220,80+len(nodes)*92);width=1000
    positions={n.id:(80,60+i*92) for i,n in enumerate(nodes)}
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Facharchitektur">']
    for index,r in enumerate(edges):
        if r.source_id not in positions or r.target_id not in positions:continue
        _,sy=positions[r.source_id];_,ty=positions[r.target_id];x=540+(index%10)*36
        out.append(f'<path d="M 490 {sy+30} H {x} V {ty+30} H 490" fill="none" stroke="#64748b" stroke-width="2"/>')
        out.append(f'<path d="M 490 {ty+30} l 8 -4 v 8 z" fill="#64748b"/>')
        out.append(f'<text x="{x+5}" y="{(sy+ty)/2+25}" font-size="12" fill="#334155">{escape(r.name[:25])}</text>')
    for node in nodes:
        x,y=positions[node.id];color='#d97706' if node.id==selected else '#0f766e'
        out.append(f'<g data-system-id="{escape(node.id,quote=True)}" style="cursor:pointer"><rect x="{x}" y="{y}" width="410" height="64" rx="8" fill="#f0fdfa" stroke="{color}" stroke-width="2"/>')
        out.append(f'<text x="{x+14}" y="{y+25}" font-size="15" fill="#17365d">{escape(node.name[:48])}</text>')
        out.append(f'<text x="{x+14}" y="{y+46}" font-size="12" fill="#52657b">{escape(getattr(node,'kind','Funktions Element'))} · {len(node.requirement_ids)} Anforderungen · {len(node.realization_ids)} Realisierungen</text></g>')
    out.append('</svg>');return ''.join(out)
