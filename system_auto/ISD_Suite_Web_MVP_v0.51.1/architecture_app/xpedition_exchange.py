"""SPOT projection and three-way reviews. No Xpedition-specific public JSON model."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json
from .ecad_connector import AnnotationChange, AnnotationPreview
from .models import ArchitecturePackage, Domain, ArchitectureElement, InterfacePort, ArchitectureSignal, FunctionElement
from .topology import synchronize_signal_topology
from .hardware_topology import is_global_ground, block_port_visible

KINDS = ('domain', 'element', 'port', 'signal', 'function_element')


def fingerprint(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def binding(package):
    return package.properties.get('ecadConnectors', {}).get('xpedition', {})


def state(package):
    result = {kind: {} for kind in KINDS}
    def dump(obj, excluded=()):
        excluded=set(excluded)
        if isinstance(obj,FunctionElement):excluded.update({'source_block_uuid','source_project','source_sheet','source_revision'})
        row = obj.model_dump(mode='json', exclude=excluded)
        # Transport observations must never masquerade as architecture changes.
        row['properties'] = {k: v for k, v in row.get('properties', {}).items() if k not in {'xpeditionNative','portSignalsMaterialized','portNamingRule'}}
        if isinstance(obj,InterfacePort):
            row['interface_link_id'] = obj.interface_link_id or obj.properties.get('architectureSignalId')
        return row
    for domain in package.domains:
        result['domain'][domain.id] = dump(domain, ('elements',))
        for element in domain.elements:
            result['element'][element.id] = {**dump(element, ('ports',)), 'parent_id': domain.id}
            for port in element.ports:
                if not block_port_visible(package,port):continue
                result['port'][port.id] = {**dump(port), 'parent_id': element.id}
    for signal in package.signals:
        row=dump(signal)
        for ep in ([row['source']] if row.get('source') else [])+row.get('sinks',[]):
            if is_global_ground(signal):ep['port_id']=None
            else:
                matching=[p['id'] for p in result['port'].values() if p['parent_id']==ep['element_id'] and p.get('interface_link_id')==signal.id]
                if len(matching)==1:ep['port_id']=matching[0]
        row['sinks']=sorted(row.get('sinks',[]),key=lambda ep:(ep['element_id'],ep.get('port_id') or ''))
        result['signal'][signal.id] = row
    for fe in package.function_elements:
        if fe.discipline == 'hardware':
            result['function_element'][fe.id] = dump(fe)
    return result


def package_from_state(package, rows):
    candidate = deepcopy(package)
    candidate.domains = [Domain.model_validate(v) for v in rows['domain'].values()]
    domains = {d.id: d for d in candidate.domains}
    elements = {}
    for oid, row in rows['element'].items():
        parent = row.get('parent_id')
        if parent not in domains: raise ValueError('AE ohne gültige Domänenzuordnung: '+row['name'])
        element = ArchitectureElement.model_validate({k:v for k,v in row.items() if k != 'parent_id'})
        domains[parent].elements.append(element); elements[oid] = element
    for row in rows['port'].values():
        parent = row.get('parent_id')
        if parent not in elements: raise ValueError('Port ohne gültiges AE: '+row['name'])
        elements[parent].ports.append(InterfacePort.model_validate({k:v for k,v in row.items() if k != 'parent_id'}))
    candidate.signals = [ArchitectureSignal.model_validate(v) for v in rows['signal'].values()]
    old_fe={f.id:f for f in candidate.function_elements}
    candidate.function_elements = [f for f in candidate.function_elements if f.discipline != 'hardware'] + [FunctionElement.model_validate({**({k:getattr(old_fe[v['id']],k) for k in ('source_block_uuid','source_project','source_sheet','source_revision')} if v['id'] in old_fe else {}),**v}) for v in rows['function_element'].values()]
    # Remove stale generated connections, retain unrelated user connections.
    existing_ports = {p.id for e in elements.values() for p in e.ports}
    candidate.connections = [c for c in candidate.connections if not c.signal_id and all(ep.port_id in existing_ports for ep in c.endpoints)]
    for signal in candidate.signals:
        synchronize_signal_topology(candidate, signal)
    return ArchitecturePackage.model_validate(candidate.model_dump(mode='json', by_alias=True))


def compare(package, observed, direction, *, baseline=None):
    local = state(package); remote = state(observed)
    source, target = (local, remote) if direction == 'forward' else (remote, local)
    baseline = deepcopy(baseline if baseline is not None else binding(package).get('baseline', {}))
    preview = AnnotationPreview(direction)
    for kind in KINDS:
        for oid in sorted(source[kind].keys() | target[kind].keys() | baseline.get(kind, {}).keys()):
            wanted, current, old = source[kind].get(oid), target[kind].get(oid), baseline.get(kind, {}).get(oid)
            if wanted == current: continue
            if wanted is None or current is None:
                if wanted == old: continue
                status = 'conflict' if current != old and old is not None else 'ready'
                preview.changes.append(AnnotationChange(oid, kind+'Object', current, wanted, status,
                    (wanted or current or old).get('name', oid)))
                continue
            for field in sorted(wanted.keys() | current.keys()):
                before, after = current.get(field), wanted.get(field)
                if before == after or (old is not None and after == old.get(field)): continue
                status = 'conflict' if old is not None and before != old.get(field) else 'ready'
                preview.changes.append(AnnotationChange(oid, kind+'.'+field, before, after, status, wanted['name']))
    preview.xpedition_context = {'project_id': package.project.id, 'local_hash': fingerprint(local),
        'remote_hash': fingerprint(remote), 'remote': remote, 'baseline': baseline,
        'observed': observed.model_dump(mode='json', by_alias=True)}
    return preview


def selected_state(package, preview):
    context = preview.xpedition_context
    if package.project.id != context['project_id'] or fingerprint(state(package)) != context['local_hash']:
        raise ValueError('ISD-Projekt wurde seit der Vorschau geändert. Bitte erneut prüfen.')
    if not preview.can_apply: raise ValueError('Offene Konflikte oder nicht unterstützte Änderungen.')
    rows = deepcopy(context['remote'] if preview.direction == 'forward' else state(package))
    for change in preview.changes:
        if change.field.endswith('Object'):
            kind = change.field.removesuffix('Object')
            if change.after is None: rows[kind].pop(change.object_id, None)
            else: rows[kind][change.object_id] = deepcopy(change.after)
        else:
            kind, field = change.field.split('.', 1)
            if change.object_id not in rows[kind]: raise ValueError('Abhängige Objektanlage wurde ausgelassen.')
            rows[kind][change.object_id][field] = deepcopy(change.after)
    # Validate the entire result before any native mutation.
    return state(package_from_state(package, rows))


def advance_baseline(package, preview, rows, project_path, native=None):
    result = deepcopy(package)
    result.properties['activeEcadConnector']='xpedition'
    old = deepcopy(preview.xpedition_context['baseline'])
    local = state(result)
    # Advance only fields that actually agree; skipped conflicts remain detectable.
    for kind in KINDS:
        old.setdefault(kind, {})
        for oid in local[kind].keys() | rows[kind].keys() | old[kind].keys():
            a, b = local[kind].get(oid), rows[kind].get(oid)
            if a == b:
                if a is None: old[kind].pop(oid, None)
                else: old[kind][oid] = deepcopy(a)
            elif a is not None and b is not None:
                prior = old[kind].setdefault(oid, {})
                for key in a.keys() | b.keys():
                    if a.get(key) == b.get(key): prior[key] = deepcopy(a.get(key))
    result.properties.setdefault('ecadConnectors', {})['xpedition'] = {
        **binding(package), 'projectPath': str(project_path), 'baseline': old,
        'nativeBindings': deepcopy(native or binding(package).get('nativeBindings', {}))}
    return result
