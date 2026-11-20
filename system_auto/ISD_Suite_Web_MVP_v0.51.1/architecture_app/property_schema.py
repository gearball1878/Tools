"""Project property definitions. Empty is None; definitions are separate from values."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import math
from functools import lru_cache
from typing import Any, Literal
import json
from pathlib import Path
from pydantic import BaseModel, Field, model_validator

KINDS = ['SystemDefinition','SystemDomain','SystemElement','SystemRelation','Domain',
         'ArchitectureElement','InterfacePort','ArchitectureSignal','Signal','Connection',
         'TechnicalRealization','MechanicalComponent','MechanicalConstraint','SoftwareComponent','InterfaceRequirement',
         'MechanicalArchitectureElement','SoftwareArchitectureElement','DisciplineRelation','FunctionElement','EcadRequirement','DesignComponent','IntegrationInterface']
KIND_LABELS = dict(zip(KINDS, ['Systemdefinition','Systemdomäne','Systemelement','Systembeziehung','HW-Domäne',
    'HW-Architekturelement','Port','Netz / Bus','Busmitglied / Signal','Elektrische Verbindung','FE-Implementierung',
    'Mechanische Realisierung','Mechanische Randbedingung','Software-Realisierung','Schnittstellenanforderung',
    'Mechanik-Architekturelement','Software-Architekturelement','Facharchitektur-Beziehung','Funktions Element (FE)','Requirement','Bauteil','Disziplinübergreifende Schnittstelle']))
TYPE_LABELS = {'text':'Text','number':'Zahl / Wertebereich','boolean':'Ja / Nein','enum':'Auswahlliste',
               'list':'Mehrere Werte','reference':'Objektverknüpfung','json':'Strukturierte Angaben'}
DESCRIPTIONS = {
    'evidence':'Dokumente, Berichte und Quellen, auf denen die Realisierungsangaben beruhen; ersetzt keine geprüfte Erfüllungsbewertung.',
    'valueOrigin':'Art der Herkunft einer Realisierungsangabe: ausgewählt, explizit angegeben, berechnet, simuliert oder gemessen.',
    'revision':'Revisionskennung der konkreten Umsetzung, zum Beispiel Schaltplanstand, CAD-Version oder Firmwarestand.',
    'purpose':'Übergeordneter Nutzen und Ziel des Systems aus Sicht des Anwenders.',
    'systemBoundary':'Abgrenzung des betrachteten Systems zu seiner Umgebung und zu externen Akteuren.',
    'responsibility':'Aufgaben und Verantwortungsbereich, die dieser Domäne zugeordnet sind.',
    'independence':'Geforderte oder realisierte funktionale, elektrische oder organisatorische Unabhängigkeit gegenüber anderen Teilen.',
    'resourceBudget':'Vorgegebene oder belegte Ressourcen, zum Beispiel Speicher, Rechenzeit oder Kapazität.',
    'allocatedObjects':'Dokumentierte Referenzen auf zugehörige Umsetzungsobjekte. Gespeicherte Architekturzuordnungen werden separat verwaltet.',
    'exchangeContent':'Information, Energie oder Material, das über die Beziehung oder Schnittstelle ausgetauscht wird.',
    'availability':'Anteil der Zeit, in dem die geforderte Funktion verfügbar sein muss beziehungsweise ist.',
    'voltage':'Elektrischer Spannungswert oder zulässiger Spannungsbereich mit Bezug auf das dokumentierte Potenzial.',
    'current':'Dauerstrom der Versorgung, Schnittstelle oder Leitung; konkrete PCB-Dimensionierung erfolgt im ECAD-Tool.',
    'peakCurrent':'Kurzzeitiger Spitzenstrom unter den angegebenen Betriebsbedingungen.',
    'power':'Elektrische Leistungsaufnahme oder übertragene Leistung des Objekts.',
    'referencePotential':'Elektrisches Bezugspotenzial, etwa Masse, getrennte Masse oder eine Referenzspannung.',
    'isolation':'Anforderungen und Angaben zur galvanischen Trennung und zum Isolationskonzept.',
    'channels':'Anzahl unabhängiger Mess-, Steuer- oder Verarbeitungskanäle.',
    'resolution':'Digitale Auflösung eines Mess- oder Verarbeitungspfads in Bit.',
    'capacity':'Benötigter oder verfügbarer Umfang, etwa Speicherkapazität oder Anzahl verarbeitbarer Einträge.',
    'componentConstraints':'Technische Vorgaben zur Bauteilauswahl, etwa festgelegte Familien oder verpflichtende Komponenten.',
    'coreComponents':'Wichtigste Bausteine und ihre Referenzen in der konkreten Hardwareumsetzung.',
    'schematicReference':'Referenz auf die zugehörigen Schaltplanblätter oder Designobjekte.',
    'interfaceVersion':'Version oder Betriebsvariante der Schnittstelle; keine automatische Ableitung von Layoutregeln.',
    'required':'Legt fest, ob der Anschluss oder das Signal für die geforderte Funktion benötigt wird.',
    'frequency':'Frequenz des Signals oder Takts; Flankenzeiten werden separat dokumentiert.',
    'dataRate':'Übertragene Datenmenge pro Sekunde für den betrachteten Betriebsmodus.',
    'riseTime':'Zeit des Übergangs vom niedrigen zum hohen Signalpegel.',
    'fallTime':'Zeit des Übergangs vom hohen zum niedrigen Signalpegel.',
    'impedance':'Vorgegebene oder realisierte Impedanz einer einzelnen Signalführung.',
    'differentialImpedance':'Vorgegebene oder realisierte Impedanz eines zusammengehörigen Differenzpaars.',
    'physicalForm':'Physikalische Übertragungsform, zum Beispiel Differenzpaar, Trio oder Koaxleitung.',
    'interfaceProfile':'Zusätzliche Benennung des physikalischen Schnittstellenprofils oder Betriebsmodus.',
    'differentialPair':'Zuordnung zu einer Differenzpaargruppe oder Angabe des zugehörigen Partnernetzes.',
    'termination':'Anforderung oder Ausführung der Terminierung einschließlich Bezug und Bauteilwerten.',
    'topology':'Geplanter oder realisierter Verbindungsaufbau wie Punkt zu Punkt, Stern oder Kette.',
    'memberCount':'Anzahl der elektrischen Signale innerhalb eines Busses oder Interfaces.',
    'memberDefinition':'Zusammensetzung des Busses aus Signalen, Vektoren und deren Rollen.',
    'maxLength':'Vorgegebene maximale Signalführungslänge. Die wirksame Layoutregel wird im ECAD-Tool festgelegt.',
    'maxSkew':'Vorgegebener maximaler Laufzeitunterschied zwischen zusammengehörigen Signalen.',
    'voltageDrop':'Vorgegebener oder ermittelter Spannungsabfall entlang einer Verbindung.',
    'temperatureRise':'Zulässige oder ermittelte Temperaturerhöhung im betrachteten elektrischen Pfad.',
    'classPriority':'Aus dem ECAD-Projekt übernommene Reihenfolge mehrerer wirksamer Netzklassen.',
    'connectedNet':'Name oder Referenz des elektrisch angeschlossenen Netzes oder Busses.',
    'pinMapping':'Zuordnung von Architekturanschlüssen zu konkreten Symbolpins oder Bauteilanschlüssen.',
    'dimensions':'Vorgegebene oder realisierte Geometrie, Abmessungen und Einbauräume.',
    'mass':'Vorgegebene oder realisierte Masse der mechanischen Baugruppe.',
    'material':'Vorgegebenes oder gewähltes Material der mechanischen Umsetzung.',
    'loadCases':'Mechanische Beanspruchungen und Betriebsfälle, gegen die die Ausführung ausgelegt wird.',
    'manufacturing':'Vorgaben und Angaben zum Fertigungsverfahren und zur Montage.',
    'sealing':'Anforderungen an Dichtung und Schutz gegen äußere Einflüsse.',
    'cadReference':'Referenz auf das konkrete CAD-Modell oder die Fertigungszeichnung.',
    'dataContract':'Struktur und Bedeutung der über eine API oder Softwareschnittstelle ausgetauschten Daten.',
    'protocol':'Protokoll und fachliche Regeln der Software- oder Firmwarekommunikation.',
    'timing':'Vorgegebene oder ermittelte Laufzeiten, Latenzen und zeitliche Abhängigkeiten.',
    'errorHandling':'Erwartetes oder implementiertes Verhalten bei Fehlern und unzulässigen Zuständen.',
    'compatibility':'Anforderungen an die Kompatibilität zu Versionen, Schnittstellen oder Zielsystemen.',
    'deployment':'Zielplattform oder Hardwareobjekt, auf dem die Software ausgeführt wird.',
    'repository':'Referenz auf den Quellcode und seine Versionsverwaltung.',
    'build':'Identität des konkreten Builds oder ausgelieferten Softwarestands.',
    'performance':'Messbare Funktions- und Leistungskennwerte des betrachteten Systemteils.',
    'inputsOutputs':'Fachliche Eingaben, Ausgaben und deren Bedeutung für das Architekturelement.',
    'stateBehavior':'Erwartetes oder umgesetztes Zustandsverhalten einschließlich Übergängen.',
    'exchangeRoles':'Rollen der beteiligten Partner innerhalb der fachlichen Schnittstelle.',
    'powerBudget':'Verfügbares elektrisches Leistungsbudget für die Domäne.',
    'chosenImplementation':'Beschreibung der gewählten technischen Umsetzung; Objektzuordnungen bleiben separat nachvollziehbar.',
    'polarity':'Aktiver Signalpegel für Steuer- und Statusfunktionen.',
    'noiseLimit':'Zulässiger oder ermittelter Störspannungsanteil des Signals.',
    'accuracy':'Geforderte oder belegte Mess- und Verarbeitungsgenauigkeit.',
    'tolerances':'Zulässige oder dokumentierte geometrische Abweichungen und Passungen.',
    'thermalRequirements':'Anforderungen an Wärmeabfuhr, Temperaturen und thermische Kopplung.',
    'assembly':'Montage- und Befestigungskonzept sowie zugehörige Randbedingungen.',
    'surface':'Vorgegebene oder realisierte Oberfläche und Oberflächenbehandlung.',
    'interfacePartners':'Beteiligte Objekte der mechanischen oder fachlichen Schnittstelle.',
    'runtimeResources':'Benötigte oder belegte Laufzeitressourcen wie Speicher, CPU-Zeit und Tasks.',
    'operations':'Bereitgestellte oder geforderte Funktionen und Operationen der Softwareschnittstelle.',
}
SCOPES = ['requirement_attributes','realization_attributes']
EXCHANGE = ['Nur ISD','Forward','Backward','Abgleich']

ATTRIBUTE_KINDS = {'identity':'Identität','description':'Beschreibung','relation':'Beziehung',
    'technical':'Technischer Kennwert','classification':'Klassifikation','tool_rule':'Werkzeugregel',
    'source':'Quelle / Nachweis','process':'Prozess / Bewertung','derived':'Abgeleitete Anzeige'}
AUTHORITIES = ['ISD','ECAD','CAD','Softwarewerkzeug','PLM / ERP','Quelle / Nachweis','Topologie']

class PropertyDefinition(BaseModel):
    id: str = ''
    key: str
    label: str
    description: str = ''
    object_types: list[str] = Field(default_factory=lambda: list(KINDS))
    scopes: list[str] = Field(default_factory=lambda: list(SCOPES))
    data_type: Literal['text','number','boolean','enum','list','reference','json'] = 'text'
    unit: str = ''
    choices: list[str] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    default: Any = None
    exchange: str = 'Nur ISD'
    system: bool = False
    readonly: bool = False
    origin: str = 'Benutzer'
    selection_source: Literal['','templates','netclasses','objects','signal_roles'] = ''
    target_types: list[str] = Field(default_factory=list)
    disciplines: list[str] = Field(default_factory=list)
    attribute_kind: Literal['','identity','description','relation','technical','classification','tool_rule','source','process','derived'] = ''
    authority: Literal['ISD','ECAD','CAD','Softwarewerkzeug','PLM / ERP','Quelle / Nachweis','Topologie'] = 'ISD'
    ecad_target: str = ''
    ecad_mapping: str = ''
    storage: Literal['property','native'] = 'property'

    @model_validator(mode='after')
    def valid(self):
        if not self.key.strip() or not self.label.strip(): raise ValueError('Attributname fehlt')
        if set(self.object_types)-set(KINDS) or not self.object_types: raise ValueError('Ungültige Objekttypen')
        if set(self.scopes)-set(SCOPES) or not self.scopes: raise ValueError('Ungültiger Attributraum')
        if self.exchange not in EXCHANGE: raise ValueError('Ungültige Austauschrichtung')
        if set(self.target_types)-set(KINDS):raise ValueError('Ungültige Beziehungspartner')
        if set(self.disciplines)-{'System','Hardware','Mechanik','Software','Firmware'}:raise ValueError('Ungültige Disziplin')
        for bound in (self.minimum,self.maximum):
            if bound is not None and not math.isfinite(bound):raise ValueError('Endliche Grenze erwartet')
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError('Minimum liegt über Maximum')
        if self.data_type=='enum' and not self.choices and not self.selection_source: raise ValueError('Auswahlwerte fehlen')
        if self.minimum is not None or self.maximum is not None:
            if self.data_type!='number':raise ValueError('Wertebereiche gelten für Zahlenattribute')
        if not self.id: self.id=hashlib.sha256(('isd/property/'+self.key).encode()).hexdigest()
        validate_value(self,self.default)
        return self


def validate_value(d, value):
    if value is None: return
    if d.data_type=='number':
        if isinstance(value,dict):
            if set(value)-{'min','max','value','unit'} or not any(k in value for k in ('min','max','value')):
                raise ValueError(f'{d.label}: Zahl oder Wertebereich erwartet')
            if value.get('unit',d.unit)!=d.unit: raise ValueError(f'{d.label}: Einheit muss {d.unit} sein')
            nums=[value[k] for k in ('min','max','value') if k in value and value[k] is not None]
            if not nums: raise ValueError(f'{d.label}: Wertebereich ist leer')

        else: nums=[value]
        for number in nums:
            if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number):
                raise ValueError(f'{d.label}: Endliche Zahl erwartet')
            if d.minimum is not None and number<d.minimum or d.maximum is not None and number>d.maximum:
                raise ValueError(f'{d.label}: Wert außerhalb des zulässigen Bereichs')
        if isinstance(value,dict) and value.get('min') is not None and value.get('max') is not None and value['min']>value['max']:
            raise ValueError(f'{d.label}: Minimum liegt über Maximum')
    elif d.data_type in ('text','reference') and not isinstance(value,str): raise ValueError(f'{d.label}: Text erwartet')
    elif d.data_type=='boolean' and not isinstance(value,bool): raise ValueError(f'{d.label}: Boolean erwartet')
    elif d.data_type=='enum' and (not isinstance(value,str) or not d.selection_source and value not in d.choices): raise ValueError(f'{d.label}: Ungültiger Auswahlwert')
    elif d.data_type=='list' and not isinstance(value,list): raise ValueError(f'{d.label}: Liste erwartet')


@lru_cache(maxsize=1)
def _system_definition_templates():
    definitions=[]
    def add(key,label,typ='text',unit='',kinds=None,scopes=None,exchange='Nur ISD',choices=None,readonly=False,description='',source=''):
        if isinstance(unit,list): kinds,unit=unit,''
        if source and typ=='text':typ='enum'
        definitions.append(PropertyDefinition(key=key,label=label,data_type=typ,unit=unit,
            object_types=kinds or KINDS,scopes=scopes or SCOPES,exchange=exchange,
            choices=choices or [],system=True,origin='ISD',readonly=readonly,
            description=description or DESCRIPTIONS.get(key,label),selection_source=source))
    blocks=['SystemDefinition','SystemDomain','SystemElement','Domain','ArchitectureElement','TechnicalRealization','FunctionElement','DesignComponent',
            'MechanicalComponent','SoftwareComponent','MechanicalArchitectureElement','SoftwareArchitectureElement']
    add('function','Funktion / Aufgabe',exchange='Forward',description='Aufgabe und erwarteter Beitrag des Objekts zum System.')
    add('operatingConditions','Betriebsbedingungen','json',kinds=blocks,description='Umgebungs- und Einsatzbedingungen, unter denen die Funktion verfügbar sein muss.')
    add('operatingModes','Betriebsmodi','list',kinds=blocks,description='Betriebszustände wie Normalbetrieb, Standby, Diagnose oder Wartung.')
    add('variants','Varianten','list',kinds=blocks,description='Systemausführungen, für die das Objekt oder die Angaben gelten.')
    add('dependencies','Abhängigkeiten','list',kinds=blocks,source='objects',description='Andere Projektobjekte, deren Funktion dieses Objekt benötigt.')
    add('evidence','Nachweise / Quellen','list',scopes=[SCOPES[1]])
    add('valueOrigin','Herkunft der Realisierungswerte','enum',scopes=[SCOPES[1]],
        choices=['Ausgewählt','Explizite Designangabe','Berechnet','Simuliert','Gemessen'])
    add('revision','Realisierungsrevision',scopes=[SCOPES[1]],exchange='Backward')
    add('purpose','Systemzweck',kinds=['SystemDefinition'])
    add('systemBoundary','Systemgrenze',kinds=['SystemDefinition','SystemDomain'])
    add('responsibility','Verantwortung / Zuständigkeit',kinds=['SystemDomain','Domain'])
    add('independence','Unabhängigkeit / Isolation',kinds=['SystemDomain','Domain','SystemElement','ArchitectureElement'])
    add('resourceBudget','Ressourcenbudget','json',kinds=['SystemDomain','SystemElement','Domain','ArchitectureElement','SoftwareComponent'])
    add('allocatedObjects','Zugeordnete Realisierungsobjekte','list',kinds=['SystemDefinition','SystemDomain','SystemElement'],scopes=[SCOPES[1]])
    add('exchangeContent','Austauschinhalt',kinds=['SystemRelation','Connection','InterfaceRequirement'])
    add('availability','Verfügbarkeit','number','%',kinds=['SystemDefinition','SystemRelation','SystemElement'])
    hw=['Domain','ArchitectureElement','InterfacePort','ArchitectureSignal','Signal','TechnicalRealization']
    wires=['InterfacePort','ArchitectureSignal','Signal']
    add('voltage','Spannung','number','V',hw,exchange='Forward')
    add('current','Dauerstrom','number','A',hw,exchange='Forward')
    add('peakCurrent','Spitzenstrom','number','A',hw,exchange='Forward')
    add('power','Leistung','number','W',hw,exchange='Forward')
    add('referencePotential','Bezugspotenzial',kinds=hw,exchange='Abgleich')
    add('isolation','Isolationsanforderung','json',hw,exchange='Forward')
    add('channels','Kanalanzahl','number','', ['ArchitectureElement','TechnicalRealization'])
    add('resolution','Auflösung','number','bit',['ArchitectureElement','TechnicalRealization'])
    add('capacity','Kapazität / Umfang','json',['ArchitectureElement','TechnicalRealization','SoftwareComponent'])
    add('componentConstraints','Bauteilvorgaben','list',['ArchitectureElement','TechnicalRealization'])
    add('coreComponents','Systemdefinierende Bauteile','list',['TechnicalRealization'],scopes=[SCOPES[1]],exchange='Backward',source='objects')
    add('schematicReference','Schaltplanreferenz',kinds=hw,scopes=[SCOPES[1]],exchange='Backward')
    add('interfaceType','Schnittstellentyp',kinds=wires,exchange='Abgleich',source='templates',description='Elektrischer Schnittstellentyp aus dem gemeinsamen Signal- und Interfacekatalog.')
    add('interfaceVersion','Schnittstellenversion',kinds=wires,exchange='Abgleich')
    add('signalRole','Signalrolle',kinds=wires,exchange='Abgleich',source='signal_roles',description='Rolle des Signals innerhalb des gewählten Schnittstellentyps, zum Beispiel Takt oder Daten.')
    add('interfaceRole','Schnittstellenrolle','enum',kinds=wires,choices=['Host','Teilnehmer','Quelle','Senke'],exchange='Abgleich',description='Fachliche Rolle des Anschlusses in der Schnittstelle.')
    add('direction','Richtung','enum',kinds=wires,choices=['Eingang','Ausgang','Bidirektional','Passiv'],exchange='Abgleich',description='Geforderte oder realisierte Signalrichtung; die elektrische Pinzuordnung bleibt separat.')
    add('required','Erforderlich','boolean',kinds=wires,scopes=[SCOPES[0]])
    add('frequency','Frequenz','number','Hz',wires,exchange='Forward')
    add('dataRate','Datenrate','number','bit/s',wires,exchange='Forward')
    add('riseTime','Anstiegszeit','number','ns',wires,exchange='Forward')
    add('fallTime','Abfallzeit','number','ns',wires,exchange='Forward')
    add('impedance','Single-ended Impedanz','number','Ω',wires,exchange='Forward')
    add('differentialImpedance','Differenzielle Impedanz','number','Ω',wires,exchange='Forward')
    add('physicalForm','Physikalische Signalform','enum',kinds=wires,choices=['Single-ended','Differentiell','Trio','Koax','Stromschnittstelle'],exchange='Abgleich')
    add('interfaceProfile','Schnittstellenprofil',kinds=wires,exchange='Abgleich')
    add('differentialPair','Differenzpaar / Partner',kinds=wires,exchange='Abgleich')
    add('termination','Terminierung','json',wires,exchange='Forward')
    add('topology','Topologie',kinds=['ArchitectureSignal','Connection'],choices=['Punkt zu Punkt','Mehrere Teilnehmer','Stern','Kette','Ring'],exchange='Abgleich')
    add('memberCount','Mitgliederanzahl','number','', ['ArchitectureSignal'])
    add('memberDefinition','Businhalt / Vektoren','list',['ArchitectureSignal','InterfacePort'],exchange='Abgleich')
    add('maxLength','Maximale Länge','number','mm',['ArchitectureSignal','Signal','Connection'],exchange='Forward')
    add('maxSkew','Maximaler Laufzeitversatz','number','ps',wires,exchange='Forward')
    add('voltageDrop','Spannungsabfall','number','V',wires,exchange='Forward')
    add('temperatureRise','Zulässige Erwärmung','number','K',wires,exchange='Forward')
    add('netClass','Netzklasse / Bus-Standardklasse',kinds=['ArchitectureSignal','Signal'],scopes=[SCOPES[1]],exchange='Abgleich',source='netclasses',description='Netzklasse des Einzelnetzes oder Vorgabe für Busmitglieder ohne eigene Klasse. Regeln werden im ECAD-Tool gepflegt.')
    add('netClasses','Weitere ECAD-Netzklassen','list',kinds=['ArchitectureSignal','Signal'],scopes=[SCOPES[1]],exchange='Abgleich',source='netclasses',description='Zusätzliche ECAD-Klassenzuweisungen; ihre Priorität und Regeln stammen aus dem ECAD-Projekt.')
    add('classPriority','ECAD-Klassenpriorität','json',kinds=['ArchitectureSignal','Signal'],scopes=[SCOPES[1]],exchange='Backward',readonly=True)
    add('connectedNet','Angeschlossenes Netz / Bus',kinds=['InterfacePort'],scopes=[SCOPES[1]],exchange='Backward')
    add('pinMapping','Pinzuordnung','json',['InterfacePort','Signal'],scopes=[SCOPES[1]],exchange='Backward')
    add('dimensions','Geometrie / Abmessungen','json',['MechanicalComponent','MechanicalConstraint'])
    add('mass','Masse','number','kg',['MechanicalComponent'])
    add('material','Material',kinds=['MechanicalComponent'])
    add('loadCases','Lastfälle','list',['MechanicalComponent','MechanicalConstraint'])
    add('manufacturing','Fertigung / Montage',kinds=['MechanicalComponent','MechanicalConstraint'])
    add('sealing','Dichtung / Schutz',kinds=['MechanicalConstraint'])
    add('cadReference','CAD-Referenz',kinds=['MechanicalComponent'],scopes=[SCOPES[1]])
    sw=['SoftwareComponent','InterfaceRequirement']
    add('dataContract','API / Datenvertrag','json',sw)
    add('protocol','Protokoll',kinds=sw)
    add('timing','Timing / Latenz','json',sw)
    add('errorHandling','Fehlerverhalten',kinds=sw)
    add('compatibility','Kompatibilität',kinds=sw)
    add('deployment','Deployment-Ziel',kinds=['SoftwareComponent'],scopes=[SCOPES[1]])
    add('repository','Repository',kinds=['SoftwareComponent'],scopes=[SCOPES[1]])
    add('build','Build / Version',kinds=['SoftwareComponent'],scopes=[SCOPES[1]])
    add('performance','Leistungs- / Funktionskennwerte','json',['SystemDefinition','SystemDomain','SystemElement','SystemRelation','ArchitectureElement','TechnicalRealization'])
    add('inputsOutputs','Ein- und Ausgaben','json',['SystemElement','ArchitectureElement'])
    add('stateBehavior','Zustands- und Betriebsverhalten','json',['SystemElement','ArchitectureElement'])
    add('exchangeRoles','Schnittstellenrollen','list',['SystemRelation','InterfaceRequirement'])
    add('powerBudget','Leistungsbudget','number','W',['SystemDomain','Domain'],scopes=[SCOPES[0]])
    add('chosenImplementation','Gewählte Umsetzung',kinds=['SystemElement','ArchitectureElement','TechnicalRealization'],scopes=[SCOPES[1]])
    add('polarity','Polarität','enum',kinds=['ArchitectureSignal','Signal'],choices=['Active high','Active low'],exchange='Abgleich')
    add('noiseLimit','Rauschgrenze','number','V',wires,exchange='Forward')
    add('accuracy','Genauigkeit','json',hw,exchange='Forward')
    add('tolerances','Geometrische Toleranzen','json',['MechanicalComponent','MechanicalConstraint'])
    add('thermalRequirements','Thermische Anforderungen','json',['MechanicalComponent','MechanicalConstraint'])
    add('assembly','Montage / Befestigung','json',['MechanicalComponent','MechanicalConstraint'])
    add('surface','Oberfläche',kinds=['MechanicalComponent'])
    add('interfacePartners','Schnittstellenpartner','list',['SystemRelation','MechanicalConstraint','InterfaceRequirement'])
    add('runtimeResources','Laufzeitressourcen','json',['SoftwareComponent'])
    add('operations','Operationen / Funktionen','list',['SoftwareComponent','InterfaceRequirement'])
    # Facharchitekturen inherit their discipline-specific fields, not electrical rules.
    for d in definitions:
        if 'MechanicalComponent' in d.object_types and 'MechanicalArchitectureElement' not in d.object_types and d.key not in {'cadReference','revision'}:
            d.object_types.append('MechanicalArchitectureElement')
        if 'SoftwareComponent' in d.object_types and 'SoftwareArchitectureElement' not in d.object_types and d.key not in {'deployment','repository','build','revision'}:
            d.object_types.append('SoftwareArchitectureElement')
    for d in definitions:
        if 'ArchitectureElement' in d.object_types and d.key not in {'coreComponents','componentConstraints','chosenImplementation'}:
            d.object_types.append('FunctionElement')
        if d.key in {'operatingConditions','operatingModes','variants','performance','dimensions','mass','loadCases','thermalRequirements','tolerances','runtimeResources','timing','dataContract','protocol','availability','voltage','current','power','frequency','dataRate','accuracy','isolation'}:
            d.object_types.append('EcadRequirement')
            # Requirements contain targets/limits, never as-built values.
        if d.key=='coreComponents':d.target_types=['DesignComponent']
    from .technical_comparison import TECHNICAL_KEYS
    electrical_metadata={'interfaceType','interfaceVersion','signalRole','interfaceRole','direction','required','memberDefinition','pinMapping','connectedNet'}
    for definition in definitions:
        if definition.key in electrical_metadata:
            definition.object_types.extend(['InterfaceRequirement','EcadRequirement'])
        if definition.key in TECHNICAL_KEYS and 'EcadRequirement' not in definition.object_types:definition.object_types.append('EcadRequirement')
    # Architecture owns responsibility and links; targets/actuals keep their source.
    slim={'SystemDomain','SystemElement','Domain','ArchitectureElement','InterfacePort',
          'ArchitectureSignal','Signal','Connection','MechanicalArchitectureElement',
          'SoftwareArchitectureElement','DisciplineRelation','SystemRelation','FunctionElement'}
    retained={'function':slim-{'InterfacePort','ArchitectureSignal','Signal','Connection','DisciplineRelation','SystemRelation','FunctionElement'},
              'netClass':{'ArchitectureSignal','Signal'},'netClasses':{'ArchitectureSignal','Signal'},
              'classPriority':{'ArchitectureSignal','Signal'}}
    for definition in definitions:
        definition.object_types=[k for k in definition.object_types if k not in slim or k in retained.get(definition.key,set())]
        if definition.key=='function':
            definition.label='Aufgabe / Verantwortung'
            definition.scopes=[SCOPES[0]]
        if definition.object_types and set(definition.object_types)<= {'TechnicalRealization','MechanicalComponent','SoftwareComponent','DesignComponent'}:
            definition.scopes=[SCOPES[1]]
    definitions=[d for d in definitions if d.object_types]
    add('ecadKey','ECAD-Key',kinds=['Domain','ArchitectureElement','InterfacePort','ArchitectureSignal','Signal','FunctionElement'],
        scopes=[SCOPES[1]],exchange='Abgleich',readonly=True,description='Stabile ECAD-Zuordnung; unabhängig vom fachlichen Anzeigenamen.')
    add('responsible','Verantwortlicher',kinds=['SystemDomain','MechanicalArchitectureElement','SoftwareArchitectureElement'],scopes=[SCOPES[0]],description='Verantwortliche Person oder Rolle für diesen Architekturteil.')
    add('systemContribution','Systembeitrag',kinds=['FunctionElement'],scopes=[SCOPES[1]],description='Beitrag der realisierten Funktion zum System; Kernbauteile und Implementierungen bleiben verknüpfte Objekte.')
    # FE owns its function description natively; technical demand stays at Requirements.
    for key in ('operatingConditions','operatingModes','revision','evidence','valueOrigin'):
        definition=next(d for d in definitions if d.key==key)
        if 'FunctionElement' not in definition.object_types:definition.object_types.append('FunctionElement')
    from .technical_comparison import TECHNICAL_KEYS
    for definition in definitions:
        if definition.key in TECHNICAL_KEYS:definition.attribute_kind='technical'
        elif definition.selection_source=='objects' or definition.key in {'dependencies','allocatedObjects','coreComponents'}:definition.attribute_kind='relation'
        elif definition.key in {'netClass','netClasses','physicalForm','polarity','interfaceType','signalRole','direction','interfaceRole'}:definition.attribute_kind='classification'
        elif definition.key in {'evidence','schematicReference','cadReference','repository','build'}:definition.attribute_kind='source'
        elif definition.key=='ecadKey':definition.attribute_kind='identity'
        elif definition.readonly:definition.attribute_kind='derived'
        elif definition.key in {'revision','valueOrigin','variants'}:definition.attribute_kind='process'
        else:definition.attribute_kind='description'
        if definition.key in {'ecadKey','classPriority','pinMapping','connectedNet','schematicReference'}:definition.authority='ECAD'
        elif definition.key in {'evidence','valueOrigin'}:definition.authority='Quelle / Nachweis'
        elif definition.key=='cadReference':definition.authority='CAD'
        elif definition.key in {'repository','build'}:definition.authority='Softwarewerkzeug'
        if definition.key in {'netClass','netClasses'}:
            definition.ecad_target='KiCad-Projekt / Netzklassenzuordnung'
            definition.ecad_mapping='net_settings.netclass_patterns; eigene Mitgliedsklasse vor Bus-Standardklasse'
        elif definition.key=='classPriority':
            definition.ecad_target='KiCad-Projekt / Netzklassenpriorität';definition.ecad_mapping='Übernahme vorhandener ECAD-Prioritäten'
        elif definition.key=='ecadKey':
            definition.ecad_target='Schaltplanobjekt';definition.ecad_mapping='Stabile Connector-Zuordnung (Name / native UUID)'
        elif definition.key in TECHNICAL_KEYS:
            definition.ecad_target='Technische Vorgabe / Designwert'
            definition.ecad_mapping='Projektmetadaten; keine automatische Umsetzung in PCB-Designregeln'
        definition.object_types = list(dict.fromkeys(definition.object_types))
    return definitions



def system_definitions():
    """Return independent definitions; callers cannot mutate shared templates."""
    return deepcopy(_system_definition_templates())


@lru_cache(maxsize=1)
def _legacy_definition_versions():
    """Read bundled, immutable migration catalogs once per process."""
    return tuple({d['key']:d for d in json.loads(Path(__file__).with_name(filename).read_text(encoding='utf-8'))}
                 for filename in ('property_schema_v041.json','property_schema_v042.json','property_schema_v043.json','property_schema_v048.json'))

def applicable(definitions,obj,scope):
    from .requirement_profiles import property_applies
    return [d for d in definitions if type(obj).__name__ in d.object_types and scope in d.scopes and property_applies(d,obj,scope)]


def initialize_object(obj,definitions=None):
    for scope in SCOPES:
        values=getattr(obj,scope)
        for d in applicable(definitions or _system_definition_templates(),obj,scope):
            values.setdefault(d.key,deepcopy(d.default))
    return obj


def objects(package):
    """All engineering objects, including physical interfaces and nested port signals."""
    seen=set()
    def walk(value):
        if isinstance(value,list):
            for item in value: yield from walk(item)
        elif isinstance(value,BaseModel):
            if hasattr(value,'requirement_attributes') and id(value) not in seen:
                seen.add(id(value));yield value
            for field in type(value).model_fields:
                child=getattr(value,field)
                if isinstance(child,(list,BaseModel)): yield from walk(child)
    yield from walk(package)


def definitions_for(package):
    return package.property_definitions


def synchronize_schema(package):
    builtins={d.key:d for d in _system_definition_templates()}
    engineering_objects=list(objects(package))
    known={}
    from .attribute_spaces import is_system_key
    legacy_versions=_legacy_definition_versions()
    retired={'speedClass','powerClass'}
    retired.update(key for version in legacy_versions for key in version if key not in builtins)
    for d in package.property_definitions:
        dump=d.model_dump(exclude={'target_types','disciplines','attribute_kind','authority','ecad_target','ecad_mapping','storage'})
        old_dump=d.model_dump(exclude={'attribute_kind','authority','ecad_target','ecad_mapping','storage'})
        legacy_metadata=not d.attribute_kind and d.authority=='ISD' and not d.ecad_target and not d.ecad_mapping and d.storage=='property'
        is_legacy=d.system and legacy_metadata and any(d.model_dump()==version.get(d.key) or old_dump==version.get(d.key) or dump==version.get(d.key) or {k:v for k,v in dump.items() if k!='selection_source'}==version.get(d.key) for version in legacy_versions)
        if is_legacy:
            if d.key in retired or d.key not in builtins:continue
            d=deepcopy(builtins[d.key])
        if d.storage=='native':raise ValueError('Native Objektfelder werden über die Objektmaske verwaltet')
        if d.key not in builtins and is_system_key(d.key):raise ValueError('Technische Identitätsfelder sind geschützt')
        if d.key in known: raise ValueError(f'Doppelte Attributdefinition: {d.key}')
        if d.key in builtins and d.model_dump()!=builtins[d.key].model_dump():
            raise ValueError(f'Systemattribut {d.key} darf nicht umdefiniert werden')
        if d.system and d.key not in builtins: raise ValueError('Benutzerattribute dürfen nicht als Systemattribute angelegt werden')
        known[d.key]=d
    if len({d.id for d in known.values()})!=len(known):raise ValueError('Doppelte Attribut-IDs')
    for key,d in builtins.items(): known.setdefault(key,deepcopy(d))
    aliases={'netclass':'netClass','netclasses':'netClasses','interfacekind':'interfaceType','interfacetype':'interfaceType','speedclass':'speedClass','powerclass':'powerClass'}
    for key in list(known):
        canonical=aliases.get(key.casefold())
        if canonical and canonical!=key:known.pop(key)
    # Older free-form properties are adopted losslessly as custom JSON definitions.
    from .attribute_spaces import is_system_key
    for obj in engineering_objects:
        for scope in SCOPES:
            values=getattr(obj,scope)
            for key in list(values):
                canonical=aliases.get(key.casefold(),key)
                if canonical!=key:
                    value=values.pop(key)
                    if values.get(canonical) is None:values[canonical]=value
                    elif value is not None and values[canonical]!=value:obj.attributes.setdefault('legacyPropertyValues',{}).setdefault(scope,{})[key]=deepcopy(value)
                    key=canonical
                d=known.get(key)
                if key in retired or d and d not in applicable([d],obj,scope):
                    value=values.pop(key)
                    if value is not None:obj.attributes.setdefault('legacyPropertyValues',{}).setdefault(scope,{})[key]=deepcopy(value)
    custom_kinds={}
    for obj in engineering_objects:
        for scope in SCOPES:
            for key in getattr(obj,scope):
                if key not in known and not is_system_key(key):
                    kinds=custom_kinds.setdefault(key,[])
                    if type(obj).__name__ not in kinds:kinds.append(type(obj).__name__)
    for key,kinds in custom_kinds.items():
        known[key]=PropertyDefinition(key=key,label=key,data_type='json',object_types=kinds,origin='Bestandsprojekt',exchange='Abgleich')
    package.property_definitions=list(known.values())
    from .requirement_profiles import property_applies
    definition_index={}
    for d in package.property_definitions:
        for kind in d.object_types:
            for scope in d.scopes:definition_index.setdefault((kind,scope),[]).append(d)
    for obj in engineering_objects:
        kind=type(obj).__name__
        first_scope=[d for d in definition_index.get((kind,SCOPES[0]),[]) if property_applies(d,obj,SCOPES[0])]
        legacy=obj.attributes.get('legacyPropertyValues',{})
        prior=legacy.get('requirement_attributes',{}).get('responsibility')
        if prior and any(d.key=='function' for d in first_scope):
            function=obj.requirement_attributes.get('function')
            if prior not in str(function or ''):
                obj.requirement_attributes['function']='\n'.join(str(v) for v in (function,prior) if v)
        for scope in SCOPES:
            applicable_definitions=first_scope if scope==SCOPES[0] else [d for d in definition_index.get((kind,scope),[]) if property_applies(d,obj,scope)]
            values=getattr(obj,scope)
            for d in applicable_definitions:
                values.setdefault(d.key,deepcopy(d.default))
                validate_value(d,values.get(d.key))
    return package


def selection_options(definition,obj,package):
    """Display catalog choices; retaining legacy values never silently replaces them."""
    source=definition.selection_source
    if source=='netclasses':return {c.name:c.name for c in package.net_classes}
    if source=='objects':
        from .requirement_profiles import allowed_dependency_types,dependency_target_applies
        allowed=set(definition.target_types or allowed_dependency_types(obj))
        return {o.id:f'{KIND_LABELS.get(type(o).__name__,type(o).__name__)} · {getattr(o,"name",getattr(o,"title","System"))}'
                for o in objects(package) if type(o).__name__ in allowed and getattr(o,'id',None) and o.id!=getattr(obj,'id',None)
                and (definition.target_types or dependency_target_applies(obj,o))}
    if source=='templates':
        from .bus_content import BusContentTemplates
        catalog=BusContentTemplates(Path(__file__).resolve().parent.parent/'Interface_Template_File.json')
        names=sorted(set(catalog.interface_templates())|{t.name for t in package.interface_templates if not t.deprecated})
        return {name:name for name in names}
    if source=='signal_roles':
        profile=(obj.realization_attributes.get('interfaceType') or obj.requirement_attributes.get('interfaceType') or getattr(obj,'catalog_template','') or '').upper()
        roles=['Daten','Takt','Steuerung','Status','Versorgung','Referenz','Rückleitung']
        if 'SPI' in profile:roles=['Takt','MOSI','MISO','Chip Select','Steuerung','Status']
        elif 'UART' in profile:roles=['TX','RX','RTS','CTS']
        elif 'I2C' in profile or 'I3C' in profile:roles=['SCL','SDA','Interrupt']
        return {v:v for v in roles}
    return {v:v for v in definition.choices}


def update_definition(package,definition):
    from .attribute_spaces import is_system_key
    if is_system_key(definition.key): raise ValueError('Technische Identitäts- und Zuordnungsfelder sind geschützt')
    if definition.key.casefold() in {'netclass','netclasses','interfacekind','interfacetype','speedclass','powerclass'}:
        raise ValueError('Der Attributschlüssel ist für die systemseitige Netz- und Interfacezuordnung reserviert')
    existing=next((d for d in package.property_definitions if d.key==definition.key),None)
    if existing and existing.system: raise ValueError('Systemattribute können nicht geändert werden')
    if existing and existing.id!=definition.id:raise ValueError('Die Attribut-ID ist unveränderlich')
    candidate=deepcopy(package)
    candidate.property_definitions=[d for d in candidate.property_definitions if d.key!=definition.key]+[definition]
    for obj in objects(candidate):
        if existing:
            for scope in SCOPES:
                old=getattr(obj,scope).get(definition.key)
                if old is not None and (type(obj).__name__ not in definition.object_types or scope not in definition.scopes):
                    raise ValueError('Vorhandene Werte würden aus dem Geltungsbereich fallen')
    return synchronize_schema(candidate)


def delete_definition(package,key,confirm_values=False):
    d=next(d for d in package.property_definitions if d.key==key)
    if d.system: raise ValueError('Systemattribute können nicht gelöscht werden')
    count=sum(getattr(o,s).get(key) is not None for o in objects(package) for s in SCOPES)
    if count and not confirm_values: raise ValueError(f'{count} vorhandene Werte: Löschung ausdrücklich bestätigen')
    candidate=deepcopy(package)
    candidate.property_definitions=[d for d in candidate.property_definitions if d.key!=key]
    for o in objects(candidate):
        for s in SCOPES: getattr(o,s).pop(key,None)
    return candidate


def exchange_mode(d,scope):
    # System electrical fields carry Soll forward and explicit Ist values both ways.
    if d.system and d.exchange=='Forward' and scope=='realization_attributes':return 'Abgleich'
    return d.exchange


def exchange_values(obj,scope,direction,definitions=None):
    values=getattr(obj,scope,{})
    accepted={'Abgleich','Forward' if direction=='forward' else 'Backward'}
    result = {d.key:deepcopy(values[d.key]) for d in applicable(definitions or system_definitions(),obj,scope)
            if exchange_mode(d,scope) in accepted and values.get(d.key) is not None}
    # Read preserved values for existing connector bindings. They remain visibly
    # marked as legacy in ISD; no requirement or realization is invented.
    from .technical_comparison import ARCHITECTURE_KINDS, TECHNICAL_KEYS
    if type(obj).__name__ in ARCHITECTURE_KINDS:
        legacy={**getattr(obj,'attributes',{}).get('legacyPropertyValues',{}).get(scope,{}),**values}
        for d in definitions or system_definitions():
            if d.key in TECHNICAL_KEYS and exchange_mode(d,scope) in accepted and legacy.get(d.key) is not None:
                result[d.key]=deepcopy(legacy[d.key])
    return result


def merge_ecad_values(obj,incoming,definitions):
    if not isinstance(incoming,dict):raise ValueError('ECAD-Attribute müssen ein Objekt sein')
    result=deepcopy(obj.realization_attributes)
    allowed={d.key:d for d in applicable(definitions,obj,'realization_attributes')
             if exchange_mode(d,'realization_attributes') in {'Backward','Abgleich'}}
    from .technical_comparison import ARCHITECTURE_KINDS, TECHNICAL_KEYS
    if type(obj).__name__ in ARCHITECTURE_KINDS:
        allowed.update({d.key:d for d in definitions if d.key in TECHNICAL_KEYS and exchange_mode(d,'realization_attributes') in {'Backward','Abgleich'}})
    for key,d in allowed.items():
        if key in incoming:
            validate_value(d,incoming[key]);result[key]=deepcopy(incoming[key])
    return result
