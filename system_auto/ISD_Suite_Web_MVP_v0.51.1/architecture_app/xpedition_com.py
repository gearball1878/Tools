"""Local Windows COM backend, using signatures from the supplied viewdraw.tlb wrapper.

No generated/version-pinned wrapper and no legacy scripts are imported. All COM
objects live inside the calling thread's STA. Exceptions propagate with context.
"""
from __future__ import annotations
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone
from zipfile import ZipFile, ZIP_DEFLATED

from .models import Domain, ArchitectureElement, InterfacePort, ArchitectureSignal, Signal, SignalEndpoint, FunctionElement, ConnectionType
from .hardware_topology import is_global_ground
from .ecad_pin_mapping import hierarchical_mapping
from .xpedition_exchange import state, package_from_state, fingerprint, binding

# Enum values confirmed in the user's generated ViewDraw type-library wrapper.
SHORT_NAME, FULL_PATH_NAME, VDM_PIN, VDDT_SCHEMATIC = 1, 0, 512, 0
VD_WIRE, VD_BUS, VDINVISIBLE = 0, 1, 0


def value(obj, name):
    item = getattr(obj, name)
    return item() if callable(item) else item


def collection(obj):
    return list(obj)


def attr(obj, key, default=''):
    item = obj.FindAttribute(key)
    return str(item.Value) if item is not None else default


def metadata(obj):
    text = attr(obj, 'ISD_SPOT')
    if not text: return {}
    try:
        result = json.loads(text)
        if not isinstance(result, dict): raise ValueError('Objektmetadaten sind kein Dictionary')
        return result
    except (ValueError, TypeError) as error:
        raise ValueError('Ungültige SPOT-Metadaten in Xpedition: '+str(error)) from error


def set_attr(obj, key, text, segment=None):
    text = str(text)
    existing = obj.FindAttribute(key)
    if existing is not None: existing.Value = text
    elif segment is None: obj.AddAttribute(key+'='+text, 0, 0, VDINVISIBLE)
    else: obj.AddAttribute(segment, key+'='+text, 0, 0, VDINVISIBLE)
    if attr(obj, key) != text: raise RuntimeError('COM-Attribut konnte nicht bestätigt werden: '+key)


def native_id(project, kind, uid, instance=''):
    return sha256(('isd/xpedition/'+str(Path(project).resolve()).casefold()+'/'+kind+'/'+uid+'/'+instance).encode()).hexdigest()


def project_file(path):
    file = Path(path).expanduser().resolve()
    if file.suffix.lower() != '.prj' or not file.is_file():
        raise ValueError('Eine vorhandene Xpedition-Projektdatei (.prj) auswählen.')
    return file


class XpeditionCOM:
    def __init__(self, progid='ViewDraw.Application', app_factory=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', progid): raise ValueError('Ungültige COM-ProgID')
        self.progid = progid
        self.app_factory = app_factory

    @contextmanager
    def session(self):
        if self.app_factory is not None:
            yield self.app_factory(); return
        if os.name != 'nt':
            raise RuntimeError('Xpedition COM benötigt Windows am ECAD-Arbeitsplatz. Den SPOT-Bridge-Aufruf dort ausführen.')
        try:
            import pythoncom
            from win32com.client import gencache
        except ImportError as error:
            raise RuntimeError('COM-Abhängigkeit fehlt: python -m pip install pywin32') from error
        pythoncom.CoInitialize()
        try:
            # Generate bindings from the locally installed version's type library.
            app = gencache.EnsureDispatch(self.progid)
            yield app
        except Exception as error:
            raise RuntimeError('Xpedition COM: '+str(error)) from error
        finally:
            pythoncom.CoUninitialize()

    def _open(self, app, path):
        file = project_file(path)
        if app.IsProjectOpened():
            opened = Path(app.GetProjectData().GetProjectFilePath()).resolve()
            if str(opened).casefold() != str(file).casefold():
                raise ValueError('Ein anderes Xpedition-Projekt ist geöffnet. Speichern und schließen: '+str(opened))
        elif app.OpenProject(str(file)) is False:
            raise RuntimeError('OpenProject hat das Projekt nicht geöffnet.')
        if not app.IsProjectOpened(): raise RuntimeError('Projekt ist nach OpenProject nicht geöffnet.')
        actual = Path(app.GetProjectData().GetProjectFilePath()).resolve()
        if str(actual).casefold() != str(file).casefold(): raise RuntimeError('COM meldet eine andere Projektdatei.')
        return file

    def diagnose(self, path=''):
        report = {'progid': self.progid, 'platform': os.name, 'checks': [], 'nativeTest': True}
        try:
            with self.session() as app:
                report['version'] = str(app.Version)
                for method in ('OpenProject', 'NewProject', 'DesignComponents', 'DesignNets', 'PushPath', 'SchematicSheetDocuments', 'GetProjectData'):
                    report['checks'].append({'name': method, 'ok': callable(getattr(app, method, None))})
                if path:
                    file = self._open(app, path)
                    data = app.GetProjectData()
                    root = self._root(app)
                    report.update(projectPath=str(file), rootBlock=str(root),
                        components=len(collection(app.DesignComponents('', root, '-1', 'STD', True))),
                        nets=len(collection(app.DesignNets('', root, '-1', 'STD', True))),
                        busContentsFile=str(data.GetBusContentsFilePath(True)))
                    report['checks'].append({'name':'Projekt auslesen', 'ok':True})
                report['constraintManager'] = 'Nicht verifiziert: Net Class-Attribut ist kein Nachweis einer CM-Klassenzuordnung.'
        except Exception as error:
            report['checks'].append({'name': 'COM-Verbindung / Projektzugriff', 'ok': False, 'error': str(error)})
        report['ok'] = bool(report['checks']) and all(c['ok'] for c in report['checks'])
        return report

    def create_project(self, parent, name, library='', template='', server=''):
        if not re.fullmatch(r'[\w .-]{1,80}', name) or name.strip() != name or name in {'.','..'}:
            raise ValueError('Projektname: 1–80 Buchstaben, Ziffern, Leerzeichen, Punkt, Bindestrich oder Unterstrich.')
        parent = Path(parent).expanduser().resolve()
        if not parent.is_dir(): raise ValueError('Zielordner existiert nicht.')
        target = parent/name
        if target.exists(): raise ValueError('Projektordner existiert bereits: '+str(target))
        for label, path in [('Zentralbibliothek', library), ('Projektvorlage', template)]:
            if path and not Path(path).exists(): raise ValueError(label+' nicht gefunden: '+path)
        with self.session() as app:
            if app.IsProjectOpened(): raise ValueError('Vor Projektanlage das geöffnete Xpedition-Projekt speichern und schließen.')
            target.mkdir()
            requested = target/(name+'.prj')
            try:
                if app.NewProject(str(requested), library, server, template) is False:
                    raise RuntimeError('NewProject meldet einen Fehler. Bibliothek und Vorlage prüfen.')
                if not app.IsProjectOpened(): raise RuntimeError('NewProject hat kein Projekt geöffnet.')
                actual = Path(app.GetProjectData().GetProjectFilePath()).resolve()
                if actual.parent != target or not actual.is_file():
                    raise RuntimeError('Projektanlage nicht bestätigt: '+str(actual))
                data=app.GetProjectData()
                if not collection(data.GetiCDBDesigns()):
                    if data.AddiCDBDesign(name) is False or not collection(data.GetiCDBDesigns()):
                        raise RuntimeError('Kein iCDB-Design angelegt. Eine passende Projektvorlage auswählen.')
                return str(actual)
            except Exception as error:
                # Do not erase a partially created project, library or native error evidence.
                raise RuntimeError('Projektanlage fehlgeschlagen. Teilstand unter '+str(target)+': '+str(error)) from error

    @staticmethod
    def _root(app):
        data=app.GetProjectData()
        designs=collection(data.GetiCDBDesigns())
        if not designs:raise ValueError('Projekt enthält kein iCDB-Design. Projektvorlage / Designanlage prüfen.')
        active=app.GetActiveDesign()
        if active not in designs:active=designs[0]
        root=data.GetiCDBDesignRootBlock(active)
        if not root:raise ValueError('Kein Rootblock im Xpedition-Projekt.')
        return root

    def _identity(self, obj, project, kind, instance, prior):
        uid = str(obj.UID)
        explicit = attr(obj, 'ISD_ID')
        if explicit:
            if not re.fullmatch(r'[0-9a-f]{64}', explicit): raise ValueError('ISD_ID ist keine gültige SHA-256-Identität: '+explicit)
            return explicit
        for oid, native in prior.items():
            if native.get('uid') == uid and native.get('instance') == instance: return oid
        return native_id(project, kind, uid, instance)

    def _pins(self, app, component):
        name = component.SymbolBlock.GetName(SHORT_NAME)
        document = app.SchematicSheetDocuments().OpenSymbol(name, '1')
        views = collection(document.GetViews())
        if not views: raise RuntimeError('Keine Symbolansicht für '+name)
        views[0].Activate()
        return collection(views[0].Query(VDM_PIN, 0))

    def read_project(self, package, path):
        with self.session() as app:
            file = self._open(app, path)
            return self._read(app, package, file)

    def _read(self, app, package, file):
        data = app.GetProjectData(); root = self._root(app)
        prior = binding(package).get('nativeBindings', {})
        rows = {k:{} for k in state(package)}; native = {}; objects = {}
        components = collection(app.DesignComponents('', root, '-1', 'STD', True))
        available = set(collection(app.SchematicSheetDocuments().GetAvailableSchematics()))
        hierarchy = []
        for comp in components:
            symbol = comp.SymbolBlock
            if symbol.GetName(SHORT_NAME) not in available and not symbol.IsFub: continue
            instance = comp.GetName(FULL_PATH_NAME)
            kind = attr(comp, 'ISD_KIND')
            if kind == 'system': continue
            depth = instance.count('\\')
            if kind not in ('domain','element','function_element'):
                kind = 'domain' if depth == 0 else 'element' if depth == 1 else 'function_element'
            hierarchy.append((depth, instance, kind, comp))
        paths = {}
        for _, instance, kind, comp in sorted(hierarchy, key=lambda v: (v[0],v[1])):
            oid = self._identity(comp,file,kind,instance,prior)
            if oid in native: raise ValueError('Mehrfach verwendete ISD_ID in Hierarchieinstanzen: '+oid)
            paths[instance] = oid
            native[oid] = {'uid':str(comp.UID),'instance':instance,'kind':kind}
            objects[oid] = comp
            name = comp.GetName(SHORT_NAME)
            row = metadata(comp)
            row.update(id=oid, name=name)
            parent_path = instance.rsplit('\\',1)[0] if '\\' in instance else ''
            parent = paths.get(parent_path)
            if kind == 'domain':
                rows[kind][oid] = {**Domain(name=name).model_dump(mode='json',exclude={'elements'}), **row}
            elif kind == 'element':
                if parent not in rows['domain']: raise ValueError('AE-Hierarchie nicht eindeutig. ISD_KIND und Elternzuordnung prüfen: '+instance)
                rows[kind][oid] = {**ArchitectureElement(name=name).model_dump(mode='json',exclude={'ports'}), **row, 'parent_id': parent}
                for pin in self._pins(app, comp):
                    pid = self._identity(pin,file,'port',instance,prior)
                    native[pid] = {'uid':str(pin.UID),'instance':instance,'kind':'port','owner':oid}
                    objects[pid] = pin
                    prow = {**InterfacePort(name=pin.GetName(SHORT_NAME)).model_dump(mode='json'), **metadata(pin)}
                    prow.update(id=pid, name=pin.GetName(SHORT_NAME), parent_id=oid)
                    role = attr(pin,'ISD_ROLE')
                    if role: prow['role'] = role
                    rows['port'][pid] = prow
            else:
                # Nested function blocks retain the owning architecture element.
                owner_path = parent_path
                while owner_path and paths.get(owner_path) not in rows['element']:
                    owner_path = owner_path.rsplit('\\',1)[0] if '\\' in owner_path else ''
                owner = paths.get(owner_path)
                if owner not in rows['element']: raise ValueError('Funktionsblock ohne AE-Zuordnung: '+instance)
                frow = FunctionElement(name=name, architecture_element_id=owner).model_dump(mode='json')
                frow.update(row)
                frow.update(architecture_element_id=owner, source_block_uuid=str(comp.UID), source_project=str(file), source_sheet=instance)
                rows[kind][oid] = frow
        # Connections are observed separately from the complete pin inventory.
        pin_lookup = {(n['owner'], n['uid']):oid for oid,n in native.items() if n['kind']=='port'}
        nets = {}; endpoints = {}
        for eid, comp in objects.copy().items():
            if eid not in rows['element']: continue
            for conn in collection(value(comp,'GetConnections')):
                pin = conn.CompPin.Pin
                pid = pin_lookup.get((eid,str(pin.UID)))
                if not pid: raise ValueError('Verbundener Pin fehlt im Symbolinventar: '+str(pin.UID))
                segment = value(conn,'_GetSegment')
                if segment is None: continue
                net = segment.Parent
                sid = self._identity(net,file,'signal','',prior)
                nets[sid] = net
                entry=(eid,pid,net.GetConnectedNetName(segment))
                if entry not in endpoints.setdefault(sid,[]):endpoints[sid].append(entry)
        # Include managed nets with no AE connection, rather than silently deleting them.
        for net in collection(app.DesignNets('', root, '-1', 'STD', True)):
            if attr(net,'ISD_ID'):
                nets.setdefault(self._identity(net,file,'signal','',prior),net)
        for sid, net in nets.items():
            segments = collection(value(net,'GetSegments'))
            if not segments: raise ValueError('Netz ohne auslesbares Segment: '+str(net.UID))
            name = net.GetConnectedNetName(segments[0])
            is_bus = any(bool(s.IsBus) for s in segments)
            row = {**ArchitectureSignal(name=name).model_dump(mode='json'), **metadata(net)}
            row.update(id=sid,name=name,connection_type='Bus' if is_bus else 'Net')
            native[sid] = {'uid':str(net.UID),'instance':'','kind':'signal'}
            eps = endpoints.get(sid,[])
            if any(n != name for _,_,n in eps):raise ValueError('Widersprüchliche Netznamen für dieselbe ISD-ID: '+name)
            declared_endpoints={ep['element_id']:ep for ep in ([row['source']] if row.get('source') else [])+row.get('sinks',[])}
            def endpoint(eid,pid):
                return {**SignalEndpoint(element_id=eid,port_id=pid).model_dump(mode='json'),**declared_endpoints.get(eid,{}),'element_id':eid,'port_id':pid}
            hosts = [endpoint(eid,pid) for eid,pid,_ in eps if rows['port'][pid].get('role')=='Host']
            if len(hosts)>1: raise ValueError('Mehrere Hosts am Netz: '+name)
            global_ground=bool(attr(net,'ISD_GLOBAL')) and is_global_ground(ArchitectureSignal.model_validate(row))
            declared_source=row.get('source');declared_sinks=row.get('sinks',[])
            row['source'] = hosts[0] if hosts else None
            row['sinks'] = [endpoint(eid,pid) for eid,pid,_ in eps if not hosts or pid != hosts[0]['port_id']]
            if global_ground:row.update(source=declared_source,sinks=declared_sinks)
            for eid,pid,_ in eps:
                rows['port'][pid].update(name=name, interface_link_id=sid, connection_type=row['connection_type'])
            if is_bus:
                names = [str(n) for n in collection(net.GetSignals())]
                if not names: raise ValueError('Businhalt nicht auslesbar: '+name+'. Buscontent im Projekt prüfen.')
                old_members = {m['name']:m for m in row.get('bus_contents',[])}
                row['bus_contents'] = [old_members.get(n) or Signal(id=native_id(file,'member',str(net.UID),n),name=n).model_dump(mode='json') for n in names]
            requested = attr(net,'ISD_NETCLASS')
            if requested: row.setdefault('realization_attributes',{})['netClass'] = requested
            rows['signal'][sid] = row
        connected_pids={pid for eps in endpoints.values() for _,pid,_ in eps}
        for pid,prow in rows['port'].items():
            if pid not in connected_pids:
                prow['interface_link_id']=None
                for key in ('architectureSignalId','generatedBy','topologyRole'):prow.setdefault('properties',{}).pop(key,None)
        result = package_from_state(package,rows)
        result.properties.setdefault('ecadConnectors',{})['xpedition'] = {**binding(package),'projectPath':str(file),'nativeBindings':native}
        return result

    def _save(self, app):
        docs = value(app,'Documents')
        if docs.SaveAll() is False: raise RuntimeError('SaveAll meldet einen Fehler.')

    def _view(self, app, root, instance):
        if app.PushPath(root,instance,'1') is False: raise RuntimeError('PushPath fehlgeschlagen: '+instance)
        return app.ActiveView.Block

    def _stamp(self,obj,kind,row,segment=None):
        for key,text in [('ISD_ID',row['id']),('ISD_KIND',kind),('ISD_SPOT',json.dumps(row,ensure_ascii=False,separators=(',',':')))]:
            set_attr(obj,key,text,segment)

    def _backup(self, file):
        folder = file.parent
        target = folder.parent/(folder.name+'_ISD_backup_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.zip')
        with ZipFile(target,'x',ZIP_DEFLATED) as archive:
            for item in sorted(folder.rglob('*')):
                if item.is_file(): archive.write(item,item.relative_to(folder))
        return str(target)

    def apply(self, package, path, rows, expected_hash):
        with self.session() as app:
            file = self._open(app,path)
            if app.IsReadOnlyMode(): raise ValueError('Xpedition-Projekt ist schreibgeschützt.')
            observed = self._read(app,package,file)
            if fingerprint(state(observed)) != expected_hash: raise ValueError('Xpedition wurde seit der Vorschau geändert. Erneut prüfen.')
            before = state(observed)
            # Capability boundaries are checked before the first write.
            for kind in before:
                if before[kind].keys() - rows[kind].keys():
                    raise ValueError('Native Löschung ist noch nicht freigegeben. Änderung auslassen und gezielt in Xpedition löschen.')
            for oid,row in rows['element'].items():
                if oid in before['element'] and row['parent_id'] != before['element'][oid]['parent_id']:
                    raise ValueError('Verschieben eines bestehenden AE zwischen Domänen benötigt eine native Zuordnungsprüfung.')
            for oid,row in rows['signal'].items():
                old = before['signal'].get(oid)
                if old and any(old.get(k)!=row.get(k) for k in ('source','sinks','connection_type')):
                    raise ValueError('Bestehende Netztopologie in Xpedition ändern und zurückannotieren; native Neuverdrahtung noch nicht freigegeben.')
            self._save(app)
            backup = self._backup(file)
            try:
                self._write(app,observed,file,rows)
                self._save(app)
                reread = self._read(app,package,file)
                actual = state(reread)
                # Verify requested object identity and names against live COM data.
                for kind in rows:
                    for oid,row in rows[kind].items():
                        if actual[kind].get(oid) != row:
                            differences=[k for k in row if actual[kind].get(oid,{}).get(k)!=row[k]]
                            raise RuntimeError('COM-Rücklesen bestätigt Objekt nicht vollständig: '+row['name']+' · '+', '.join(differences))
                (file.parent/'ISD_SPOT.json').write_text(package_from_state(package,rows).model_dump_json(by_alias=True,indent=2),encoding='utf-8')
                return reread, backup
            except Exception as error:
                raise RuntimeError('COM-Übernahme fehlgeschlagen; keine erfolgreiche Annotation gespeichert. Sicherung: '+backup+' · '+str(error)) from error

    def _write(self,app,observed,file,rows):
        root = self._root(app)
        native = binding(observed).get('nativeBindings',{})
        comps = collection(app.DesignComponents('',root,'-1','STD',True))
        by_uid = {str(c.UID):c for c in comps}
        objects = {}; paths = {}
        for kind in ('domain','element','function_element'):
            for index,(oid,row) in enumerate(rows[kind].items()):
                parent = row.get('parent_id') if kind=='element' else row.get('architecture_element_id') if kind=='function_element' else None
                parent_path = paths.get(parent,'')
                comp = by_uid.get(native.get(oid,{}).get('uid'))
                if comp is None:
                    block = self._view(app,root,parent_path)
                    comp = block.AddFub(row['name'],100+(index%3)*700,150+(index//3)*1000,600+(index%3)*700,850+(index//3)*1000)
                    if comp is None: raise RuntimeError('AddFub hat keinen Block erzeugt: '+row['name'])
                elif comp.GetName(SHORT_NAME) != row['name']:
                    # Visible component label, not its stable native UID, is renamed.
                    comp.Label.TextString = row['name']
                self._stamp(comp,kind,row)
                objects[oid] = comp
                paths[oid] = comp.GetName(FULL_PATH_NAME)
                self._view(app,root,paths[oid])
        pin_objects = {}
        for eid,erow in rows['element'].items():
            comp = objects[eid]
            document = app.SchematicSheetDocuments().OpenSymbol(comp.SymbolBlock.GetName(SHORT_NAME),'1')
            view = collection(document.GetViews())[0]; view.Activate()
            pins = {attr(p,'ISD_ID'):p for p in collection(view.Query(VDM_PIN,0)) if attr(p,'ISD_ID')}
            owned = [r for r in rows['port'].values() if r['parent_id']==eid]
            for index,row in enumerate(owned):
                pin = pins.get(row['id'])
                new_pin=pin is None
                host = row.get('role')=='Host'
                x = 500 if host else 0; y = 650-index*20
                if pin is None:
                    pin = view.Block.AddPin(x,y)
                    if pin is None: raise RuntimeError('AddPin fehlgeschlagen: '+row['name'])
                    pin.AddLabel(row['name'],x+(-20 if host else 20),y)
                else: pin.Label.TextString = row['name']
                if new_pin or attr(pin,'ISD_ROLE')!=row.get('role',''):pin.SetLocation(x+(-10 if host else 10),y,x,y)
                signal=next((s for s in observed.signals if s.id==row.get('interface_link_id')),None)
                # New signals may only exist in the desired projection.
                if signal is None and row.get('interface_link_id') in rows['signal']:signal=ArchitectureSignal.model_validate(rows['signal'][row['interface_link_id']])
                set_attr(pin,'Pin Type',self._pin_type(observed,signal,row.get('role','')))
                set_attr(pin,'ISD_ROLE',row.get('role',''))
                self._stamp(pin,'port',row); pin_objects[row['id']]=pin
            document.Save()
        # Domain pins aggregate roles: at least one internal host wins.
        for did in rows['domain']:
            comp = objects[did]
            doc = app.SchematicSheetDocuments().OpenSymbol(comp.SymbolBlock.GetName(SHORT_NAME),'1')
            view = collection(doc.GetViews())[0];view.Activate()
            existing = {attr(p,'ISD_SIGNAL_ID'):p for p in collection(view.Query(VDM_PIN,0)) if attr(p,'ISD_SIGNAL_ID')}
            grouped = {}
            for pid,p in rows['port'].items():
                if rows['element'][p['parent_id']]['parent_id']==did and p.get('interface_link_id'):
                    grouped.setdefault(p['interface_link_id'],[]).append(p)
            for index,(sid,ports) in enumerate(grouped.items()):
                signal = rows['signal'].get(sid)
                if not signal: continue
                host = any(p.get('role')=='Host' for p in ports)
                x,y = (500 if host else 0),650-index*20
                pin = existing.get(sid)
                new_pin=pin is None
                if pin is None:
                    pin = view.Block.AddPin(x,y);pin.AddLabel(signal['name'],x+(-20 if host else 20),y)
                else:pin.Label.TextString=signal['name']
                if new_pin or attr(pin,'ISD_ROLE')!=('Host' if host else 'Participant'):pin.SetLocation(x+(-10 if host else 10),y,x,y)
                set_attr(pin,'ISD_SIGNAL_ID',sid);set_attr(pin,'ISD_ROLE','Host' if host else 'Participant')
            doc.Save()
        # Bus members are materialized into the real project buscontents file.
        self._buscontents(app,rows)
        # Keep connector labels synchronized with their attached architecture signal.
        for comp in collection(app.DesignComponents('',root,'-1','STD',True)):
            sid=attr(comp,'ISD_SIGNAL_ID')
            if sid in rows['signal']:comp.Label.TextString=rows['signal'][sid]['name']
        existing_nets = {}
        for net in collection(app.DesignNets('',root,'-1','STD',True)):
            if attr(net,'ISD_ID'):existing_nets.setdefault(attr(net,'ISD_ID'),[]).append(net)
        for sid,row in rows['signal'].items():
            if sid in existing_nets:
                for net in existing_nets[sid]:
                    segments = collection(value(net,'GetSegments'))
                    for seg in segments:
                        # Updating attached labels must preserve geometry.
                        label=net.GetLabel(seg)
                        if label is not None:label.TextString=row['name']
                        else:net.AddLabel(seg,row['name'],0,0)
                    self._stamp(net,'signal',row,segments[0])
                    set_attr(net,'ISD_NETCLASS',self._netclass(row),segments[0])
                continue
            if is_global_ground(ArchitectureSignal.model_validate(row)):
                endpoints=([row['source']] if row.get('source') else [])+row.get('sinks',[])
                for index,ep in enumerate(endpoints):
                    eid=ep['element_id']
                    block=self._view(app,root,paths[eid])
                    y=100+index*40
                    symbol=block.AddSymbolInstance('Globals','power_in',100,y)
                    set_attr(symbol,'Global Signal Name',row['name'])
                    net=self._stub(block,100,y,180,row)
                    set_attr(net,'ISD_GLOBAL','true',collection(value(net,'GetSegments'))[0])
                if not endpoints:
                    net=self._stub(self._view(app,root,''),100,100,180,row)
                    set_attr(net,'ISD_GLOBAL','true',collection(value(net,'GetSegments'))[0])
                continue
            # Named stubs connect AE pins to domain hierarchy connectors.
            endpoints=([row['source']] if row.get('source') else [])+row.get('sinks',[])
            domain_roles={}
            for ep in endpoints:
                eid,pid=ep['element_id'],ep.get('port_id')
                if eid not in objects or pid not in pin_objects: raise ValueError('Netzendpunkt ohne zugeordneten Architekturport: '+row['name'])
                parent=rows['element'][eid]['parent_id']
                host=rows['port'][pid].get('role')=='Host'
                domain_roles[parent]=domain_roles.get(parent,False) or host
                block=self._view(app,root,paths[parent]);comp=objects[eid];pin=pin_objects[pid]
                loc=value(comp,'GetLocation');ploc=pin.GetLocation(1)
                x,y=loc.X+ploc.X,loc.Y+ploc.Y
                self._stub(block,x,y,180 if host else -180,row,hierarchical=True,host=host)
                # AE implementation sheet exposes the same boundary name.
                child=self._view(app,root,paths[eid])
                self._hierarchical_stub(child,100 if not host else 1600,200+list(rows['signal']).index(sid)*40,row,host)
            for did,host in domain_roles.items():
                comp=objects[did]
                document=app.SchematicSheetDocuments().OpenSymbol(comp.SymbolBlock.GetName(SHORT_NAME),'1')
                view=collection(document.GetViews())[0];view.Activate()
                pin=next(p for p in collection(view.Query(VDM_PIN,0)) if attr(p,'ISD_SIGNAL_ID')==sid)
                ploc=pin.GetLocation(1);loc=value(comp,'GetLocation')
                block=self._view(app,root,'')
                self._stub(block,loc.X+ploc.X,loc.Y+ploc.Y,180 if host else -180,row)
            if not endpoints:
                block=self._view(app,root,'')
                self._stub(block,100,100+list(rows['signal']).index(sid)*40,180,row)
        # Native Constraint Manager API is deliberately not invented: explicit pending status.

    @staticmethod
    def _pin_type(package,signal,role):
        if signal is not None and signal.connection_type==ConnectionType.BUS:
            return 'OUT' if role=='Host' else 'IN' if role=='Participant' else 'TERMINAL'
        if signal is not None and signal.signal_type.value=='Analog':return 'ANALOG'
        if signal is None or not role:return 'TERMINAL'
        direction,_=hierarchical_mapping(package,signal,role)
        return {'input':'IN','output':'OUT','bidirectional':'BI'}.get(direction,'TERMINAL')

    def _stub(self,block,x,y,length,row,hierarchical=False,host=False):
        bus=VD_BUS if row['connection_type']=='Bus' else VD_WIRE
        net=block.AddNet(x,y,x+length,y,None,None,bus)
        seg=collection(value(net,'GetSegments'))[0]
        net.AddLabel(seg,row['name'],x+length,y)
        self._stamp(net,'signal',row,seg);set_attr(net,'ISD_NETCLASS',self._netclass(row),seg)
        block.AddNet(x,y,x+(10 if length>0 else -10),y,None,None,bus)
        if hierarchical:
            connector=block.AddSymbolInstance('builtin','con_hier_o' if host else 'con_hier_i',x+length,y)
            connector.AddLabel(row['name'],x+length,y)
            set_attr(connector,'ISD_SIGNAL_ID',row['id'])
        return net

    def _hierarchical_stub(self,block,x,y,row,host):
        connector=block.AddSymbolInstance('builtin','con_hier_o' if host else 'con_hier_i',x,y)
        connector.AddLabel(row['name'],x,y)
        set_attr(connector,'ISD_SIGNAL_ID',row['id'])
        self._stub(block,x,y,-180 if host else 180,row)

    @staticmethod
    def _netclass(row):
        return str(row.get('realization_attributes',{}).get('netClass') or row.get('requirement_attributes',{}).get('netClass') or row.get('attributes',{}).get('netClass') or '')

    def _buscontents(self,app,rows):
        data=app.GetProjectData(); file=Path(data.GetBusContentsFilePath(True))
        buses={r['name']:[m['name'] for m in r.get('bus_contents',[])] for r in rows['signal'].values() if r['connection_type']=='Bus'}
        if not buses:return
        if any(not names for names in buses.values()):raise ValueError('Bus ohne Mitglieder darf nicht übertragen werden.')
        original=file.read_text(encoding='utf-8-sig') if file.exists() else ''
        kept=[line for line in original.splitlines() if not line.strip() or line.strip().split()[0] not in buses]
        text='\n'.join(kept+[name+' '+','.join(members) for name,members in buses.items()])+'\n'
        file.parent.mkdir(parents=True,exist_ok=True);file.write_text(text,encoding='utf-8')
        data.SetBusContentsFilePath(str(file)); app.SaveIni()
