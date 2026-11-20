"""Read-only comparison of explicit requirement and implementation sources."""
from __future__ import annotations
from dataclasses import dataclass
import math

ARCHITECTURE_KINDS = {'SystemDomain','SystemElement','SystemRelation','Domain','ArchitectureElement',
    'InterfacePort','ArchitectureSignal','Signal','Connection','MechanicalArchitectureElement',
    'SoftwareArchitectureElement','DisciplineRelation','FunctionElement'}
TECHNICAL_KEYS = {'voltage','current','peakCurrent','power','powerBudget','frequency','dataRate','riseTime',
    'fallTime','impedance','differentialImpedance','maxLength','maxSkew','voltageDrop','temperatureRise',
    'accuracy','noiseLimit','isolation','resolution','channels','capacity','dimensions','mass','material',
    'loadCases','thermalRequirements','tolerances','runtimeResources','timing','dataContract','protocol',
    'availability','performance','resourceBudget','termination','referencePotential','physicalForm','polarity'}


def connected_signal(package, obj):
    if type(obj).__name__ == 'ArchitectureSignal': return obj
    if type(obj).__name__ == 'Signal':
        return next((s for s in package.signals if any(m.id==obj.id for m in s.bus_contents)),None)
    if type(obj).__name__ == 'Connection': identifier = obj.signal_id
    elif type(obj).__name__ == 'InterfacePort':
        identifier = obj.interface_link_id or obj.attributes.get('architectureSignalId') or obj.properties.get('architectureSignalId')
        if not identifier:
            connection = next((c for c in package.connections if any(e.port_id == obj.id for e in c.endpoints)), None)
            identifier = connection.signal_id if connection else None
    else: return None
    return next((s for s in package.signals if s.id == identifier), None)


def ecad_key(obj):
    return (getattr(obj, 'technical_name', '') or getattr(obj, 'source_block_uuid', '')
            or getattr(obj, 'attributes', {}).get('nativeScmUuid') or getattr(obj,'properties',{}).get('nativeScmUuid') or getattr(obj,'properties',{}).get('kicadPinUuid')
            or getattr(obj, 'realization_attributes', {}).get('ecadKey') or obj.id)


def actual_objects(package, obj):
    from .traceability import project_objects
    registry = project_objects(package)
    identifiers = set(getattr(obj, 'realization_ids', []))
    if type(obj).__name__ == 'FunctionElement':
        identifiers.update(r.id for r in package.technical_realizations if r.function_element_id == obj.id)
    if type(obj).__name__ == 'ArchitectureElement':
        identifiers.update(r.id for r in package.technical_realizations if r.architecture_element_id == obj.id)
    for f in package.function_elements:
        if f.architecture_element_id == obj.id:
            identifiers.update(r.id for r in actual_objects(package, f))
    identifiers.update(a.target_id for a in package.architecture_allocations if a.system_element_id == obj.id)
    identifiers.update(r.target_id for r in package.model_relations if r.source_id == obj.id and r.kind == 'realized_by')
    # A technical realization is itself a valid source for its active variant.
    if type(obj).__name__ not in ARCHITECTURE_KINDS: identifiers.add(obj.id)
    result = []
    real_kinds = {'Realization','Component','SoftwareComponent','MechanicalComponent','InterfaceRequirement','IntegrationInterface'}
    for kind in real_kinds:
        for identifier, actual in registry[kind].items():
            if identifier in identifiers: result.append(actual)
    for actual in list(result):
        if type(actual).__name__ == 'TechnicalRealization':
            for variant in actual.variants:
                if variant.id != actual.selected_variant_id: continue
                ids = {c.component_id for c in variant.component_roles} | set(variant.software_component_ids) | set(variant.mechanical_component_ids)
                result.extend(o for kind in real_kinds for i, o in registry[kind].items() if i in ids)
    return list({o.id: o for o in result}.values())


@dataclass
class ComparisonRow:
    key: str
    label: str
    required: object
    actual: object
    unit: str
    status: str
    requirement_id: str | None
    actual_id: str | None
    conditions: dict
    origin: str = ''
    revision: str = ''
    evidence: str = 'Offen'
    legacy: bool = False
    source_ids: tuple = ()
    rationale: str = ''


SCALES = {'V':('voltage',1),'mV':('voltage',.001),'A':('current',1),'mA':('current',.001),
    'W':('power',1),'mW':('power',.001),'Hz':('frequency',1),'kHz':('frequency',1e3),'MHz':('frequency',1e6),
    's':('time',1),'ms':('time',.001),'µs':('time',1e-6),'ns':('time',1e-9),'ps':('time',1e-12),
    'm':('length',1),'mm':('length',.001),'kg':('mass',1),'g':('mass',.001)}


def compare(required, actual, unit='', conditions=None, actual_conditions=None):
    if required is None or actual is None: return 'Offen'
    if (conditions or {}) != (actual_conditions or {}): return 'Bedingungen prüfen'
    ru = required.get('unit', unit) if isinstance(required, dict) else unit
    au = actual.get('unit', unit) if isinstance(actual, dict) else unit
    factor = 1
    if ru != au:
        if ru not in SCALES or au not in SCALES or SCALES[ru][0] != SCALES[au][0]: return 'Einheiten prüfen'
        factor = SCALES[au][1] / SCALES[ru][1]
    value = actual.get('value') if isinstance(actual, dict) else actual
    numeric = isinstance(value, (int,float)) and not isinstance(value, bool) and math.isfinite(value)
    if isinstance(required, dict) and any(k in required for k in ('min','max','value')):
        if not numeric: return 'Manuell bewerten'
        value *= factor
        bounds = [(k, v) for k,v in required.items() if k in {'min','max','value'} and v is not None]
        if not bounds: return 'Offen'
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for _,v in bounds): return 'Manuell bewerten'
        good = all(value >= v if k=='min' else value <= v if k=='max' else math.isclose(value,v,rel_tol=1e-9,abs_tol=1e-12) for k,v in bounds)
        return 'Passend' if good else 'Abweichung'
    if numeric and isinstance(required,(int,float)) and not isinstance(required,bool):
        return 'Passend' if math.isclose(required,value*factor,rel_tol=1e-9,abs_tol=1e-12) else 'Abweichung'
    if ru != au: return 'Manuell bewerten'
    if isinstance(required,(dict,list)): return 'Manuell bewerten'
    return 'Passend' if required == actual else 'Abweichung'


def comparison_rows(package, obj):
    from .requirement_graph import allocation_edges
    definitions = {d.key:d for d in package.property_definitions}
    ids = {obj.id}
    attached = connected_signal(package, obj)
    if attached: ids.add(attached.id)
    implementation_objects=actual_objects(package,obj)
    if type(obj).__name__=='FunctionElement':ids.update(a.id for a in implementation_objects)
    requirements = {rid for rid, _, target in allocation_edges(package) if target in ids}
    requirements.update(getattr(obj, 'requirement_ids', []))
    demands = []
    for req in package.requirements:
        if req.id not in requirements: continue
        conditions = req.requirement_attributes.get('operatingConditions') or {}
        for key, value in req.requirement_attributes.items():
            if value is not None and (key in TECHNICAL_KEYS or key in definitions and not definitions[key].system):
                demands.append((key, value, req.id, conditions, False))
    # Applicable fields on directly allocated requirements are visible even when open.
    from .property_schema import applicable
    for req in package.requirements:
        if req.id not in requirements:continue
        existing={(key,rid) for key,_,rid,_,_ in demands}
        for d in applicable(package.property_definitions,req,'requirement_attributes'):
            if (d.key in TECHNICAL_KEYS or not d.system) and (d.key,req.id) not in existing:
                demands.append((d.key,None,req.id,req.requirement_attributes.get('operatingConditions') or {},False))
    legacy = getattr(obj,'attributes',{}).get('legacyPropertyValues',{})
    for key, value in legacy.get('requirement_attributes',{}).items():
        if key in TECHNICAL_KEYS and value is not None: demands.append((key,value,None,legacy.get('requirement_attributes',{}).get('operatingConditions') or {},True))
    actuals = {}
    open_actuals={}
    for actual in implementation_objects:
        for d in applicable(package.property_definitions,actual,'realization_attributes'):
            if d.key in TECHNICAL_KEYS or not d.system:open_actuals.setdefault(d.key,actual.id)
        old_values=getattr(actual,'attributes',{}).get('legacyPropertyValues',{})
        for key,value in old_values.get('requirement_attributes',{}).items():
            if key in TECHNICAL_KEYS and value is not None:
                demands.append((key,value,actual.id,old_values.get('requirement_attributes',{}).get('operatingConditions') or {},True))
        for key,value in old_values.get('realization_attributes',{}).items():
            if key in TECHNICAL_KEYS and value is not None:
                actuals.setdefault(key,[]).append((value,actual.id,{},'Bestandswert','',True,(),''))
        for key, value in actual.realization_attributes.items():
            if value is not None: actuals.setdefault(key,[]).append((value,actual.id,{},'Explizite Designangabe',getattr(actual,'version',getattr(actual,'revision','')),False,(),''))
        if type(actual).__name__ == 'TechnicalRealization':
            for variant in actual.variants:
                if variant.id == actual.selected_variant_id:
                    for key,value in variant.technical_parameters.items():
                        actuals.setdefault(key,[]).append((value,actual.id,{},'Aktive Variante',variant.name,False,tuple(variant.evidence_source_ids),''))
        for value in package.technical_values:
            if value.owner_id != actual.id or value.target_id and value.target_id not in ids: continue
            if value.variant_id and value.variant_id != getattr(actual,'selected_variant_id',None): continue
            val = {'value':value.value,'unit':value.unit} if value.unit and not isinstance(value.value,dict) else value.value
            actuals.setdefault(value.key,[]).append((val,actual.id,value.conditions,value.origin,value.revision,False,tuple(value.source_ids),value.rationale))
    for key,value in legacy.get('realization_attributes',{}).items():
        if key in TECHNICAL_KEYS and value is not None:
            provenance=getattr(obj,'attributes',{}).get('attributeProvenance',{}).get(key,{})
            actuals.setdefault(key,[]).append((value,obj.id,legacy.get('realization_attributes',{}).get('operatingConditions') or {},'Bestandswert · '+str(provenance.get('source','Herkunft prüfen')),str(provenance.get('revision','')),True,(),str(provenance.get('rationale',''))))
    for key,identifier in open_actuals.items():
        actuals.setdefault(key,[(None,identifier,{},'','',False,(),'')])
    demand_keys = {d[0] for d in demands}
    demands.extend((key,None,None,{},False) for key in actuals if key in TECHNICAL_KEYS and key not in demand_keys)
    rows = []
    for key,required,rid,conditions,is_legacy in demands:
        definition = definitions.get(key)
        for value,aid,ac,origin,revision,old,sources,rationale in actuals.get(key,[(None,None,{},'','',False,(),'')]):
            status = compare(required,value,definition.unit if definition else '',conditions,ac)
            if is_legacy or old: status = 'Bestand prüfen'
            assessments = [a for a in package.fulfillment_assessments if a.requirement_id == rid and a.realization_id == aid]
            from .traceability import assessment_current
            evidence = ', '.join('Erneut prüfen' if a.status=='Reviewed' and not assessment_current(package,a) else a.status+' · '+a.result for a in assessments) or 'Offen'
            rows.append(ComparisonRow(key,definition.label if definition else key,required,value,definition.unit if definition else '',status,rid,aid,{'Soll':conditions,'Ist':ac},origin,revision,evidence,is_legacy or old,sources,rationale))
    return rows
