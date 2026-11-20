"""Shared applicability rules for property editors, imports and AI changes."""
from __future__ import annotations

COMMON = {'Function','Interface','Performance','Safety & Redundancy','Environment',
          'Reliability & Availability','Security','Compliance','Lifecycle & Service','Unclassified'}
CATEGORIES = {
    'System': COMMON | {'Data Transfer','Power','Physical Integration','Thermal'},
    'Hardware': COMMON | {'Data Transfer','Power','Clock & Reset','Analog','Control & Status','Diagnostic & Test','Physical Integration','Thermal','Schematic'},
    'Mechanik': COMMON | {'Physical Integration','Thermal'},
    'Software': COMMON | {'Data Transfer','Control & Status','Diagnostic & Test'},
    'Firmware': COMMON | {'Data Transfer','Clock & Reset','Control & Status','Diagnostic & Test'},
}
ELECTRICAL = {'voltage','current','peakCurrent','power','referencePotential','isolation','frequency','dataRate','riseTime','fallTime','impedance','differentialImpedance','physicalForm','interfaceProfile','differentialPair','termination','topology','maxLength','maxSkew','voltageDrop','temperatureRise','noiseLimit','accuracy'}
ELECTRICAL |= {'interfaceType','interfaceVersion','signalRole','interfaceRole','direction','required','memberDefinition','pinMapping','connectedNet'}
MECHANICAL = {'dimensions','mass','loadCases','thermalRequirements','tolerances'}
SOFTWARE = {'runtimeResources','timing','dataContract','protocol'}

def category_options(discipline):
    from .models import RequirementCategory
    key=getattr(discipline,'value',discipline)
    return {v.value:v.value for v in RequirementCategory if v.value in CATEGORIES.get(key,COMMON)}

def property_applies(definition,obj,scope):
    kind=type(obj).__name__;discipline=getattr(getattr(obj,'classification',None),'value','')
    if definition.disciplines and discipline and discipline not in definition.disciplines:return False
    if kind in {'TechnicalRealization','DesignComponent','SoftwareComponent','MechanicalComponent'} and scope=='requirement_attributes' and definition.system:return False
    if kind=='FunctionElement' and scope=='requirement_attributes' and definition.system:return False
    if kind=='FunctionElement' and definition.key=='ecadKey' and obj.discipline!='hardware':return False
    if kind=='EcadRequirement':
        if scope!='requirement_attributes':return False
        allowed = ELECTRICAL if discipline=='Hardware' else MECHANICAL if discipline=='Mechanik' else SOFTWARE if discipline in {'Software','Firmware'} else {'power','availability'}
        if definition.system and definition.key in ELECTRICAL|MECHANICAL|SOFTWARE and definition.key not in allowed:return False
    if kind=='InterfaceRequirement':
        cls=getattr(getattr(obj,'interface_class',None),'value','')
        if definition.key in SOFTWARE and cls in {'EHW_IF','MECH_IF'}:return False
        if definition.key in ELECTRICAL and cls in {'SW_IF','FW_IF','MECH_IF'}:return False
    return True

def allowed_dependency_types(obj):
    kind=type(obj).__name__
    if kind=='FunctionElement':
        discipline=getattr(obj,'discipline','hardware')
        return ['FunctionElement', {'hardware':'ArchitectureElement','software':'SoftwareArchitectureElement','mechanical':'MechanicalArchitectureElement'}[discipline], 'InterfaceRequirement'] + (['ArchitectureSignal','InterfacePort'] if discipline=='hardware' else [])
    return {
        'Domain':['Domain','ArchitectureElement','FunctionElement','SystemElement'],
        'ArchitectureElement':['ArchitectureElement','FunctionElement','ArchitectureSignal','InterfacePort','InterfaceRequirement'],
        'FunctionElement':['FunctionElement','ArchitectureElement','ArchitectureSignal','InterfacePort','InterfaceRequirement'],
        'TechnicalRealization':['TechnicalRealization','ArchitectureElement','FunctionElement','DesignComponent','InterfaceRequirement'],
        'DesignComponent':['DesignComponent','ArchitectureElement','FunctionElement','InterfaceRequirement'],
        'MechanicalComponent':['MechanicalComponent','MechanicalArchitectureElement','MechanicalConstraint','InterfaceRequirement','SystemElement'],
        'MechanicalArchitectureElement':['MechanicalArchitectureElement','MechanicalComponent','MechanicalConstraint','InterfaceRequirement','SystemElement'],
        'SoftwareComponent':['SoftwareComponent','SoftwareArchitectureElement','InterfaceRequirement','ArchitectureElement','FunctionElement'],
        'SoftwareArchitectureElement':['SoftwareArchitectureElement','SoftwareComponent','InterfaceRequirement','ArchitectureElement','FunctionElement'],
    }.get(kind,['SystemElement','SystemDomain','Domain','ArchitectureElement','FunctionElement','MechanicalArchitectureElement','SoftwareArchitectureElement'])

def dependency_target_applies(obj,target):
    if type(target).__name__ not in allowed_dependency_types(obj):return False
    if type(obj).__name__=='FunctionElement' and type(target).__name__=='FunctionElement':return obj.discipline==target.discipline
    if type(target).__name__!='InterfaceRequirement':return True
    source=type(obj).__name__;cls=getattr(target.interface_class,'value',target.interface_class)
    if source=='FunctionElement':return cls in {'hardware':{'EHW_IF'},'software':{'SW_IF','FW_IF'},'mechanical':{'MECH_IF'}}[obj.discipline]
    if source in {'ArchitectureElement','DesignComponent'}:return cls=='EHW_IF'
    if source in {'MechanicalComponent','MechanicalArchitectureElement'}:return cls=='MECH_IF'
    if source in {'SoftwareComponent','SoftwareArchitectureElement'}:return cls in {'SW_IF','FW_IF','EHW_IF'}
    return True

def validate_selection(definition,obj,package,value):
    from .property_schema import selection_options,validate_value
    validate_value(definition,value)
    if value is None or not (definition.selection_source or definition.choices):return
    allowed=selection_options(definition,obj,package)
    entries=value if isinstance(value,list) else [value]
    if any(not isinstance(v,str) or v not in allowed for v in entries):
        raise ValueError(f'{definition.label}: Auswahl passt nicht zum Objekttyp oder Katalog')

def eligible_parents(package,requirement):
    from .requirements_layers import effective_layer,LAYERS
    ranks={layer:i for i,(_,_,layer) in enumerate(LAYERS)}
    own=ranks[effective_layer(requirement)]
    return [r for r in package.requirements if r.id!=requirement.id and ranks[effective_layer(r)]<own]
