"""One catalog for native object fields, inspectors and protected definitions.

Native fields are displayed from the model. They never create a second value in
an attribute dictionary; the object's existing edit mask remains responsible.
"""
from functools import lru_cache
from enum import Enum
import hashlib
import re
from typing import get_args
from .property_schema import PropertyDefinition, KIND_LABELS

NATIVE_KIND_LABELS = {**KIND_LABELS,'ArchitectureAllocation':'Architekturzuordnung','ComponentRequirement':'Komponentenanforderung','ComponentAllocation':'Bauteileinsatz / Zuordnung','RealizationComponentRole':'Bauteilrolle','SolutionVariant':'Implementierungsvariante','TechnicalValue':'Technischer Ist-Wert','TechnicalSource':'Technische Dokumentquelle','SourceDocument':'Quelldokument','StandardReference':'Norm / Standard','ComponentStandardClaim':'Normenqualifikation','RequirementStandardLink':'Requirement-Norm-Zuordnung','RequirementDerivation':'Requirement-Ableitung','RequirementLink':'Requirement-Verknüpfung','ModelRelation':'Modellbeziehung','Observation':'Beobachtung','FulfillmentAssessment':'Erfüllungsbewertung','VerificationCase':'Verifikation','SoftwareWorkItem':'Softwareaufgabe','InterfaceDefinition':'Signal- / Interfacevorlage','ProjectInfo':'Projekt'}

INTERNAL = {'requirement_attributes','realization_attributes','attributes','properties'}
LABELS = {
    'core_idea':'Kernidee','system_boundary':'Systemgrenze','primary_flow':'Hauptfunktion / Hauptfluss','operating_locations':'Einsatzorte','operating_scenarios':'Einsatzszenarien','external_systems':'Externe Systeme','exclusions':'Ausnahmen / Abgrenzung','assumptions':'Annahmen','reviewed_at':'Prüfstand',
    'pin_type':'ECAD-Pintyp','active_low':'Aktiv bei Low','required':'Erforderlich','external':'Externes System / Akteur','package_id':'Package-Kennung','build_id':'Build-Kennung','artifact_url':'Softwareartefakt','runtime':'Laufzeitumgebung','port_type':'Schnittstellentyp','interface_kind':'Interfacefamilie','instance_index':'Instanznummer','catalog_family':'Katalogfamilie','catalog_status':'Vorlagenzuordnung','observed_names':'Beobachtete Signalnamen',
    'id':'UUID / Objektkennung','name':'Name','title':'Titel','description':'Beschreibung','technical_name':'Technischer Name',
    'domain_type_id':'Domänentyp','role_type_id':'AE-Rolle','technical_domain_ids':'Technische Domänen',
    'color':'Darstellungsfarbe','elements':'Architekturelemente','ports':'Ports','signals':'Signale',
    'role':'Host / Teilnehmer','direction':'Signalrichtung','side':'Zeichenseite','order':'Reihenfolge',
    'position':'Position','signal_type':'Signaltyp','connection_type':'Netz / Bus','bus_contents':'Businhalt',
    'source':'Host / Quelle','sinks':'Teilnehmer / Senken','endpoints':'Verbindungsendpunkte','signal_id':'Netz / Bus',
    'interface_link_id':'Verknüpftes Netz / Bus','catalog_template':'Signalvorlage','template_name':'Signalvorlage',
    'architecture_element_id':'Architekturelement','realization_ids':'Implementierungen',
    'requirement_ids':'Direkt zugeordnete Requirements','dependency_ids':'Abhängige Funktionselemente',
    'interface_signal_ids':'HW-Netze / Busse','interface_requirement_ids':'Funktionale Schnittstellen',
    'source_block_uuid':'ECAD-Blockkennung','source_project':'ECAD-Projekt','source_sheet':'Schaltplanblatt','source_revision':'Quellrevision',
    'discipline':'Disziplin','kind':'Objekttyp','status':'Status','generic_function':'Funktionsbeschreibung der Implementierung',
    'function_element_id':'Führendes Funktionselement','variants':'Implementierungsvarianten','selected_variant_id':'Aktive Variante',
    'source_document_id':'Quelldokument','source_document_ids':'Quelldokumente','rationale':'Begründung','provenance':'Herkunft',
    'manufacturer':'Hersteller','manufacturer_part_number':'MPN','package_name':'Gehäuse','part_revision':'Bauteilrevision',
    'system_defining':'Systemdefinierendes Bauteil','system_defining_reason':'Systembeitrag','alternative_component_ids':'Alternative Bauteile',
    'standard_claims':'Normen- und Standardangaben','quantity':'Menge','reference_designators':'ECAD-Referenzbezeichner',
    'lifecycle_status':'Lebenszyklusstatus','component_type':'Bauteiltyp','part_number':'Teilenummer','maturity':'Reifegrad',
    'cad_reference':'CAD-Referenz','cad_revision':'CAD-Revision','plm_reference':'PLM / ERP-Referenz','material':'Material',
    'dimensions':'Abmessungen','mass':'Masse','protection_rating':'Schutzart','cooling_method':'Kühlkonzept',
    'power_dissipation':'Verlustleistung','temperature_range':'Temperaturbereich','repository_url':'Repository',
    'code_path':'Codepfad','commit':'Commit','version':'Version','package_reference':'Package-Referenz','build_reference':'Build-Referenz',
    'runtime_platform':'Zielplattform','domain':'Software / Firmware','hardware_element_ids':'HW-Architekturelemente',
    'signal_ids':'HW-Netze / Busse','component_ids':'Bauteile','software_element_ids':'SW-Architekturelemente',
    'software_component_ids':'Softwarekomponenten','software_interface_ids':'Softwareschnittstellen',
    'mechanical_element_ids':'Mechanik-Architekturelemente','mechanical_component_ids':'Mechanische Teile',
    'mechanical_interface_ids':'Mechanische Schnittstellen','configuration':'Implementierungskonfiguration','revision':'Revision',
    'required_standards':'Geforderte Normen','standard_ids':'Normen und Standards','statement':'Anforderungsaussage',
    'text':'Anforderungsaussage','identifier':'Requirement-Kennung','classification':'Disziplin','acceptance_criteria':'Akzeptanzkriterien',
    'interface_class':'Schnittstellenklasse','type':'Typ','value':'Wert','unit':'Einheit','parent_id':'Übergeordnetes Objekt',
    'system_element_ids':'Systemelemente','source_id':'Quellobjekt','target_id':'Zielobjekt','source_type':'Quellobjekttyp',
    'target_type':'Zielobjekttyp','relation':'Beziehung','connection_ids':'Verbindungen','dependencies':'Abhängigkeiten',
}
RELATIONS = {'elements','ports','signals','source','sinks','endpoints','bus_contents','variants','standard_claims'}
SOURCES = {'source_project','source_sheet','source_revision','source_block_uuid','repository_url','code_path','commit','version','cad_reference','cad_revision','plm_reference','part_revision','revision','package_reference','build_reference'}
PROCESS = {'status','maturity','provenance','lifecycle_status','rationale','system_defining_reason'}
CLASSIFICATION = {'kind','type','component_type','domain_type_id','role_type_id','domain','discipline','classification','interface_class','signal_type','connection_type','role','direction','side','system_defining'}
TECHNICAL = {'dimensions','mass','material','power_dissipation','temperature_range','protection_rating','cooling_method','quantity'}


def field_label(name):
    return LABELS.get(name,re.sub(r'(?<=[a-z])(?=[A-Z])',' ',name.replace('_',' ')).capitalize())


def field_kind(name):
    if name in {'id','technical_name','source_block_uuid'}:return 'identity'
    if name.endswith(('_id','_ids')) or name in RELATIONS:return 'relation'
    if name in SOURCES:return 'source'
    if name in PROCESS:return 'process'
    if name in CLASSIFICATION:return 'classification'
    if name in TECHNICAL:return 'technical'
    if name in {'order','position','color'}:return 'derived' if name=='position' else 'classification'
    return 'description'


def native_definition(kind,name,field):
    annotation=field.annotation;args=get_args(annotation)
    plain=next((a for a in args if a is not type(None)),annotation) if type(None) in args else annotation
    choices=[]
    if isinstance(plain,type) and issubclass(plain,Enum):choices=[v.value for v in plain]
    elif get_args(plain) and all(isinstance(a,str) for a in get_args(plain)):choices=list(get_args(plain))
    explicit_choices={('InterfacePort','role'):['Host','Participant'],('InterfacePort','side'):['Auto','Left','Right'],('Signal','pin_type'):['IN','OUT','BI','POWER','GROUND','ANALOG','OCL','OEM','TRI','TERMINAL']}
    choices=explicit_choices.get((kind,name),choices)
    category=field_kind(name)
    typ='enum' if choices else 'boolean' if plain is bool else 'number' if plain in {int,float} else 'list' if getattr(plain,'__origin__',None) is list else 'reference' if name.endswith('_id') else 'json' if getattr(plain,'__origin__',None) is dict else 'text'
    scope='requirement_attributes' if kind=='EcadRequirement' else 'realization_attributes' if kind in {'TechnicalRealization','DesignComponent','MechanicalComponent','SoftwareComponent'} or category=='source' else None
    description=field.description or (f'{field_label(name)} des Objekts. ' + ('Verknüpft vorhandene Projektobjekte.' if category=='relation' else 'Wird in der Objektmaske gepflegt.'))
    authority='ECAD' if name.startswith('source_') and kind=='FunctionElement' or name=='reference_designators' else 'CAD' if name.startswith('cad_') else 'PLM / ERP' if name=='plm_reference' else 'Softwarewerkzeug' if name in {'code_path','commit','repository_url','build_reference'} else 'Topologie' if kind=='InterfacePort' and name in {'role','direction','side','interface_link_id'} else 'ISD'
    readonly=name in {'id','technical_name','source_block_uuid','source_project','source_sheet','source_revision','reference_designators','side'}
    return PropertyDefinition.model_construct(id=hashlib.sha256(('native:'+kind+':'+name).encode()).hexdigest(),key='native.'+kind+'.'+name,
        label=field_label(name),description=description,object_types=[kind],scopes=[scope] if scope else ['requirement_attributes','realization_attributes'],
        data_type=typ,choices=choices,system=True,readonly=readonly,origin='ISD-Objektmodell',storage='native',attribute_kind=category,authority=authority,
        exchange='Abgleich' if kind in {'Domain','ArchitectureElement','InterfacePort','ArchitectureSignal','Signal','FunctionElement'} and name in {'name','description','source_block_uuid'} else 'Nur ISD')


@lru_cache(maxsize=1)
def _native_catalog():
    from . import models
    return tuple(native_definition(kind,name,field) for kind in NATIVE_KIND_LABELS
        for name,field in getattr(models,kind).model_fields.items() if name not in INTERNAL)


def native_definitions():
    return [d.model_copy(deep=True) for d in _native_catalog()]


def native_fields(obj):
    return [(d.key.rsplit('.',1)[1],d) for d in _native_catalog() if type(obj).__name__ in d.object_types and not d.key.endswith('.id')]


def _value(value,registry):
    if value is None or value=='' or value==[] or value=={}:return 'Offen'
    if isinstance(value,Enum):return str(value.value)
    if isinstance(value,bool):return 'Ja' if value else 'Nein'
    if isinstance(value,list):return '\n'.join(_value(v,registry) for v in value)
    if isinstance(value,dict):return '\n'.join(str(k)+': '+_value(v,registry) for k,v in value.items())
    if hasattr(value,'model_dump'):
        if hasattr(value,'name'):return value.name
        return _value({k:v for k,v in value.model_dump().items() if k not in INTERNAL},registry)
    linked=registry.get(value) if isinstance(value,str) else None
    return getattr(linked,'name',getattr(linked,'title',str(value))) if linked else str(value)


def render_native_fields(package,obj):
    from nicegui import ui
    from .traceability import project_objects
    registry={i:o for group in project_objects(package).values() for i,o in group.items()}
    fields=native_fields(obj)
    for relations,title in [(False,'Objektangaben'),(True,'Verknüpfungen und Bestandteile')]:
        selected=[(name,d) for name,d in fields if (d.attribute_kind=='relation')==relations]
        if not selected:continue
        with ui.expansion(title,value=not relations).classes('w-full border rounded'):
            for name,d in selected:
                with ui.column().classes('w-full gap-0 border-b py-2').mark('native-field-'+name):
                    ui.label(d.label+': '+_value(getattr(obj,name),registry)).classes('text-sm whitespace-pre-wrap break-all')
                    ui.label(d.description).classes('text-xs text-slate-500')
