"""Xpedition project association, explicit creation and separate annotation reviews."""
from __future__ import annotations
import json
import os
from nicegui import events, run, ui
from .annotation_review import open_annotation_review
from .xpedition_connector import XpeditionConnector
from .xpedition_exchange import binding


def open_xpedition_dialog(package, commit):
    connector=XpeditionConnector(); active=binding(package); native=os.name=='nt'
    with ui.dialog() as dialog,ui.card().classes('w-[1000px] max-w-[96vw] max-h-[92vh] overflow-auto p-6 gap-4'):
        from .help_ui import mask_help
        mask_help(dialog,'xpedition',mask='Xpedition · SPOT und COM')
        with ui.row().classes('w-full items-center'):
            ui.label('ECAD-Konnektor · Xpedition').classes('text-xl font-bold grow')
            ui.button('Schließen',on_click=dialog.close).props('flat no-caps')
        from .ecad_ui import ecad_system_selection
        ecad_system_selection(dialog, package, commit, 'xpedition')
        ui.label('Aktives Projekt: '+(active.get('projectPath') or 'noch nicht verknüpft')).classes('text-sm break-all')
        ui.label('SPOT JSON enthält die Projektdaten. Änderungen werden vor der Übernahme im eigenen Fenster geprüft.').classes('text-sm')
        ui.label('Constraint Manager: Klassenvorgaben werden transportiert; die wirksame native Zuordnung ist noch nicht verifiziert.').classes('text-sm text-amber-800')
        if not native:
            ui.label('COM läuft am Windows-Arbeitsplatz. Für diese Serverinstallation SPOT exportieren, dort die Bridge ausführen und das Rücklesen hier importieren.').classes('text-sm')
        with ui.tabs().classes('w-full') as tabs:
            association=ui.tab('Projekt / COM');forward=ui.tab('Forward Annotation');backward=ui.tab('Backward Annotation')
        with ui.tab_panels(tabs,value=association).classes('w-full'):
            with ui.tab_panel(association):
                path=ui.input('Xpedition-Projektdatei (.prj)',value=active.get('projectPath','')).classes('w-full')
                report=ui.code('',language='json').classes('w-full');report.set_visibility(False)
                async def diagnose():
                    result=await run.io_bound(connector.backend.diagnose,path.value or '')
                    report.content=json.dumps(result,ensure_ascii=False,indent=2);report.set_visibility(True)
                    ui.notify('COM-Prüfung erfolgreich' if result['ok'] else 'COM-Prüfung fehlgeschlagen',type='positive' if result['ok'] else 'negative')
                    ui.download(json.dumps(result,ensure_ascii=False,indent=2).encode(),'Xpedition_COM_Diagnose.json',media_type='application/json')
                async def link():
                    try:
                        updated=await run.io_bound(connector.link_project,package,path.value or '')
                        if commit(updated,'Xpedition-Projekt ausdrücklich verknüpft'):dialog.close()
                    except (ValueError,RuntimeError,OSError) as error:ui.notify(str(error),type='negative',close_button=True)
                with ui.row():
                    ui.button('COM und Projekt prüfen',icon='science',on_click=diagnose).props('outline no-caps')
                    ui.button('Bestehendes Projekt verknüpfen',icon='link',on_click=link).props('no-caps').set_enabled(native)
                ui.separator();ui.label('Neues Xpedition-Projekt explizit anlegen').classes('font-semibold')
                parent=ui.input('Zielordner am Windows-Arbeitsplatz').classes('w-full')
                name=ui.input('Projektname',value=package.project.name).classes('w-full')
                library=ui.input('Zentralbibliothek · Pfad').classes('w-full')
                template=ui.input('Projektvorlage · Pfad, falls benötigt').classes('w-full')
                server=ui.input('iCDB-Server · falls benötigt').classes('w-full')
                async def create():
                    try:
                        updated=await run.io_bound(connector.create_project,package,parent.value or '',name.value or '',library.value or '',template.value or '',server.value or '')
                        if commit(updated,'Neues Xpedition-Projekt angelegt und verknüpft'):
                            ui.notify('Projekt angelegt und verknüpft. Forward Annotation öffnen und Änderungen prüfen.',type='positive',close_button=True);dialog.close()
                        else:ui.notify('Projekt angelegt; ISD-Verknüpfung nicht gespeichert: '+binding(updated)['projectPath'],type='warning',close_button=True)
                    except (ValueError,RuntimeError,OSError) as error:ui.notify(str(error),type='negative',close_button=True)
                ui.button('Neues Projekt anlegen und verknüpfen',icon='add',on_click=create).props('no-caps').set_enabled(native)
                ui.label('Die Projektanlage erzeugt zunächst das native Projekt. Architekturänderungen werden anschließend separat geprüft.').classes('text-sm')
            with ui.tab_panel(forward):
                async def inspect_forward():
                    try:
                        preview=await run.io_bound(connector.forward_project_preview,package)
                        def apply(resolved,indices):
                            updated=connector.apply_forward(package,resolved)
                            if commit(updated,'Xpedition Forward Annotation übernommen'):
                                dialog.close();ui.notify('COM-Übernahme bestätigt. Sicherung: '+binding(updated)['lastForwardBackup'],type='positive',close_button=True);return True
                            ui.notify('ECAD wurde geändert, ISD-Stand konnte nicht gespeichert werden. Sicherung: '+binding(updated)['lastForwardBackup'],type='negative',close_button=True);return False
                        open_annotation_review(package,preview,apply,title='Xpedition · Forward Annotation prüfen',help_section='xpedition')
                    except (ValueError,RuntimeError,OSError) as error:ui.notify(str(error),type='negative',close_button=True)
                ui.button('Forward-Änderungen über COM prüfen',icon='compare_arrows',on_click=inspect_forward).props('no-caps').set_enabled(native and bool(active.get('projectPath')))
                def export():
                    ui.download(connector.forward_archive(package),'Xpedition_SPOT_Austausch.zip',media_type='application/zip')
                ui.button('SPOT-Austauschpaket herunterladen',icon='download',on_click=export).props('outline no-caps')
                ui.code('python -m architecture_app.xpedition_cli --help',language='bash').classes('w-full')
                ui.label('Das Austauschpaket enthält SPOT JSON und die Bridge-Aufrufe. Es ist kein bereits erzeugtes Xpedition-Projekt.').classes('text-sm')
            with ui.tab_panel(backward):
                backward_path=ui.input('Xpedition-Projektdatei (.prj)',value=active.get('projectPath','')).classes('w-full')
                mode=ui.select({'update':'Bestehende Hardwarearchitektur aktualisieren','initial':'Hardwarearchitektur aus Schaltplan erstellen'},value='initial' if not package.domains and not package.signals else 'update',label='Importmodus').classes('w-full')
                def review(preview):
                    def apply(resolved,indices):
                        updated=connector.backward_apply(package,resolved)
                        if commit(updated,'Xpedition Backward Annotation übernommen'):dialog.close();return True
                        return False
                    open_annotation_review(package,preview,apply,title='Xpedition · Backward Annotation prüfen',help_section='xpedition')
                async def inspect_backward():
                    try:
                        preview=await run.io_bound(connector.backward_project_preview,package,backward_path.value or '',mode.value=='initial')
                        review(preview)
                    except (ValueError,RuntimeError,OSError) as error:ui.notify(str(error),type='negative',close_button=True)
                ui.button('Schaltplan über COM einlesen und prüfen',icon='compare_arrows',on_click=inspect_backward).props('no-caps').set_enabled(native)
                async def upload(event:events.UploadEventArguments):
                    try:
                        if mode.value=='initial' and (package.domains or package.signals):raise ValueError('Erstimport benötigt eine leere Hardwarearchitektur.')
                        payload=await event.file.read()
                        preview=connector.backward_preview(package,payload)
                        review(preview)
                    except (ValueError,RuntimeError,OSError) as error:ui.notify(str(error),type='negative',close_button=True)
                ui.upload(label='SPOT JSON aus COM-Rücklesen importieren',on_upload=upload,auto_upload=True).props('accept=".json" max-files=1').classes('w-full')
                ui.label('Unverbundene Ports bleiben erhalten. Offene Hostrollen werden nicht aus elektrischen Pintypen erfunden.').classes('text-sm')
    dialog.open()
    return dialog
