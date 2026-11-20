"""Cross-discipline contracts and references to concrete implementations."""
from __future__ import annotations

REFERENCE_COLLECTIONS = {
    'hardware_element_ids': 'ArchitectureElement', 'signal_ids': 'ArchitectureSignal',
    'component_ids': 'Component', 'software_element_ids': 'SoftwareArchitectureElement',
    'software_component_ids': 'SoftwareComponent', 'software_interface_ids': 'InterfaceRequirement',
    'mechanical_element_ids': 'MechanicalArchitectureElement',
    'mechanical_component_ids': 'MechanicalComponent', 'mechanical_interface_ids': 'InterfaceRequirement',
    'requirement_ids': 'Requirement',
}


def validate_function_element(package, element):
    reals = {'hardware': package.technical_realizations, 'software': package.software_components,
             'mechanical': package.mechanical_components}[element.discipline]
    if set(element.realization_ids) - {r.id for r in reals}:
        raise ValueError('FE-Realisierung passt nicht zur Disziplin oder fehlt')
    allowed = {'hardware': {'EHW_IF'}, 'software': {'SW_IF', 'FW_IF'}, 'mechanical': {'MECH_IF'}}[element.discipline]
    interfaces = {i.id for i in package.interface_requirements if i.interface_class.value in allowed}
    if set(element.interface_requirement_ids) - interfaces:
        raise ValueError('FE-Schnittstelle passt nicht zur Disziplin oder fehlt')
    if element.discipline != 'hardware' and (element.interface_signal_ids or element.source_block_uuid):
        raise ValueError('ECAD-Referenzen gehören zu Hardware-FEs')
    lookup = {f.id: f for f in package.function_elements}
    for dep in element.dependency_ids:
        if dep not in lookup or dep==element.id:raise ValueError('FE-Abhängigkeit fehlt oder verweist auf sich selbst')
        if lookup[dep].discipline!=element.discipline:raise ValueError('Fachübergreifende FE-Verknüpfung über Schnittstelle zuordnen')


def validate_integrations(package, ids):
    from .traceability import project_objects
    registry = project_objects(package)
    for interface in package.integration_interfaces:
        if interface.id in ids: raise ValueError('Doppelte Schnittstellen-ID')
        ids.add(interface.id)
        if not interface.name.strip(): raise ValueError('Schnittstellenname fehlt')
        for field, kind in REFERENCE_COLLECTIONS.items():
            refs = getattr(interface, field)
            if len(refs) != len(set(refs)): raise ValueError('Doppelte Schnittstellenzuordnung')
            if set(refs) - set(registry[kind]): raise ValueError(f'Schnittstellenziel fehlt: {field}')
        if interface.kind == 'HSI' and any(getattr(interface, k) for k in REFERENCE_COLLECTIONS if k.startswith('mechanical_')):
            raise ValueError('HSI verbindet Hardware und Software')
        if interface.kind == 'HW-Mechanik' and any(getattr(interface, k) for k in REFERENCE_COLLECTIONS if k.startswith('software_')):
            raise ValueError('HW-Mechanik verbindet Hardware und Mechanik')
        for field, allowed in [('software_interface_ids', {'SW_IF', 'FW_IF'}), ('mechanical_interface_ids', {'MECH_IF'})]:
            if any(registry['InterfaceRequirement'][i].interface_class.value not in allowed for i in getattr(interface, field)):
                raise ValueError('Schnittstellentyp passt nicht zur Disziplin')
    real_kinds = {'Realization', 'Component', 'MechanicalComponent', 'SoftwareComponent', 'IntegrationInterface', 'InterfaceRequirement'}
    owners = {i for kind in real_kinds for i in registry[kind]}
    sources = set(registry['TechnicalSource']) | set(registry['SourceDocument'])
    for value in package.technical_values:
        if value.id in ids: raise ValueError('Doppelte Kennwert-ID')
        ids.add(value.id)
        if value.owner_id not in owners: raise ValueError('Ist-Kennwert benötigt eine konkrete Realisierung')
        if not value.key.strip() or value.value is None: raise ValueError('Kennwert und Wert erforderlich')
        import json
        try:json.dumps(value.value,allow_nan=False)
        except (ValueError,TypeError) as e:raise ValueError('Kennwert benötigt endliche JSON-Werte') from e
        from .property_schema import validate_value
        from .technical_comparison import SCALES
        definition = next((d for d in package.property_definitions if d.key==value.key), None)
        if not definition: raise ValueError('Kennwert im Property Manager definieren')
        check = value.value
        if definition.data_type=='number' and value.unit != definition.unit:
            if value.unit not in SCALES or definition.unit not in SCALES or SCALES[value.unit][0]!=SCALES[definition.unit][0]:
                raise ValueError('Kennwerteinheit passt nicht zur Definition')
            if isinstance(check,bool) or not isinstance(check,(int,float)): raise ValueError('Numerischer Ist-Wert erwartet')
            check = check * SCALES[value.unit][1] / SCALES[definition.unit][1]
        validate_value(definition,check)
        if set(value.source_ids) - sources: raise ValueError('Kennwertquelle fehlt')
        if value.target_id and value.target_id not in {i for kind in ('Domain','ArchitectureElement','ArchitectureSignal','Signal','Port','Connection','FunctionElement','SystemDomain','SystemElement','SoftwareArchitectureElement','MechanicalArchitectureElement') for i in registry[kind]}:
            raise ValueError('Kennwertziel muss ein vorhandenes Architekturobjekt sein')
        if value.variant_id:
            real = registry['Realization'].get(value.owner_id)
            if not real or value.variant_id not in {v.id for v in real.variants}:
                raise ValueError('Kennwertvariante gehört nicht zur Realisierung')
    for c in package.software_components:
        refs = c.dependency_ids + c.included_component_ids
        if c.id in refs or set(refs) - set(registry['SoftwareComponent']):
            raise ValueError('Software-Abhängigkeit oder Buildbestandteil fehlt')
    visiting = set(); done = set()
    def visit(identifier):
        if identifier in visiting: raise ValueError('Zyklus in Build- / Firmwarebestandteilen')
        if identifier in done: return
        visiting.add(identifier)
        c = registry['SoftwareComponent'][identifier]
        for dep in c.included_component_ids: visit(dep)
        visiting.remove(identifier); done.add(identifier)
    for identifier in registry['SoftwareComponent']: visit(identifier)
    for c in package.mechanical_components:
        if c.id in c.alternative_component_ids or set(c.alternative_component_ids) - set(registry['MechanicalComponent']):
            raise ValueError('Mechanische Alternative fehlt oder verweist auf sich selbst')


def linked_interfaces(package, object_id):
    return [i for i in package.integration_interfaces if any(object_id in getattr(i, k) for k in REFERENCE_COLLECTIONS)]


def remove_references(package, deleted):
    for i in package.integration_interfaces:
        for field in REFERENCE_COLLECTIONS:
            setattr(i, field, [v for v in getattr(i, field) if v not in deleted])
    package.integration_interfaces[:] = [i for i in package.integration_interfaces if i.id not in deleted]
    package.technical_values[:] = [v for v in package.technical_values if v.id not in deleted and v.owner_id not in deleted and v.target_id not in deleted]
    for v in package.technical_values:
        if v.target_id in deleted:v.target_id=None
        v.source_ids[:] = [i for i in v.source_ids if i not in deleted]
    for fe in package.function_elements:
        if fe.architecture_element_id in deleted: fe.architecture_element_id = None
        for field in ('requirement_ids', 'dependency_ids', 'realization_ids', 'interface_signal_ids', 'interface_requirement_ids'):
            setattr(fe, field, [i for i in getattr(fe, field) if i not in deleted])
    for c in package.software_components:
        for field in ('dependency_ids', 'included_component_ids'):
            setattr(c, field, [i for i in getattr(c, field) if i not in deleted])
    for c in package.mechanical_components:
        c.alternative_component_ids[:] = [i for i in c.alternative_component_ids if i not in deleted]
