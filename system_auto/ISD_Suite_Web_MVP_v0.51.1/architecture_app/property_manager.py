"""Readable project definitions and semantic net-class assignments."""
from copy import deepcopy
import json
from .property_schema import PropertyDefinition, KIND_LABELS, TYPE_LABELS, SCOPES, EXCHANGE, objects, update_definition, delete_definition, ATTRIBUTE_KINDS, AUTHORITIES
from .netclasses import NetClassDefinition, assignment_targets, member_class, suggest_class, set_assignment, assignment_coverage, rename_class


def open_property_manager(get_package,commit):
    from nicegui import ui
    from .object_properties import native_definitions, NATIVE_KIND_LABELS
    def apply(candidate,message):
        from .models import ArchitecturePackage
        try:
            candidate=ArchitecturePackage.model_validate(candidate.export_dict())
            if commit(candidate,message) is False:return False
            content.refresh();return True
        except (ValueError,TypeError) as error:
            ui.notify(str(error),type='negative');return False

    def edit_definition(d=None):
        protected=bool(d and d.system)
        with ui.dialog() as editor,ui.card().classes('w-[820px] max-w-[95vw] max-h-[92vh] overflow-auto p-6 gap-4'):
            with ui.row().classes('w-full items-center'):
                ui.label(d.label if d else 'Attribut anlegen').classes('text-xl font-bold grow')
                ui.badge('Systemattribut · geschützt' if protected else 'Eigenes Attribut')
            ui.label('Die Definition legt Felder fest. Werte werden am jeweiligen Objekt gepflegt.').classes('text-sm text-slate-600')
            ui.label('Bezeichnung und Bedeutung').classes('font-semibold')
            with ui.row().classes('w-full gap-3'):
                key=ui.input('Attributschlüssel',value=d.key if d else '').classes('grow')
                label=ui.input('Anzeigename',value=d.label if d else '').classes('grow')
            desc=ui.textarea('Beschreibung',value=d.description if d else '').props('autogrow').classes('w-full')
            ui.label('Geltungsbereich').classes('font-semibold')
            kinds=ui.select(NATIVE_KIND_LABELS if protected and d.storage=='native' else KIND_LABELS,multiple=True,value=d.object_types if d else [],label='Objekttypen').props('use-chips use-input').classes('w-full')
            scopes=ui.select(dict(zip(SCOPES,['Anforderung','Realisierung'])),multiple=True,value=d.scopes if d else SCOPES,label='Attributräume').props('use-chips').classes('w-full')
            disciplines=ui.select(['System','Hardware','Mechanik','Software','Firmware'],multiple=True,value=d.disciplines if d else [],label='Requirement-Disziplinen (leer = alle)').props('use-chips').classes('w-full')
            targets=ui.select(KIND_LABELS,multiple=True,value=d.target_types if d else [],label='Zulässige Beziehungspartner (leer = fachliche Vorgabe)').props('use-chips').classes('w-full')
            category=ui.select(ATTRIBUTE_KINDS,value=d.attribute_kind if d and d.attribute_kind else 'description',label='Attributart').classes('w-full')
            authority=ui.select(AUTHORITIES,value=d.authority if d else 'ISD',label='Führende Pflegequelle').classes('w-full')
            ecad_target=ui.input('ECAD-Ziel',value=d.ecad_target if d else '').classes('w-full')
            ecad_mapping=ui.textarea('ECAD-Abbildung / Austauschumfang',value=d.ecad_mapping if d else '').props('autogrow').classes('w-full')
            ui.label('Werte und Eingabe').classes('font-semibold')
            with ui.row().classes('w-full gap-3'):
                typ=ui.select(TYPE_LABELS,value=d.data_type if d else 'text',label='Datentyp').classes('grow')
                unit=ui.input('Einheit',value=d.unit if d else '').classes('grow')
                source=ui.select({'':'Freie Eingabe / feste Werte','templates':'Signal- und Interfacekatalog','netclasses':'Netzklassenkatalog',
                                 'objects':'Projektobjekte','signal_roles':'Rollen zum Schnittstellentyp'},value=d.selection_source if d else '',label='Auswahlquelle').classes('grow')
            choices=ui.textarea('Auswahlwerte (eine Zeile pro Wert)',value='\n'.join(d.choices) if d else '').classes('w-full')
            with ui.row().classes('w-full'):
                minimum=ui.number('Zulässiges Minimum',value=d.minimum if d else None)
                maximum=ui.number('Zulässiges Maximum',value=d.maximum if d else None)
            default=ui.input('Standardwert (leer = offen)',value=json.dumps(d.default,ensure_ascii=False) if d and d.default is not None else '').classes('w-full')
            default.tooltip('Text direkt eingeben; Zahlen numerisch, Listen und Strukturen in JSON-Schreibweise. Leer bedeutet keinen Standardwert.')
            exchange=ui.select(EXCHANGE,value=d.exchange if d else 'Nur ISD',label='ECAD-Austausch').classes('w-full')
            if d:
                ui.label('Speicherort: '+('Objektfeld · Bearbeitung über die Objektmaske' if d.storage=='native' else 'Attributraum am Objekt')).classes('text-sm')
                ui.label('Herkunft: '+d.origin+' · Objektwert: '+('nur lesbar' if d.readonly else 'bearbeitbar')).classes('text-sm')
            def visibility(_=None):
                numeric=typ.value=='number'
                for field in (minimum,maximum,unit):field.set_visibility(numeric)
                choices.set_visibility(typ.value=='enum' or bool(choices.value))
            typ.on_value_change(visibility);visibility()
            if d:key.disable()
            fields=[label,desc,kinds,scopes,disciplines,targets,typ,unit,source,choices,minimum,maximum,default,exchange,category,authority,ecad_target,ecad_mapping]
            if protected:
                for field in fields:field.disable()
                ui.label('Identität und fachliche Definition der Systemattribute sind geschützt. Die Werte am Objekt bleiben bearbeitbar.').classes('text-sm bg-blue-50 p-3 rounded')
            else:
                ui.label('Änderungen werden gegen vorhandene Werte geprüft. Der Schlüssel bleibt nach der Anlage unveränderlich.').classes('text-sm text-slate-600')
                def persist():
                    try:
                        value=None
                        if default.value:
                            value=default.value if typ.value in ('text','reference') else json.loads(default.value)
                        data=PropertyDefinition(id=d.id if d else '',key=(key.value or '').strip(),label=(label.value or '').strip(),description=desc.value or '',
                            object_types=kinds.value,scopes=scopes.value,data_type=typ.value,unit=unit.value or '' if typ.value=='number' else '',
                            choices=[v.strip() for v in (choices.value or '').splitlines() if v.strip()],minimum=minimum.value if typ.value=='number' else None,
                            maximum=maximum.value if typ.value=='number' else None,default=value,exchange=exchange.value,selection_source=source.value or '',target_types=targets.value or [],disciplines=disciplines.value or [],attribute_kind=category.value,authority=authority.value,ecad_target=ecad_target.value or '',ecad_mapping=ecad_mapping.value or '')
                        if not d and any(x.key==data.key for x in get_package().property_definitions):raise ValueError('Attributschlüssel existiert bereits')
                        if apply(update_definition(get_package(),data),'Attributdefinition gespeichert'):editor.close()
                    except (ValueError,TypeError) as error:ui.notify(str(error),type='negative')
                ui.button('Definition speichern',on_click=persist,icon='save')
            ui.button('Schließen' if protected else 'Abbrechen',on_click=editor.close).props('flat')
        editor.open()

    def remove_definition(d):
        uses=[f'{getattr(o,"name",type(o).__name__)} · {"Anforderung" if s==SCOPES[0] else "Realisierung"}'
              for o in objects(get_package()) for s in SCOPES if getattr(o,s).get(d.key) is not None]
        with ui.dialog() as confirm,ui.card().classes('w-[650px] max-w-[95vw] max-h-[85vh] overflow-auto'):
            ui.label(f'Attribut {d.label} löschen?').classes('font-bold')
            ui.label(f'{len(uses)} belegte Werte werden ebenfalls entfernt.')
            for text in uses:ui.label(text).classes('text-sm')
            def delete():
                if apply(delete_definition(get_package(),d.key,confirm_values=True),'Attributdefinition gelöscht'):confirm.close()
            ui.button('Definition und Werte löschen',on_click=delete,color='negative')
            ui.button('Abbrechen',on_click=confirm.close)
        confirm.open()

    def edit_class(c=None):
        with ui.dialog() as editor,ui.card().classes('w-[760px] max-w-[95vw] max-h-[90vh] overflow-auto p-6 gap-4'):
            ui.label('Netzklasse bearbeiten' if c else 'Netzklasse anlegen').classes('text-xl font-bold')
            ui.label('Name und Verwendungszweck werden im ISD gepflegt. Constraints und Design Rules werden im ECAD-Tool festgelegt.').classes('text-sm text-slate-600')
            name=ui.input('Klassenname',value=c.name if c else '').classes('w-full')
            desc=ui.textarea('Beschreibung / Verwendungszweck',value=c.description if c else '').props('autogrow').classes('w-full')
            if c:
                from .identity import show_sha_identity
                show_sha_identity(c.id,show_reference=False)
                ui.label('Eine Umbenennung erhält die Klassenkennung und aktualisiert alle ISD-Zuweisungen. ECAD-Dateien werden erst nach Annotation geändert.').classes('text-sm')
                with ui.expansion('ECAD-Regeln und Herkunft',icon='rule').classes('w-full border rounded'):
                    ui.label('Herkunft: '+c.origin)
                    if c.priority is not None:ui.label(f'ECAD-Priorität: {c.priority}')
                    if not c.ecad_parameters:ui.label('Noch keine Regelparameter aus dem ECAD-Projekt übernommen.')
                    for k,v in c.ecad_parameters.items():
                        labels={'track_width':'Leiterbahnbreite','clearance':'Abstand','via_diameter':'Via-Durchmesser','via_drill':'Via-Bohrung',
                                'diff_pair_width':'Differenzpaar-Breite','diff_pair_gap':'Differenzpaar-Abstand','diff_pair_via_gap':'Differenzpaar-Via-Abstand',
                                'wire_width':'Schaltplan-Leitungsbreite','bus_width':'Schaltplan-Busbreite','pcb_color':'PCB-Farbe','schematic_color':'Schaltplanfarbe'}
                        with ui.row().classes('w-full border-b items-start'):
                            ui.label(labels.get(k,k)).classes('w-56 font-medium')
                            ui.label(str(v)).classes('grow text-sm break-all')
                    ui.label('Diese Angaben werden verlustfrei gespeichert und im ECAD-Tool bearbeitet.').classes('text-sm')
            def persist():
                try:
                    candidate=deepcopy(get_package());newname=(name.value or '').strip()
                    if c:rename_class(candidate,c.id,newname,desc.value or '')
                    else:
                        if any(v.name==newname for v in candidate.net_classes):raise ValueError('Netzklasse existiert bereits')
                        candidate.net_classes.append(NetClassDefinition(name=newname,description=desc.value or ''))
                    if apply(candidate,'Netzklasse gespeichert'):editor.close()
                except (ValueError,TypeError) as error:ui.notify(str(error),type='negative')
            with ui.row().classes('w-full justify-end'):
                ui.button('Abbrechen',on_click=editor.close).props('flat')
                ui.button('Netzklasse speichern',on_click=persist,icon='save')
        editor.open()

    def assignments():
        p=get_package();targets=list(assignment_targets(p));choices={}
        catalog={c.name:c.name for c in p.net_classes}
        with ui.dialog().props('maximized') as wizard,ui.card().classes('w-full h-full overflow-auto p-6'):
            ui.label('Netzklassenzuordnung prüfen').classes('text-xl font-bold')
            ui.label('Einzelnetze und jedes Busmitglied werden berücksichtigt. Bestehende Zuweisungen bleiben erhalten; offene Fälle gezielt auswählen.')
            search=ui.input('Netze filtern').classes('w-full')
            only_open=ui.checkbox('Nur offene Zuweisungen anzeigen',value=True)
            @ui.refreshable
            def rows():
                for signal,member in targets:
                    obj=member or signal;effective=member_class(signal,member);label=f'{signal.name} / {obj.name}' if member else obj.name
                    if only_open.value and effective:continue
                    if search.value and search.value.casefold() not in label.casefold():continue
                    proposal=suggest_class(signal,member)
                    with ui.card().classes('w-full border shadow-none'):
                        ui.label(label).classes('font-medium')
                        if effective:ui.label('Aktuell: '+', '.join(effective)).classes('text-sm')
                        choice=ui.select(catalog,value=choices.get(obj.id,effective[0] if effective else None),label='Netzklasse',clearable=True).props('use-input').classes('w-full')
                        choice.on_value_change(lambda e,oid=obj.id:choices.update({oid:e.value}))
                        ui.label(proposal['reason']).classes('text-sm text-slate-600')
            search.on_value_change(lambda _:rows.refresh());only_open.on_value_change(lambda _:rows.refresh());rows()
            def accept():
                candidate=deepcopy(get_package());byid={o.id:o for o in objects(candidate) if getattr(o,'id',None)}
                for oid,name in choices.items():set_assignment(byid[oid],name,'Manuell im ISD')
                if apply(candidate,'Netzklassenzuordnungen gespeichert'):wizard.close()
            with ui.row().classes('w-full justify-end'):
                ui.button('Abbrechen',on_click=wizard.close).props('flat')
                ui.button('Zuordnungen speichern',on_click=accept,icon='save')
        wizard.open()

    with ui.dialog().props('maximized') as dialog,ui.card().classes('w-full h-full overflow-auto p-5'):
        with ui.row().classes('w-full items-center'):
            ui.label('Property Manager').classes('text-2xl font-bold grow')
            ui.button('Schließen',on_click=dialog.close)
        ui.label('Definitionen projektweit verwalten · Werte am jeweiligen Objekt bearbeiten')
        with ui.tabs() as tabs:
            attrs=ui.tab('Attribute');classes=ui.tab('Netzklassen')
        with ui.row().classes('w-full items-center'):
            search=ui.input('Definitionen filtern').classes('grow')
            category_filter=ui.select({'':'Alle Attributarten',**ATTRIBUTE_KINDS},value='',label='Attributart').classes('w-56')
            object_filter=ui.select({'':'Alle Objekttypen',**NATIVE_KIND_LABELS},value='',label='Objekttyp').classes('w-72')
        @ui.refreshable
        def content():
            p=get_package();query=(search.value or '').casefold()
            with ui.tab_panels(tabs,value=tabs.value or attrs).classes('w-full'):
                with ui.tab_panel(attrs):
                    ui.button('Attribut hinzufügen',icon='add',on_click=lambda:edit_definition())
                    with ui.row().classes('w-full items-center border-b py-3 font-semibold'):
                        ui.label('Attribut').classes('w-64');ui.label('Beschreibung').classes('grow');ui.label('Attributraum').classes('w-56')
                    for d in [*native_definitions(),*p.property_definitions]:
                        if category_filter.value and category_filter.value!=d.attribute_kind:continue
                        if object_filter.value and object_filter.value not in d.object_types:continue
                        if query and query not in (d.key+' '+d.label+' '+d.description).casefold():continue
                        with ui.row().classes('w-full items-start border-b py-3 gap-3 flex-wrap'):
                            ui.button(d.label,on_click=lambda _,d=d:edit_definition(d)).props('flat no-caps align=left').classes('w-64 text-left font-medium')
                            ui.label(d.description or 'Beschreibung noch offen.').classes('grow basis-80 text-sm')
                            with ui.column().classes('w-56 gap-1'):
                                ui.label(ATTRIBUTE_KINDS.get(d.attribute_kind,'Beschreibung')).classes('text-xs font-medium')
                                if d.storage=='native':ui.label('Objektfeld').classes('text-xs')
                                ui.label(' / '.join('Anforderung' if s==SCOPES[0] else 'Realisierung' for s in d.scopes)).classes('text-xs')
                                ui.badge('Systemattribut' if d.system else 'Eigenes Attribut',color='blue' if d.system else 'grey')
                            ui.button(icon='open_in_new',on_click=lambda _,d=d:edit_definition(d)).props('flat round').tooltip('Eigenschaften öffnen')
                            if not d.system:ui.button(icon='delete',on_click=lambda _,d=d:remove_definition(d)).props('flat round')
                with ui.tab_panel(classes):
                    assigned,total,missing=assignment_coverage(p)
                    with ui.row().classes('w-full items-center gap-3'):
                        ui.button('Netzklasse hinzufügen',on_click=lambda:edit_class())
                        ui.button('Netzzuordnungen prüfen',on_click=assignments,icon='rule')
                        ui.badge(f'{assigned} von {total} Netzen / Busmitgliedern zugeordnet',color='green' if not missing else 'orange')
                    ui.label('Netzklassen beschreiben den Verwendungszweck. Die elektrische Ausgestaltung erfolgt im ECAD-Tool.').classes('text-sm')
                    for c in p.net_classes:
                        if query and query not in (c.name+' '+c.description).casefold():continue
                        with ui.row().classes('w-full items-start border-b py-3 gap-3 flex-wrap'):
                            ui.button(c.name,on_click=lambda _,c=c:edit_class(c)).props('flat no-caps align=left').classes('w-64 text-left font-medium')
                            ui.label(c.description or 'Beschreibung noch offen.').classes('grow basis-80 text-sm')
                            ui.button(icon='edit',on_click=lambda _,c=c:edit_class(c)).props('flat round')
        search.on_value_change(lambda _:content.refresh());category_filter.on_value_change(lambda _:content.refresh());object_filter.on_value_change(lambda _:content.refresh());content()
    dialog.open()
