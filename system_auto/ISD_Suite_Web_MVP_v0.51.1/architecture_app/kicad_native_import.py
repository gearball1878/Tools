"""Read-only normalization of a native SCM hierarchy for initial ISD import."""
from copy import deepcopy
import json
from pathlib import PurePosixPath
import uuid

from .kicad_readback import parse_sexpr, _children, _value, _value_from_property


def render(node):
    return '(' + ' '.join(render(value) if isinstance(value, list) else
                          json.dumps(str(value), ensure_ascii=False) for value in node) + ')'


def prepare_native_project(package, project_name, read, hierarchy='auto', initial=False):
    from .kicad_project_readback import _relative
    if initial and (package.domains or package.signals or package.connections):
        raise ValueError('Für den Erstimport bitte ein neues, leeres ISD-Architekturprojekt anlegen')
    if hierarchy not in {'auto', 'domains', 'elements'}:
        raise ValueError('Unbekannte Hierarchiezuordnung')
    document = json.loads(read(project_name))
    old_manifest = document.get('isd_suite', {}).get('manifest', {})
    root_name = old_manifest.get('nativeImport', {}).get('sourceRoot') or old_manifest.get('root') or PurePosixPath(project_name).with_suffix('.kicad_sch').name
    root_path = _relative(project_name, root_name)
    cache, originals = {}, {}
    def load(filename, ancestors=()):
        if filename in ancestors:
            raise ValueError('Zyklische Schaltplanhierarchie')
        if filename in originals:
            return originals[filename]
        if len(originals)>500: raise ValueError('Zu viele Schaltplanblätter')
        tree = parse_sexpr(read(filename))
        if tree[0]!='kicad_sch': raise ValueError('Referenz ist kein KiCad-Schaltplan')
        originals[filename]=tree
        for sheet in _children(tree,'sheet'):
            child=_value_from_property(sheet,'Sheetfile')
            if not child: raise ValueError('Sheetfile fehlt')
            load(_relative(filename,child),(*ancestors,filename))
        return tree
    root=load(root_path)
    root_uuid=_value(root,'uuid')
    if not root_uuid: raise ValueError('Wurzel-Schaltplan hat keine UUID')
    binding=package.properties.get('ecadConnectors',{}).get('kicad',{})
    previous=binding.get('nativeImport')
    if not initial and previous and previous.get('rootUuid')!=root_uuid:
        raise ValueError('Schaltplan gehört nicht zur importierten SCM-Struktur')
    if not initial and previous:
        hierarchy=previous['hierarchy']
    top_sheets=_children(root,'sheet')
    if hierarchy=='auto':
        hierarchy='domains' if top_sheets and all(_children(originals[_relative(root_path,_value_from_property(s,'Sheetfile'))],'sheet') for s in top_sheets) else 'elements'
    # Preserve descriptions and engineering attributes; foreign project identities
    # must never become ISD identities in a newly created project.
    protected={'ISD_ID','ISD_SHA256','ISD_PARENT_ID','ISD_SignalID','ISD_SignalSHA256',
               'ISD_PortID','ISD_PortSHA256','ISD_ConnectionID','ISD_ConnectionSHA256',
               'ISD_SourceAE','ISD_SinkAEs','ISD_Properties','ISD_PortProperties',
               'ISD_ConnectionProperties','ISD_EndpointProperties','ISD_EndpointAttributes'}
    def clean(node):
        node[:]=[child for child in node if not(isinstance(child,list) and len(child)>1 and child[0]=='property' and child[1] in protected)]
        for child in node:
            if isinstance(child,list):clean(child)
    for filename,tree in originals.items():
        normalized=deepcopy(tree);clean(normalized);cache[filename]=render(normalized)
    mapping = (previous or {}).get('sheetMapping', {})
    if mapping:
        for filename in list(cache):
            tree = parse_sexpr(cache[filename])
            for native_sheet in _children(tree, 'sheet'):
                mapped = mapping.get(_value(native_sheet, 'uuid'))
                if mapped:
                    native_sheet.append(['property', 'ISD_ID', mapped])
            cache[filename] = render(tree)
    stem='__isd_scm_'+root_uuid.replace('-','')[:12]
    wrapper_root=stem+'.kicad_sch'
    wrapper_domain=stem+'_domain.kicad_sch'
    def uid(kind):return str(uuid.uuid5(uuid.NAMESPACE_URL,package.project.id+'/'+root_uuid+'/'+kind))
    def sheet(name,file,kind):
        return ['sheet',['uuid',uid(kind)],['property','Sheetname',name],['property','Sheetfile',file]]
    warnings=[]
    if hierarchy=='elements':
        domain=sheet('Schaltplan',root_name,'domain')
        if mapping.get(_value(domain, 'uuid')):
            mapped_id = mapping[_value(domain, 'uuid')]
            domain.append(['property', 'ISD_ID', mapped_id])
            mapped_domain = package.find_domain(mapped_id)
            if mapped_domain:
                next(p for p in _children(domain, 'property') if p[1] == 'Sheetname')[2] = mapped_domain.name
        normalized_root=['kicad_sch',['uuid',uid('root')],domain]
        if not top_sheets:
            # A flat drawing has no block partition to infer. Keep it as one AE,
            # exposing only explicit hierarchical boundary labels.
            ae=sheet(PurePosixPath(root_name).stem,root_name,'flat-ae')
            if mapping.get(_value(ae, 'uuid')): ae.append(['property','ISD_ID',mapping[_value(ae, 'uuid')]])
            for label in _children(root,'hierarchical_label'):
                ae.append(['pin',str(label[1]),_value(label,'shape','passive'),
                           ['at',str(20+len(ae)*10),'40','0'],['uuid',uid('flat-pin/'+_value(label,'uuid'))]])
            cache[_relative(project_name,wrapper_domain)]=render(['kicad_sch',['uuid',uid('domain-screen')],ae])
            _children(domain,'property')[-1][2]=wrapper_domain
            warnings.append('Flacher Schaltplan: ein AE für das gesamte Blatt. Eine fachliche Aufteilung in weitere AEs muss anschließend vorgenommen werden.')
        cache[_relative(project_name,wrapper_root)]=render(normalized_root)
        import_root=wrapper_root
        warnings.append('Zuordnung: eine Domäne „Schaltplan“, darunter die obersten Schaltplanblätter als AEs.')
    else:
        import_root=root_name
        warnings.append('Zuordnung: oberste Schaltplanblätter als Domänen, deren Unterblätter als AEs.')
    source={'sourceRoot':root_name,'rootUuid':root_uuid,'hierarchy':hierarchy}
    if mapping: source['sheetMapping'] = deepcopy(mapping)
    manifest={'format':'isd-kicad/v1','projectId':package.project.id,'root':import_root,
              'nativeImport':source,'snapshot':{'domains':{},'elements':{},'signals':{}},
              'metadata':{},'bindings':[]}
    # A newly linked native project maps sheet pins by the reviewed AE mapping
    # and exact net/bus names. No physical or source files are changed.
    if mapping:
        for filename, content in cache.items():
            tree = parse_sexpr(content)
            for native_sheet in _children(tree, 'sheet'):
                aeid = mapping.get(_value(native_sheet, 'uuid'))
                found = package.find_element(aeid) if aeid else None
                if not found: continue
                ae = found[1]
                for pin in _children(native_sheet, 'pin'):
                    pin_name = str(pin[1]).strip('{}')
                    candidates = [p for p in ae.ports if p.name == pin_name]
                    if len(candidates) != 1: continue
                    port = candidates[0]
                    sid = port.interface_link_id or port.properties.get('architectureSignalId')
                    manifest['bindings'].append({'uuid':_value(pin,'uuid'),'spotId':port.id,
                        'role':'aePort','signalId':sid})
    # Existing native pin IDs remain mapped when re-reading an imported project.
    for data in binding.get('backwardBaseline',{}).get('state',{}).get('element',{}).values():
        for port in data.get('ports',[]):
            pin=port.get('properties',{}).get('kicadPinUuid')
            if pin:
                manifest['bindings'].append({'uuid':pin,'spotId':port['id'],'role':'aePort',
                    'signalId':port.get('interface_link_id')})
    doc=deepcopy(document)
    doc['isd_suite']={'manifest':manifest,'baseline':deepcopy(binding.get('linkedState', {'domain':{},'element':{},'signal':{}}))}
    cache[project_name]=json.dumps(doc)
    return lambda filename: cache[filename] if filename in cache else read(filename), source, warnings


def resolve_import_hosts(preview, choices):
    """Apply reviewed HOST choices to the proposed graph, never the live package."""
    resolved=deepcopy(preview)
    before = deepcopy(resolved.back_annotation_state)
    for sid, element in choices.items():
        signal=resolved.back_annotation_state['signal'][sid]
        candidates=[e['element_id'] for e in signal['sinks']]
        if signal.get('source'):candidates.append(signal['source']['element_id'])
        if element not in candidates:raise ValueError('HOST muss ein angeschlossenes AE sein')
        signal['source']={'element_id':element,'pin_type':'BI','attributes':{},'properties':{}}
        signal['sinks']=[e for e in signal['sinks'] if e['element_id']!=element]
        signal['properties'].pop('hostAssignmentPending',None)
        signal['properties']['nativeHostOverride']=element
        for data in resolved.back_annotation_state['element'].values():
            for port in data['ports']:
                if port.get('interface_link_id')==sid:
                    port['role']='Host' if data['id']==element else 'Participant'
        for change in resolved.changes:
            if change.field=='signalObject' and change.object_id==sid:change.after=deepcopy(signal)
            if change.field=='elementObject':change.after=deepcopy(resolved.back_annotation_state['element'][change.object_id])
            if change.field=='element.ports':change.after=deepcopy(resolved.back_annotation_state['element'][change.object_id]['ports'])
        from .ecad_connector import AnnotationChange
        existing = {(c.object_id, c.field) for c in resolved.changes}
        if (sid, 'signalObject') not in existing:
            for field in ('source', 'sinks', 'properties'):
                key = (sid, 'signal.' + field)
                if key in existing:
                    next(c for c in resolved.changes if (c.object_id,c.field)==key).after=deepcopy(signal[field])
                elif before['signal'][sid][field]!=signal[field]:
                    resolved.changes.append(AnnotationChange(sid,key[1],before['signal'][sid][field],deepcopy(signal[field]),detail='HOST zugeordnet'))
        for eid, data in resolved.back_annotation_state['element'].items():
            if (eid,'elementObject') not in existing and (eid,'element.ports') not in existing and data['ports']!=before['element'][eid]['ports']:
                resolved.changes.append(AnnotationChange(eid,'element.ports',before['element'][eid]['ports'],deepcopy(data['ports']),detail='Portrolle zum HOST zugeordnet'))
    return resolved
