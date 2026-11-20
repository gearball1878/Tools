"""Explicit project association, separate reviews and reviewed ECAD mutations."""
from __future__ import annotations

from copy import deepcopy
import logging
from typing import Callable

from nicegui import events, run, ui

from .annotation_review import open_annotation_review
from .ecad_connector import AnnotationChange, AnnotationPreview, connector_for
from .kicad_connector import _metadata, _snapshot
from .kicad_forward import apply_forward_project, forward_project_preview, inspect_link, link_project, rollback_forward_project
from .kicad_local import choose_workstation_path, create_local_project, find_kicad, open_in_kicad, save_workstation_program, workstation_mode
from .kicad_project_readback import _state
from .models import ArchitecturePackage

log = logging.getLogger(__name__)


def new_project_preview(package, connector):
    """Keep object maps and the project-level class catalog distinct."""
    preview = AnnotationPreview('forward')
    state = _state(package)
    for kind in ('domain', 'element', 'signal'):
        for oid, data in state[kind].items():
            preview.changes.append(AnnotationChange(
                oid, kind+'Object', None, data, detail='Neues Projekt · '+data['name']))
    preview.changes.append(AnnotationChange(
        package.project.id, 'project.net_classes', None, state['net_classes'],
        detail='Netzklassen und signalbezogene Zuordnungen ins KiCad-Projekt übernehmen'))
    preview.warnings = connector.forward_preview(package).warnings
    return preview


def ecad_system_selection(dialog, package, commit, system):
    """Switch dialogs as siblings; a closed ancestor must not hide the new one."""
    from . import __version__
    ui.label(f'ISD Suite v{__version__}').classes('text-xs text-slate-500')
    def selected(event):
        if event.value not in {'kicad', 'xpedition'} or event.value == system:
            return
        dialog.close()
        with dialog.client.layout.default_slot:
            open_ecad_dialog(package, commit, system=event.value)
        dialog.delete()
    ui.select({'kicad': 'KiCad', 'xpedition': 'Xpedition'}, value=system,
              label='ECAD-System', on_change=selected).classes('w-full').mark('ecad-system-selector')


def open_ecad_dialog(package: ArchitecturePackage,
                     commit: Callable[[ArchitecturePackage, str], bool], *, system: str | None = None) -> None:
    if (system or package.properties.get('activeEcadConnector'))=='xpedition':
        from .xpedition_ui import open_xpedition_dialog
        return open_xpedition_dialog(package,commit)
    original_commit=commit
    def commit(updated,reason):
        updated.properties['activeEcadConnector']='kicad'
        return original_commit(updated,reason)
    connector=connector_for('kicad')
    local=workstation_mode()=='local'
    binding=package.properties.get('ecadConnectors',{}).get('kicad',{})
    with ui.dialog() as dialog, ui.card().classes('w-[960px] max-w-[96vw] max-h-[92vh] overflow-auto p-6 gap-4'):
        from .help_ui import mask_help
        mask_help(dialog,'ecad',mask='KiCad-Projekt und Annotation')
        with ui.row().classes('w-full items-center'):
            ui.label('ECAD-Konnektor · KiCad').classes('text-xl font-bold grow')
            ui.button('Schließen',on_click=dialog.close).props('flat no-caps')
        ecad_system_selection(dialog, package, original_commit, 'kicad')
        ui.label('Aktives Projekt: '+(binding.get('projectPath') or 'noch nicht verknüpft')).classes('text-sm break-all')
        with ui.tabs().classes('w-full') as tabs:
            forward=ui.tab('Forward Annotation')
            backward=ui.tab('Backward Annotation')
        with ui.tab_panels(tabs,value=forward).classes('w-full'):
            with ui.tab_panel(forward):
                ui.label('Architektur → KiCad · Projekt ausdrücklich verknüpfen, Änderungen prüfen und übernehmen.')
                project_path=ui.input('Bestehende KiCad-Projektdatei (.kicad_pro)',value=binding.get('projectPath','')).classes('w-full')
                project_path.set_visibility(local)

                async def link_selected():
                    try:inspection=await run.io_bound(inspect_link,package,project_path.value or '')
                    except (ValueError,OSError) as error:
                        ui.notify(str(error),type='negative');return
                    with ui.dialog() as link_dialog, ui.card().classes('w-[900px] max-w-[94vw] max-h-[90vh] overflow-auto'):
                        ui.label('Architektur mit bestehendem Projekt verknüpfen').classes('text-xl font-bold')
                        ui.label('Die Verknüpfung speichert nur die Zuordnung. Schaltplan und Architektur werden dabei nicht verändert.').classes('text-sm')
                        ui.label(inspection['path']).classes('text-sm break-all')
                        widgets={}
                        for row in inspection['rows']:
                            choices={d.id:d.name for d in package.domains} if row['kind']=='domain' else {e.id:d.name+' · '+e.name for d in package.domains for e in d.elements}
                            widgets[row['uuid']]=ui.select({'':'Zuordnung wählen',**choices},value=row['target'],label=row['name']).classes('w-full')
                        if inspection['bound']:ui.label('Bestehende ISD-Objektkennungen erkannt.').classes('text-emerald-700')
                        def apply_link():
                            try:
                                updated=link_project(package,inspection,{uid:w.value for uid,w in widgets.items() if w.value})
                                if commit(updated,'KiCad-Projekt ausdrücklich verknüpft'):
                                    link_dialog.close();dialog.close()
                                    ui.notify('Projekt verknüpft. ECAD-Konnektor erneut öffnen, um Änderungen zu prüfen.',type='positive')
                            except (ValueError,OSError) as error:ui.notify(str(error),type='negative')
                        ui.button('Als aktives Projekt verknüpfen',icon='link',on_click=apply_link).props('no-caps')
                        ui.button('Abbrechen',on_click=link_dialog.close).props('flat')
                    link_dialog.open()

                async def choose_link():
                    try:
                        path=await run.io_bound(choose_workstation_path,'project')
                        if path:project_path.value=path;await link_selected()
                    except (ValueError,OSError,RuntimeError) as error:ui.notify(str(error)+' · Pfad direkt eingeben.',type='warning')

                async def review_forward():
                    try:
                        preview=await run.io_bound(forward_project_preview,package,binding.get('projectPath',''))
                        def apply(resolved,indices):
                            updated=apply_forward_project(package,resolved)
                            if not commit(updated,'KiCad Forward Annotation übernommen'):
                                rollback_forward_project(resolved)
                                return False
                            dialog.close()
                            ui.notify('KiCad-Projekt aktualisiert. Sicherung: '+updated.properties['ecadConnectors']['kicad']['lastForwardBackup'],type='positive',close_button=True)
                            return True
                        open_annotation_review(package,preview,apply)
                    except (ValueError,OSError) as error:ui.notify(str(error),type='negative',close_button=True)

                if local:
                    with ui.row().classes('flex-wrap'):
                        ui.button('Bestehendes Projekt auswählen …',icon='folder_open',on_click=choose_link).props('outline no-caps')
                        ui.button('Projektpfad verknüpfen',icon='link',on_click=link_selected).props('outline no-caps')
                        ui.button('Forward-Änderungen prüfen',icon='compare_arrows',on_click=review_forward).props('no-caps').set_enabled(bool(binding.get('projectPath')))
                else:ui.label('Lokale Projektverknüpfung benötigt den Arbeitsplatz-Connector. ZIP-Austausch bleibt verfügbar.').classes('text-sm text-amber-800')
                ui.separator()
                ui.label('Neues KiCad-Projekt explizit anlegen').classes('font-semibold')
                detected=find_kicad() if local else None
                program=ui.input('KiCad-Programm · automatisch höchste installierte Version',value=str(detected) if detected else '').classes('w-full')
                program.set_visibility(local)
                launch=ui.checkbox('Neues Projekt anschließend in KiCad öffnen',value=bool(detected));launch.set_visibility(local)
                async def choose_program():
                    try:
                        chosen=await run.io_bound(choose_workstation_path,'program')
                        if chosen:program.value=str(save_workstation_program(chosen));launch.value=True
                    except (ValueError,OSError,RuntimeError) as error:ui.notify(str(error)+' · Programmpfad direkt eingeben.',type='warning')
                if local:ui.button('Programm manuell auswählen …',on_click=choose_program).props('flat no-caps')

                def initial_preview():
                    return new_project_preview(package, connector)

                def review_new_project(callback, title):
                    try:
                        open_annotation_review(package,initial_preview(),callback,
                                               selectable=False,title=title)
                    except Exception as error:
                        log.exception('KiCad project preview failed')
                        ui.notify('KiCad-Projektprüfung fehlgeschlagen: '+str(error),
                                  type='negative',close_button=True)

                def create_at(parent):
                    try:
                        selected_program=program.value.strip() or None
                        if launch.value and find_kicad(selected_program) is None:raise ValueError('KiCad-Programm nicht gefunden.')
                        project=create_local_project(package,parent,connector,selected_program)
                        updated=deepcopy(package)
                        # New project always replaces the active association and old native baselines.
                        updated.properties.setdefault('ecadConnectors',{})['kicad']={
                            'projectPath':str(project),'snapshot':_snapshot(updated),
                            'metadataSnapshot':_metadata(updated),'linkedState':_state(updated)}
                        if not commit(updated,'Neues KiCad-Projekt angelegt und verknüpft'):
                            ui.notify('Projekt wurde angelegt, Zuordnung konnte nicht gespeichert werden: '+str(project),type='warning',close_button=True);return False
                        if launch.value:
                            try:open_in_kicad(project,selected_program)
                            except OSError as error:ui.notify('Projekt angelegt; Start fehlgeschlagen: '+str(error),type='warning')
                        dialog.close();return True
                    except (ValueError,OSError,RuntimeError) as error:ui.notify(str(error),type='negative',close_button=True);return False

                async def create_local():
                    try:parent=await run.io_bound(choose_workstation_path,'directory')
                    except RuntimeError:
                        with ui.dialog() as path_dialog, ui.card():
                            folder=ui.input('Zielordner / Share').classes('w-[500px] max-w-[90vw]')
                            def accept():
                                path_dialog.close()
                                review_new_project(lambda _r,_i:create_at(folder.value),'Neues KiCad-Projekt · Änderungen prüfen')
                            ui.button('Projekt prüfen',on_click=accept)
                        path_dialog.open();return
                    if parent:review_new_project(lambda _r,_i:create_at(parent),'Neues KiCad-Projekt · Änderungen prüfen')
                if local:ui.button('Neues Projekt lokal anlegen …',icon='add',on_click=create_local).props('no-caps')

                def export_zip():
                    def generate(_resolved,_indices):
                        from .kicad_connector import _safe_filename
                        payload=connector.forward_archive(package)
                        # ZIP generation does not imply a local project association or annotation baseline.
                        ui.download(payload,_safe_filename(package.project.name)+'_KiCad.zip',media_type='application/zip')
                        return True
                    review_new_project(generate,'Neues KiCad-Projekt als ZIP · Änderungen prüfen')
                ui.button('Neues Projekt als ZIP herunterladen',icon='download',on_click=export_zip).props('outline no-caps')
            with ui.tab_panel(backward):
                ui.label('KiCad → HW-Architektur · Schaltplan speichern, Projekt einlesen und Änderungen im eigenen Fenster prüfen.')
                import_mode=ui.select({'update':'Bestehende Architektur aktualisieren','initial':'Architektur aus Schaltplan erstellen'},value='initial' if not package.domains and not package.signals else 'update',label='Importmodus').classes('w-full')
                hierarchy=ui.select({'auto':'Automatisch vorschlagen','domains':'Oberste Blätter = Domänen; Unterblätter = AEs','elements':'Oberste Blätter = AEs in gemeinsamer Domäne'},value='auto',label='SCM-Struktur zuordnen').classes('w-full')
                hierarchy.bind_visibility_from(import_mode,'value',backward=lambda v:v=='initial')
                ui.label('Erstimport benötigt eine leere HW-Architektur. System-, Mechanik- und Softwareobjekte bleiben erhalten.').classes('text-sm')
                backward_path=ui.input('KiCad-Projektdatei (.kicad_pro)',value=binding.get('projectPath','')).classes('w-full');backward_path.set_visibility(local)

                def review_backward(preview):
                    if hasattr(preview,'ecad_inventory'):
                        from .ecad_functional import bom_csv
                        ui.button('Vollständige BOM aus eingelesenem Projekt',icon='download',on_click=lambda:ui.download(bom_csv(preview.ecad_inventory),'ECAD_BOM.csv',media_type='text/csv')).props('flat no-caps')
                    def apply(resolved,indices):
                        updated=connector.backward_apply(package,resolved)
                        if commit(updated,'KiCad Backward Annotation übernommen'):
                            dialog.close();return True
                        return False
                    open_annotation_review(package,preview,apply,hosts=True)

                async def inspect_local():
                    try:
                        preview=await run.io_bound(connector.backward_project_preview,package,backward_path.value or '',import_mode.value=='initial',hierarchy.value)
                        review_backward(preview)
                    except (ValueError,OSError) as error:ui.notify(str(error),type='negative',close_button=True)
                async def choose_backward():
                    try:
                        chosen=await run.io_bound(choose_workstation_path,'project')
                        if chosen:backward_path.value=chosen;await inspect_local()
                    except (ValueError,OSError,RuntimeError) as error:ui.notify(str(error)+' · Projektpfad direkt eingeben.',type='warning')
                if local:
                    with ui.row():
                        def export_bom():
                            try:
                                from .ecad_functional import linked_bom
                                ui.download(linked_bom(package),'ECAD_BOM.csv',media_type='text/csv')
                            except (ValueError,OSError) as error:ui.notify(str(error),type='negative')
                        ui.button('Vollständige BOM exportieren',icon='download',on_click=export_bom).props('outline no-caps')
                        ui.button('Projektdatei auswählen …',icon='folder_open',on_click=choose_backward).props('outline no-caps')
                        ui.button('Projekt einlesen und prüfen',icon='compare_arrows',on_click=inspect_local).props('no-caps')
                async def upload(event:events.UploadEventArguments):
                    try:
                        payload=await event.file.read()
                        preview=await run.io_bound(connector.backward_project_archive_preview,package,payload,import_mode.value=='initial',hierarchy.value)
                        review_backward(preview)
                    except (ValueError,OSError) as error:ui.notify(str(error),type='negative',close_button=True)
                ui.upload(label='KiCad-Projekt-ZIP auswählen',on_upload=upload,auto_upload=True).props('accept=".zip" max-files=1').classes('w-full')
    dialog.open()
