"""Project-based HW back annotation. Physical circuitry stays below AE boundaries."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from io import BytesIO
import json
import hashlib
from pathlib import Path, PurePosixPath
import re
import uuid
from zipfile import ZipFile, BadZipFile

from .ecad_connector import AnnotationChange, AnnotationPreview
from .identity import sha_identity
from .kicad_readback import parse_sexpr, _children, _value, _value_from_property, _xy
from .models import ArchitecturePackage, ArchitectureSignal, ArchitectureElement, Domain, InterfacePort, Signal
from .topology import synchronize_signal_topology
from .property_schema import merge_ecad_values

LIMIT = 40_000_000


def _id(project, kind, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'isd/backward/{project}/{kind}/{key}'))


def _relative(parent, child):
    path = PurePosixPath(parent).parent / child
    if path.is_absolute() or '..' in path.parts or '\\' in child:
        raise ValueError('Schaltplanreferenz muss innerhalb des Projektordners liegen')
    return str(path)


def inspect_project(package, project_file, build_architecture=False, hierarchy="auto"):
    """Read the selected .kicad_pro and recursively referenced sheets, without writes."""
    path = Path(project_file).expanduser().resolve()
    if path.suffix.lower() != '.kicad_pro' or not path.is_file():
        raise ValueError('Bitte eine vorhandene .kicad_pro-Projektdatei auswählen')
    total = 0
    def read(name):
        nonlocal total
        target = (path.parent / name).resolve()
        if not target.is_relative_to(path.parent):
            raise ValueError('Schaltplanreferenz verlässt den Projektordner')
        size = target.stat().st_size
        total += size
        if total > LIMIT:
            raise ValueError('KiCad-Projekt ist zu groß')
        return target.read_text(encoding='utf-8-sig')
    native = package.properties.get('ecadConnectors', {}).get('kicad', {}).get('nativeImport')
    bound = json.loads(read(path.name)).get('isd_suite', {}).get('manifest', {}).get('projectId') == package.project.id
    if build_architecture or (native and not bound):
        from .kicad_native_import import prepare_native_project
        read, source, warnings = prepare_native_project(package, path.name, read, hierarchy, build_architecture)
        preview = _inspect(package, path.name, read)
        preview.native_source = source
        preview.warnings[:0] = warnings
    else:
        preview = _inspect(package, path.name, read)
    preview.project_path = str(path)
    return preview


def inspect_project_archive(package, payload, build_architecture=False, hierarchy="auto"):
    if len(payload) > LIMIT:
        raise ValueError('KiCad-Archiv ist zu groß')
    try:
        opened = ZipFile(BytesIO(payload))
    except BadZipFile as error:
        raise ValueError('Datei ist kein gültiges KiCad-Projekt-ZIP') from error
    with opened as archive:
        entries = archive.infolist()
        if sum(e.file_size for e in entries) > LIMIT or len(entries) > 2000:
            raise ValueError('Entpacktes KiCad-Projekt ist zu groß')
        if len({e.filename for e in entries}) != len(entries):
            raise ValueError('Archiv enthält doppelte Dateinamen')
        projects = [e.filename for e in entries if e.filename.endswith('.kicad_pro')]
        if len(projects) != 1:
            raise ValueError('Archiv muss genau eine .kicad_pro-Projektdatei enthalten')
        def read(name):
            try:
                return archive.read(name).decode('utf-8-sig')
            except KeyError as error:
                raise ValueError(f'Referenzierte Projektdatei fehlt: {name}') from error
        native = package.properties.get('ecadConnectors', {}).get('kicad', {}).get('nativeImport')
        bound = json.loads(read(projects[0])).get('isd_suite', {}).get('manifest', {}).get('projectId') == package.project.id
        if build_architecture or (native and not bound):
            from .kicad_native_import import prepare_native_project
            read, source, warnings = prepare_native_project(package, projects[0], read, hierarchy, build_architecture)
            preview = _inspect(package, projects[0], read)
            preview.native_source = source
            preview.warnings[:0] = warnings
            return preview
        return _inspect(package, projects[0], read)


def _state(package):
    result = {'domain': {}, 'element': {}, 'signal': {}, 'net_classes': [c.model_dump(mode='json') for c in package.net_classes]}
    for domain in package.domains:
        data = domain.model_dump(mode='json')
        data.pop('elements')
        result['domain'][domain.id] = data
        for element in domain.elements:
            data = element.model_dump(mode='json')
            data['domain_id'] = domain.id
            result['element'][element.id] = data
    result['signal'] = {s.id: s.model_dump(mode='json') for s in package.signals}
    for signal in result['signal'].values():
        signal['sinks'].sort(key=lambda endpoint: endpoint['element_id'])
    return result


def embed_project_binding(files, manifest, package):
    project = str(PurePosixPath(manifest['root']).with_suffix('.kicad_pro'))
    document = json.loads(files[project])
    document['isd_suite'] = {'format': 'isd-kicad/project-v2', 'manifest': manifest,
                             'baseline': _state(package), 'netSettingsBaseline': deepcopy(document.get('net_settings',{}))}
    files[project] = json.dumps(document, ensure_ascii=False, indent=2)


class _Graph:
    def __init__(self):
        self.parent = {}
    def find(self, node):
        self.parent.setdefault(node, node)
        if self.parent[node] != node:
            self.parent[node] = self.find(self.parent[node])
        return self.parent[node]
    def join(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def _on(p, a, b):
    return (abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])) < 1e-5
            and min(a[0], b[0])-1e-5 <= p[0] <= max(a[0], b[0])+1e-5
            and min(a[1], b[1])-1e-5 <= p[1] <= max(a[1], b[1])+1e-5)


def _bus(text, aliases, stack=()):
    """Resolve native group/vector buses; return base name and full member names."""
    if text in aliases:
        if text in stack:
            raise ValueError('Zyklischer Bus-Alias')
        _, members = _bus('{' + ' '.join(aliases[text]) + '}', aliases, (*stack, text))
        return text, members
    vector = re.fullmatch(r'(.+)\[(\d+)\.\.(\d+)\]', text)
    if vector:
        name, a, b = vector.groups()
        if abs(int(a)-int(b)) > 4095:
            raise ValueError('Busvektor darf höchstens 4096 Mitglieder enthalten')
        return text, [name + str(i) for i in range(min(int(a), int(b)), max(int(a), int(b))+1)]
    group = re.fullmatch(r'([^{}]*)\{([^{}]+)\}', text)
    if not group:
        return text, None
    prefix, body = group.groups()
    members = []
    for token in body.split():
        if token in aliases:
            if token in stack:
                raise ValueError('Zyklischer Bus-Alias')
            _, expanded = _bus('{' + ' '.join(aliases[token]) + '}', aliases, (*stack, token))
        else:
            _, expanded = _bus(token, aliases, stack)
        members.extend(expanded if expanded is not None else [token])
    if len(set(members)) != len(members):
        raise ValueError(f'Doppelte Busmitglieder: {text}')
    return prefix or (body if body in aliases else text), [prefix + '.' + m if prefix else m for m in members]


def _inspect(package, project_name, read):
    preview = AnnotationPreview('backward')
    project = json.loads(read(project_name))
    embedded = project.get('isd_suite', {})
    manifest = embedded.get('manifest')
    if not manifest:
        manifest = json.loads(read(_relative(project_name, 'isd_kicad_bindings.json')))
    if manifest.get('projectId') != package.project.id or manifest.get('format') != 'isd-kicad/v1':
        raise ValueError('KiCad-Projekt gehört nicht zu diesem SPOT-Projekt')
    native_source = manifest.get('nativeImport')
    export_key = hashlib.sha256(json.dumps(native_source or manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    current = _state(package)
    baseline = embedded.get('baseline')
    if baseline is None:
        baseline = deepcopy(current)
        for kind, key in [('domain', 'domains'), ('element', 'elements')]:
            for oid, name in manifest['snapshot'][key].items():
                if oid not in baseline[kind]:
                    continue
                baseline[kind][oid]['name'] = name
                meta = manifest.get('metadata', {}).get(key, {}).get(oid, {})
                for field, mk in [('description', 'description'), ('color', 'color'),
                                  ('technical_name', 'technicalName'), ('domain_id', 'domainId'),
                                  ('attributes', 'attributes'), ('domain_type_id', 'domainTypeId'),
                                  ('role_type_id', 'roleTypeId')]:
                    if mk in meta:
                        baseline[kind][oid][field] = meta[mk]
        for oid, data in manifest['snapshot']['signals'].items():
            if oid in baseline['signal']:
                baseline['signal'][oid].update(name=data['name'],
                    source={'element_id': data['source'], 'pin_type': 'BI', 'attributes': {}, 'properties': {}} if data['source'] else None,
                    sinks=[{'element_id': e, 'pin_type': 'BI', 'attributes': {}, 'properties': {}} for e in data['sinks']])
    # A successful prior import supplies the new three-way baseline even if KiCad's
    # embedded export baseline has not been rewritten.
    previous = package.properties.get('ecadConnectors', {}).get('kicad', {}).get('backwardBaseline')
    previous_labels = {}
    if previous and previous.get('root') == manifest['root'] and previous.get('exportKey') == export_key:
        baseline = previous['state']
        previous_labels = previous.get('labels', {})
    desired = deepcopy(current)
    trees, sheets, aliases = {}, [], {}
    old_bindings = {b['uuid']: b for b in manifest.get('bindings', [])}
    seen_ids = set()
    seen_architecture_files = set()
    native_names = set()
    def walk(filename, depth=0, owner=None, path=()):
        if filename in path:
            raise ValueError('Zyklische Schaltplanhierarchie')
        if len(trees) > 500:
            raise ValueError('Zu viele Schaltplanblätter')
        if filename not in trees:
            tree = parse_sexpr(read(filename))
            if tree[0] != 'kicad_sch':
                raise ValueError('Referenz ist kein KiCad-Schaltplan')
            trees[filename] = tree
        tree = trees[filename]
        for alias in _children(tree, 'bus_alias'):
            members = [str(m) for node in _children(alias, 'members') for m in node[1:]]
            if alias[1] in aliases and aliases[alias[1]] != members:
                raise ValueError(f'Bus-Alias {alias[1]} hat widersprüchliche Mitglieder')
            aliases[alias[1]] = members
        for sheet in _children(tree, 'sheet'):
            props = {str(p[1]): str(p[2]) for p in _children(sheet, 'property') if len(p)>2}
            uid = _value(sheet, 'uuid')
            binding = old_bindings.get(uid, {})
            oid = binding.get('spotId') if binding.get('role') in {'domain', 'ae'} else None
            if oid and props.get('ISD_ID') != oid:
                raise ValueError('Geschützte ISD-Objektkennung verändert')
            oid = oid or props.get('ISD_ID') or _id(package.project.id, 'sheet', uid)
            kind = 'domain' if depth == 0 else 'element' if depth == 1 else None
            child = _relative(filename, props.get('Sheetfile', ''))
            if not props.get('Sheetfile'):
                raise ValueError('Sheetfile fehlt')
            if kind:
                if child in seen_architecture_files:
                    raise ValueError('Mehrfach verwendete Architekturblätter müssen vor dem Import eindeutig aufgeteilt werden')
                seen_architecture_files.add(child)
                if oid in seen_ids:
                    raise ValueError('Mehrfach instanziierte Architekturblätter oder doppelte ISD-ID')
                seen_ids.add(oid)
                if props.get('ISD_SHA256') and props['ISD_SHA256'] != sha_identity(oid):
                    raise ValueError('Geschützte Architekturkennung verändert')
                old = current[kind].get(oid)
                data = deepcopy(old) if old else (Domain(id=oid, name=props['Sheetname']).model_dump(mode='json') if kind=='domain'
                    else ArchitectureElement(id=oid, name=props['Sheetname']).model_dump(mode='json'))
                data.pop('elements', None)
                data['name'] = props.get('Sheetname', '')
                if native_source:
                    original_name = data['name']
                    count = 2
                    while data['name'].casefold() in native_names:
                        data['name'] = original_name + f' ({count})'
                        count += 1
                    native_names.add(data['name'].casefold())
                    data['properties'].update(nativeScmUuid=uid, nativeSheetName=original_name)
                for prop, field in [('ISD_DESCRIPTION', 'description'), ('ISD_TECHNICAL_NAME', 'technical_name'),
                                    ('ISD_TYPE', 'domain_type_id' if kind=='domain' else 'role_type_id')]:
                    if prop in props:
                        data[field] = props[prop]
                if 'ISD_PROPERTIES' in props:
                    data['properties'].update(json.loads(props['ISD_PROPERTIES']))
                if 'ISD_TECHNICAL_DOMAIN_IDS' in props:
                    data['technical_domain_ids'] = json.loads(props['ISD_TECHNICAL_DOMAIN_IDS'])
                if 'ISD_REALIZATION_ATTRIBUTES' in props:
                    data['realization_attributes'] = merge_ecad_values((Domain if kind=='domain' else ArchitectureElement).model_validate(data),json.loads(props['ISD_REALIZATION_ATTRIBUTES']),package.property_definitions)
                if 'ISD_ATTRIBUTES' in props:
                    data['attributes'] = json.loads(props['ISD_ATTRIBUTES'])
                if kind == 'domain':
                    color = props.get('ISD_COLOR', data['color'])
                    fills = _children(sheet, 'fill')
                    rgb = _children(fills[0], 'color') if fills else []
                    basecolor = baseline[kind].get(oid, {}).get('color')
                    if rgb and len(rgb[0]) >= 4:
                        fill = '#{:02X}{:02X}{:02X}'.format(*(int(float(v)) for v in rgb[0][1:4]))
                        if basecolor and fill.casefold() != basecolor.casefold():
                            if color.casefold() not in {basecolor.casefold(), fill.casefold()}:
                                raise ValueError('ISD_COLOR und Blattfüllung widersprechen sich')
                            color = fill
                    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                        raise ValueError('Domänenfarbe muss #RRGGBB sein')
                    data['color'] = color
                else:
                    data['domain_id'] = owner
                desired[kind][oid] = data
                sheets.append((filename, child, sheet, kind, oid))
            walk(child, depth+1, oid if kind=='domain' else owner, (*path, filename))
    walk(_relative(project_name, manifest['root']))
    for kind in ('domain', 'element'):
        for oid in baseline[kind]:
            if oid not in seen_ids:
                desired[kind].pop(oid, None)
    graph = _Graph()
    labels, pins = [], []
    # Geometric connectivity: wire and bus layers remain separate. Crossing
    # segments join only at endpoints, explicit junctions, or attached terminals.
    for filename, tree in trees.items():
        terminals = []
        for label in [*_children(tree, 'label'), *_children(tree, 'hierarchical_label'), *_children(tree, 'global_label')]:
            text = str(label[1]); name, members = _bus(text, aliases)
            layer = 'bus' if members is not None else 'wire'
            point = _xy(label)
            if point is None: continue
            node = (filename, layer, point)
            graph.find(node); terminals.append(node)
            labels.append((filename, label, node, name, members))
            scope = '*' if label[0] == 'global_label' else filename
            graph.join(node, ('label', scope, layer, text))
        for sheet in _children(tree, 'sheet'):
            for pin in _children(sheet, 'pin'):
                point = _xy(pin)
                if point is None: continue
                _, members = _bus(str(pin[1]), aliases)
                node = (filename, 'bus' if members is not None else 'wire', point)
                terminals.append(node); graph.find(node)
                pins.append((filename, sheet, pin, node))
        for layer in ('wire', 'bus'):
            segments = []
            points = {n[2] for n in terminals if n[1] == layer}
            for segment in _children(tree, layer):
                pts = _children(segment, 'pts')
                xy = _children(pts[0], 'xy') if pts else []
                if len(xy)!=2: continue
                a,b = [(float(p[1]),float(p[2])) for p in xy]
                segments.append((a,b)); points.update((a,b))
            points.update(p for j in _children(tree,'junction') if (p:=_xy(j)) is not None)
            for a,b in segments:
                for point in points:
                    if _on(point,a,b): graph.join((filename,layer,a),(filename,layer,point))
    for _, label, _, _, _ in labels:
        for prefix in ("Signal", "Port", "Connection"):
            identifier = _value_from_property(label, "ISD_" + prefix + "ID")
            checksum = _value_from_property(label, "ISD_" + prefix + "SHA256")
            if identifier and checksum != sha_identity(identifier):
                raise ValueError("Geschützte Netz-/Portkennung verändert")
    for filename, child, sheet, kind, oid in sheets:
        for pin in _children(sheet, 'pin'):
            matches = [l for l in labels if l[0]==child and l[1][0]=='hierarchical_label' and l[1][1]==pin[1]]
            if not matches:
                raise ValueError(f'Blatt-Pin {pin[1]} hat kein passendes hierarchisches Label in {child}')
            node = next(n for f,s,p,n in pins if f==filename and s is sheet and p is pin)
            for match in matches: graph.join(node,match[2])
    grouped = defaultdict(list)
    for filename,child,sheet,kind,oid in sheets:
        if kind!='element': continue
        oldports = {p['id']:p for p in current['element'].get(oid,{}).get('ports',[])}
        result = []
        for pin in _children(sheet,'pin'):
            uid = _value(pin,'uuid'); binding = old_bindings.get(uid,{})
            port_id = binding.get('spotId') if binding.get('role')=='aePort' else None
            port_id = port_id or _id(package.project.id,'port',uid)
            node = next(n for f,s,p,n in pins if f==filename and s is sheet and p is pin)
            group = graph.find(node)
            connected_labels = [l for l in labels if graph.find(l[2])==group]
            name,members = _bus(str(pin[1]),aliases)
            local = [l for l in connected_labels if l[0]==filename]
            if local:
                choices = {(l[3],tuple(l[4]) if l[4] is not None else None) for l in local}
                if len(choices)>1: raise ValueError(f'Mehrere Netzbezeichnungen am Port {name}')
                name,ms = next(iter(choices)); members = list(ms) if ms is not None else None
            if members is not None:
                for l in connected_labels:
                    if l[4] is None or len(l[4])!=len(members):
                        raise ValueError(f'Bus-Mismatch an {name}')
                    # Native group prefixes may differ between hierarchy levels.
                    keys = lambda values: {v.split('.')[-1] for v in values}
                    if keys(l[4]) != keys(members): raise ValueError(f'Bus-Mitglieder passen nicht an {name}')
            port = deepcopy(oldports.get(port_id)) if port_id in oldports else InterfacePort(id=port_id,name=name).model_dump(mode='json')
            port.update(name=name, connection_type='Bus' if members is not None else 'Net',
                        role='Host' if pin[2]=='output' else 'Participant')
            port['properties'].update(kicadPinUuid=uid, portNamingRule='BusName1to1' if members is not None else 'SignalName1to1',
                                       manualPortName=name)
            port['implementation_binding']['kicadPinType'] = str(pin[2])
            port['signals'] = []
            result.append(port)
            grouped[group].append((oid,port,connected_labels,members))
        # Independent manual architecture ports were never exported; retain them.
        exported = {b['spotId'] for b in manifest['bindings'] if b['role']=='aePort'}
        result.extend(deepcopy(p) for p in oldports.values() if p['id'] not in exported
                      and not p['properties'].get('kicadPinUuid'))
        global_ids = set(manifest.get('globalSignalIds', []))
        result.extend(deepcopy(p) for p in oldports.values() if p['id'] not in {v['id'] for v in result} and (p.get('interface_link_id') or p.get('properties', {}).get('architectureSignalId')) in global_ids)
        desired['element'][oid]['ports'] = result
    def update_metadata(data, connected, spec, base):
        for field, prop, decode in spec:
            values = []
            for label in connected:
                raw = _value_from_property(label[1], prop)
                if raw is None:
                    continue
                value = decode(raw)
                label_key = label[0] + ':' + _value(label[1], 'uuid')
                prior = previous_labels.get(label_key, {}).get(prop)
                expected = decode(prior) if prior is not None else base.get(field)
                if value != expected:
                    values.append(value)
            if values:
                if any(value != values[0] for value in values):
                    raise ValueError(f"Widersprüchliche Labelattribute: {prop}")
                if field=='realization_attributes':
                    cls=InterfacePort if 'role' in data and 'signals' in data else ArchitectureSignal
                    data[field]=merge_ecad_values(cls.model_validate(data),values[0],package.property_definitions)
                else:data[field] = values[0]

    represented = {b['signalId'] for b in manifest['bindings'] if b['role']=='aePort'}
    if native_source:
        represented.update(sid for sid, data in baseline['signal'].items() if data.get('properties', {}).get('nativeScmImport'))
    used_signals = set()
    for group, endpoints in grouped.items():
        aeids = [e[0] for e in endpoints]
        if len(set(aeids))!=len(aeids): raise ValueError('Mehrere Ports desselben AE am selben Netz')
        references = {str(_value_from_property(l[1],'ISD_SignalID')) for _,_,ls,_ in endpoints for l in ls
                      if _value_from_property(l[1],'ISD_SignalID')}
        if len(references)>1: raise ValueError('Verschiedene SPOT-Netze verbunden; Zusammenführung zuerst klären')
        sid = next(iter(references),None)
        if sid is None:
            sid = next((p['interface_link_id'] for _,p,_,_ in endpoints if p.get('interface_link_id')),None)
        if sid in used_signals:
            # A physically disconnected original port must survive without a link.
            sid = None
        if len(endpoints)==1 and not any(l[0] == next(f for f,_,sh,k,oid in sheets if k=='element' and oid==endpoints[0][0]) for l in endpoints[0][2]):
            p=endpoints[0][1]; p['interface_link_id']=None
            p['properties'].pop('architectureSignalId',None)
            continue
        name = endpoints[0][1]['name']; members=endpoints[0][3]
        sid = sid or _id(package.project.id,'net',min(p['id'] for _,p,_,_ in endpoints))
        used_signals.add(sid)
        data = deepcopy(current['signal'].get(sid)) if sid in current['signal'] else ArchitectureSignal(id=sid,name=name).model_dump(mode='json')
        all_labels = list({ _value(l[1], 'uuid'): l for _,_,ls,_ in endpoints for l in ls }.values())
        meta = manifest.get('metadata', {}).get('signals', {}).get(sid, {})
        update_metadata(data, all_labels, [
            ('description', 'ISD_Description', str), ('attributes', 'ISD_Attributes', json.loads),
            ('properties', 'ISD_Properties', json.loads), ('realization_attributes', 'ISD_RealizationAttributes', json.loads), ('signal_type', 'ISD_SignalType', str)],
            {**meta, 'signal_type': meta.get('signalType')})
        if current['signal'].get(sid, {}).get('properties', {}).get('manualDefinitionOverride'):
            data['properties']['manualDefinitionOverride'] = True
        for e,port,ls,_ in endpoints:
            own_labels = [l for l in ls if _value_from_property(l[1], 'ISD_PortID') == port['id']]
            portmeta = manifest.get('metadata', {}).get('ports', {}).get(port['id'], {})
            update_metadata(port, own_labels, [
                ('description', 'ISD_PortDescription', str), ('attributes', 'ISD_PortAttributes', json.loads),
                ('port_type', 'ISD_PortType', str), ('realization_attributes', 'ISD_PortRealizationAttributes', json.loads)],
                {**portmeta, 'port_type': portmeta.get('portType')})
        hosts = [e for e,p,_,_ in endpoints if p['role']=='Host']
        if len(hosts)>1 and not native_source: raise ValueError(f'Mehrere HOSTs an {name}; Rollen in KiCad klären')
        old_source=data.get('source')
        host=hosts[0] if len(hosts)==1 else (old_source['element_id'] if old_source and any(e==old_source['element_id'] and p['implementation_binding'].get('kicadPinType') in {'bidirectional', 'passive', 'tri_state'} for e,p,_,_ in endpoints) else None)
        if native_source and len(hosts)!=1 and data['properties'].get('nativeHostOverride') in aeids:
            host = data['properties']['nativeHostOverride']
        if len(endpoints)>1 and not host:
            if not native_source:
                raise ValueError(f'HOST für {name} ist nicht eindeutig; Blatt-Pin als Ausgang markieren')
            preview.warnings.append(f'{name}: HOST ist noch zuzuordnen; ohne Zuordnung wird keine gerichtete Verbindung erzeugt.')
            data['properties']['hostAssignmentPending'] = True
        old_endpoints = {x['element_id']: x for x in ([data['source']] if data.get('source') else []) + data.get('sinks', [])}
        old_members = data.get('bus_contents', [])
        alias_name = str(data.get('name', '')).strip('{}')
        if (members is not None and len(old_members)>1 and len(members)==1
                and members[0].strip('{}') in {alias_name, name.strip('{}')}):
            raise ValueError(f'Bus-Alias für {name} fehlt oder ist unvollständig. '
                             'Vorhandene Busmitglieder bleiben erhalten; Alias in KiCad korrigieren.')
        data.update(name=name,connection_type='Bus' if members is not None else 'Net',
                    source=deepcopy(old_endpoints.get(host, {'element_id':host,'pin_type':'BI','attributes':{},'properties':{}})) if host else None,
                    sinks=[deepcopy(old_endpoints.get(e, {'element_id':e,'pin_type':'BI','attributes':{},'properties':{}})) for e in sorted(aeids) if e!=host])
        if members is not None:
            oldmembers={m['name']:m for m in data['bus_contents']}
            data['bus_contents']=[deepcopy(oldmembers[m]) if m in oldmembers else
                                  Signal(id=_id(package.project.id,'member',sid+'/'+m),name=m).model_dump(mode='json') for m in members]
        else: data['bus_contents']=[]
        if members is not None:
            member_metadata=[]
            for _,_,connected,_ in endpoints:
                for label in connected:
                    raw=_value_from_property(label[1],'ISD_BusMemberRealizationAttributes')
                    if raw is not None:member_metadata.append(json.loads(raw))
            if member_metadata:
                if any(v!=member_metadata[0] for v in member_metadata):raise ValueError('Widersprüchliche Busmitgliedsattribute')
                for m in data['bus_contents']:
                    incoming=member_metadata[0].get(m['name'])
                    if incoming is not None:m['realization_attributes']=merge_ecad_values(Signal.model_validate(m),incoming,package.property_definitions)
        # Preserve external names on future template migration.
        if sid not in current['signal'] or data['name'] != current['signal'][sid]['name'] or data['bus_contents'] != current['signal'][sid]['bus_contents']:
            data['properties']['manualDefinitionOverride']=True
        if native_source:
            data['properties']['nativeScmImport'] = True
        if members is None:
            classes=[];changed_class=False
            for _,_,connected,_ in endpoints:
                for label in connected:
                    for prop in ('Netclass','Net Class'):
                        raw=_value_from_property(label[1],prop)
                        if raw is None:continue
                        label_key=label[0]+':'+_value(label[1],'uuid')
                        prior=previous_labels.get(label_key,{}).get(prop)
                        if prior is None:
                            prior=next((b.get('netClass') for b in manifest.get('bindings',[]) if b.get('uuid')==_value(label[1],'uuid')),None)
                        if prior is None:
                            from .kicad_rules import class_for
                            existing_signal=package.find_architecture_signal(sid)
                            prior=class_for(existing_signal) if existing_signal else ''
                        if raw!=prior:
                            changed_class=True
                            for value in raw.split(','):
                                value=value.strip()
                                if value and value not in classes:classes.append(value)
            if changed_class:
                data['realization_attributes']['netClass']=classes[0] if classes else None
                data['realization_attributes']['netClasses']=classes[1:] or None
                data['attributes'].setdefault('attributeProvenance',{})['netClass']={'source':'KiCad-Label'}
        desired['signal'][sid]=data
        for e,p,_,_ in endpoints:
            p['interface_link_id']=sid
            p['properties']['architectureSignalId']=sid
            p['role']='Host' if e==host else 'Participant'
    for sid in represented-used_signals:
        desired['signal'].pop(sid,None)
    remaining=set(desired['element'])
    for data in desired['signal'].values():
        if data['source'] and data['source']['element_id'] not in remaining: data['source']=None
        data['sinks']=[e for e in data['sinks'] if e['element_id'] in remaining]
    from .netclass_readback import inspect_netclasses
    inspect_netclasses(package,project,preview,desired,baseline)
    for kind in ('domain','element','signal'):
        for oid in sorted(set(desired[kind])|set(baseline[kind])):
            before=current[kind].get(oid); after=desired[kind].get(oid); base=baseline[kind].get(oid)
            if before==after: continue
            if after is None or before is None:
                status='ready' if before==base else 'conflict'
                preview.changes.append(AnnotationChange(oid,kind+'Object',before,after,status,
                    ('Objekt löschen' if after is None else 'Objekt anlegen')+' · '+str((after or before).get('name',''))))
                continue
            for field,value in after.items():
                if before.get(field)==value: continue
                # Unchanged KiCad fields must not overwrite independent ISD edits.
                if base is not None and value==base.get(field): continue
                status='ready' if base is not None and before.get(field)==base.get(field) else 'conflict'
                preview.changes.append(AnnotationChange(oid,kind+'.'+field,before.get(field),value,status,
                    str(after['name'])+' · '+('In ISD und KiCad geändert' if status=='conflict' else 'KiCad geändert')))
    preview.back_annotation_state=desired
    preview.back_annotation_root=manifest['root']
    preview.back_annotation_export_key=export_key
    preview.back_annotation_labels = {filename + ':' + _value(label, 'uuid'): {str(p[1]): str(p[2]) for p in _children(label, 'property') if len(p)>2}
                                      for filename,label,_,_,_ in labels}
    from .ecad_functional import append_functional_review
    append_functional_review(package,preview,project_name,read)
    preview.warnings.append('Domänen, AEs, Netze, FEs und systemdefinierende Bauteile werden als prüfbare Änderungen angeboten. Bitte den KiCad-ERC zusätzlich ausführen.')
    return preview


def apply_project_changes(package, preview):
    if not preview.can_apply: raise ValueError('Offene Konflikte zuerst lösen')
    state=_state(package)
    collections={'function_element':'function_elements','component':'components','realization':'technical_realizations','technical_source':'technical_sources'}
    for kind,collection in collections.items():state[kind]={o.id:o.model_dump(mode='json') for o in getattr(package,collection)}
    for change in preview.changes:
        if change.field=='project.net_classes':
            state['net_classes']=deepcopy(change.after);continue
        if change.field.endswith('Object'):
            kind=change.field[:-6]
            if change.after is None: state[kind].pop(change.object_id,None)
            else: state[kind][change.object_id]=deepcopy(change.after)
        else:
            kind,field=change.field.split('.',1)
            if change.object_id not in state[kind]: raise ValueError('Architekturobjekt fehlt')
            state[kind][change.object_id][field]=deepcopy(change.after)
    candidate=deepcopy(package)
    from .models import FunctionElement,DesignComponent,TechnicalRealization,TechnicalSource
    classes={'function_element':FunctionElement,'component':DesignComponent,'realization':TechnicalRealization,'technical_source':TechnicalSource}
    for kind,collection in collections.items():setattr(candidate,collection,[classes[kind].model_validate(v) for v in state[kind].values()])
    from .netclasses import NetClassDefinition
    candidate.net_classes=[NetClassDefinition.model_validate(v) for v in state.get('net_classes',[])]
    candidate.domains=[]
    for data in state['domain'].values():
        candidate.domains.append(Domain.model_validate({**data,'elements':[]}))
    by_domain={d.id:d for d in candidate.domains}
    for data in state['element'].values():
        data=deepcopy(data); parent=data.pop('domain_id')
        if parent not in by_domain: raise ValueError('Übernahme führt zu einem AE ohne Domäne')
        by_domain[parent].elements.append(ArchitectureElement.model_validate(data))
    candidate.signals=[ArchitectureSignal.model_validate(s) for s in state['signal'].values()]
    element_ids={e.id for d in candidate.domains for e in d.elements}
    port_ids={p.id for d in candidate.domains for e in d.elements for p in e.ports}
    candidate.connections=[c for c in candidate.connections if c.signal_id in state['signal']
        or (not c.signal_id and all(e.element_id in element_ids and e.port_id in port_ids for e in c.endpoints))]
    for signal in candidate.signals:
        synchronize_signal_topology(candidate,signal)
    # ECAD can only change realization values, never engineering requirements.
    from .architecture_editing import find_architecture_object
    originals = [*package.domains, *package.signals, *package.connections,
                 *(e for d in package.domains for e in d.elements),
                 *(p for d in package.domains for e in d.elements for p in e.ports),
                 *(m for signal in package.signals for m in signal.bus_contents)]
    for original in originals:
        target = find_architecture_object(candidate, original.id)
        if target is not None and hasattr(target, 'requirement_attributes'):
            target.requirement_attributes = deepcopy(original.requirement_attributes)
    # Deleted HW objects leave explicit missing architecture allocations; existing
    # realization/deployment references must no longer point at removed AEs.
    for realization in candidate.technical_realizations:
        if realization.architecture_element_id and realization.architecture_element_id not in element_ids:
            realization.architecture_element_id = None
    for fe in candidate.function_elements:
        if fe.architecture_element_id and fe.architecture_element_id not in element_ids:fe.architecture_element_id=None
        fe.interface_signal_ids=[i for i in fe.interface_signal_ids if i in state['signal']]
        fe.dependency_ids=[i for i in fe.dependency_ids if i in {f.id for f in candidate.function_elements}]
    for component in candidate.software_components:
        if component.deployment_element_id and component.deployment_element_id not in element_ids:
            component.deployment_element_id = None
    for constraint in candidate.mechanical_constraints:
        if constraint.architecture_element_id and constraint.architecture_element_id not in element_ids:
            constraint.architecture_element_id = None
    from .deletion import _remove_traceability_targets
    before_ids = {o.id for o in originals}
    after_ids = {d.id for d in candidate.domains} | element_ids | port_ids | {s.id for s in candidate.signals} | {c.id for c in candidate.connections} | {m.id for s in candidate.signals for m in s.bus_contents}
    _remove_traceability_targets(candidate, before_ids - after_ids)
    for realization in candidate.technical_realizations:
        for variant in realization.variants:
            variant.architecture_element_ids = [oid for oid in variant.architecture_element_ids if oid in element_ids]
    candidate=ArchitecturePackage.model_validate(candidate.export_dict())
    binding=candidate.properties.setdefault('ecadConnectors',{}).setdefault('kicad',{})
    binding['linkedState'] = _state(candidate)
    binding['functionalBaseline']={kind:{o.id:o.model_dump(mode='json') for o in getattr(candidate,collection)} for kind,collection in collections.items()}
    if hasattr(preview,'functional_observations'):
        source_baseline=deepcopy(package.properties.get('ecadConnectors',{}).get('kicad',{}).get('functionalSourceBaseline',{}))
        for kind,collection in collections.items():
            group=source_baseline.setdefault(kind,{})
            current_objects={o.id:o.model_dump(mode='json') for o in getattr(candidate,collection)}
            observed=preview.functional_observations.get(kind,{})
            selected_ids={c.object_id for c in preview.changes if c.field==kind+'Object'}
            for oid in selected_ids:
                if oid in current_objects and oid in observed:group[oid]=deepcopy(observed[oid])
                else:group.pop(oid,None)
            for oid,data in observed.items():
                if current_objects.get(oid)==data:group[oid]=deepcopy(data)
        binding['functionalSourceBaseline']=source_baseline
    binding['netSettingsBaseline']=deepcopy(getattr(preview,'net_settings',{}))
    binding['backwardBaseline']={'root':preview.back_annotation_root, 'exportKey': preview.back_annotation_export_key, 'labels': preview.back_annotation_labels,
                                 'state':_state(candidate)}
    if getattr(preview,'project_path',None): binding['projectPath']=preview.project_path
    if getattr(preview,'native_source',None): binding['nativeImport']=deepcopy(preview.native_source)
    return candidate
