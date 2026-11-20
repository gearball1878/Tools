"""Reviewed project linking and three-way forward edits, preserving native circuitry."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import tempfile
import uuid

from .ecad_connector import AnnotationChange, AnnotationPreview
from .kicad_readback import _children, _value, _value_from_property
from .kicad_project_readback import _state
from .models import ArchitectureElement, ArchitectureSignal, Domain


class Atom(str):
    pass


def parse_raw(content):
    stack=[]; root=[]; current=root
    for match in re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',content):
        token=match.group()
        if token=='(':
            child=[]; current.append(child); stack.append(current); current=child
        elif token==')':
            if not stack:raise ValueError('Ungültiger KiCad-Schaltplan')
            current=stack.pop()
        else:current.append(json.loads(token) if token.startswith('"') else Atom(token))
    if stack or len(root)!=1 or not isinstance(root[0],list):raise ValueError('Ungültiger KiCad-Schaltplan')
    return root[0]


def render_raw(node):
    if isinstance(node,list):return '('+' '.join(render_raw(v) for v in node)+')'
    return str(node) if isinstance(node,Atom) else json.dumps(str(node),ensure_ascii=False)


def digest(data):return sha256(data).hexdigest()


def load_project(project_file):
    path=Path(project_file).expanduser().resolve()
    if path.suffix.lower()!='.kicad_pro' or not path.is_file():raise ValueError('Eine vorhandene .kicad_pro-Datei auswählen.')
    documents={path.name:path.read_bytes()}; project=json.loads(documents[path.name])
    manifest=project.get('isd_suite',{}).get('manifest',{})
    if not manifest and (path.parent/'isd_kicad_bindings.json').is_file():
        manifest=json.loads((path.parent/'isd_kicad_bindings.json').read_text(encoding='utf-8'))
    sidecar = path.parent/'isd_kicad_bindings.json'
    if sidecar.is_file(): documents[sidecar.name] = sidecar.read_bytes()
    root=manifest.get('nativeImport',{}).get('sourceRoot') or manifest.get('root') or path.with_suffix('.kicad_sch').name
    trees={}
    def walk(name,ancestors=()):
        target=(path.parent/name).resolve()
        if not target.is_relative_to(path.parent):raise ValueError('Schaltplanreferenz verlässt den Projektordner.')
        name=target.relative_to(path.parent).as_posix()
        if name in ancestors:raise ValueError('Zyklische Schaltplanhierarchie.')
        if name in trees:return
        if len(trees)>500:raise ValueError('Zu viele Schaltplanblätter.')
        raw=target.read_bytes(); documents[name]=raw
        if sum(map(len,documents.values()))>40_000_000:raise ValueError('KiCad-Projekt ist zu groß.')
        tree=parse_raw(raw.decode('utf-8-sig'))
        if tree[0]!='kicad_sch':raise ValueError('Referenz ist kein Schaltplan.')
        trees[name]=tree
        for sheet in _children(tree,'sheet'):
            child=_value_from_property(sheet,'Sheetfile')
            if not child:raise ValueError('Blattreferenz fehlt.')
            walk((Path(name).parent/child).as_posix(),(*ancestors,name))
    walk(root)
    return path,project,manifest,documents,trees,root


def inspect_link(package,project_file):
    path,project,manifest,documents,trees,root=load_project(project_file)
    rows=[]
    top=_children(trees[root],'sheet')
    hierarchy='domains' if top and all(_children(trees[(Path(root).parent/_value_from_property(s,'Sheetfile')).as_posix()],'sheet') for s in top) else 'elements'
    native_uuid=_value(trees[root],'uuid')
    bound=manifest.get('projectId')==package.project.id
    if bound:return {'path':str(path),'bound':True,'rows':[],'root':root,'rootUuid':native_uuid,'hierarchy':hierarchy}
    objects=[*package.domains,*(e for d in package.domains for e in d.elements)]
    def walk(file,depth=0):
        for sheet in _children(trees[file],'sheet'):
            name=_value_from_property(sheet,'Sheetname') or ''
            kind='domain' if hierarchy=='domains' and depth==0 else 'element' if (hierarchy=='elements' and depth==0) or (hierarchy=='domains' and depth==1) else None
            if kind:
                oid=_value_from_property(sheet,'ISD_ID')
                allowed=[o for o in objects if (kind=='domain')==isinstance(o,Domain)]
                matches=[o.id for o in allowed if o.id==oid or o.properties.get('nativeScmUuid')==_value(sheet,'uuid') or name.casefold() in {o.name.casefold(),o.technical_name.casefold()}]
                rows.append({'uuid':_value(sheet,'uuid'),'name':name,'kind':kind,'target':matches[0] if len(matches)==1 else '', 'file':file})
            child=(Path(file).parent/_value_from_property(sheet,'Sheetfile')).as_posix()
            walk(child,depth+1)
    walk(root)
    if not top:
        synthetic_ae=str(uuid.uuid5(uuid.NAMESPACE_URL,package.project.id+'/'+native_uuid+'/flat-ae'))
        allowed=[e for d in package.domains for e in d.elements]
        rows.append({'uuid':synthetic_ae,'name':Path(root).stem,'kind':'element',
                     'target':allowed[0].id if len(allowed)==1 else '', 'file':None})
    if hierarchy=='elements':
        synthetic=str(uuid.uuid5(uuid.NAMESPACE_URL,package.project.id+'/'+native_uuid+'/domain'))
        rows.insert(0,{'uuid':synthetic,'name':'Gemeinsame HW-Domäne','kind':'domain','target':package.domains[0].id if len(package.domains)==1 else '', 'file':None})
    return {'path':str(path),'bound':False,'rows':rows,'root':root,'rootUuid':native_uuid,'hierarchy':hierarchy}


def link_project(package,inspection,mapping=None):
    # Re-read selected files before storing an association; no ECAD writes.
    latest=inspect_link(package,inspection['path'])
    if (latest['rootUuid'],latest['root'])!=(inspection['rootUuid'],inspection['root']):raise ValueError('Projekt wurde seit der Auswahl geändert.')
    candidate=deepcopy(package)
    old=candidate.properties.setdefault('ecadConnectors',{}).get('kicad',{})
    binding={k:deepcopy(v) for k,v in old.items() if k not in {'projectPath','snapshot','metadataSnapshot','backwardBaseline','nativeImport','references','linkedState','forwardDocuments'}}
    binding['projectPath']=inspection['path']
    binding['linkedState']=_state(package)
    from .kicad_connector import _snapshot, _metadata
    binding['snapshot'] = _snapshot(package)
    binding['metadataSnapshot'] = _metadata(package)
    if not latest['bound']:
        mapping=mapping or {r['uuid']:r['target'] for r in latest['rows'] if r['target']}
        allowed={'domain':{d.id for d in package.domains},'element':{e.id for d in package.domains for e in d.elements}}
        seen=set()
        for row in latest['rows']:
            oid=mapping.get(row['uuid'])
            if not oid:raise ValueError('Jedes Architekturblatt muss vor dem Verknüpfen zugeordnet werden.')
            if oid not in allowed[row['kind']] or oid in seen:raise ValueError('Ungültige oder mehrfache Blattzuordnung.')
            seen.add(oid)
        binding['nativeImport']={'sourceRoot':latest['root'],'rootUuid':latest['rootUuid'],'hierarchy':latest['hierarchy'],'sheetMapping':mapping}
    candidate.properties['ecadConnectors']['kicad']=binding
    return candidate


def node_key(node):
    if not isinstance(node,list) or not node:return None
    uid=_value(node,'uuid')
    if uid and node[0]!='uuid':return (str(node[0]),uid)
    if node[0] in {'property','bus_alias'} and len(node)>1:return (str(node[0]),str(node[1]))
    return (str(node[0]),)


def merge_node(base,current,wanted):
    if wanted==base:return deepcopy(current),False
    if current==base or current==wanted:return deepcopy(wanted),False
    if all(isinstance(v,list) for v in (base,current,wanted)) and base and current and wanted and base[0]==current[0]==wanted[0] and any(isinstance(v,list) for v in base):
        # Merge child fields, retaining user-created pins, symbol instances and properties.
        def parts(node):
            children=[v for v in node if isinstance(v,list)]
            keys=[node_key(v) for v in children]
            return [v for v in node if not isinstance(v,list)],dict(zip(keys,children)),len(set(keys))==len(keys)
        ba,b,bok=parts(base);ca,c,cok=parts(current);wa,w,wok=parts(wanted)
        if bok and cok and wok:
            atoms,conflict=merge_node(ba,ca,wa) if any(ba!=v for v in (ca,wa)) else (deepcopy(ca),False)
            result=list(atoms)
            for key in list(c)+[k for k in w if k not in c]:
                new,failed=merge_node(b.get(key),c.get(key),w.get(key)) if key in b or key in w else (deepcopy(c[key]),False)
                conflict|=failed
                if new is not None:result.append(new)
            return result,conflict
    return deepcopy(wanted),True



def merge_json(base, current, wanted):
    if wanted == base: return deepcopy(current), False
    if current == base or current == wanted: return deepcopy(wanted), False
    if all(isinstance(v, dict) for v in (base, current, wanted)):
        result = {}; conflict = False
        for key in set(current) | set(wanted):
            if key not in base and key not in wanted:
                result[key] = deepcopy(current[key]); continue
            value, failed = merge_json(base.get(key), current.get(key), wanted.get(key))
            conflict |= failed
            if value is not None: result[key] = value
        return result, conflict
    if all(isinstance(v, list) for v in (base, current, wanted)):
        members = base + current + wanted
        key = 'name' if members and all(isinstance(v,dict) and 'name' in v for v in members) else 'pattern'
        if members and all(isinstance(v,dict) and key in v for v in members):
            identity=lambda v: (v['pattern']+'\0'+str(v.get('netclass',''))) if key=='pattern' else v[key]
            b={identity(v):v for v in base};c={identity(v):v for v in current};w={identity(v):v for v in wanted}
            merged,conflict=merge_json(b,c,w)
            return list(merged.values()),conflict
    return deepcopy(wanted), True

def baseline_package(package,state,manifest=None):
    candidate=deepcopy(package)
    candidate.domains=[Domain.model_validate({**d,'elements':[]}) for d in state['domain'].values()]
    by_domain={d.id:d for d in candidate.domains}
    for data in state['element'].values():
        data=deepcopy(data);parent=data.pop('domain_id')
        if parent in by_domain:by_domain[parent].elements.append(ArchitectureElement.model_validate(data))
    candidate.signals=[ArchitectureSignal.model_validate(v) for v in state['signal'].values()]
    if 'net_classes' in state:
        from .netclasses import NetClassDefinition
        candidate.net_classes=[NetClassDefinition.model_validate(v) for v in state['net_classes']]
    candidate.connections=[]
    from .topology import synchronize_signal_topology
    for signal in candidate.signals:synchronize_signal_topology(candidate,signal)
    if manifest:
        # Reproduce the exported baseline rather than inventing new connection IDs.
        from .models import Connection, SignalEndpoint
        metadata = manifest.get('metadata', {})
        for signal in candidate.signals:
            original = metadata.get('signals', {}).get(signal.id, {})
            endpoints = original.get('sinkEndpoints')
            if endpoints is not None and {v['element_id'] for v in endpoints} == {v.element_id for v in signal.sinks}:
                signal.sinks = [SignalEndpoint.model_validate(v) for v in endpoints]
        originals = {v.get('signalId'): (i, v) for i, v in metadata.get('connections', {}).items()}
        for index, connection in enumerate(candidate.connections):
            if connection.signal_id not in originals: continue
            identifier, original = originals[connection.signal_id]
            candidate.connections[index] = Connection(id=identifier, name=original['name'],
                description=original.get('description', ''), signal_id=connection.signal_id,
                connection_type=original.get('connectionType', connection.connection_type),
                attributes=original.get('attributes', {}), properties=original.get('properties', {}),
                endpoints=[{'element_id': v['elementId'], 'port_id': v['portId'], 'role': v.get('role'),
                            'attributes': v.get('attributes', {}), 'properties': v.get('properties', {})}
                           for v in original.get('endpoints', [])])
    return candidate


def forward_project_preview(package,project_file):
    from .kicad_connector import KiCadConnector
    from .property_schema import exchange_values
    path,project,manifest,documents,trees,root=load_project(project_file)
    binding=package.properties.get('ecadConnectors',{}).get('kicad',{})
    if Path(binding.get('projectPath','')).resolve()!=path:raise ValueError('Projekt zuerst ausdrücklich mit der Architektur verknüpfen.')
    preview=AnnotationPreview('forward')
    preview.project_path=str(path)
    preview.expected_documents={name:digest(raw) for name,raw in documents.items()}
    preview.file_changes=[]
    if manifest.get('projectId')==package.project.id and not manifest.get('nativeImport'):
        state=project.get('isd_suite',{}).get('baseline') or binding.get('linkedState')
        if not state:raise ValueError('Forward-Basis fehlt. Zuerst Projektverknüpfung prüfen.')
        connector=KiCadConnector()
        old_policy = manifest.get("blockTopologyPolicy", "legacy")
        base_files,base_manifest=connector.generate(baseline_package(package,state,manifest if old_policy == "legacy" else None), topology_policy=old_policy, legend_policy=manifest.get("legendPolicy", "legacy"))
        new_files,new_manifest=connector.generate(package)
        old_by_id={b['spotId']:b['file'] for b in manifest.get('bindings',[]) if b.get('role') in {'domain','ae'}}
        def remap(files,generated):
            mapping={generated['root']:root, str(Path(generated['root']).with_suffix('.kicad_pro')):path.name}
            for b in generated.get('bindings',[]):
                if b.get('role') in {'domain','ae'} and b['spotId'] in old_by_id:mapping[b['file']]=old_by_id[b['spotId']]
            result={}
            for name,content in files.items():
                if name.endswith('.kicad_sch'):
                    tree=parse_raw(content)
                    for sheet in _children(tree,'sheet'):
                        prop=next((p for p in _children(sheet,'property') if p[1]=='Sheetfile'),None)
                        if prop and prop[2] in mapping:prop[2]=mapping[prop[2]]
                    result[mapping.get(name,name)]=tree
            return result,mapping
        bases,_=remap(base_files,base_manifest);wanted,mapping=remap(new_files,new_manifest)
        for name in sorted(set(bases)|set(wanted)):
            current=trees.get(name);base=bases.get(name);new=wanted.get(name)
            if new is None:
                preview.warnings.append(f'Entferntes Architekturblatt {name} bleibt als Datei erhalten; der Elternverweis wird geprüft entfernt.')
                continue
            if current is None:
                after=render_raw(new)+'\n'
                status='conflict' if (path.parent/name).exists() else 'ready'
                preview.changes.append(AnnotationChange(name,'file.new',None,after,status,'Neues Architekturblatt: '+name))
                preview.file_changes.append((name,None,new));continue
            base_nodes={node_key(n):n for n in base if isinstance(n,list)} if base else {}
            new_nodes={node_key(n):n for n in new if isinstance(n,list)}
            current_nodes={node_key(n):n for n in current if isinstance(n,list)}
            for key in sorted(set(base_nodes)|set(new_nodes)):
                if key[0] in {'lib_symbols','uuid','version','generator','generator_version'}:continue
                b=base_nodes.get(key);w=new_nodes.get(key);c=current_nodes.get(key)
                if b==w:continue
                merged,conflict=merge_node(b,c,w)
                if merged==c:continue
                label=_value_from_property(w or c or [],'Sheetname') or _value_from_property(w or c or [],'ISD_SignalID') or (str((w or c or ['',''])[1]) if len(w or c or [])>1 and not isinstance((w or c)[1],list) else key[0])
                preview.changes.append(AnnotationChange(name, 'schematic.'+key[0],render_raw(c) if c else None,render_raw(merged) if merged else None,
                    'conflict' if conflict else 'ready',name+' · '+label))
                preview.file_changes.append((name,key,merged))
        # New baseline records requested SPOT state; three-way merge keeps native independent changes.
        updated_project=deepcopy(project)
        new_manifest['root']=root
        new_manifest['files']=[mapping.get(n,n) for n in new_manifest['files']]
        for b in new_manifest['bindings']:
            for field in ('file','parentFile'):
                if b.get(field) in mapping:b[field]=mapping[b[field]]
        for b in new_manifest['labelBindings']:
            if b.get('file') in mapping:b['file']=mapping[b['file']]
        updated_project['isd_suite']={'format':'isd-kicad/project-v2','manifest':new_manifest,'baseline':_state(package)}
        preview.updated_project=updated_project
    else:
        native=binding.get('nativeImport')
        if not native or native['rootUuid']!=_value(trees[root],'uuid'):raise ValueError('Blattzuordnung für dieses Projekt fehlt.')
        base=binding.get('linkedState',_state(package));now=_state(package)
        mapping=native.get('sheetMapping') or {o.properties.get('nativeScmUuid'):o.id for d in package.domains for o in [d,*d.elements] if o.properties.get('nativeScmUuid')}
        wanted=deepcopy(trees)
        for name,tree in wanted.items():
            conflicts = set()
            for sheet in _children(tree,'sheet'):
                oid=mapping.get(_value(sheet,'uuid'))
                kind='domain' if oid in now['domain'] else 'element'
                if oid not in now[kind] or oid not in base[kind]:continue
                data=now[kind][oid];old=base[kind][oid]
                for field,prop in [('name','Sheetname'),('description','ISD_DESCRIPTION'),('realization_attributes','ISD_REALIZATION_ATTRIBUTES'), ('attributes','ISD_ATTRIBUTES'), ('properties','ISD_PROPERTIES'), ('technical_name','ISD_TECHNICAL_NAME'), ('technical_domain_ids','ISD_TECHNICAL_DOMAIN_IDS'), ('domain_type_id','ISD_TYPE') if kind=='domain' else ('role_type_id','ISD_TYPE'), ('color','ISD_COLOR')]:
                    before_value=old.get(field);after_value=data.get(field)
                    if field=='realization_attributes':
                        cls=Domain if kind=='domain' else ArchitectureElement
                        before_value=exchange_values(cls.model_validate(old),field,'forward',package.property_definitions)
                        after_value=exchange_values(cls.model_validate(data),field,'forward',package.property_definitions)
                    if before_value==after_value:continue
                    existing=next((p for p in _children(sheet,'property') if p[1]==prop),None)
                    value=json.dumps(data.get(field,{}),ensure_ascii=False) if isinstance(data.get(field), (dict,list)) else data.get(field,'')
                    if field=='realization_attributes':value=json.dumps(exchange_values((Domain if kind=='domain' else ArchitectureElement).model_validate(data),field,'forward',package.property_definitions),ensure_ascii=False)
                    actual = existing[2] if existing else before_value
                    if existing and isinstance(old.get(field), (dict,list)):
                        try: actual = json.loads(actual)
                        except ValueError: pass
                    if actual != before_value and actual != after_value: conflicts.add(node_key(sheet))
                    if existing:existing[2]=value
                    else:sheet.append([Atom('property'),prop,value,[Atom('at'),Atom('0'),Atom('0'),Atom('0')],[Atom('effects'),[Atom('font'),[Atom('size'),Atom('1'),Atom('1')]], [Atom('hide'),Atom('yes')]]])
            renames={v['name']:now['signal'][sid]['name'] for sid,v in base['signal'].items() if sid in now['signal'] and v['name']!=now['signal'][sid]['name']}
            def rename(node):
                if node and node[0] in {'label','hierarchical_label','global_label'} and len(node)>1:
                    raw_name = str(node[1]).strip('{}')
                    matches = [(sid, old) for sid, old in base['signal'].items() if old['name'] == raw_name and sid in now['signal']]
                    if len(matches) == 1:
                        sid, old_data = matches[0]; new_data = now['signal'][sid]
                        for field, prop in [('description','ISD_Description'), ('realization_attributes','ISD_RealizationAttributes'), ('attributes','ISD_Attributes'), ('properties','ISD_Properties'), ('signal_type','ISD_SignalType')]:
                            before_value=old_data.get(field);after_value=new_data.get(field)
                            if field=='realization_attributes':
                                before_value=exchange_values(ArchitectureSignal.model_validate(old_data),field,'forward',package.property_definitions)
                                after_value=exchange_values(ArchitectureSignal.model_validate(new_data),field,'forward',package.property_definitions)
                            if before_value==after_value:continue
                            value = after_value if after_value is not None else ''
                            if isinstance(value, (dict,list)): value = json.dumps(value, ensure_ascii=False)
                            existing = next((p for p in _children(node, 'property') if p[1] == prop), None)
                            actual = existing[2] if existing else before_value
                            if existing and isinstance(old_data.get(field),(dict,list)):
                                try: actual = json.loads(actual)
                                except ValueError: pass
                            if actual != before_value and actual != after_value: conflicts.add(node_key(node))
                            if existing: existing[2] = value
                            else: node.append([Atom('property'),prop,value,[Atom('at'),Atom('0'),Atom('0'),Atom('0')],[Atom('effects'),[Atom('font'),[Atom('size'),Atom('1'),Atom('1')]],[Atom('hide'),Atom('yes')]]])
                if node and node[0] in {'label','hierarchical_label','global_label','pin','bus_alias'} and len(node)>1:
                    old=str(node[1]);raw=old.strip('{}')
                    if raw in renames:node[1]=('{'+renames[raw]+'}') if old.startswith('{') else renames[raw]
                for child in node:
                    if isinstance(child,list):rename(child)
            rename(tree)
            current_nodes={node_key(n):n for n in trees[name] if isinstance(n,list)}
            for node in tree:
                if not isinstance(node,list):continue
                key=node_key(node);before=current_nodes.get(key)
                if node!=before:
                    preview.changes.append(AnnotationChange(name,'schematic.'+key[0],render_raw(before) if before else None,render_raw(node),status='conflict' if key in conflicts else 'ready',detail=name+' · '+key[0]))
                    preview.file_changes.append((name,key,node))
        # Native structural changes need an explicit boundary mapping; never infer or erase circuitry.
        for kind in ('domain','element','signal'):
            for oid in set(base[kind])|set(now[kind]):
                before=base[kind].get(oid);after=now[kind].get(oid)
                structural=before is None or after is None
                if kind=='element' and before and after:structural=before.get('domain_id')!=after.get('domain_id')
                if kind=='signal' and before and after:structural=any(before.get(f)!=after.get(f) for f in ('source','sinks','bus_contents'))
                if structural:
                    preview.changes.append(AnnotationChange(oid,kind+'.structure',before,after,'unsupported','Native SCM-Struktur zuerst explizit im Schaltplan ändern und zurücklesen.'))
                    preview.file_changes.append(None)
    from .kicad_rules import project_settings
    baseline_state = binding.get('linkedState') if binding.get('backwardBaseline') else state if manifest.get('projectId')==package.project.id and not manifest.get('nativeImport') else base
    baseline_project = baseline_package(package, baseline_state)
    baseline_signals = baseline_project.signals
    old_settings = json.loads(project_settings([s for s in baseline_signals if s.source and s.sinks], path.name, baseline_project.net_classes))['net_settings']
    new_settings = json.loads(project_settings([s for s in package.signals if s.source and s.sinks], path.name, package.net_classes))['net_settings']
    if old_settings != new_settings:
        merged, conflict = merge_json(old_settings, project.get('net_settings'), new_settings)
        if merged != project.get('net_settings'):
            preview.changes.append(AnnotationChange(package.project.id,'project.net_settings',project.get('net_settings'),merged,
                'conflict' if conflict else 'ready','Explizite KiCad-Netzklassen und Zuordnungen'))
            preview.file_changes.append((path.name, ('project','net_settings'), merged))
    preview.original_project=project
    preview.original_trees=trees
    preview.requested_state=_state(package)
    return preview


def apply_forward_project(package,preview,selected=None):
    """Stale-file guard and rollback; only reviewed nodes are replaced."""
    from .kicad_connector import _snapshot,_metadata
    path=Path(preview.project_path)
    selected=set(range(len(preview.changes))) if selected is None else set(selected)
    complete = getattr(preview, 'annotation_complete', True) and len(selected) == len(preview.changes)
    if any(preview.changes[i].status!='ready' for i in selected):raise ValueError('Konflikte zuerst lösen.')
    for name,expected in preview.expected_documents.items():
        target=path.parent/name
        if not target.is_file() or digest(target.read_bytes())!=expected:raise ValueError('KiCad-Projekt wurde seit der Prüfung verändert. Bitte erneut einlesen.')
    trees=deepcopy(preview.original_trees);writes={}
    for i in sorted(selected):
        patch=preview.file_changes[i]
        if patch is None:raise ValueError('Diese Änderung wird nicht unterstützt.')
        name,key,node=patch
        if key == ('project','net_settings'):
            document=json.loads(writes[path.name]) if path.name in writes else deepcopy(preview.original_project)
            document['net_settings']=deepcopy(node)
            writes[path.name]=json.dumps(document,ensure_ascii=False,indent=2).encode('utf-8')
            continue
        if key is None:trees[name]=deepcopy(node)
        else:
            tree=trees[name]
            index=next((j for j,n in enumerate(tree) if isinstance(n,list) and node_key(n)==key),None)
            if index is None:
                if node is not None:tree.append(deepcopy(node))
            elif node is None:tree.pop(index)
            else:tree[index]=deepcopy(node)
        writes[name]=(render_raw(trees[name])+'\n').encode('utf-8')
    # Partial application retains baseline, so rejected changes are offered again.
    if complete and hasattr(preview,'updated_project'):
        document=json.loads(writes[path.name]) if path.name in writes else deepcopy(preview.original_project)
        document['isd_suite']=deepcopy(preview.updated_project['isd_suite'])
        document['isd_suite']['netSettingsBaseline']=deepcopy(document.get('net_settings',{}))
        writes[path.name]=json.dumps(document,ensure_ascii=False,indent=2).encode()
        if 'isd_kicad_bindings.json' in preview.expected_documents:
            writes['isd_kicad_bindings.json']=json.dumps(preview.updated_project['isd_suite']['manifest'],ensure_ascii=False,indent=2).encode()
    # Validate selected structural changes together before any filesystem write.
    # Skipping a required child-sheet addition is rejected instead of creating
    # a dangling hierarchy. Existing deeper circuitry is traversed read-only.
    def check(file, ancestors=()):
        if file in ancestors: raise ValueError('Auswahl erzeugt eine zyklische Schaltplanhierarchie.')
        tree = trees.get(file)
        if tree is None: raise ValueError('Auswahl verweist auf ein fehlendes Schaltplanblatt: '+file)
        for sheet in _children(tree, 'sheet'):
            child = _value_from_property(sheet, 'Sheetfile')
            if not child: raise ValueError('Auswahl erzeugt eine unvollständige Blattreferenz.')
            child = (Path(file).parent / child).as_posix()
            check(child, (*ancestors, file))
    root = json.loads((path.parent/path.name).read_text(encoding='utf-8-sig')).get('isd_suite', {}).get('manifest', {}).get('root') or path.with_suffix('.kicad_sch').name
    if root in trees: check(root)
    # Guard every newly generated filename against overwriting untracked native data.
    for name in writes:
        if name not in preview.expected_documents and (path.parent/name).exists():raise ValueError('Zieldatei wurde inzwischen angelegt: '+name)
    originals={name:(path.parent/name).read_bytes() if (path.parent/name).exists() else None for name in writes}
    backup=Path(tempfile.mkdtemp(prefix='isd_forward_backup_',dir=path.parent))
    try:
        for name,raw in originals.items():
            if raw is not None:
                target=backup/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        for name,raw in writes.items():
            target=path.parent/name;target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_suffix(target.suffix+'.isd-tmp');temporary.write_bytes(raw);temporary.replace(target)
    except OSError:
        for name,raw in originals.items():
            target=path.parent/name
            if raw is None:target.unlink(missing_ok=True)
            else:target.write_bytes(raw)
        raise
    preview.applied_originals = originals
    preview.applied_writes = {name: digest(raw) for name, raw in writes.items()}
    candidate=deepcopy(package)
    binding=candidate.properties.setdefault('ecadConnectors',{}).setdefault('kicad',{})
    if complete:
        binding['snapshot']=_snapshot(candidate);binding['metadataSnapshot']=_metadata(candidate)
        binding['linkedState']=preview.requested_state
        binding['netSettingsBaseline']=deepcopy(json.loads(path.read_text(encoding='utf-8-sig')).get('net_settings',{}))
        binding.pop('backwardBaseline',None)
    binding['lastForwardBackup']=str(backup)
    return candidate


def rollback_forward_project(preview):
    """If SPOT persistence fails, undo our file edits without erasing concurrent edits."""
    path=Path(preview.project_path)
    for name,raw in preview.applied_originals.items():
        target=path.parent/name
        if not target.is_file() or digest(target.read_bytes())!=preview.applied_writes[name]:
            raise ValueError('Projekt wurde inzwischen geändert. Sicherung für Wiederherstellung verwenden.')
    for name,raw in preview.applied_originals.items():
        target=path.parent/name
        if raw is None:target.unlink(missing_ok=True)
        else:target.write_bytes(raw)
