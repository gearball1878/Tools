# Entwicklerübersicht

## Systemgrenzen und Datenfluss

`main.py` startet NiceGUI und bindet `architecture_app/app.py` ein. Die
Browserseite hält einen `PageState` mit Projektkopie und laufender
Versionsnummer. Fachaktionen verändern das Pydantic-Paket; der
`ArchitectureRepository` speichert es als versionierten SQLite-Stand.
Separate Anhänge enthalten Binärdateien und Extraktionskontexte. Der
vollständige Projekt-JSON-Export umfasst das fachliche Modell, keine
Binärdateien oder Zugangsdaten. Ein Import als Revision prüft zunächst das
Paket und schreibt danach innerhalb einer Transaktion den neuen Stand.

| Modul | Zuständigkeit |
| --- | --- |
| `models.py` | Pydantic-Objekte, IDs, SPOT-Schema und Feldvalidierung alter Daten |
| `repository.py` | SQLite, Revisionshistorie, Importtransaktion und Projekt-IDs |
| `project_import.py` | Projekttypen und bewusste Auswahl bei JSON-Import |
| `project_import_ui.py` | Upload, Vorschau, verpflichtende Typauswahl und Importaktionen |
| `package_preparation.py` | Ein geordneter Durchlauf für Katalog-, Topologie- und Requirements-Vorbereitung |
| `architecture_editing.py` | Validiertes Bearbeiten aller Modellobjekte, Schutz bestehender Objekt-IDs und Projektion abgeleiteter Ports/Verbindungen |
| `signal_naming.py` | Konservative Bereinigung neu erzeugter Namen und Herkunft des Rohwerts |
| `bus_content.py` | Eingebaute Interface- und Signaltemplates; Rohinstanzen |
| `topology.py` | Host, Teilnehmer, Port- und Verbindungssynchronisierung |
| `property_schema.py` / `property_manager.py` | Geschützte und eigene Attributdefinitionen, objektbezogene Geltung, Dropdownquellen und Detailverwaltung |
| `property_schema_v041.json` / `property_schema_v042.json` | Exakter früherer Systemkatalog für eine kontrollierte Migration; keine allgemeine Freigabe beliebig veränderter Systemattribute |
| `netclasses.py` | Semantische Klassen, Mitgliedszuordnungen, Abdeckung und verlustarme Katalogmigration |
| `system_architecture.py` / `discipline_architecture.py` | Vier Fachsichten, eigenständige Mechanik-/Softwarearchitekturelemente, Beziehungen und Systemzuordnungen |
| `requirement_graph.py` | Gemeinsame Ableitungs-, Zuordnungs- und Testkanten über alle gespeicherten Beziehungsformen |
| `traceability.py` | Typisierte Beziehungen, Pfad, Kriterienabgleich, Evidenz und Status |
| `traceability_ui.py` | Separates Prüffenster für die vollständige Requirementskette |
| `requirements_service.py` | Analysekompilierung, Requirements- und Architekturvorschläge |
| `requirements_exchange.py` | ReqIF/Office-Parser und Export samt Formatgrenzen |
| `requirements_exchange_ui.py` | Austauschdialog, Vorschau, Mapping und geprüfte Übernahme |
| `architecture_catalog.py` | Fachliche Klassifikationen und technische Namen |
| `attachment_store.py` | Originale und Kontexte mit Hashpfaden |
| `ai_provider.py` / `analysis_queue.py` | KI-Provider und serverseitige Analyseschlange |
| `development_ui.py` | Mechanik-, Software- und fachliche Interfaceansichten |
| `requirements_ui.py` | Requirements-Arbeitsfläche und fachliche Dialoge |
| `diagram.py` / `architecture_pdf.py` | Architekturvisualisierung und PDF |
| `handbook.py` / `help_ui.py` | Gemeinsame Kapitelquelle, Volltextsuche, Treffer und kontextbezogener Einstieg |
| `docs/HANDBUCH_ISD_SUITE.md` | Detaillierte, funktionsorientierte Referenz |

## Änderungsregeln

Neue Beziehungen mit `traceability.add_relation` validieren; gemeinsame
Requirement-Zuordnungen sind keine impliziten Interfaces. Zuordnung,
bewertete Erfüllung und verifizierter Test bleiben getrennte Objekte.
Vor einer Architekturübernahme wird auf einer tiefen Projektkopie gearbeitet;
nur ein gültiges Modell wird veröffentlicht. Das manuelle Signal-Wizard
sammelt neue Signale vor dem Anhängen, damit Namenskollisionen nicht zu
halb angelegten Signallisten führen. Bereits gespeicherte Namen und IDs
werden durch die Namensbereinigung nicht rückwirkend geändert.

Ältere Projekte bleiben lesbar. Kompatibilitätsregeln an der Modellgrenze
und im einen Vorbereitungsschritt pflegen; keine neue UI-spezifische
Nachkorrektur hinter Speichern oder Import einbauen. Eine Änderung an einem
alten Datenstand darf fehlende Evidenz nicht nachträglich erfinden.

Tests einschließlich UI: `python -m pip install -r requirements-test.txt`,
danach `python -m pytest -q`. Canvas: `node tests/test_canvas_selection.js`.

Seit v0.42.0 werden gespeicherte Parent-IDs, RequirementDerivations und
`derived_from`-Modellbeziehungen gemeinsam ausgewertet. Parent → Child ist
die Leserichtung; die Modellbeziehung speichert Child → Parent. Zyklen werden
über alle Repräsentationen geprüft. Ein bewusster Ebenensprung benötigt eine
Begründung. Architekturzuordnung, Erfüllungsbewertung und Test bleiben
unterschiedliche fachliche Aussagen.

Bewertungen und bestätigte Testnachweise speichern Fingerprints des geprüften
Requirements, der Architektur und ihrer explizit referenzierten Umsetzung.
Ausgewählte Varianten und Bauteile/Module gehören zu diesem Stand. Eine
Änderung macht den Nachweis prüfbedürftig, ohne den Bericht zu löschen.
Beim ausdrücklichen Löschen eines Objekts werden dessen aktuelle typisierte
Beziehungen und zugehörige Bewertungen mit entfernt; frühere Repository-
Revisionen enthalten den vorherigen Stand.

Mechanik- und Softwarearchitekturelemente sind von konkreten Realisierungen
getrennt und referenzieren sie über IDs. Die explizite Bestandsübernahme
erzeugt neue Architekturkennungen. Netzklassen gelten an elektrischen Netzen
und Busmitgliedern; Ports zeigen die Klasse des angeschlossenen Netzes.
Klassenumbenennungen aktualisieren die ISD-Zuweisungen. Der synchronisierte
ECAD-Baseline bleibt bis zur geprüften Annotation unverändert, damit die
Umbenennung im Prüffenster sichtbar wird und native Regeln erhalten bleiben.

Der Canvas rendert die Kanten mit `signalId` als DOM-Attribut.
`xpedHighlightCanvas` selektiert deshalb alle grafischen Verbindungszüge
zu einem ausgewählten Architektur-Signal, auch bei mehreren Ästen.
Templategebundene Objekte können projektspezifisch angepasst werden;
`manualDefinitionOverride` erhält eine bewusste Anpassung beim Laden.
Für abgeleitete Ports werden abweichende Bezeichnung, Port Type und Seite
als explizite manuelle Werte gespeichert. Die Topologie bleibt aus dem
übergeordneten Signal abgeleitet.


## Ergänzungen in v0.43.0

`requirement_profiles.py` definiert disziplinspezifische Kategorien,
Attributgeltung, zulässige Beziehungspartner und Vorgänger. UI und
KI-Änderungen verwenden dieselben Regeln. Legacy-Werte außerhalb der aktiven
Definition werden archiviert; frühere geschützte Katalogdefinitionen werden
nur anhand der exakten v0.41-/v0.42-Snapshots migriert.

`FunctionElement` ist die abstrahierte ECAD-Funktionsgrenze und referenziert
AE, Requirements, Schnittstellen und andere FE. `TechnicalRealization`
referenziert das FE und enthält Varianten; `DesignComponent` hält Technologie,
explizite Systembedeutung und Alternative-IDs. Eine Variante erlaubt mehrere
Kernbauteile. `realization_service.py` filtert die Systemdarstellung und
bewertet revisionsbezogene Bauteilqualifikation. Die Normausgabe und
Fingerprints von MPN/Package/Revision und Quelldokumenten müssen zur
festgehaltenen Prüfung passen. Verifikationsfälle bleiben davon getrennt.

`ecad_functional.py` liest ausschließlich das verknüpfte Projekt und dessen
Blätter, bietet FE-/Kernbauteil-Deltas an und erzeugt die vollständige BOM-CSV.
`ecad_functional_links.py` verarbeitet explizite Blattpin-Verbindungen;
unklare Grenzen werden nicht durch sämtliche äußeren AE-Signale ersetzt.
`functionalSourceBaseline` hält die geprüften ECAD-Ausgangswerte für den
Dreiwegevergleich unabhängig vom bearbeiteten ISD-Modell. Ausgelassene Deltas
werden bei erneuter Prüfung wieder angeboten. Ein Entfernen im ECAD erhält
Bauteilhistorie, kennzeichnet den aktuellen Bestand und ändert die beobachtete
Variante. Symbol-Instanzreferenzen und Multi-Unit-Deduplizierung verhindern
falsche BOM-Mengen.

`ai_context.py` erzeugt den gemeinsamen typisierten Graphen samt Definitionen,
aktuellem Nachweisstand und ausdrücklich gekennzeichneten Kontextgrenzen.
`reviewed_delta.py` kompiliert KI-Integrationen auf einer Kopie und hält einen
Hash des Ausgangspakets. Die atomare Übernahme validiert den ausgewählten
Modellstand; konkurrierende Änderungen verhindern eine veraltete Übernahme.
Initiale Dokumentanalysen benötigen keine zusätzliche Kandidatenfreigabe.

`requirements_layers.focused_graph` berechnet Vorfahren und Nachfahren
getrennt, sodass Geschwisterzweige außerhalb des gewählten Strangs bleiben.
Die Kartenwahl zeigt ausschließlich Details; der Fokus wird explizit gewählt.
`vendor/requirements_graph.js` verwendet tatsächliche Kartenränder, separate
Anschlussstellen, horizontale Endsegmente und untere Umfahrungen.
Zusätzliche Routingprüfung: `node tests/test_requirements_routes.js`.

Leere neue Felder ändern vorhandene v0.42-Objektfingerprints nicht. Die
Abhängigkeitsprüfung berücksichtigt zusätzlich FE, funktionale Schnittstellen
und Bauteilquellen. Bisher nicht erfasste Nachweisabhängigkeiten führen zur
erneuten Prüfung. `tests/fixtures/v042_reviewed_objects.json` enthält dafür
echte v0.42-Exportstände. Der Economy-Kontext priorisiert Requirements und
Architektur vor Detailbauteilen und kennzeichnet jede Kürzung.

`architecture_pdf.py` ergänzt abstrahierte FE-Detailseiten mit umbrochenen,
vollständigen Funktionsbeschreibungen und internen AE-/FE-Verknüpfungen.
Konkrete MPNs gehören weiterhin in den Realisierungskontext.


## v0.44: Verantwortung, Umsetzung und Schnittstellen

`ArchitectureAttributes` enthält weiterhin zwei Attributräume. Für
Architekturobjekte werden Systemdefinitionen auf Aufgabe, ECAD-Key und
Netzklassenzuordnung begrenzt. Native Felder enthalten Name, Beschreibung,
Typ und Referenzen. `property_schema_v043.json` sichert den exakten vorherigen
Systemkatalog; gefüllte entfallene Werte werden verlustfrei archiviert.

`FunctionElement.discipline` trennt HW, SW/FW und Mechanik. Parent-, Interface-
und Realisierungsreferenzen werden disziplinspezifisch geprüft.
`IntegrationInterface` beschreibt HSI oder HW-Mechanik mit typisierten
Referenzlisten und separater Implementierungskonfiguration.
`TechnicalValue` gehört einer konkreten Umsetzung und führt optional ein
Architekturziel, Variante, Einheit, Bedingungen, Herkunft und Revisionsquellen.

`technical_comparison` liest explizite Requirementzuordnungen und konkrete
Realisierungsquellen; `comparison_ui` zeigt das Ergebnis eingeklappt.
`architecture_bindings_ui` ergänzt Quellzuordnungen in den Objektmasken.
`integration_ui` wird von Architektur und Fachrealisierung verwendet. Registry,
Requirementsgraph, KI-Kontext, Löschbereinigung und Review-Snapshots berücksichtigen
die neuen Referenzen. Eine numerische Passung ersetzt keine Bewertung.

`ecad_pin_mapping` leitet hierarchische Formen aus expliziten oder eindeutigen
Vorlagenrichtungen ab. Offene Fälle bleiben passiv; tatsächliche Symbolpintypen
werden nicht umgeschrieben. KiCad-Metadaten führen technische Quellwerte und
Mappingstatus. `help_ui` enthält kompakte Kontextschritte; `handbook` navigiert
und durchsucht das vollständige Handbuch.

## Konsolidierter Aufbau ab v0.46.0

Der Seitencontroller verbindet Fachansichten über explizite Callbacks.
Fachmodule greifen auf den aktuellen Projektstand über `package()` zu; sie
halten keine zweite Projektkopie als unabhängige Datenquelle. Bestehende Service-
Importpfade bleiben als klar gekennzeichnete Weiterleitungen verfügbar.

| Modul | Verantwortung |
|---|---|
| `app.py`, `requirements_ui.py` | Seitenzustand, Navigation, Speichern und Zusammenstellung der Arbeitsräume |
| `architecture_masks_ui.py`, `catalog_ui.py` | HW-Objektmasken und Signal-/Buskatalog |
| `requirements_edit_ui.py` | Requirements, Abhängigkeiten, Konflikte und Bewertungen |
| `realization_dialogs_ui.py` | FE, Bauteile, Realisierungen und Varianten |
| `technical_sources_ui.py` | Revisionsbezogene Datenblatt-/Nachweisquellen |
| `document_analysis_ui.py`, `assistant_ui.py` | Dokumenteingang, Kontextwiederherstellung und geprüfte KI-Aktionen |
| `requirements_presentation.py`, `ui_assets.py` | Gemeinsame Beschriftungen, Browserstile und Integration |
| `interface_compilation.py`, `architecture_compilation.py` | Kataloggebundene Schnittstellen und atomare Architekturübernahme |
| `models.py`, `model_validation.py` | Objektschema, Altformatvalidierung und projektweite Referenzintegrität |
| `property_schema.py` | Definitionen, isolierte Systemvorlagen und indizierte Attributvalidierung |
| `handbook.py` | Unveränderliche Kapitel, Suche und versionsbezogen invalidierter Inhaltscache |
| `scripts/build_release.py` | Explizite, reproduzierbare Paketdateiauswahl und Inhaltsmanifest |
| `scripts/benchmark_project.py` | Wiederholbare Messung ohne Schreibzugriff auf Projektdaten |

Caches halten ausschließlich gebündelte Schema-Vorlagen und unveränderliche
Handbuchkapitel. Veränderliche Projektobjekte werden nicht projektübergreifend
gecacht. Modell-, Konflikt- und Speicherprüfungen bleiben erhalten. Ein
Releasebau nimmt keine Arbeitsverzeichnisse, Datenbanken, Credentials oder
installierten Python-Pakete auf. Tests und Versionshistorie bleiben im
Entwicklerpaket; beide Pakete enthalten denselben Anwendungscode.

Beim zentralen Speichern aktualisiert jeder Fachcontroller seine Arbeitsräume.
Die gemeinsamen Navigations-/Detailbereiche werden anschließend einmal gerendert.
Eigenständige Fachaktionen verwenden weiterhin die vollständige Aktualisierung.

### KiCad-Korrekturen v0.46.1

`ecad_ui.new_project_preview` verarbeitet Objektabbildungen und Netzklassenkatalog
separat. Die gemeinsame Annotation-Ansicht wird im Clientkontext angelegt und
trägt einen eigenen Hilfekontext. `kicad_rules.project_settings` projiziert die
wirksamen Klassen pro Netz/Busmitglied auf exakte und hierarchische Muster.
`kicad_project_readback` löst direkte Bus-Aliase auf und verwirft eine mehrdeutige
Reduktion eines bekannten Mehrsignalbusses auf dessen eigenen Namen vor jeder
Projektmutation. Vorhandenes Dreiwege-Merging für ECAD-Regeln bleibt maßgeblich.

### Kontextprojektion und globale Masse v0.47.0

`realization_focus.focus_projection` projiziert vorhandene Domänen, AEs, FEs,
Realisierungen, aktive Varianten, Kernbauteile und zugeordnete Requirements.
Es werden keine Fachobjekte dupliziert. `RealizationFocus` hält pro Client
Kontext, Architekturfilter, Suche und Auswahl; ein Projektwechsel verwirft
ungültige Referenzen. `realization_focus_ui` nutzt die gemeinsamen linken und
rechten Panels der Anwendung. Explizite Verwaltungsaktionen verwenden die
bestehenden Eingabemasken und Quellen-/Qualifikationsdialoge.

`hardware_topology` enthält die gemeinsamen Sichtbarkeitsregeln für Masse und
die Host-priorisierte Domänenrolle. Die Architekturprojektion und der PDF-Export
unterdrücken Masse-Blockports und deren Linien ohne die SPOT-Objekte zu löschen.
KiCad erzeugt globale Labels auf den funktionalen Blättern und überträgt ihre
Netzklassen in die Projektdatei. `globalSignalIds` im Manifest kennzeichnet
absichtlich nicht als Blattanschluss exportierte Netze. Backannotation bewahrt
zugehörige alte Portzuordnungen; die Archivprüfung behandelt deren fehlende
Blattpins nicht als getrennten Host. Domänenpins verwenden die aus AEs abgeleitete
Host-/Teilnehmerrolle; tatsächliche AE-Endpunktrollen bleiben erhalten.

Die Darstellungsregel wird als `blockTopologyPolicy` im Manifest versioniert.
Bei der Umstellung älterer Projekte verwendet die Forward-Prüfung die bisherige
Regel zur Rekonstruktion der Vergleichsbasis. Ursprüngliche Verbindungskennungen
und Endpunktreihenfolgen werden dafür aus den Exportmetadaten wiederhergestellt.
Ein vorhandener ECAD-Konflikt bleibt ein explizit zu prüfender Konflikt.


## v0.48.0: Fokus als gemeinsamer Bezugsrahmen

RealizationFocus trennt focus_id (Dossier) von selected_id (rechte Details).
focus_projection liefert dieselben Objektmengen für alle Kontextdarstellungen.
Direkte Requirements nutzen allocation_edges ohne Ableitungstraversierung;
Architekturverantwortung wird nicht als Realisierungszuordnung interpretiert.
Kontext steuert Reihenfolge und Expansion, nicht den Bestand des Dossiers.
KiCad legendPolicy split-bottom-right-v1 speichert die Darstellungsfassung.
Die Forward-Baseline rekonstruiert alte kombinierte Legenden über legacy,
wodurch die Dreifachzusammenführung die Darstellung gezielt aktualisieren kann.


## v0.49.0: gemeinsamer Feldkatalog und FE-Zuordnung

object_properties beschreibt native Felder des Modellkatalogs als geschützte,
virtuelle Definitionen. storage=native wird nicht in property_definitions oder
Objekt-Attributwerte geschrieben. Dieselben Deskriptoren liefern Property Manager
und Objektanzeigen. Dictionary-Attribute besitzen zusätzlich attribute_kind,
authority, ecad_target und ecad_mapping. Systemdefinitionen werden exakt geprüft;
nur unveränderte ältere Kataloge einschließlich v048 werden migriert.

function_migration gehört zur geordneten package_preparation. Kennungen neuer
FEs werden deterministisch aus den retained Implementierungs- oder AE-Kennungen
abgeleitet. Hardware-Variantencontainer bleiben referenzierbare Datensätze unter
dem FE. Vorhandene inverse und gemeinsame FE-Zuordnungen bleiben erhalten.
Explizit aufgehobene Zuordnungen kennzeichnet feAssignmentOpen; wiederholtes
Öffnen darf daraus keine neue Funktion erzeugen.

technical_comparison erhält Quellenkennung und Bedingungen für offene und gefüllte
Felder. Direkt dem FE und seinen Implementierungen zugeordnete Vorgaben werden
zusammengeführt, ohne Requirement-IDs oder ursprüngliche Zuordnungen zu ändern.
Technische Bestandswerte behalten ihren alten Attributraum und Prüfflag.

## Xpedition Connector (v0.50.0)

`xpedition_exchange.py` projiziert die Hardwareobjekte der SPOT JSON in interne Objektkarten und berechnet einen feldweisen Dreiwegevergleich. Dies ist kein zusätzliches persistentes Projektformat. Ausgewählte Änderungen werden als vollständiges SPOT-Paket validiert; nur tatsächlich gemeinsame Werte aktualisieren die Baseline.

`xpedition_connector.py` implementiert die ECAD-Connector-Schnittstelle, explizite Projektverknüpfung, Anlage, Vorschau und Anwendung. `xpedition_com.py` kapselt den Windows-Zugriff über die installierte ViewDraw-Typbibliothek, STA-Lebensdauer, native Identitäten, Symbolpin-Inventar unabhängig von Verbindungen, Hierarchieblöcke, Netzsegmente und Projekt-Buscontent. Objektmetadaten (`ISD_ID`, `ISD_KIND`, `ISD_SPOT`) erhalten ISD-Identität und Attribute; Namen und Topologie werden beim Rücklesen aus nativen Objekten ermittelt. Eine Kopie `ISD_SPOT.json` im ECAD-Projekt ist keine Quelle für beobachtete Schaltplanänderungen.

`xpedition_ui.py` ergänzt die ECAD-Auswahl und verwendet die gemeinsame Annotation Review mit eigener kontextbezogener Hilfe. `xpedition_cli.py` bildet die lokale SPOT-Bridge für eine entfernte ISD ab. Prüfdokumente sind temporär; die Apply-Operation akzeptiert nur Entscheidungen für eine frisch neu berechnete, identische Vorschau.

Native Schreiboperationen sichern das Projekt und verifizieren die angeforderten Werte durch COM-Rücklesen. Bei Teilfehlern wird die Sicherung angegeben, keine erfolgreiche Baseline fortgeschrieben und kein automatischer Restore in eine aktive Anwendung durchgeführt. Löschungen, bestehende Neuverdrahtung und Hierarchieverschiebung werden vor Änderungen abgewiesen. Die Constraint-Manager-Integration ist explizit unverified; ein `ISD_NETCLASS`-Attribut darf nicht als angewendete CM-Klasse ausgegeben werden. Physische BOM/Part-Importe sind noch nicht Teil dieses Connectors.

## v0.51.0 – Gemeinsamer KI-Workflow und Provideradapter

`ai_catalog.py` definiert Fähigkeiten, Endpunkte, Umgebungsvariablen und
Verbindungshilfe. `ai_ui.py` hält die Providerkonfiguration bis zur Übernahme
als Entwurf; Katalog und Inferenztest verwenden diesen Entwurf.
`ai_provider.py` behält gemeinsame Prompts, ISD-Regeln, Schema-Validierung,
Kontextprofil und Cache. `ai_transports.py` übersetzt native Claude-Inhalte und
führt optional GitHub Copilot über dessen SDK aus. Andere Anbieter nutzen die
bereits vorhandene OpenAI-kompatible JSON-Schnittstelle. Modellkataloge sind
accountabhängig, kein festes vollständiges Modellinventar. Geheimnisse werden
nur beim gleichen Provider und Endpunkt wiederverwendet; kein SPOT-Secret.

## v0.51.1 – Auswahlzustand und ECAD-Dialogwechsel

`ai_catalog.model_options` vereinigt dokumentierte Vorschläge mit API-IDs und
der gespeicherten/aktuellen Modellwahl. `ai_ui` aktualisiert die Optionen über
`set_options`, so dass die Auswahl und die serialisierten Browseroptionen
konsistent bleiben. Vorschläge implizieren keinen Accountzugriff.
`ecad_ui.ecad_system_selection` wird von beiden ECAD-Dialogen genutzt und öffnet
den gewählten Dialog im unabhängigen Client-Kontext. Der vorherige Dialog wird
gelöscht; der Ansichtswechsel verknüpft kein anderes Projekt. Versionsanzeigen
in beiden Dialogen identifizieren den tatsächlich laufenden Serverstand.
