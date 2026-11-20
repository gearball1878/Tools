"""Deterministic KiCad functional-block readback and explicit complete BOM export."""
from __future__ import annotations
from copy import deepcopy
from io import StringIO
import csv
import hashlib
import json
from pathlib import PurePosixPath, Path

from .kicad_readback import parse_sexpr, _children, _value
from .models import FunctionElement, DesignComponent, TechnicalRealization, SolutionVariant, RealizationComponentRole, ComponentRepresentation, ComponentDecisionType, ComponentRoleInRealization, RealizationProvenance
from .ecad_connector import AnnotationChange

def _properties(node):
    return {str(p[1]):str(p[2]) for p in _children(node,'property') if len(p)>2}

def scan_project(project_name,read):
    from .kicad_project_readback import _relative,LIMIT
    doc=json.loads(read(project_name));manifest=doc.get('isd_suite',{}).get('manifest',{})
    root=manifest.get('nativeImport',{}).get('sourceRoot') or manifest.get('root') or PurePosixPath(project_name).with_suffix('.kicad_sch').name
    root=_relative(project_name,root);blocks=[];parts=[];hashes=[];links=[];size=0;root_uuid=''
    def walk(filename,path=(),chain=(),parent_block=None):
        nonlocal size,root_uuid
        if filename in path:raise ValueError('Zyklische Schaltplanhierarchie')
        content=read(filename);size+=len(content.encode());hashes.append(content)
        if size>LIMIT or len(path)>64:raise ValueError('KiCad-Projekt ist zu groß')
        tree=parse_sexpr(content)
        if tree[0]!='kicad_sch':raise ValueError('Ungültiger Schaltplan')
        if not path:root_uuid=_value(tree,'uuid')
        from .ecad_functional_links import sheet_links
        links.extend(sheet_links(tree,chain))
        for symbol in _children(tree,'symbol'):
            props=_properties(symbol);ref=props.get('Reference','')
            instance_path='/'+'/'.join((root_uuid,*chain))
            records=[entry for instances in _children(symbol,'instances')
                     for project in _children(instances,'project')
                     if len(project)>1 and project[1]==PurePosixPath(project_name).stem
                     for entry in _children(project,'path') if len(entry)>1 and entry[1]==instance_path]
            if records:ref=_value(records[0],'reference',ref)
            if not ref or ref.startswith('#') or _value(symbol,'in_bom','yes')=='no':continue
            uid=_value(symbol,'uuid');mpn=next((props.get(k,'').strip() for k in ('MPN','Manufacturer Part Number','Manufacturer_Part_Number','Part Number') if props.get(k,'').strip()),'')
            explicit=props.get('ISD_SYSTEM_DEFINING',props.get('ISD_CorePart','')).casefold()
            defining=True if explicit in {'yes','true','1','ja'} else False if explicit in {'no','false','0','nein'} else None
            parts.append({'key':'/'.join((*chain,uid)),'symbol_uuid':uid,'reference':ref,'value':props.get('Value',''),
                          'manufacturer':props.get('Manufacturer',props.get('Hersteller','')),'mpn':mpn,
                          'footprint':props.get('Footprint',''),'datasheet':props.get('Datasheet',''),
                          'dnp':_value(symbol,'dnp','no')=='yes','sheet':filename,'sheets':[filename],'block':parent_block,
                          'unit':int(_value(symbol,'unit','1')),
                          'system_defining':defining,'properties':props})
        for sheet in _children(tree,'sheet'):
            props=_properties(sheet);uid=_value(sheet,'uuid');child=_relative(filename,props.get('Sheetfile',''))
            if not props.get('Sheetfile'):raise ValueError('Sheetfile fehlt')
            key='/'.join((*chain,uid));blocks.append({'key':key,'uuid':uid,'name':props.get('Sheetname',PurePosixPath(child).stem),
                'sheet':child,'parent':parent_block,'properties':props,'depth':len(chain),
                'pin_names':[str(p[1]) for p in _children(sheet,'pin')]})
            walk(child,(*path,filename),(*chain,uid),key)
    walk(root)
    # KiCad stores one symbol per unit, but a multi-unit IC is one physical part.
    # Annotated references are global; anonymous references retain their UUIDs.
    unique={}
    for part in sorted(parts,key=lambda p:(p['unit'],p['key'])):
        physical_key=part['reference'] if '?' not in part['reference'] else part['key']
        if physical_key in unique:
            previous=unique[physical_key]
            previous['sheets']=sorted(set(previous['sheets']+part['sheets']))
            previous['dnp']=previous['dnp'] or part['dnp']
        else:unique[physical_key]=part
    parts=list(unique.values())
    revision=hashlib.sha256('\n'.join(hashes).encode()).hexdigest()
    return {'project':project_name,'root':root,'revision':revision,'variant':'Schaltplanstand · alle BOM-Symbole einschließlich DNP','blocks':blocks,'parts':parts,'functional_links':links}

def append_functional_review(package,preview,project_name,read):
    from .kicad_project_readback import _id
    data=scan_project(project_name,read);preview.ecad_inventory=data
    state=preview.back_annotation_state;elements=state['element']
    blocks={b['key']:b for b in data['blocks']};proposed={};bound={}
    if not data['blocks'] and len(elements)==1 and data['parts']:
        uid=_value(parse_sexpr(read(data['root'])),'uuid');key='flat/'+uid
        data['blocks'].append({'key':key,'uuid':uid,'name':next(iter(elements.values()))['name'],'sheet':data['root'],'parent':None,'properties':{},'depth':0})
        blocks={b['key']:b for b in data['blocks']};bound[key]=next(iter(elements))
        for part in data['parts']:part['block']=key
    for b in data['blocks']:
        found=next((e for e in elements.values() if e.get('properties',{}).get('nativeScmUuid')==b['uuid'] or e.get('id')==b['properties'].get('ISD_ID')),None)
        if found:bound[b['key']]=found['id']
    for b in data['blocks']:
        if b['key'] in bound:continue  # AE itself is already the abstract responsibility boundary.
        parent=b['parent'];aeid=None
        while parent:
            if parent in bound:aeid=bound[parent];break
            parent=blocks.get(parent,{}).get('parent')
        if not aeid:continue  # A domain or a branch outside a reviewed AE.
        feid=_id(package.project.id,'function',b['key']);old=next((f for f in package.function_elements if f.id==feid),None)
        fe=old.model_copy(deep=True) if old else FunctionElement(id=feid,name=b['name'])
        fe.name=b['name'];fe.architecture_element_id=aeid;fe.source_block_uuid=b['uuid'];fe.source_project=project_name;fe.source_sheet=b['sheet'];fe.source_revision=data['revision']
        description=b['properties'].get('ISD_FUNCTION_DESCRIPTION',b['properties'].get('ISD_DESCRIPTION',''))
        if description:fe.description=description
        if not fe.description:fe.description='Funktionsbeschreibung noch offen.'
        observed_names=set(b.get('pin_names',[]))
        observed_names.update(name for link in data['functional_links'] if any(p['block']==b['key'] for p in link['pins']) for name in link['names'])
        observed_ids={s['id'] for s in state['signal'].values() if s['name'] in observed_names or any(m['name'] in observed_names for m in s.get('bus_contents',[]))}
        fe.interface_signal_ids=sorted((set(fe.interface_signal_ids)-set(fe.properties.get('observedFunctionInterfaces',[])))|observed_ids)
        fe.properties['observedFunctionInterfaces']=sorted(observed_ids)
        fe.properties['nativeFunctionalPortNames']=b.get('pin_names',[])
        proposed[fe.id]=fe;bound[b['key']]=aeid
        before=old.model_dump(mode='json') if old else None;after=fe.model_dump(mode='json')
        if before!=after:preview.changes.append(AnnotationChange(fe.id,'function_elementObject',before,after,detail='FE aus Funktionsblock; Aufgabe und Schnittstellen fachlich prüfen.'))
    # A flat AE containing components gets one abstract FE as its realization context.
    for key,aeid in list(bound.items()):
        b=blocks[key]
        if any(f.source_block_uuid==b['uuid'] for f in proposed.values()):continue
        if not any(p['block']==key for p in data['parts']):continue
        feid=_id(package.project.id,'function',key);old=next((f for f in package.function_elements if f.id==feid),None)
        fe=old.model_copy(deep=True) if old else FunctionElement(id=feid,name=b['name'])
        fe.architecture_element_id=aeid;fe.source_block_uuid=b['uuid'];fe.source_sheet=b['sheet'];fe.source_project=project_name;fe.source_revision=data['revision']
        fe.name=b['name']
        description=b['properties'].get('ISD_FUNCTION_DESCRIPTION',b['properties'].get('ISD_DESCRIPTION',''))
        if description:fe.description=description
        fe.interface_signal_ids=[s['id'] for s in state['signal'].values() if any(ep.get('element_id')==aeid for ep in ([s.get('source')] if s.get('source') else [])+s.get('sinks',[]))]
        if not fe.description:fe.description='Funktionsbeschreibung noch offen.'
        proposed[feid]=fe
        if (old.model_dump(mode='json') if old else None)!=fe.model_dump(mode='json'):preview.changes.append(AnnotationChange(feid,'function_elementObject',old.model_dump(mode='json') if old else None,fe.model_dump(mode='json'),detail='Abstraktes FE für die konkrete Umsetzung des AE.'))
    by_block={b['key']:next((f for f in proposed.values() if f.source_block_uuid==b['uuid']),None) for b in data['blocks']}
    observed_dependencies={f.id:set() for f in proposed.values()}
    for link in data['functional_links']:
        producers={by_block[p['block']].id for p in link['pins'] if by_block.get(p['block']) and p['direction'] in {'output','bidirectional','tri_state'}}
        for pin in link['pins']:
            consumer=by_block.get(pin['block'])
            if consumer and pin['direction'] in {'input','bidirectional'}:observed_dependencies[consumer.id].update(producers-{consumer.id})
    for fe in proposed.values():
        previous=set(fe.properties.get('observedFunctionDependencies',[]))
        fe.dependency_ids=sorted((set(fe.dependency_ids)-previous)|observed_dependencies[fe.id])
        fe.properties['observedFunctionDependencies']=sorted(observed_dependencies[fe.id])
        change=next((c for c in preview.changes if c.object_id==fe.id and c.field=='function_elementObject'),None)
        old=next((f for f in package.function_elements if f.id==fe.id),None)
        if change:change.after=fe.model_dump(mode='json')
        elif old and old.model_dump(mode='json')!=fe.model_dump(mode='json'):
            preview.changes.append(AnnotationChange(fe.id,'function_elementObject',old.model_dump(mode='json'),fe.model_dump(mode='json'),detail='Funktionale Schnittstellen und gespeicherte Schaltplanabhängigkeiten prüfen.'))
        roles=[]
        for part in data['parts']:
            owner=blocks.get(part['block'],{})
            if owner.get('uuid')!=fe.source_block_uuid:continue
            # Suggest ICs as core technology; an explicit classification also covers shunts/references.
            cid=_id(package.project.id,'core-part',part['key']);old=next((c for c in package.components if c.id==cid or c.properties.get('nativeSymbolKey')==part['key']),None)
            is_core=not part['dnp'] and part['system_defining'] is not False and (part['system_defining'] is True or part['reference'].startswith('U'))
            if not is_core and old is None:continue
            c=old.model_copy(deep=True) if old else DesignComponent(id=cid,name=part['value'] or part['reference'])
            c.manufacturer=part['manufacturer'];c.manufacturer_part_number=part['mpn'];c.legacy_ecad_reference=part['reference'];c.package_name=part['footprint'];c.representation=ComponentRepresentation.PHYSICAL;c.decision_type=ComponentDecisionType.EXISTING;c.provenance=RealizationProvenance.OBSERVED
            if part['system_defining'] is not None:c.system_defining=part['system_defining']
            if not c.system_defining_reason:c.system_defining_reason='Explizit im ECAD markiert.' if part['system_defining'] is True else 'Kernbauteil-Vorschlag aus IC-Zuordnung; fachlich prüfen.'
            c.properties.update(nativeSymbolKey=part['key'],nativeSymbolUuid=part['symbol_uuid'],ecadSourceRevision=data['revision'],ecadSourceProject=project_name,ecadPresence='DNP' if part['dnp'] else 'Present')
            before=old.model_dump(mode='json') if old else None;after=c.model_dump(mode='json')
            if before!=after:preview.changes.append(AnnotationChange(c.id,'componentObject',before,after,detail='Eingesetztes Kernbauteil; MPN und Bedeutung prüfen.'))
            if is_core:roles.append(RealizationComponentRole(component_id=c.id,role=ComponentRoleInRealization.A_PART,purpose=c.system_defining_reason))
            if part['datasheet'].startswith(('https://','http://')) and not any(s.owner_id==c.id and s.url==part['datasheet'] for s in package.technical_sources):
                from .models import TechnicalSource,TechnicalSourceOwner,TechnicalSourceType
                source=TechnicalSource(id=_id(package.project.id,'datasheet',part['key']+part['datasheet']),owner_type=TechnicalSourceOwner.COMPONENT,owner_id=c.id,title='Datenblatt · '+c.name,source_type=TechnicalSourceType.DATASHEET,url=part['datasheet'],notes='Referenz aus ECAD; Dokumentrevision und Inhalt noch prüfen.')
                preview.changes.append(AnnotationChange(source.id,'technical_sourceObject',None,source.model_dump(mode='json'),detail='Datenblattreferenz; noch kein geprüfter Nachweis.'))
        rid=_id(package.project.id,'fe-realization',fe.id);old=next((r for r in package.technical_realizations if r.function_element_id==fe.id),None)
        r=old.model_copy(deep=True) if old else TechnicalRealization(id=rid,name=fe.name,generic_function=fe.description,function_element_id=fe.id,architecture_element_id=fe.architecture_element_id,provenance=RealizationProvenance.OBSERVED)
        r.architecture_element_id=fe.architecture_element_id;r.generic_function=fe.description
        v=next((v for v in r.variants if v.properties.get('ecadObserved')),None)
        if roles or v:
            if not v:
                v=SolutionVariant(id=_id(package.project.id,'fe-variant',fe.id),name='Eingesetzte ECAD-Umsetzung',properties={'ecadObserved':True});r.variants.append(v)
            v.component_roles=roles
            if not r.selected_variant_id:
                from .models import SolutionVariantStatus,TechnicalRealizationStatus
                v.status=SolutionVariantStatus.SELECTED;r.selected_variant_id=v.id;r.status=TechnicalRealizationStatus.SELECTED
        before=old.model_dump(mode='json') if old else None;after=r.model_dump(mode='json')
        if before!=after:preview.changes.append(AnnotationChange(r.id,'realizationObject',before,after,detail='FE-Realisierung mit systemdefinierenden Bauteilen.'))
    present=set(proposed)
    part_keys={p['key']:p for p in data['parts']}
    for old in package.components:
        if old.properties.get('ecadSourceProject')!=project_name:continue
        observation=part_keys.get(old.properties.get('nativeSymbolKey'))
        presence='Missing' if observation is None else 'DNP' if observation['dnp'] else 'Present'
        if presence=='Missing' and old.properties.get('ecadPresence')!=presence:
            after=old.model_copy(deep=True);after.properties.update(ecadPresence=presence,ecadSourceRevision=data['revision'])
            preview.changes.append(AnnotationChange(old.id,'componentObject',old.model_dump(mode='json'),after.model_dump(mode='json'),detail='Kernbauteil im aktuellen ECAD-Stand nicht mehr bestückt. Katalog und historische Nachweise bleiben erhalten.'))
    for old in package.function_elements:
        if old.source_project==project_name and old.id not in present:
            preview.changes.append(AnnotationChange(old.id,'function_elementObject',old.model_dump(mode='json'),None,detail='Funktionsblock nicht mehr im ECAD-Projekt enthalten.'))
            for r in package.technical_realizations:
                if r.function_element_id==old.id:
                    after=r.model_dump(mode='json');after['function_element_id']=None
                    preview.changes.append(AnnotationChange(r.id,'realizationObject',r.model_dump(mode='json'),after if r.requirement_ids else None,detail='Zuordnung zum entfernten FE prüfen.'))
    binding=package.properties.get('ecadConnectors',{}).get('kicad',{})
    baseline=binding.get('functionalSourceBaseline',binding.get('functionalBaseline',{}))
    preview.functional_observations=deepcopy(baseline)
    for change in preview.changes:
        if not change.field.endswith('Object'):continue
        kind=change.field[:-6]
        if kind not in {'function_element','component','realization','technical_source'}:continue
        previous=baseline.get(kind,{}).get(change.object_id)
        if change.after is None:preview.functional_observations.setdefault(kind,{}).pop(change.object_id,None)
        else:preview.functional_observations.setdefault(kind,{})[change.object_id]=deepcopy(change.after)
        if previous is not None and isinstance(change.before,dict) and isinstance(change.after,dict):
            conflicts=[]
            for field,value in list(change.after.items()):
                if value==previous.get(field):change.after[field]=deepcopy(change.before.get(field))
                elif change.before.get(field)!=previous.get(field) and value!=change.before.get(field):conflicts.append(field)
            if conflicts:change.status='conflict';change.detail+=' In ISD und ECAD geändert: '+', '.join(conflicts)
        elif previous is not None and change.before!=previous and change.after!=change.before:
            change.status='conflict';change.detail+=' ISD-Objekt wurde seit der letzten Rückübernahme geändert.'
    preview.changes=[c for c in preview.changes if c.before!=c.after]
    preview.warnings.append('FE und Kernbauteil-Vorschläge prüfen. Die vollständige BOM bleibt über den ECAD-Projektzugriff verfügbar.')

def bom_csv(inventory):
    output=StringIO();writer=csv.writer(output,delimiter=';')
    writer.writerow(['Projekt',inventory['project'],'ECAD-Revision',inventory['revision'],'Variante',inventory['variant']])
    writer.writerow(['Anzahl','Referenzbezeichner','Wert','Hersteller','MPN','Footprint','DNP','Blätter','Datenblatt'])
    groups={}
    for p in inventory['parts']:
        key=(p['value'],p['manufacturer'],p['mpn'],p['footprint'],p['dnp'],p['datasheet'])
        groups.setdefault(key,{})[p['key']]=p
    for key,parts in sorted(groups.items(),key=lambda x:str(x[0])):
        writer.writerow([len(parts),', '.join(sorted(p['reference'] for p in parts.values())),*key[:4],'Ja' if key[4] else 'Nein',', '.join(sorted({sheet for p in parts.values() for sheet in p.get('sheets',[p['sheet']])})),key[5]])
    return ('\ufeff'+output.getvalue()).encode('utf-8')

def linked_bom(package):
    from .kicad_project_readback import LIMIT
    binding=package.properties.get('ecadConnectors',{}).get('kicad',{});path=Path(binding.get('projectPath','')).expanduser().resolve()
    if not path.is_file() or path.suffix!='.kicad_pro':raise ValueError('Bitte zuerst ein lokales KiCad-Projekt verknüpfen.')
    def read(name):
        target=(path.parent/name).resolve()
        if not target.is_relative_to(path.parent) or target.stat().st_size>LIMIT:raise ValueError('Ungültige Projektdatei')
        return target.read_text(encoding='utf-8-sig')
    return bom_csv(scan_project(path.name,read))
