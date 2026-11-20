"""Explicit, immutable selection for requirement-driven architecture proposals."""
from nicegui import ui
from .requirements_layers import LAYERS, effective_layer
from .architecture_scope import selected_requirements
from .help_ui import mask_help


def open_generation_dialog(package,generate,show_preview):
    with ui.context.client,ui.dialog() as dialog,ui.card().classes('w-[1000px] max-w-[96vw] max-h-[92vh] overflow-auto p-5 gap-3'):
        mask_help(dialog,'requirements',mask='Architektur aus Requirements erzeugen')
        ui.label('Architektur aus Requirements erzeugen').classes('text-xl font-bold')
        ui.label('Nur die bestätigten Requirements begründen den Vorschlag. Vorhandene Architektur bleibt als Kontext erhalten.').classes('text-sm')
        with ui.row().classes('w-full gap-3'):
            level=ui.select({'All':'Alle Ebenen',**{l.value:n+' · '+t for n,t,l in LAYERS}},value='All',label='Ebene').classes('grow')
            discipline=ui.select(['Alle','System','Hardware','Mechanik','Software','Firmware'],value='Alle',label='Disziplin').classes('grow')
            status=ui.select({'Approved':'Freigegeben','In Review':'In Prüfung','Detected':'Erfasst','All':'Alle aktiven Prüfstände'},value='Approved',label='Prüfstand').classes('grow')
        chosen=set();running={'value':False}
        selection_area=ui.column().classes('w-full border rounded p-3')
        count=ui.label('0 Requirements ausgewählt')
        def select_changed(event,identifier):
            if event.value:chosen.add(identifier)
            else:chosen.discard(identifier)
            count.set_text(str(len(chosen))+' Requirements ausgewählt')
        def refresh():
            selection_area.clear()
            # Changing filters cannot silently retain now-hidden selections.
            chosen.clear();count.set_text('0 Requirements ausgewählt')
            with selection_area:
                visible=[r for r in package().requirements if r.maturity.value not in {'Rejected','Obsolete'} and r.customer_decision!='Rejected' and
                    (level.value=='All' or effective_layer(r).value==level.value) and
                    (discipline.value=='Alle' or r.classification.value==discipline.value) and
                    (status.value=='All' or r.maturity.value==status.value)]
                if not visible:ui.label('Keine Requirements für diese Filter. Prüfstand ändern oder Requirements freigeben.')
                for r in visible:
                    ui.checkbox((r.identifier or r.id[:9])+' · '+r.title,value=False,on_change=lambda e,i=r.id:select_changed(e,i))
        for field in (level,discipline,status):field.on_value_change(lambda _:refresh())
        refresh()
        targets=ui.select({'system':'Systemarchitektur','hardware':'Hardware / ECAD','software':'Software / Firmware','mechanical':'Mechanik / CAD'},value=['hardware'],multiple=True,label='Zielarchitekturen').props('use-chips').classes('w-full')
        guidance=ui.textarea('Zusätzliche Vorgaben',value='Bestehende Objekte wiederverwenden. Requirement-Bezüge explizit zuordnen. Fehlende Angaben offen lassen. Keine vollständige Bauteilstruktur erzeugen.').classes('w-full')
        async def start():
            if running['value']:return
            try:
                identifiers=tuple(sorted(chosen));target_views=tuple(targets.value or [])
                selected_requirements(package(),identifiers)
                if not target_views:raise ValueError('Mindestens eine Zielarchitektur auswählen')
                running['value']=True;button.disable()
                outcome=await generate(guidance.value or '',requirement_ids=list(identifiers),target_views=list(target_views))
                if outcome:
                    dialog.close()
                    with dialog.client:show_preview()
            except ValueError as error:ui.notify(str(error),type='negative')
            finally:running['value']=False;button.enable()
        ui.label('Der Aufruf erzeugt eine Vorschau. Architekturänderungen werden erst nach Ihrer Prüfung übernommen.').classes('text-sm text-blue-800')
        with ui.row().classes('w-full justify-end'):
            ui.button('Abbrechen',on_click=dialog.close).props('flat')
            button=ui.button('Auswahl bestätigen und Vorschlag erzeugen',icon='auto_awesome',on_click=start).props('no-caps')
    dialog.open()
