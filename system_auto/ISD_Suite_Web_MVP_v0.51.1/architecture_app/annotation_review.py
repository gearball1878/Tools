"""Large, separate, selectable annotation review with before/after columns."""
from __future__ import annotations

from copy import deepcopy
import json

from nicegui import ui



def resolve_preview(preview,decisions):
    resolved=deepcopy(preview)
    resolved.changes=[]
    indices=[]
    for index,change in enumerate(preview.changes):
        choice=decisions.get(index,'skip')
        if choice=='skip':continue
        if choice=='open':raise ValueError('Bitte die ausgewählten Konflikte lösen.')
        if change.status=='unsupported':raise ValueError('Nicht unterstützte Änderungen können nicht übernommen werden.')
        copy=deepcopy(change);copy.status='ready'
        resolved.changes.append(copy);indices.append(index)
    resolved.annotation_complete = len(indices) == len(preview.changes)
    if hasattr(preview,'file_changes'):
        resolved.file_changes=[deepcopy(preview.file_changes[i]) for i in indices]
    return resolved,indices


def open_annotation_review(package,preview,on_apply,*,selectable=True,hosts=False,title=None,help_section='ecad'):
    decisions={i:('apply' if c.status=='ready' else 'open' if c.status=='conflict' else 'skip') for i,c in enumerate(preview.changes)}
    filter_state={'status':'all','query':''}
    host_widgets={}
    names={o.id:o.name for d in package.domains for o in [d,*d.elements,*[p for e in d.elements for p in e.ports]]}
    names.update({s.id:s.name for s in package.signals})
    from .traceability import project_objects
    names.update({o.id:getattr(o,'name',getattr(o,'title',o.id)) for group in project_objects(package).values() for o in group.values()})
    labels={'domain':'Domänen','domains':'Domänen','element':'Architekturelemente','elements':'Architekturelemente','signal':'Netze / Busse','signals':'Netze / Busse','ports':'Ports','connections':'Verbindungen','function_element':'Funktions Elemente (FE)','component':'Systemdefinierende Bauteile','realization':'Realisierungen','technical_source':'Dokumentverbindungen'}
    labels.update(function_elements='Funktions Elemente (FE)',components='Bauteile',technical_realizations='Realisierungen',
                  technical_sources='Dokumentverbindungen',requirements='Requirements',standards='Normen und Standards',
                  system_elements='Systemarchitektur',mechanical_architecture_elements='Mechanikarchitektur',
                  software_architecture_elements='Softwarearchitektur',mechanical_components='Mechanik-Realisierungen',
                  software_components='Software-Realisierungen',interface_requirements='Schnittstellenanforderungen')
    def humanize(value):
        if isinstance(value, dict):
            return {k: humanize(v) for k, v in value.items() if k not in {'id', 'properties', 'attributes'} and v is not None and v not in ('',[],{})}
        if isinstance(value, list): return [humanize(v) for v in value]
        if isinstance(value, str): return names.get(value, value)
        return value
    def summary(value):
        value = humanize(value)
        if value is None:return '—'
        if isinstance(value,dict):
            return '\n'.join(f'{k}: '+(str(v) if not isinstance(v,(list,dict)) else json.dumps(v,ensure_ascii=False)) for k,v in value.items() if k not in {'id','properties','attributes'})[:1800]
        if isinstance(value,list):return '\n'.join(str(v.get('name') or names.get(v.get('element_id'),v.get('element_id',''))) if isinstance(v,dict) else str(v) for v in value)[:1800] or '[]'
        text=str(value)
        return text[:1800]+(' …' if len(text)>1800 else '')
    with ui.context.client, ui.dialog().props('maximized persistent') as dialog, ui.card().classes('w-full h-full p-5 gap-3'):
        from .help_ui import HelpContext
        dialog._isd_help_context = HelpContext(help_section, mask=title or 'Annotation prüfen')
        with ui.row().classes('w-full items-center'):
            ui.label(title or ('Backward Annotation · Änderungen prüfen' if preview.direction=='backward' else 'Forward Annotation · Änderungen prüfen')).classes('text-2xl font-bold grow')
            ui.button('Schließen',icon='close',on_click=dialog.close).props('flat no-caps')
        ui.label('Vorher und nachher vergleichen. Änderungen werden erst nach ausdrücklicher Übernahme angewendet.').classes('text-sm')
        for warning in preview.warnings:ui.label(warning).classes('text-sm text-amber-800')
        if not preview.changes:ui.label('Keine Änderungen gefunden.').classes('font-semibold')
        if hosts and hasattr(preview,'back_annotation_state'):
            with ui.expansion('Offene HOST-Zuordnungen',value=True).classes('w-full'):
                imported=preview.back_annotation_state
                for sid,signal in imported['signal'].items():
                    if not signal.get('properties',{}).get('hostAssignmentPending'):continue
                    options={'':'Offen lassen · Port ohne gerichtete Verbindung'}
                    options.update({v['element_id']:imported['element'][v['element_id']]['name'] for v in signal['sinks']})
                    host_widgets[sid]=ui.select(options,value='',label='HOST für '+signal['name']).classes('w-full')

        @ui.refreshable
        def footer():
            counts={'apply':sum(v=='apply' for v in decisions.values()),'skip':sum(v=='skip' for v in decisions.values()),'open':sum(v=='open' for v in decisions.values())}
            ui.label(f"Übernehmen: {counts['apply']} · Auslassen: {counts['skip']} · Offene Konflikte: {counts['open']}").classes('font-medium')

        def choose(i,value):decisions[i]=value;footer.refresh()

        @ui.refreshable
        def rows():
            groups={}
            for i,c in enumerate(preview.changes):
                if filter_state['status']!='all':
                    if filter_state['status'] in {'ready','conflict','unsupported'} and c.status!=filter_state['status']:continue
                    if filter_state['status']=='new' and c.before is not None:continue
                    if filter_state['status']=='deleted' and c.after is not None:continue
                    if filter_state['status']=='modified' and (c.before is None or c.after is None):continue
                objname=names.get(c.object_id,'')
                if not objname and isinstance(c.after or c.before,dict): objname=(c.after or c.before).get('name','')
                text=(objname+' '+c.detail+' '+c.field).casefold()
                if filter_state['query'].casefold() not in text:continue
                prefix=c.field.replace('metadata.','').split('.')[0].removesuffix('Object')
                groups.setdefault(labels.get(prefix,'Schaltplan / Projekt'),[]).append((i,c,objname))
            for group,items in groups.items():
                with ui.expansion(f'{group} ({len(items)})',value=True).classes('w-full border rounded-lg'):
                    for i,c,objname in items:
                        with ui.card().classes('w-full shadow-none border p-3'):
                            with ui.row().classes('w-full items-center flex-wrap'):
                                ui.label(objname or c.detail or c.field).classes('font-semibold grow')
                                kind='Neu' if c.before is None else 'Gelöscht' if c.after is None else 'Geändert'
                                ui.badge(kind)
                                ui.badge({'ready':'Übernehmbar','conflict':'Konflikt','unsupported':'Nicht unterstützt'}.get(c.status,c.status),color='red' if c.status!='ready' else 'teal')
                                if selectable and c.status=='ready':
                                    ui.checkbox('Übernehmen',value=decisions[i]=='apply',on_change=lambda e,index=i:choose(index,'apply' if e.value else 'skip'))
                                elif selectable and c.status=='conflict':
                                    ui.select({'open':'Lösung wählen','skip':'Aktuellen Stand behalten','apply':'Vorgeschlagene Änderung übernehmen'},value=decisions[i],on_change=lambda e,index=i:choose(index,e.value)).classes('w-80')
                            ui.label(c.field).classes('text-xs text-slate-500')
                            with ui.row().classes('w-full gap-4 no-wrap'):
                                for heading,value in [('Vorher',c.before),('Nachher',c.after)]:
                                    with ui.column().classes('w-1/2 min-w-0 bg-slate-50 rounded p-3'):
                                        ui.label(heading).classes('font-semibold')
                                        if isinstance(c.before,dict) and isinstance(c.after,dict):
                                            changed={k for k in c.before.keys()|c.after.keys() if c.before.get(k)!=c.after.get(k)}
                                            value={k:v for k,v in value.items() if k in changed}
                                        ui.label(summary(value)).classes('text-sm whitespace-pre-wrap break-all')
                            if c.detail:ui.label(c.detail).classes('text-xs text-slate-600')
                            with ui.expansion('Identität und vollständige Werte').classes('w-full'):
                                ui.label(c.object_id).classes('font-mono text-xs break-all')
                                ui.code(json.dumps({'vorher':c.before,'nachher':c.after},ensure_ascii=False,indent=2),language='json').classes('w-full')

        def filter_changed(event):filter_state['status']=event.value;rows.refresh()
        def query_changed(event):filter_state['query']=event.value or '';rows.refresh()
        with ui.row().classes('w-full items-center'):
            ui.select({'all':'Alle Änderungen','new':'Neu','modified':'Geändert','deleted':'Gelöscht','ready':'Übernehmbar','conflict':'Konflikte','unsupported':'Nicht unterstützt'},value='all',label='Filter',on_change=filter_changed).classes('w-52')
            ui.input('Objekt / Änderung suchen',on_change=query_changed).classes('grow')
        with ui.scroll_area().classes('w-full grow min-h-0'):rows()
        with ui.row().classes('w-full items-center justify-between'):
            footer()
            def apply():
                try:
                    resolved,indices=resolve_preview(preview,decisions)
                    selected_hosts={sid:widget.value for sid,widget in host_widgets.items() if widget.value}
                    if selected_hosts:
                        from .kicad_native_import import resolve_import_hosts
                        resolved=resolve_import_hosts(resolved,selected_hosts)
                    if selectable and not resolved.changes and not selected_hosts:
                        ui.notify('Keine Änderungen ausgewählt.',type='info');return
                    if on_apply(resolved,indices) is not False:dialog.close()
                except (ValueError,OSError,RuntimeError) as error:ui.notify(str(error),type='negative',close_button=True)
            ui.button('Ausgewählte Änderungen übernehmen' if selectable else 'Geprüftes Projekt erzeugen',icon='check',on_click=apply).props('no-caps')
    dialog.open()
    return dialog
