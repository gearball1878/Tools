"""Explicit Xpedition annotations through SPOT JSON and a local COM backend."""
from __future__ import annotations
from copy import deepcopy
from io import BytesIO
import json
from zipfile import ZipFile, ZIP_DEFLATED
from .ecad_connector import AnnotationPreview, register
from .models import ArchitecturePackage
from .xpedition_com import XpeditionCOM
from .xpedition_exchange import state, compare, binding, selected_state, package_from_state, advance_baseline


class XpeditionConnector:
    name = 'xpedition'
    def __init__(self, backend=None): self.backend = backend or XpeditionCOM()

    def forward_preview(self, package):
        preview = AnnotationPreview('forward')
        preview.warnings = ['Xpedition COM am Windows-Arbeitsplatz erforderlich.',
            'Netzklassen werden als SPOT-Vorgabe am Netz transportiert. Die wirksame Constraint-Manager-Zuordnung ist noch nicht verifiziert.']
        return preview

    def forward_archive(self, package):
        buffer = BytesIO()
        with ZipFile(buffer,'w',ZIP_DEFLATED) as archive:
            archive.writestr('ISD_SPOT.json',package.model_dump_json(by_alias=True,indent=2))
            archive.writestr('README.txt', 'SPOT JSON für Xpedition. Kein fertiges ECAD-Projekt.\n'
                'Auf dem Windows-Arbeitsplatz mit der ISD Suite:\n'
                'python -m architecture_app.xpedition_cli diagnose --project "C:\\Projekt\\Projekt.prj" --output diagnose.json\n'
                'python -m architecture_app.xpedition_cli link --spot ISD_SPOT.json --project \"C:\\Projekt\\Projekt.prj\" --output ISD_SPOT_verknuepft.json\n'
                'python -m architecture_app.xpedition_cli preview --spot ISD_SPOT_verknuepft.json --project "C:\\Projekt\\Projekt.prj" --output review.json\n'
                'python -m architecture_app.xpedition_cli apply --spot ISD_SPOT_verknuepft.json --review review.json --output ISD_SPOT_bestaetigt.json\n'
                'python -m architecture_app.xpedition_cli read --spot ISD_SPOT_bestaetigt.json --project "C:\\Projekt\\Projekt.prj" --output ISD_SPOT_ruecklesen.json\n'
                'review.json ist nur eine Änderungsvorschau; die Projektdaten bleiben SPOT JSON.\n')
        return buffer.getvalue()

    def link_project(self, package, path):
        observed = self.backend.read_project(package,path)
        remote = state(observed)
        result = deepcopy(package)
        result.properties['activeEcadConnector']='xpedition'
        # No name-based silent pairing. Existing ISD IDs are recognized, otherwise review import first.
        local = state(package)
        common = any(local[k].keys() & remote[k].keys() for k in local)
        if any(remote[k] for k in remote) and any(local[k] for k in local) and not common:
            raise ValueError('Keine gemeinsamen ISD-IDs. Schaltplan zuerst zurücklesen und zuordnen; keine automatische Namensverknüpfung.')
        baseline = {k:{oid:row for oid,row in remote[k].items() if local[k].get(oid)==row} for k in remote}
        result.properties.setdefault('ecadConnectors',{})['xpedition'] = {
            'projectPath':str(path),'baseline':baseline,
            'nativeBindings':binding(observed).get('nativeBindings',{})}
        return result

    def forward_project_preview(self, package, path=''):
        path = path or binding(package).get('projectPath','')
        if not path: raise ValueError('Zuerst ein Xpedition-Projekt verknüpfen.')
        observed = self.backend.read_project(package,path)
        preview = compare(package,observed,'forward')
        preview.xpedition_context['project_path'] = str(path)
        preview.warnings = self.forward_preview(package).warnings
        for change in preview.changes:
            if change.after is None and change.field.endswith('Object'):
                change.status='unsupported';change.detail+=' · Native Löschung benötigt eine geprüfte Xpedition-Zuordnung.'
            kind,_,field=change.field.partition('.')
            if kind=='element' and field=='parent_id':
                change.status='unsupported';change.detail+=' · Native Hierarchieverschiebung noch nicht freigegeben.'
            if kind=='signal' and field in ('source','sinks','connection_type'):
                change.status='unsupported';change.detail+=' · Bestehende Netztopologie im ECAD bearbeiten und zurücklesen.'
        return preview

    def apply_forward(self, package, preview):
        if preview.direction!='forward': raise ValueError('Keine Forward-Vorschau.')
        rows = selected_state(package,preview)
        path = preview.xpedition_context['project_path']
        observed,backup = self.backend.apply(package,path,rows,preview.xpedition_context['remote_hash'])
        result = advance_baseline(package,preview,state(observed),path,binding(observed).get('nativeBindings'))
        result.properties['ecadConnectors']['xpedition']['lastForwardBackup']=backup
        result.properties['ecadConnectors']['xpedition']['constraintManagerStatus']='unverified'
        return result

    def backward_project_preview(self, package, path='', initial=False):
        if initial and (package.domains or package.signals): raise ValueError('Erstimport benötigt eine leere Hardwarearchitektur.')
        path = path or binding(package).get('projectPath','')
        observed = self.backend.read_project(package,path)
        preview = compare(package,observed,'backward',baseline={} if initial else None)
        preview.xpedition_context['project_path'] = str(path)
        self._protect_requirements(preview)
        preview.warnings = ['Unverbundene Ports bleiben erhalten. Funktionsblöcke werden als FE im Realisierungskontext geführt.',
            'Netzklassen sind übertragene Vorgaben; eine CM-Regelprüfung wurde nicht ausgeführt.']
        return preview

    def backward_preview(self, package, archive):
        try: document=json.loads(archive.decode('utf-8-sig'))
        except (UnicodeError,ValueError) as error: raise ValueError('Eine SPOT JSON aus dem COM-Rücklesen auswählen.') from error
        observed=ArchitecturePackage.model_validate(document)
        source=binding(observed)
        if not source.get('projectPath'):raise ValueError('SPOT enthält keine Xpedition-Projektverknüpfung.')
        oldpath=binding(package).get('projectPath')
        if oldpath and oldpath.casefold()!=source['projectPath'].casefold():
            raise ValueError('Rücklesen stammt aus einem anderen Projekt. Projekt ausdrücklich neu verknüpfen.')
        preview=compare(package,observed,'backward')
        preview.xpedition_context['project_path']=source['projectPath']
        self._protect_requirements(preview)
        return preview

    @staticmethod
    def _protect_requirements(preview):
        for change in preview.changes:
            field=change.field.partition('.')[2]
            if field in ('requirement_attributes','requirement_ids','interface_requirement_ids'):
                change.status='unsupported'
                change.detail+=' · Anforderungen werden in der ISD gepflegt; ECAD darf sie nicht überschreiben.'

    def backward_apply(self, package, preview):
        if preview.direction!='backward':raise ValueError('Keine Backward-Vorschau.')
        rows=selected_state(package,preview)
        updated=package_from_state(package,rows)
        observed=ArchitecturePackage.model_validate(preview.xpedition_context['observed'])
        incoming={f.id:f for f in observed.function_elements}
        for fe in updated.function_elements:
            if fe.id in incoming:
                for key in ('source_block_uuid','source_project','source_sheet','source_revision'):setattr(fe,key,getattr(incoming[fe.id],key))
        return advance_baseline(updated,preview,preview.xpedition_context['remote'],preview.xpedition_context['project_path'],binding(observed).get('nativeBindings'))

    def create_project(self,package,parent,name,library='',template='',server=''):
        path=self.backend.create_project(parent,name,library,template,server)
        return self.link_project(package,path)


register(XpeditionConnector())
