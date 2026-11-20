# ISD Suite – Integrated System Development

Die ISD Suite verbindet Quelldokumente, Requirements, technische Realisierungen,
Bauteile, Facharchitektur und Tests in einem gemeinsamen Projektmodell.
Sie unterstützt Lastenheft, Redesign, Architekturstudie und direkten HW-/ECAD-Start.

## Arbeitsbereiche

- **Prozessübersicht:** Projektprofil, Systembild und offene Arbeit.
- **Quellen & Analyse:** Dokumente, Fundstellen und Analyse.
- **Requirements:** L1 Kunde → L2 System → L3 Technik → L4 Disziplin;
  Realisierungen und Parts liegen auf einer separaten Lösungsebene.
- **Architektur:** System-, HW-/ECAD-, Mechanik-/CAD- und Software-/Firmwarearchitektur mit Anforderungen, Beziehungen und Realisierungszuordnungen.
- **HW / ECAD:** technische Realisierungen, Varianten und Bauteilauswahl; die elektrische Architektur steht im gemeinsamen Architekturarbeitsraum.
- **Mechanik / CAD:** Bauteile, Bauraum und mechanische Schnittstellen.
- **Software / Firmware:** Module, Tasks und Protokollbeziehungen.
- **Normen & Standards:** Quellen, Klauseln und Nachweise.

Eine Zuordnung bedeutet geplante Umsetzung. Erfüllung wird separat gegen
Akzeptanzkriterien und einen Ergebnisbeleg bewertet. Ein Test gilt erst mit
Ergebnis, Evidenz und geprüfter Revision als nachgewiesen.

## Start unter Windows

ZIP direkt in den Projektordner entpacken und `start_windows.bat` ausführen.
Der Starter verwendet bevorzugt `..\.venv`, prüft `requirements.txt` und
öffnet `http://127.0.0.1:8080`. Alternativ:

```powershell
py -3 -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Python 3.11 oder neuer empfohlen. Daten liegen standardmäßig unter
`%LOCALAPPDATA%\ISD_Suite\data\architecture.db`. `ISD_SUITE_DATA_DIR`
legt einen anderen Speicherort fest.

## Projekt und Austausch

Das vollständige fachliche Modell wird als SPOT-JSON (`isd-suite/v3`)
exportiert. Beim JSON-Import wird der Projekttyp ausdrücklich gewählt,
auch beim Import als Revision. Originaldokumente und extrahierte Texte sind separate Anhänge.
ReqIF, XLSX, CSV und DOCX bilden nur einen Teil der Beziehungen ab.
Die Architektur-PDF exportiert System, Hardware, Mechanik und Software/Firmware einzeln oder gemeinsam mit Übersichten, Beziehungen und Details.
Revisionen liegen in SQLite.

## ECAD-Konnektor: KiCad

Im Kopfbereich öffnet **ECAD** die manuell gestartete Forward und Backward
Annotation. Die ECAD-Auswahl zeigt zunächst KiCad als einzige aktive Option.
Forward zeigt die Änderungsvorschau. **Projekt lokal anlegen …** öffnet bei
lokal gestarteter Suite einen Dateidialog für den Zielordner; erreichbare Shares
sind möglich. KiCad wird automatisch gesucht und kann bei Bedarf über
**Programm manuell auswählen …** gewählt werden. Diese Auswahl wird am
Arbeitsplatz gespeichert, nicht im SPOT-Projekt. Ohne verfügbaren nativen
Dateidialog erscheint der Eingabepfad erst als Ausweichmöglichkeit. Die Suite
erstellt einen neuen Projektordner mit `.kicad_pro` und öffnet ihn auf Wunsch.
Bei zentralem Hosting (`ISD_ECAD_WORKSTATION_MODE=central`) werden
arbeitsplatzgebundene Aktionen bis zur Installation einer lokalen Brücke
gesperrt; der ZIP-Export bleibt verfügbar. Ein Browser kann das lokale KiCad
nicht selbst erkennen oder starten.

Der alternative ZIP-Export enthält Wurzelseite, Domain-Seiten, AE-Seiten,
hierarchische Sheet-Pins, Links, Bus-Aliase und `isd_kicad_bindings.json`.
Die nativen Sheet-Pins tragen ihre Anschlussnamen im Block. Auf Domain-Seiten
liegen die hierarchischen Verbinder direkt am Netzsegment eines beteiligten AE.
Weitere AEs derselben Domain verbinden sich über gleichnamige lokale Labels.
Auf der Wurzelseite verbinden lokale Labels die Domain-Pins. Dort und an den
übrigen Segmenten sind doppelte Netznamen ausgeblendet; die Labels bleiben
elektrisch wirksam. Die Textgeometrie einschließlich der Sheet-Pins wird vor
dem Export auf Überlagerungen geprüft und im Manifest vermerkt.
Das ZIP muss mit seiner Bindings-Datei vollständig erhalten bleiben.
Zum Prüfen außerhalb der Oberfläche:

```powershell
python -m architecture_app.kicad_cli projekt.json BMS_KiCad.zip
```

Backward liest die ausgewählte `.kicad_pro` mit ihren Schaltplanblättern oder
eine Projekt-ZIP und zeigt die Änderungen in einem eigenen Prüffenster.
Neue und geänderte Domänen, AEs, Ports, Netze und Busmitglieder können nach
Prüfung übernommen werden. Unverbundene Anschlüsse bleiben Ports ohne Link.
Mehrdeutige Zuordnungen benötigen eine bewusste Auswahl.
Bestehende Projekte werden einmalig ausdrücklich verknüpft; die lokale
Neuanlage ist eine separate Aktion und setzt das neue aktive Projekt.
Ein anderes bestehendes Projekt kann ausdrücklich ausgewählt werden.
Die lokale Projektdatei wird in den SPOT-Metadaten unter
`properties.ecadConnectors.kicad.projectPath` gespeichert. Die gemeinsame
Projektzuordnung wird für Forward und Backward verwendet.
Wenn `kicad-cli` auf dem Suite-Rechner verfügbar ist, prüft der Konnektor
den vollständigen Schaltplan vor der lokalen Projektanlage durch einen
Netzlistenexport; bei einem Ladefehler wird der neue Projektordner nicht angelegt.

### Architekturattribute im KiCad-Design

| KiCad-Objekt | Native, über Eigenschaften sichtbare ISD-Felder |
| --- | --- |
| Domain- und AE-Sheet | Interne Referenz-ID (`ISD_ID`), SHA-256-Objektkennung (`ISD_SHA256`), Art, technischer Name, Typ, Beschreibung, Architekturfarbe, freie Attribute und beim AE die Parent-Domain |
| Netzlabel und hierarchisches Label | Signal- und Verbindungs-ID mit SHA-256-Kennung, Beschreibungen, freie `attributes` und `properties`, Rolle am Anschluss (`Host` oder `Participant`), Signal- und Verbindungstyp, Quelle und Senken, Designstatus und Quellenbezug; bei AE-Ports zusätzlich Port-ID, SHA-256-Kennung, Alias, Porttyp, Beschreibung und Anschlussrolle; `Netclass` weist die KiCad-Netzklasse zu |
| Projekt-Mapping `isd_kicad_bindings.json` | KiCad-UUIDs zu SPOT-IDs, Projektkennung, vollständige freie `attributes` und `properties` aus Domain, AE, Port, Signal, Verbindung und Verbindungsendpunkten |

Attribute werden direkt am ausgewählten Architekturobjekt bearbeitet.
Definitionen verwaltet der Property Manager. Der nächste Forward-Lauf
überträgt zulässige Werte auf die zugehörigen KiCad-Objekte.
Die KiCad-Eigenschaften eines bloßen
Leitungssegments bleiben dagegen rein grafisch; native Felder liegen an
Labels, Sheets und späteren Bauteilsymbolen. Widersprüchlich geänderte
Label-Felder blockieren die automatische Backward Annotation.

Die generierten Netzklassen übernehmen die Signalkategorien und deren
Schaltplanfarben. Schaltplan-Bussegmente haben eine Breite von 0,36 mm,
einzelne Signalsegmente 0,18 mm. Bus-Direktiven werden nicht platziert;
die Busmitgliedsnamen erhalten für das spätere Auffächern passende
Netzklassenmuster in der Projektdatei. Nach dem Auffächern kann KiCad die
zugewiesenen Klassen anzeigen.
Explizite KiCad-Vorgaben können am Signal in `attributes.ecad.kicad` stehen,
beispielsweise `netClass` und `constraints.clearanceMm` oder
`constraints.trackWidthMm`. Weitere unterstützte Maße sind
`viaDiameterMm`, `viaDrillMm`, `diffPairWidthMm`, `diffPairGapMm` und
`diffPairViaGapMm`. Ohne solche Vorgaben werden keine PCB-Maße aus dem
Signaltyp abgeleitet. Netzklassenwerte für Leiterbahnbreiten sind KiCad-Vorgaben
für das spätere Routing; verbindliche Breitenlimits benötigen dann eigene
PCB-Regeln.

Für spätere physikalische Bauteile ist die Referenzvergabe projektweit je
Bauteilpräfix vorbereitet (`R1`, `R2`, `C1` usw.). Eine zugewiesene Referenz
bleibt beim Verschieben zwischen AEs erhalten; Domain und AE stehen separat
im Referenzregister. Im derzeit bauteilfreien Schaltplan werden noch keine
RefDes vergeben.

Die ISD-Felder sind am KiCad-Objekt verborgen, damit sie den Schaltplan nicht
überlagern. Per `E` bzw. **Eigenschaften** sind sie einsehbar. Der Alias bleibt
der sichtbare Sheet- bzw. Signalname. Ein Netz hat keine einzige Host-Rolle:
die Rolle steht am jeweiligen Anschlusslabel. Bei einer Domain mit beiden Rollen
steht am aggregierten Domainanschluss `Mixed`. Eine manuelle Änderung an diesen
geschützten Label-Feldern wird bei Backward Annotation als Konflikt angezeigt;
eine automatische Umdeutung der Host-/Teilnehmer-Topologie erfolgt nicht.
Sheet-Pins und die Hierarchielabels ihrer Unterseiten tragen passend zueinander
`input`, `output` oder bei gemischten Domainrollen `bidirectional`. Die nativen
Pinbezeichnungen bleiben in den Pin-Eigenschaften; eine einzelne sichtbare
Beschriftung aus dem Pinnamen steht innerhalb des inneren Blockrahmens.
Die Netz- und Busnamen stehen an den Seitenverbindern.
Auf AE-Unterseiten weisen die freien Anschlusspunkte der hierarchischen Labels
zur Blattmitte. Die Wurzelseite enthält eine automatisch erzeugte Farb-Legende
für Domänen und die tatsächlich verwendeten Signalkategorien. KiCad-Dateinamen
folgen der stabilen technischen Domain- und AE-Nummer plus Architekturalias,
zum Beispiel `D02_AE06_Wakeup_und_Shutdown.kicad_sch`.
Einadrige Interfacevorlagen können im Wizard als Signalvektoren variabler
Länge erzeugt werden. Die Anzahl der Mitglieder wird am Link gespeichert;
aus `GPIO_*_IO0` werden `IO0`, `IO1` usw. Bereits selektierte Mitglieder
mehradriger Vorlagen bleiben beim erneuten Laden erhalten.
AE-Farben erben den Farbton ihrer Domain, da die SPOT-Architektur keine eigene
AE-Farbe speichert. Die Sheet-Füllung wird mit geringer Deckkraft gezeichnet.
Für einen PDF-Layouttest sollte KiCad selbst die Schaltplanseiten als PDF
exportieren; der A4-Druck über einen System-PDF-Drucker skaliert A1/A2/A3 herunter.
Für die native KiCad-Dateiprüfung und ERC muss `kicad-cli` separat installiert sein.

## Bearbeitung und Canvas

Ein Signal im Architektur-Navigator markiert seine vollständige Verbindung
im Canvas. Ein Portklick klappt seine Gruppe auf und zoomt zum Port; das
Stiftsymbol öffnet den Portdialog auch bei projektspezifischen Port Types.
Im Detailbereich steht eine SHA-256-Kennung; die interne Referenz-ID bleibt
stabil und schreibgeschützt. Neue Objekte erhalten direkt SHA-256-IDs.
Für alle Objekte gibt es im Detailbereich die Aktion **Alle
Felder bearbeiten**. Sie erlaubt die Bearbeitung der Modellfelder und
Metadaten mit Projektvalidierung; bestehende Objekt-IDs bleiben fest.
Beim JSON-Import wird der **Startkontext des importierten Projekts** als
Pflichtauswahl angeboten und die Übernahme erst danach aktiviert.

## Weiterführende Unterlagen

- Vollständige Funktionsbeschreibung: `docs/HANDBUCH_ISD_SUITE.md` oder **Doku** in der Anwendung. **Hilfe** öffnet dieselben Kapitel passend zum Arbeitsbereich.
- Module und Datenregeln: `docs/ARCHITEKTUR.md`.
- Änderungsverlauf: `changelogs/`.
- Tests einschließlich UI: `python -m pip install -r requirements-test.txt`, danach `python -m pytest -q`; Canvas: `node tests/test_canvas_selection.js`.

## v0.39.0 · Projektbasierte KiCad Back Annotation

Im HW-Arbeitsraum **ECAD-Konnektor → Backward Annotation** öffnen und eine
`.kicad_pro` auswählen. Änderungen zuvor in KiCad speichern. Domänen, AEs,
Ports, Netze und Busmitglieder werden über stabile Kennungen abgeglichen.
Unverbundene Anschlüsse bleiben Ports ohne Verbindung. Bei alten Projekten
`isd_kicad_bindings.json` im Projektordner belassen. Details stehen im
integrierten Handbuch, Kapitel ECAD-Konnektor.

## v0.39.1 · Architektur aus bestehendem Schaltplan

Neues ISD-Projekt mit leerer HW-Architektur anlegen. Unter **ECAD-Konnektor →
Backward Annotation** den Modus **Architektur aus Schaltplan erstellen** wählen.
Die SCM-Blattebenen Domänen/AEs zuordnen, `.kicad_pro` bzw. Projekt-ZIP einlesen
und die Vorschau übernehmen. Eine vorherige ISD-Zuordnung ist nicht erforderlich.
Unklare HOSTs können in der Vorschau ausgewählt oder zunächst offen gelassen werden.
Die originalen KiCad-Dateien bleiben unverändert; Folgeimporte aktualisieren die
Architektur über stabile Kennungen. Details und Grenzen stehen im Handbuch.

## v0.40.0 · Gemeinsame Architektur

**Architektur** bündelt System, Hardware/ECAD, Mechanik/CAD und SW/FW.
Die bisherige HW-Architektur bleibt vollständig erhalten. Unter **HW / ECAD**
stehen jetzt die technischen Realisierungen mit Varianten und Bauteilauswahl.
Systemelemente werden ausdrücklich mit AEs und disziplinspezifischen
Realisierungen verknüpft; es wird keine Zuordnung aus bloßen Namensähnlichkeiten
angelegt.

Architekturobjekte besitzen **Anforderungsattribute** und
**Realisierungsattribute** mit derselben unveränderlichen Objekt-ID.
Bestehende freie Eigenschaften bleiben erhalten. Die Oberfläche bietet
Anforderung, Realisierung und Vergleich; technische Zuordnungen sind geschützt.

Der ECAD-Konnektor verknüpft auf expliziten Aufruf bestehende Projekte oder
legt ein neues aktives Projekt an. Änderungen werden in separaten maximierten
Prüffenstern angeboten. Forward in ISD-generierten Projekten erhält native
Schaltplanobjekte. Bei nativen Projekten werden Blattzuordnungen bestätigt;
Änderungen an deren Block-/Verdrahtungsstruktur werden im Schaltplan ausgeführt
und zurückgelesen. Es erfolgt keine automatische Überschreibung von
Anforderungswerten durch ECAD.

Optionale Entwicklerprüfungen:

```powershell
python -m pip install -r requirements-test.txt
python -m pytest -q
node tests/test_canvas_selection.js
```

Details und Grenzen: `changelogs/CHANGELOG_v0.40.0.md` und integriertes Handbuch.

## v0.42.0 · Attribute, Facharchitekturen und Requirementskette

Der **Property Manager** enthält Attribute und Netzklassen. Die Übersicht zeigt verständliche Beschreibungen und einen Objekttypfilter. Ein Klick öffnet die vollständige Definition in einem Detailfenster. Systemattribute sind geschützt; eigene Definitionen können innerhalb ihrer vorhandenen Werte bearbeitet werden. Objektwerte bleiben getrennt nach Anforderung und Realisierung. Fachlich unpassende Felder, Speed- und Power-Klasse werden nicht mehr angeboten. Dropdowns verwenden feste Werte, Projektkataloge oder Rollen zum Schnittstellentyp. Alte Werte bleiben im SPOT erhalten.

Netzklassen haben sprechende Namen ohne ISD-Präfix und beschreiben ihren Einsatzbereich. **POWER_SUPPLY**, **POWER_LOAD**, **POWER_SWITCHING**, **POWER_SENSE**, **POWER_RETURN** und **GROUND** unterscheiden die Funktionen der Leistungspfade. Eindeutige Vorlagenrollen erhalten automatisch eine passende Klasse; bestehende Zuweisungen bleiben erhalten. **Netzzuordnungen prüfen** zeigt die Abdeckung jedes Einzelnetzes und Busmitglieds und lässt offene Fälle per Dropdown zuordnen. Ein absichtlich geleerter Wert bleibt offen. Constraints und Design Rules werden im ECAD-Tool ergänzt und bei der Annotation erhalten. Umbenennungen behalten die Klassenkennung; ECAD-Dateien ändern sich erst nach überprüfter Annotation. Unbenutzte alte Low/Mid/High-Vorgaben werden entfernt; benutzte oder konfigurierte Altkategorien bleiben als eigene Klassen erhalten.

Mechanik- und Softwarearchitektur enthalten eigenständige Elemente und Beziehungen mit CRUD, Hierarchie, Requirementsbezug, Systemzuordnung und Verweisen auf konkrete Realisierungen. Bestehende Realisierungen können ausdrücklich in Architekturblöcke übernommen werden. Die Hardwarearchitektur bleibt die elektrische ECAD-Schnittstelle.

Die Requirementsgrafik zeigt L1–L4, Architekturverantwortung, Realisierungen und Bauteile/Module. **Vollständige Requirementskette** öffnet einen fokussierten Review von Quellen bis zu Ergebnisbelegen. Gemeinsame Beziehungsauswertung für Grafik, Status und Export; Zyklen werden auch über historische Beziehungsformen hinweg abgewiesen. Erfüllungsbewertungen berücksichtigen Umsetzungsabhängigkeiten. Neue Testnachweise speichern bei ausdrücklicher Bestätigung den geprüften Objektstand. Änderungen kennzeichnen Nachweise als prüfbedürftig; bestehende Reports werden erhalten. Alte Nachweise ohne Objektstand gelten nicht automatisch als aktuell.

**Architektur-PDF** exportiert eine oder mehrere der vier Sichten mit eigenen Seiten, Legenden, Beziehungen und anklickbaren Details.

Handbuch, integrierte Hilfe und `changelogs/CHANGELOG_v0.42.0.md` beschreiben Bedienung, Migration und Grenzen. Automatische Übersetzung von Anforderungen in PCB-Regeln, Ein nativer KiCad-Buscontent-Wizard bleibt zurückgestellt; die FE-Abstraktion ist ab v0.43.0 umgesetzt.


## v0.43.0 · Objektattribute, FE, Kernbauteile und Requirements-Fokus

- Attribute, Dropdowns und Abhängigkeiten folgen Objekttyp und Requirement-Disziplin. Legacy-Aliaswerte werden verlustarm normalisiert; die Objektkennung erscheint einmal pro Objekt.
- FE werden aus dem KiCad-Projekt prüfbar zurückgelesen und in Architektur und Realisierung angezeigt. Konkrete Technologie bleibt bei systemdefinierenden Bauteilen mit MPN, Alternativen und revisionsbezogenen Dokumentquellen.
- Bauteilqualifikation vergleicht die konkrete Normausgabe und den geprüften Bauteil-/Dokumentstand. PLM-/ERP-/DMS-Referenzen sind erfassbar; automatische Fremdsystem-Synchronisation bleibt ausstehend.
- Eine ausdrückliche BOM-CSV liest die vollständige SCM-Hierarchie einschließlich DNP und zählt mehrteilige Symbole einmal. Der Export benennt den aktuellen Schaltplanstand; separate Bestückungsvarianten werden nicht interpretiert.
- Die Requirements-Grafik trennt Kartenwahl von Abhängigkeitsfokus, zeigt kompakte Karten und gemeinsame Details und führt kleinere Pfeile horizontal an die Karten.
- KI verwendet den fachübergreifenden Modellkontext; Integrationen öffnen eine auswählbare Änderungsvorschau mit Konfliktprüfung. Die initiale Dokumentanalyse bleibt direkt als Detected-Arbeitsstand verfügbar.
- Handbuch und Hilfe nutzen einen Kapitelnavigator mit Volltextsuche und markierten Treffern.
- Die Hardware-PDF ergänzt eigene FE-Detailseiten mit vollständiger Funktionsbeschreibung, Schnittstellen und Abhängigkeiten.

Bedienung und Grenzen stehen in `docs/HANDBUCH_ISD_SUITE.md`, Kapitel 32–34,
und `changelogs/CHANGELOG_v0.43.0.md`. Vor Nutzung an bestehenden Daten eine
Projekt-JSON-Kopie beziehungsweise eine Repository-Revision sichern.


## v0.44.0 · Schlanke Architektur, Vergleich und Fachschnittstellen

Domänen, AEs, Ports, Netze und Busse haben objektbezogene Kerneigenschaften.
Technische Vorgaben bleiben am Requirement, belegte Werte an der Umsetzung;
der eingeklappte Vergleich zeigt relevante Soll-/Ist-Zeilen mit Quellen,
Bedingungen und Nachweisstatus. Bestehende technische Architekturwerte bleiben
als prüfbare Bestandsangaben erhalten. Ports und Verbindungsauswahl zeigen die
wirksamen Netzklassen einschließlich gemischter Busmitgliedsklassen.

HSI und HW-Mechanik-Schnittstellen verbinden die Disziplinen explizit. FE sind
auch für Software/Firmware und Mechanik verfügbar. Konkrete Realisierungen
führen Code/Commit, Package, Bootloader, Build/Firmwareartefakt beziehungsweise
CAD/PLM/Teilrevision und Alternativen. ECAD-Hierarchieanschlüsse berücksichtigen
die Mitgliedsrichtungen; unbekannte Fälle bleiben passiv und offen.

Bearbeiten öffnet die jeweilige Eingabemaske. Hilfe bietet kurze kontextbezogene
Schritte; Doku das vollständige durchsuchbare Handbuch. Details und Prüfgrenzen
stehen in `docs/HANDBUCH_ISD_SUITE.md`, Kapitel 35–38, und
`changelogs/CHANGELOG_v0.44.0.md`.

## v0.45.0 · Sichtbare Attribute und klare Requirement-Navigation

Die HW-Details zeigen alle passenden Attribute einschließlich **Offen**. Netzklassen
lassen sich auch vom Port oder der Verbindung erreichen; Busmitglieder können eigene
Klassen erhalten. Die HW-Realisierungsansicht ordnet Architektur, FE, Umsetzung,
aktive Variante und Kernbauteile zu. Software-/Mechanikumsetzungen zeigen ihren
Architekturbezug.

Requirements starten als lesbare Liste mit L1→L2-Verweisen. Anforderungskette und
Gesamtübersicht werden ausdrücklich gewählt. Kundenentscheidung, Prüfstand und
Erfüllung bleiben getrennt. **Architektur aus Requirements erzeugen** verwendet eine
bestätigte Auswahl und Zielarchitekturen mit anschließender Vorschlagsprüfung und
Prüfung auf einen geänderten Projektstand. Hilfe bezieht sich auf die aktuelle
Anzeige, Auswahl und Eingabemaske. Anleitung: Handbuch Kapitel 39–40.

## v0.46.0 · Konsolidierung und Paketvarianten

Für den Betrieb verwenden Sie **ISD_Suite_Web_MVP_v0.46.0.zip**. Das
**Developer-ZIP** enthält zusätzlich Tests, Build-/Benchmarkwerkzeuge und die
vollständige Dokumentationshistorie. Beide enthalten dieselbe ausführbare Suite.

Fachmasken, Dokumentanalyse, Assistent, Quellen und Architekturübernahme sind von
den zentralen Controllern getrennt. Attribute werden indiziert geprüft; gemeinsame
Schema-Dateien und unveränderliche Handbuchkapitel werden wiederverwendet.
Projektformat und bestehende IDs bleiben erhalten. Details im Handbuch Kapitel 41
und in `docs/ARCHITEKTUR.md`.

Entwicklerprüfungen: `python -m pytest -q`, `python -m pyflakes architecture_app`
und `node --test tests/test_canvas_selection.js tests/test_requirements_routes.js`.
Releasebau: `python scripts/build_release.py --output-dir dist`.

## v0.48.0 · KiCad-Korrekturstand

Projektanlage und ZIP-Export öffnen wieder das separate Prüffenster. Der
Netzklassenkatalog wird als Projekteinstellung behandelt; die Erstellung stoppt
nicht mehr beim Durchlaufen der Klassenliste. Fehler sind sichtbar.

Netzklassenzuweisungen berücksichtigen eigene Mitgliedsklassen, Bus-Standards
sowie unqualifizierte und hierarchische Netznamen. Bestehende KiCad-Regeln bleiben
beim geprüften Forward-Abgleich erhalten. Fehlende Bus-Aliase dürfen vollständige
Businhalte bei der Backannotation nicht auf ein einzelnes Busnamenssignal reduzieren.
Kontexthilfe und Handbuchkapitel 42 beschreiben den vollständigen Ablauf.

## Neuer Stand v0.48.0

Realisierung → HW / ECAD: Kontextauswahl mit Part View, Architekturfilter und Details rechts.
Masse wird auf Funktionsebene global genutzt; Domänen mit internem Host behalten den Anschluss rechts.
Details im Handbuch, Kapitel 43 und 44.

Neu: gemeinsamer Realisierungsfokus, direkte Requirement-Listen und getrennte KiCad-Legenden unten rechts. Siehe Handbuch Kapitel 45.

## Neuer Stand v0.49.0

FE führt die Realisierung; Implementierungen und aktive Varianten bleiben darunter
referenzierbar. Property Manager und Objektanzeigen nutzen einen gemeinsamen
Feldkatalog mit sichtbaren offenen Angaben, objektbezogenen Attributen und
Attributart / Pflegequelle / ECAD-Abbildung. Die Attributmatrix v1.1 und Kapitel 46
des Handbuchs beschreiben die Zuordnung. Native KiCad-10-UI und ERC/DRC wurden
hier nicht ausgeführt; Projektdatei- und Annotationstests sind separat dokumentiert.

## Neuer Stand v0.50.0: Xpedition über SPOT JSON

Im ECAD-Dialog ist **Xpedition** auswählbar. Bestehende `.prj` ausdrücklich verknüpfen oder ein neues Projekt mit Zentralbibliothek / Vorlage / Server über COM anlegen. Forward und Backward Annotation nutzen getrennte Prüffenster, Dreiwegevergleich und stabile ISD-/native Identitäten. Ein lokaler Windows-Connector und eine SPOT-CLI-Bridge für Serverbetrieb sind enthalten; Hilfe und Handbuchkapitel 47 erklären Einrichtung und Testablauf.

COM-Diagnose: `python -m architecture_app.xpedition_cli diagnose --project "C:\Design\Design.prj" --output diagnose.json`. Auf Windows wird pywin32 aus requirements.txt installiert. Alle Funktionen müssen anschließend an der eingesetzten Xpedition-Version verifiziert werden. Ein Testprotokoll aus Testobjekten ist kein nativer Nachweis.

Busmitglieder und Netzklassenvorgaben bleiben erhalten. **Wirksame Constraint-Manager-Klassenzuordnung noch unverified.** Native Löschungen, AE-Verschiebungen und bestehende Netztopologieänderungen werden als nicht unterstützt ausgewiesen. Die Architekturübertragung und der FE-Import umfassen noch keinen physischen BOM-/Part-Import. Siehe Handbuch für den genauen Umfang und die COM-Sicherung.

## Neuer Stand v0.51.0: KI-Provider und Modelle

Dieser Stand enthält v0.50.0 vollständig. Im KI-Konfigurationsdialog sind Claude,
Gemini, Grok, Ollama und weitere API-Anbieter auswählbar. Modellkatalog, manuelle
Modell-ID, strukturierter Verbindungstest und providerbezogene Verbindungshilfe
sind integriert. GitHub Copilot (optionales Python SDK und Runtime) und Microsoft
365 Copilot (delegiertes Graph-Token, Preview) sind getrennte Anbindungen.
Einrichtung und Grenzen: Kapitel 48 des Nutzerhandbuchs. Jeder neue Stand umfasst
alle seit dem vorherigen Stand vereinbarten, nicht ausdrücklich zurückgestellten
Änderungen. Native Xpedition-Nachweise bleiben gemäß Kapitel 47 offen.

## v0.51.1 – Direkt verfügbare Modell- und ECAD-Auswahl

Modellvorschläge bleiben im Dropdown sichtbar, auch nach API-Modellabfragen.
KiCad und Xpedition werden direkt über das Feld ECAD-System ausgewählt.
Beide Dialoge zeigen die laufende Version. Nach dem Update die bisherige ISD
mit Strg+C im Startfenster beenden und den neuen Stand starten; ein Browser-
Reload allein aktualisiert den Server nicht. Details: Handbuch Kapitel 49.
