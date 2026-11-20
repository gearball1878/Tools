"""Semantic net classes and conservative member-specific template suggestions.
No PCB dimensions or universal speed/current thresholds are inferred.
"""
from __future__ import annotations
import hashlib
import re
from pydantic import BaseModel, Field, model_validator

class NetClassDefinition(BaseModel):
    id: str = ''
    name: str
    description: str = ''
    physical_form: str | None = None
    speed: str | None = None
    power: str | None = None
    profile: str = ''
    criteria: dict = Field(default_factory=dict)
    origin: str = 'Benutzer'
    priority: int | None = None
    ecad_parameters: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def valid(self):
        if not re.fullmatch(r'[\w .+-]{1,64}',self.name): raise ValueError('Ungültiger Netzklassenname')
        if self.speed not in (None,'Low','Mid','High') or self.power not in (None,'Low','Mid','High'):
            raise ValueError('Ungültige Geschwindigkeits- oder Leistungsklasse')
        if self.physical_form not in (None,'Single-ended','Differentiell','Trio','Koax','Stromschnittstelle'):
            raise ValueError('Ungültige physikalische Signalform')
        if not self.id:self.id=hashlib.sha256(('isd/netclass/'+self.name).encode()).hexdigest()
        return self


def default_netclasses():
    result=[]
    def add(name,shape=None,speed=None,power=None,profile=''):
        result.append(NetClassDefinition(name=name,physical_form=shape,speed=speed,power=power,profile=profile,
            origin='Systemkatalog',description=class_description(name)))
    for family,shape in [('DIGITAL','Single-ended'),('DIFFERENTIAL','Differentiell'),('CLOCK',None)]:add(family,shape)
    for name in ['POWER_SUPPLY','POWER_LOAD','POWER_SWITCHING','POWER_SENSE','POWER_RETURN']:add(name)
    for name,shape in [('ANALOG','Single-ended'),('ANALOG_SENSITIVE',None),('ANALOG_DIFF','Differentiell'),
                       ('REFERENCE',None),('CRYSTAL',None),('GATE_DRIVE',None),('GROUND',None)]:
        add(name,shape)
    profiles={
        'UART':'Single-ended','I2C':'Single-ended','I3C':'Single-ended','SPI':'Single-ended',
        'SMI':'Single-ended','MDIO':'Single-ended','JTAG':'Single-ended','SWD':'Single-ended','1WIRE':'Single-ended',
        'CAN_LOGIC':'Single-ended','LIN_LOGIC':'Single-ended','FLEXRAY_LOGIC':'Single-ended',
        'CAN_BUS':'Differentiell','LIN_BUS':'Single-ended','FLEXRAY_BUS':'Differentiell',
        'RS485_BUS':'Differentiell','RS232_LINE':'Single-ended','SENT':'Single-ended',
        'USB2_DATA':'Differentiell','USB_SUPERSPEED_DATA':'Differentiell','USB_CC':None,'USB_SBU':None,
        'PCIE_DATA':'Differentiell','PCIE_CLOCK':'Differentiell','SATA_DATA':'Differentiell','UFS_DATA':'Differentiell','UFS_CLOCK':None,
        'HDMI_DATA':'Differentiell','HDMI_CLOCK':'Differentiell','HDMI_CONTROL':'Single-ended',
        'DP_DATA':'Differentiell','DP_AUX':'Differentiell','EDP_DATA':'Differentiell','LVDS_DATA':'Differentiell','LVDS_CLOCK':'Differentiell',
        'MIPI_DPHY_DATA':'Differentiell','MIPI_DPHY_CLOCK':'Differentiell','MIPI_CPHY_TRIO':'Trio',
        'GMSL_STP':'Differentiell','GMSL_COAX':'Koax','FPDLINK_COAX':'Koax','A2B':'Differentiell','PSI5':'Stromschnittstelle',
        'AUDIO_DATA':'Single-ended','AUDIO_CLOCK':'Single-ended','VIDEO_PARALLEL':'Single-ended','VIDEO_CLOCK':'Single-ended',
    }
    for protocol in ['MII','RMII','RGMII','SGMII','QSGMII','USXGMII','2G5','10G','MDI','100BASE_T1','1000BASE_T1','10BASE_T1S']:
        profiles['ETH_'+protocol]='Single-ended' if protocol in ['MII','RMII','RGMII'] else 'Differentiell'
    for protocol in ['QSPI','OSPI','SDIO','EMMC','LPDDR3','LPDDR4','LPDDR5']:
        for role in ['DATA','CLOCK','CONTROL']:
            profiles[protocol+'_'+role]=None if role=='CLOCK' else 'Single-ended'
        if protocol.startswith('LPDDR') or protocol in ['OSPI','EMMC','SDIO']:profiles[protocol+'_STROBE']=None
    for name,shape in profiles.items():
        add(name,shape,profile=name)
    return result


def class_description(name):
    specific={
        'DIGITAL':'Allgemeine digitale Logik-, Steuer- und Statussignale ohne eigenes Protokollprofil; keine Versorgung oder analoge Messleitung.',
        'DIFFERENTIAL':'Differenzielle Signalpaare ohne spezifisches Protokollprofil; Paarzuordnung und Regeln im ECAD-Design festlegen.',
        'CLOCK':'Taktsignale ohne spezifisches Schnittstellenprofil; Datenleitungen erhalten ihre eigene Klasse.',
        'POWER_SUPPLY':'Versorgung von Elektronik und Logik, etwa MCU-, Sensor- oder IC-Versorgung. Dimensionierung und Abstände werden im ECAD-Tool festgelegt.',
        'POWER_LOAD':'Leistungspfad zu Verbrauchern oder Energiespeichern, etwa Motor, Heizung oder Batterie-Lade-/Entladepfad. Auch eine geschaltete Lastversorgung gehört hierher.',
        'POWER_SWITCHING':'Eigentlicher Schaltknoten einer Leistungsschaltung, etwa zwischen Schalttransistor, Diode und Spule; keine allgemeine Leitung hinter einem Schalter.',
        'POWER_SENSE':'Mess- und Rückmeldeleitung eines Leistungspfads, etwa Kelvin-Anschluss am Shunt oder Spannungsrückmessung; trägt nicht den Laststrom.',
        'POWER_RETURN':'Rückleitung eines Leistungspfads, etwa Motor-, Heizungs- oder Batterierückstrom; von allgemeinen Elektronik-Masseleitungen unterscheiden.',
        'GROUND':'Allgemeine Masse und Versorgungsrückleitung der Elektronik. Dedizierte Last-Rückleitungen können POWER_RETURN erhalten.',
        'ANALOG':'Analoge Signalübertragung ohne besondere Messprofilzuordnung; keine Stromversorgung.',
        'ANALOG_SENSITIVE':'Empfindliche analoge Messsignale, etwa Zellspannung, Temperatur oder Sensorsignal; Störabstand und Genauigkeit im Design berücksichtigen.',
        'ANALOG_DIFF':'Differenzielle analoge Messsignale; beide Leiter als zusammengehöriges Paar behandeln.',
        'REFERENCE':'Analoge Referenzspannung oder Referenzsignal; keine allgemeine Versorgung.',
        'CRYSTAL':'Quarz- und Resonatoranschlüsse am Oszillator; kein allgemeines Taktausgangsnetz.',
        'GATE_DRIVE':'Gate-Ansteuerung zwischen Treiber und Leistungstransistor; von Lastpfad und Schaltknoten unterscheiden.',
        'USB_CC':'USB-C-Konfigurationskanal zur Anschluss- und Rollenverhandlung; keine USB-Nutzdatenleitung.',
        'USB_SBU':'USB-C-Sideband-Leitung; Verwendung im jeweiligen Alternate Mode im Design festlegen.',
        'MIPI_CPHY_TRIO':'Dreileitergruppe einer MIPI-C-PHY-Schnittstelle; nicht als Differenzpaar behandeln.',
        'GMSL_COAX':'GMSL-Verbindung über Koaxleitung; PHY-Anschluss, Terminierung und mögliche Versorgung über Koax im Design klären.',
        'FPDLINK_COAX':'FPD-Link-Verbindung über Koaxleitung; nicht beide PHY-Pins als getrennte aktive Koaxleitungen behandeln.',
        'A2B':'A2B-Audiobus mit Daten und möglicher Busversorgung; gemeinsame elektrische Ausgestaltung im ECAD-Design berücksichtigen.',
        'PSI5':'PSI5-Sensorverbindung mit Strommodulation und Versorgung; nicht als reine digitale Logikleitung behandeln.',
    }
    if name in specific:return specific[name]
    legacy=re.fullmatch(r'(DIGITAL|DIFF|CLOCK|POWER)_(LOW|MID|HIGH)',name)
    if legacy:
        purpose={'DIGITAL':'digitale Logiksignale','DIFF':'Differenzpaare','CLOCK':'Taktleitungen','POWER':'elektrische Leistungspfade'}[legacy[1]]
        return f'Übernommene Projektklasse für {purpose} mit historischer Einteilung {legacy[2]}. Vorhandene Zuordnungen und ECAD-Regeln bleiben erhalten; die Klasse definiert keine allgemeingültigen Geschwindigkeits- oder Stromgrenzen.'
    role={'DATA':'Datenleitungen','CLOCK':'Taktleitungen','CONTROL':'Steuer- und Statusleitungen','STROBE':'Daten-Strobe-Leitungen',
          'LOGIC':'Logikleitungen auf der Controllerseite des Transceivers','BUS':'physikalische Busleitungen auf der Leitungsseite des Transceivers',
          'AUX':'Hilfskanalleitungen','LINE':'Leitungen mit dem physikalischen Schnittstellenpegel','STP':'Verbindungen über verdrillte Differenzleitungen'}
    family,suffix=(name.rsplit('_',1) if '_' in name else (name,''))
    if suffix in role:return f'{role[suffix]} der Schnittstelle {family.replace("_"," ")}. Andere Signalrollen erhalten eigene Klassen; konkrete Designregeln werden im ECAD-Tool ergänzt.'
    if name.startswith('ETH_'):return f'Ethernet-Signale des Profils {name[4:]}; PHY-Seite, Betriebsmodus und Timing im ECAD-Design berücksichtigen.'
    return f'Signale der Schnittstelle {name.replace("_"," ")}; Versorgung, Masse und zusätzliche Steuerleitungen getrennt zuordnen. Designregeln werden im ECAD-Tool ergänzt.'


def member_class(signal,member=None):
    item=member or signal
    values=getattr(item,'realization_attributes',{})
    primary=values.get('netClass') or getattr(item,'attributes',{}).get('netClass')
    additional=values.get('netClasses') or []
    if member is not None and not primary and not additional:
        return member_class(signal)
    return list(dict.fromkeys(([primary] if primary else [])+additional))


def suggest_class(signal,member=None):
    raw=signal.catalog_template or signal.interface_kind or signal.port_type or signal.name
    raw=re.sub(r'_\[(?:Link/Port|Link|Port)\].*','',raw).upper()
    raw=re.sub(r'_(?:LINK|PORT)_?\d+.*','',raw)
    text=(getattr(member,'template_member_key','') or (member.name if member else signal.name)).upper()
    role=text.split('_')[-1]
    def suggestion(profile,reason='Profil aus Vorlage; Betriebsdaten prüfen'):
        return {'class':profile,'reason':reason,'confirmed':False}
    def control():return suggestion('DIGITAL','Steuer-/Statusfunktion erkannt; konkrete Regeln im ECAD-Tool festlegen')
    if raw in ['CSI2','DSI_3']: return {'class':None,'reason':'Unklare Trio-/Differentialstruktur; PHY zunächst klären','confirmed':False}
    if re.search(r'(?:^|_)(?:POWER_RETURN|PGND|LOAD_RETURN)(?:_|$)',text):return suggestion('POWER_RETURN','Dedizierte Leistungsrückleitung ausdrücklich benannt')
    if re.search(r'(?:^|_)(?:GND|AGND|DGND|GROUND)(?:_|$)',text):return suggestion('GROUND','Allgemeine Elektronikmasse aus der Signalrolle erkannt')
    if re.search(r'(?:^|_)(?:POWER_SENSE|KELVIN)(?:_|$)',text):return suggestion('POWER_SENSE','Mess-/Kelvinpfad ausdrücklich benannt')
    if re.search(r'(?:^|_)POWER_LOAD(?:_|$)',text):return suggestion('POWER_LOAD','Lastleistungspfad ausdrücklich benannt')
    if re.search(r'(?:^|_)(?:POWER_SWITCHING|SW_NODE)(?:_|$)',text):return suggestion('POWER_SWITCHING','Schaltknoten ausdrücklich benannt')
    if any(x in text for x in ('AUX_PWR','VCC','VDD')):return suggestion('POWER_SUPPLY','Elektronikversorgung aus dem Signalnamen erkannt')
    if 'VBAT' in text:return {'class':None,'reason':'Batteriepfad: Versorgung, Lastpfad oder Spannungsmessung auswählen','confirmed':False}
    if any(x in text for x in ('RESET','RST#','WAKE','CLKREQ','PWR_OK','HPD','RE#')) or role in ['DE','CEC','CD#','WP#','TRST#']:
        return control()
    if raw.startswith('USB_30') or raw.startswith('USB_31'):
        return suggestion('USB_SUPERSPEED_DATA' if 'SSTX' in text or 'SSRX' in text else 'USB2_DATA')
    if raw.startswith('USB_20'):return suggestion('USB2_DATA','USB2-Betriebsmodus prüfen')
    if raw.startswith('USB_C_CC'):return suggestion('USB_SBU' if 'SBU' in text else 'USB_CC','SBU-Verwendung / Alternate Mode prüfen')
    if raw.startswith('PCIE'):return suggestion('PCIE_CLOCK' if 'CLK' in text else 'PCIE_DATA')
    if raw.startswith('UFS'):return suggestion('UFS_CLOCK' if 'CLK' in text else 'UFS_DATA')
    if raw.startswith('SATA'):return suggestion('SATA_DATA')
    if raw.startswith('HDMI'):
        return suggestion('HDMI_CONTROL' if role in ['SCL','SDA','CEC','HPD'] else 'HDMI_CLOCK' if 'CLK' in text else 'HDMI_DATA')
    if raw.startswith('DP_') or raw=='EDP':
        if 'AUX' in text:return suggestion('DP_AUX')
        if 'CLK' in text:return {'class':None,'reason':'eDP-Takt im Template: physikalische Verwendung prüfen','confirmed':False}
        return suggestion('EDP_DATA' if raw=='EDP' else 'DP_DATA')
    if raw.startswith(('CSI2_','DSI2_')):return suggestion('MIPI_DPHY_CLOCK' if 'CLK' in text else 'MIPI_DPHY_DATA','D-PHY als physikalische Variante bestätigen')
    if raw.startswith('LVDS'):return suggestion('LVDS_CLOCK' if 'CLK' in text else 'LVDS_DATA')
    if raw.startswith('GMSL'):return suggestion('GMSL_COAX' if 'COAX' in raw else 'GMSL_STP','Koax: ungenutzten PHY-Pin und Terminierung prüfen' if 'COAX' in raw else 'STP/Differentialvariante bestätigen')
    if raw.startswith('FPD_LINK'):return suggestion('FPDLINK_COAX','Koax-PHY-Pins und Terminierung prüfen')
    if raw in ['A2B','PSI5']:return suggestion(raw,'Daten und mögliche Busversorgung gemeinsam berücksichtigen')
    if raw.startswith('ETH_'):
        family=raw[4:].replace('_FILT','').replace('_MII','') if raw in ['ETH_10G_MII','ETH_2G5_MII'] else raw[4:].replace('_FILT','')
        return suggestion('ETH_'+family,'PHY-Version, Daten-/Taktrolle und Timing ergänzen')
    if raw=='RS485':return suggestion('RS485_BUS')
    if raw=='RS232':return {'class':None,'reason':'RS232-Leitungspegel oder UART-Logikseite klären','confirmed':False}
    if raw in ['CAN','LIN','FLEXRAY']:return suggestion(raw+'_LOGIC')
    if raw in ['CAN_BUS','LIN_BUS','FLEXRAY_BUS']:return suggestion(raw)
    if raw in ['SSI','I2S','I2S_TDM','I2S_MASTER','I2S_SLAVE','TDM_AUDIO','PDM_MIC','AC97']:
        clock=any(x in text for x in ['CLK','SCK','FSYNC']) or role in ['WS','SYNC']
        return suggestion('AUDIO_CLOCK' if clock else 'AUDIO_DATA')
    if raw.startswith(('RGB_','PARALLEL_CAMERA')):return suggestion('VIDEO_CLOCK' if 'PCLK' in text else 'VIDEO_PARALLEL')
    memory=next((p for p in ['LPDDR3','LPDDR4','LPDDR5','QSPI','OSPI','SDIO','EMMC'] if p in raw),None)
    if memory:
        kind='STROBE' if any(x in text for x in ['DQS','RDQS','WCK']) or role=='DS' else 'CLOCK' if 'CLK' in text else 'CONTROL' if any(x in text for x in ['CA[','CS#','CMD','CKE','ODT','ZQ']) else 'DATA'
        if memory=='QSPI' and kind=='STROBE':kind='CLOCK'
        return suggestion(memory+'_'+kind,'Betriebsmodus / Byte- und Timinggruppe ergänzen')
    if raw in ['UART','I2C','I3C','SPI','SMI','MDIO','JTAG','SWD','1WIRE','SENT']:return suggestion(raw)
    if any(x in raw for x in ['SSPI_FLASH','DSPI_FLASH']):return suggestion('SPI')
    if 'VREF' in text:return suggestion('REFERENCE')
    if 'XTAL' in raw or 'XTAL' in text:return suggestion('CRYSTAL')
    if any(x in text for x in ['ISENSE','VSENSE','TSENSE','FB']):return suggestion('ANALOG_SENSITIVE')
    if 'ADC' in raw or 'ADC' in text:return suggestion('ANALOG_DIFF','Differenziellen ADC-Eingang bestätigen')
    if raw=='GATE_PAIR':return suggestion('GATE_DRIVE')
    if raw in ['PWM','LED_RGB','HSS']:return {'class':None,'reason':'Logiksignal, Gate-Ansteuerung oder Lastpfad klären','confirmed':False}
    if signal.signal_type.value=='Power':return {'class':None,'reason':'Funktion wählen: Elektronikversorgung, Lastpfad, Rückleitung oder Schaltknoten','confirmed':False}
    if 'CLK' in raw or signal.signal_type.value=='Clock':return suggestion('CLOCK')
    if signal.signal_type.value=='Differential':return suggestion('DIFFERENTIAL')
    if signal.signal_type.value=='Analog':return suggestion('ANALOG')
    if signal.signal_type.value in ['Reset','Control','Status']:return control()
    if raw=='GPIO' or signal.signal_type.value=='Digital':return control()
    return {'class':None,'reason':'Keine eindeutige Vorlagenzuordnung','confirmed':False}


def assignment_targets(package):
    for signal in package.signals:
        if signal.connection_type.value=='Bus':
            for member in signal.bus_contents:yield signal,member
        else:yield signal,None


def adopt_netclasses(package):
    migrate_netclasses(package)
    names={c.name for c in package.net_classes}
    if len(names)!=len(package.net_classes):raise ValueError('Doppelte Netzklassennamen')
    if len({c.id for c in package.net_classes})!=len(package.net_classes):raise ValueError('Doppelte Netzklassen-IDs')
    for signal in package.signals:
        for obj in [signal,*signal.bus_contents]:
            for name in member_class(obj):
                if name not in names:
                    package.net_classes.append(NetClassDefinition(name=name,origin='Bestandsprojekt'));names.add(name)
    for signal,member in assignment_targets(package):
        if member_class(signal,member):continue
        if (member or signal).attributes.get('attributeProvenance',{}).get('netClass',{}).get('explicitlyUnassigned'):continue
        proposal=suggest_class(signal,member)
        if proposal['class'] in names:set_assignment(member or signal,proposal['class'],'Vorlagenzuordnung')
    return package


def migrate_netclasses(package):
    """Rename system prefixes without changing class IDs or stored ECAD rules.

    Distinct legacy LOW/MID/HIGH classes are kept when used or configured.
    Native project files are only renamed through reviewed forward annotation.
    """
    renames={}
    existing={c.name for c in package.net_classes}
    used={name for s in package.signals for o in [s,*s.bus_contents] for name in member_class(o)}
    retired=re.compile(r'ISD_(DIGITAL|DIFF|CLOCK|POWER)_(LOW|MID|HIGH)$')
    kept=[]
    for c in package.net_classes:
        if retired.fullmatch(c.name) and c.name not in used and not c.ecad_parameters and c.priority is None:continue
        if c.name.startswith('ISD_'):
            new=c.name[4:]
            if new=='KELVIN_SENSE':new='POWER_SENSE'
            if new in existing and new!=c.name:new += '_'+c.id[:8]
            renames[c.name]=new;c.name=new;existing.add(new)
            c.description=class_description(new);c.origin='Systemkatalog' if c.origin=='ISD' else c.origin
        kept.append(c)
    package.net_classes=kept
    for obj in _all_signal_objects(package):
        for values in (obj.realization_attributes,obj.attributes):
            if values.get('netClass') in renames:values['netClass']=renames[values['netClass']]
            if isinstance(values.get('netClasses'),list):values['netClasses']=[renames.get(n,n) for n in values['netClasses']]
            rules=values.get('ecad',{}).get('kicad',{}) if isinstance(values.get('ecad'),dict) else {}
            if isinstance(rules,dict) and rules.get('netClass') in renames:rules['netClass']=renames[rules['netClass']]
    names={c.name for c in kept}
    for c in default_netclasses():
        if c.name not in names:package.net_classes.append(c)
    return renames


def _all_signal_objects(package):
    yield from package.signals
    for s in package.signals:yield from s.bus_contents
    for d in package.domains:
        for e in d.elements:
            for p in e.ports:yield from p.signals


def assignment_coverage(package):
    targets=list(assignment_targets(package))
    missing=[(s,m) for s,m in targets if not member_class(s,m)]
    return len(targets)-len(missing),len(targets),missing


def rename_class(package,identifier,name,description):
    item=next(c for c in package.net_classes if c.id==identifier)
    if any(c.name==name and c.id!=identifier for c in package.net_classes):raise ValueError('Netzklasse existiert bereits')
    old=item.name
    item.name=name;item.description=description
    NetClassDefinition.model_validate(item.model_dump())
    for obj in _all_signal_objects(package):
        for values in (obj.attributes,obj.realization_attributes):
            if values.get('netClass')==old:values['netClass']=name
            if isinstance(values.get('netClasses'),list):values['netClasses']=[name if n==old else n for n in values['netClasses']]
            rule=values.get('ecad',{}).get('kicad',{}) if isinstance(values.get('ecad'),dict) else {}
            if isinstance(rule,dict) and rule.get('netClass')==old:rule['netClass']=name
    return package


def set_assignment(obj,name,origin='ISD'):
    obj.realization_attributes['netClass']=name or None
    obj.attributes.pop('netClass',None)
    for mapping in [obj.attributes,obj.realization_attributes]:
        rules=mapping.get('ecad',{}).get('kicad',{}) if isinstance(mapping.get('ecad',{}),dict) else {}
        if isinstance(rules,dict):rules.pop('netClass',None)
    obj.attributes.setdefault('attributeProvenance',{})['netClass']={'source':origin,'explicitlyUnassigned':not bool(name)}


def template_audit(templates):
    issues=[]
    for name,members in templates.get('Interface_Temp',{}).items():
        if name.startswith('PCIe_'):
            wrong=[m for m in members if m.startswith('PCIe_') and not m.startswith(name+'_')]
            if wrong:issues.append((name,'Falscher PCIe-Variantenpräfix: '+', '.join(wrong)))
        if name.startswith('CSI2_[') or name.startswith('DSI_3'):issues.append((name,'Physikalische Variante (D-PHY/C-PHY) klären'))
        if 'COAX' in name:issues.append((name,'PHY-Pins sind keine zwei aktiven Koaxleitungen; Terminierung prüfen'))
        if name.startswith('RS232'):issues.append((name,'Logikseite oder RS232-Leitungspegel klären'))
    return issues
