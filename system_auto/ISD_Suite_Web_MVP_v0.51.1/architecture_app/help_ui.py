"""Task-focused help; the complete manual is a separate navigable document."""
from __future__ import annotations
from nicegui import ui

TOOL_DOCUMENTATION_URL = '/isd-suite-tooldokumentation'
HELP = {
    'ai': ('KI-Anbindung', 'Provider und Modell im KI-Konfigurationsdialog wählen.', ['Die Verbindungshilfe folgt dem ausgewählten Provider.', 'API-Modell zeigt Vorschläge sofort; API-Modelle laden ergänzt den Katalog. Eine exakte ID kann manuell eingetragen werden.', 'Verbindung testen prüft eine kleine strukturierte Anfrage ohne Projektinhalt.', 'Schlüssel in der Sitzung oder im Credential Manager speichern; Graph-Token nur in der Sitzung.'], 'Modellkatalog und Modellzugriff sind getrennt. Kontingent, Installation und Freigaben beim Anbieter prüfen.'),
    'xpedition': ('Xpedition · SPOT und COM', 'ISD am Windows-Arbeitsplatz starten; Xpedition und pywin32 müssen installiert sein.',
        ['Im Dropdown ECAD-System Xpedition wählen. Projekt / COM zeigt die .prj-Verknüpfung und erstellt ein Diagnoseprotokoll.',
         'Neues Projekt: Zielordner, Projektname, Zentralbibliothek und gegebenenfalls Vorlage / Server eintragen. Anlage verknüpft das neue Projekt; danach Forward Annotation prüfen.',
         'Forward / Backward Annotation öffnen ein separates Prüffenster. Konflikte lösen; nicht unterstützte Operationen auslassen.',
         'Bei Serverbetrieb das SPOT-Austauschpaket herunterladen, die Bridge am Windows-Arbeitsplatz ausführen und die zurückgelesene SPOT JSON importieren.',
         'Busmitglieder und individuelle Netzklassenvorgaben bleiben in SPOT. Die wirksame Constraint-Manager-Zuordnung benötigt noch den nativen Nachweis.'],
        'COM-Fehler: anderes geöffnetes Projekt speichern und schließen, Projektvorlage / Bibliothek prüfen und Diagnose herunterladen. Native Löschung, AE-Verschiebung und bestehende Netz-Neuverdrahtung sind noch nicht freigegeben.'),
    'ecad': ('KiCad-Projekt und Änderungsprüfung', 'Im Dropdown ECAD-System KiCad oder Xpedition wählen; dann ein Projekt verknüpfen oder ausdrücklich erzeugen.',
        ['Neues Projekt lokal anlegen: Zielordner wählen, maximiertes Prüffenster bewerten und Geprüftes Projekt erzeugen wählen.',
         'Neues Projekt als ZIP herunterladen öffnet dieselbe Prüfung; nach der Übernahme startet der Download. ZIP-Erzeugung verknüpft kein lokales Projekt.',
         'Netzklassen und Zuordnungen werden ins KiCad-Projekt übertragen. Eigene Busmitgliedsklassen gelten vor der Bus-Standardklasse.',
         'Designregeln und Constraints im KiCad-PCB-Editor pflegen. Bestehende Regeln werden beim Abgleich erhalten; konkurrierende Änderungen müssen geprüft werden.'],
        'Fehlt ein Bus-Alias, wird die Backannotation abgebrochen, bevor vorhandene Mitglieder verloren gehen. Alias im Schaltplan korrigieren und erneut prüfen.'),
    'overview': ('Projekt und Workflow', 'Projekt öffnen oder anlegen und das Projektprofil wählen.',
        ['Requirements beschreiben Vorgaben; Architektur ordnet Verantwortung zu; Realisierungen belegen die Umsetzung.',
         'Objekte im Navigator auswählen. Über Bearbeiten und die Eingabemaske ändern.'],
        'Fehlende Zuordnungen bleiben offen. Eine Zuordnung bestätigt keine Erfüllung.'),
    'hardware': ('Hardwarearchitektur und ECAD', 'Domäne und HW-AE anlegen; für Netze / Busse eine Signalvorlage wählen.',
        ['Netzklasse am Netz oder Bus wählen. Busmitglieder dürfen die Standardklasse überschreiben.',
         'Host und Teilnehmer über die Topologie zuordnen. Verbundene Ports übernehmen Namen und Rolle.',
         'Eine Domäne mit mindestens einem internen Host zeigt den Anschluss rechts, auch wenn sie intern Teilnehmer hat.',
         'GND / AGND / ISO_GND bleiben im Katalog und werden auf Funktionsblättern global genutzt; sie erscheinen nicht als Blockanschlüsse.',
         'Technischen Vergleich aufklappen: Kennwert wählen, Quellen und Bedingungen prüfen.',
         'Forward / Back Annotation öffnet eine Änderungsvorschau für das verknüpfte ECAD-Projekt.'],
        'Gemischte Busklassen in den Mitgliedsdetails prüfen. Passive Hierarchieanschlüsse können eine offene Signalrichtung anzeigen.'),
    'requirements': ('Requirements zuordnen und bewerten', 'Disziplin, Ebene, Aussage und Akzeptanzkriterien festlegen.',
        ['Fachliche Anforderungsattribute eintragen und dem verantwortlichen Architekturobjekt zuordnen.',
         'Abhängigkeitsfokus und Beziehungstiefe wählen, um die Darstellung einzugrenzen.',
         'Erfüllungsbewertung und Testnachweis separat erfassen.'],
        'Ein passender Soll-/Ist-Wert ersetzt keine fachliche Bewertung und keinen ausgeführten Test.'),
    'mechanics': ('Mechanik und HW-Kopplung', 'Mechanik-Architekturelemente und konkrete Teile / Baugruppen anlegen.',
        ['CAD- und PLM-Referenz mit Revision am realisierten Teil hinterlegen.',
         'Ein FE beschreibt die Funktion und verweist auf umsetzende Teile.',
         'HW-Mechanik-Schnittstelle für Befestigung, Bauraum, Steckverbinder oder Wärmeweg zuordnen.'],
        'Offene CAD-Revisionen oder fehlende Beziehungspartner prüfen. PLM-/ERP-Angaben sind Verweise.'),
    'software': ('Software, Firmware und HSI', 'SW/FW-Architekturelemente und konkrete Komponenten anlegen.',
        ['Codepfad, Repository, Commit / Version am Softwareobjekt pflegen.',
         'Bootloader, Package, Build und Firmware Image als passende Komponententypen anlegen.',
         'HSI anlegen und HW-Netze / Bauteile mit Software-Schnittstellen und Treibern zuordnen.'],
        'Gleiche Namen erzeugen keine Verknüpfung. HSI-Referenzen und Implementierungskonfiguration explizit prüfen.'),
    'documents': ('Quellen und KI', 'Dokumente mit nachvollziehbarer Herkunft und Revision hinterlegen.',
        ['Dokument analysieren und vorgeschlagene Requirements fachlich bewerten.',
         'Aktuelles Objekt für einen begrenzten KI-Kontext wählen.',
         'Nur antworten verändert nichts; vorbereitete Änderungen in der Vorschau einzeln prüfen.'],
        'Fehlender Dokumentinhalt und unpassende Referenzen verhindern belastbare Aussagen. Ein neuer Projektstand benötigt eine neue Vorschau.'),
    'standards': ('Normen und Belege', 'Norm mit Ausgabe und Geltungsbereich erfassen.',
        ['Norm dem Requirement zuordnen.', 'Bauteilqualifikation am konkreten MPN und Dokumentstand prüfen.'],
        'Ein Datenblattlink allein bestätigt keine Normerfüllung.'),
    'data': ('Revisionen und Migration', 'Vor größerer Übernahme eine Revision oder einen Projektexport erstellen.',
        ['Änderungen speichern und den Projektstand erneut laden.',
         'Technische Altwerte erscheinen als Bestand prüfen. Ihre bisherige Herkunft bleibt erhalten.'],
        'Unbekannte Ziele und ungültige Attributtypen werden beim Speichern abgewiesen.'),
}


from dataclasses import dataclass
from weakref import WeakKeyDictionary

@dataclass
class HelpContext:
    view: str = 'overview'
    obj: object = None
    mode: str = ''
    mask: str = ''

_CONTEXTS=WeakKeyDictionary()

def register_help_context(provider):
    _CONTEXTS[ui.context.client]=provider

def mask_help(dialog,view,obj=None,mask='Eingabemaske'):
    dialog._isd_help_context=HelpContext(view,obj,mask=mask)
    ui.button('Hilfe zur Eingabemaske',icon='help_outline',on_click=lambda:open_help_dialog(context=dialog._isd_help_context)).props('flat dense no-caps')

def current_help_context(initial_section='overview'):
    dialogs=[e for e in ui.context.client.elements.values() if isinstance(e,ui.dialog) and e.value and hasattr(e,'_isd_help_context')]
    if dialogs:return max(dialogs,key=lambda d:d.id)._isd_help_context
    provider=_CONTEXTS.get(ui.context.client)
    if provider:return provider()
    return HelpContext(initial_section)

def help_content(context):
    view={'architecture':'hardware','hardware_realizations':'hardware','quickstart':'overview','ai':'documents','tests':'requirements','integration':'hardware','evidence':'standards','revisions':'data'}.get(context.view,context.view)
    selected=view if view in HELP else 'overview'
    title,prerequisite,actions,issue=HELP[selected]
    actions=list(actions)
    obj=context.obj;kind=type(obj).__name__ if obj else ''
    if kind in {'InterfacePort','Connection','ArchitectureSignal','Signal'}:
        title='Netz, Bus und Anschlüsse'
        actions=['Objektattribute zeigt alle passenden Felder. Offen bedeutet, dass noch kein Wert eingetragen ist.',
                 'Netzklasse bearbeiten öffnet die Netz-/Busdefinition mit dem Netzklassen-Dropdown.',
                 'Businhalt / Mitgliedsdetails aufklappen und Mitglied bearbeiten wählen, um eine eigene Klasse zu setzen.',
                 'Eine leere Mitgliedsklasse übernimmt die Bus-Standardklasse. Port und Verbindung zeigen abgeleitete Klassen.']
        issue='Host/Teilnehmer wird aus der Topologie abgeleitet. Die Rolle eines gebundenen Ports ändern Sie über Topologie bearbeiten.'
    elif kind in {'Domain','ArchitectureElement','SystemElement','SystemDomain','FunctionElement','SoftwareArchitectureElement','MechanicalArchitectureElement'}:
        actions=['Objekt bearbeiten öffnet die passende Eingabemaske. Offene Attribute bleiben sichtbar.',
                 'Anforderungsattribute und Realisierungsattribute sind getrennte Räume desselben Objekts.',
                 'Zuordnungen zeigt Requirements und konkrete Umsetzungen einmalig. Technischer Vergleich zeigt deren Soll-/Istwerte.']
    elif kind=='EcadRequirement' or selected=='requirements':
        actions=['Anforderungsliste gruppiert L1 mit abgeleiteten L2; weitere L2 sowie L3/L4 bleiben getrennt erreichbar.',
                 'Ein Requirement auswählen: Zusammenhang der Auswahl zeigt gespeicherte Ableitungen und Zuordnungen; rechts stehen die Details.',
                 'Anforderungskette zeigt den gewählten Zusammenhang; Umfang wählt direkte Beziehungen oder vollständige Kette.',
                 'Gesamtübersicht öffnet die vollständige Grafik. Horizontal scrollen erhält lesbare Karten.',
                 'Architektur aus Requirements erzeugen öffnet eine explizite Auswahl mit Filtern, Zielarchitekturen und Vorschau.']
        issue='Ebene, Prüfstand und Erfüllung sind getrennt. Freigegeben bedeutet keine nachgewiesene Erfüllung. Weitere Ursprünge sind Referenzen auf dasselbe Objekt.'
    elif kind in {'TechnicalRealization','DesignComponent','MechanicalComponent','SoftwareComponent'}:
        title='Konkrete Realisierung'
        actions=['Architekturbezug nennt das verantwortliche AE/FE; Umsetzung und Varianten beschreiben die gewählte Lösung.',
                 'Systemdefinierende Bestandteile aufklappen. Datenblatt, Code oder CAD mit Revision am konkreten Objekt pflegen.',
                 'Ist-Kennwerte erfassen und mit zugeordneten Requirements vergleichen. Ein Wertevergleich ersetzt keinen Nachweis.']
    if context.view=='hardware_realizations' and not obj:
        title='Hardware-Realisierung'
        actions=['Domäne und AE nennen die Architekturverantwortung; darunter stehen ihre konkreten Realisierungen.',
                 'Aktive Variante prüfen. Umsetzung und Varianten aufklappen, um systemdefinierende Bestandteile zu öffnen.',
                 'Realisierung bearbeiten legt AE/FE-Zuordnung, Variante und technische Umsetzung fest.']
        issue='Architekturzuordnung offen und aktive Variante offen sind fehlende Angaben, keine weitere Realisierung.'
    if context.view == 'hardware_realizations':
        selected = 'hardware_realizations'
        title = 'HW-Realisierung · ' + (context.mode or 'Architektur')
        prerequisite = 'Unter Realisierung → HW / ECAD den Kontext und optional einen Architekturbezug wählen.'
        actions = ['Kontext gewichtet dieselben Informationen zu Architektur, Parts, direkten Requirements und ECAD. Der gewählte Bereich steht zuerst und ist aufgeklappt.',
                   'Ein Objekt im Navigator oder in der Übersicht auswählen; die Details erscheinen rechts ohne Attributfenster.',
                   'Fokus und Detailauswahl bleiben beim Kontextwechsel erhalten. Fokus zurücksetzen öffnet wieder die Übersicht; Architekturbezug begrenzt den Rahmen.',
                   'Requirements enthält nur direkte Zuordnungen zu FEs, ihren Implementierungen und Kernbauteilen, direkte FE-Zuordnungen, keine geerbten AE- oder Kundenanforderungen. Parts zeigt systembestimmende Bauteile einmalig: MPN, Hersteller, Revision und Dokumentstände. Alternativen und Normen stehen rechts.',
                   'Das FE führt die Realisierung. Implementierungen und aktive Varianten stehen darunter. Alle passenden Objektfelder einschließlich offener Werte sind sichtbar; technische Werte bleiben im Vergleich mit Quellen.',
                   'Bearbeiten öffnet die passende Eingabemaske; Dokumente und Qualifikation verwalten öffnet die bestehende Verwaltung.']
        issue = 'Eine offene Zuordnung oder fehlende MPN bleibt sichtbar. Inaktive Varianten sind keine eingesetzten Bauteile; die vollständige BOM kommt aus ECAD.'
    if context.mask and context.view not in {'ecad','xpedition'}:
        title=context.mask
        prerequisite='Sie bearbeiten die geöffnete Eingabemaske.'
        actions=['Felder ändern; Dropdowns bieten die für dieses Objekt zulässigen Werte.',
                 'Offene optionale Werte dürfen leer bleiben. Kennungen und abgeleitete Angaben sind geschützt.',
                 'Speichern beziehungsweise Übernehmen bestätigt die Angaben. Abbrechen verwirft die Eingabe.']+actions
    return selected,title,prerequisite,actions,issue

def open_help_dialog(initial_section='overview',*,context=None):
    context=context or current_help_context(initial_section)
    selected,title,prerequisite,actions,issue=help_content(context)
    with ui.dialog() as dialog, ui.card().classes('w-[850px] max-w-[95vw] max-h-[88vh] overflow-auto p-6 gap-4'):
        with ui.row().classes('w-full items-center'):
            ui.label('Hilfe · '+title).classes('text-xl font-bold grow')
            ui.button(icon='close',on_click=dialog.close).props('flat round aria-label=Hilfe-schließen')
        if context.obj:ui.label('Ausgewähltes Objekt: '+getattr(context.obj,'name',getattr(context.obj,'title','Objekt'))).classes('font-semibold')
        if context.mode:ui.label('Aktuelle Darstellung: '+context.mode).classes('text-sm')
        ui.label('Voraussetzung').classes('font-semibold');ui.label(prerequisite)
        ui.label('Nächste Schritte').classes('font-semibold')
        for i, action in enumerate(actions,1):ui.label(f'{i}. {action}')
        ui.label('Wenn etwas offen bleibt').classes('font-semibold');ui.label(issue).classes('text-sm')
        ui.link('Passendes Handbuchkapitel öffnen',TOOL_DOCUMENTATION_URL+'?chapter='+selected).props('target=_blank')
    dialog.open()
