# ISD Suite – Funktionshandbuch


Stand: v0.51.1. **Doku** öffnet das Nutzerhandbuch mit Kapitelnavigator und
Volltextsuche. **Hilfe** nutzt dieselben Kapitel und öffnet den passenden
Arbeitsbereich. Die folgenden Kapitel
beschreiben die Datenobjekte, Aktionen, Vorbedingungen, Ergebnisse und Grenzen
für den regulären Betrieb. Die ISD Suite ist eine lokale, browserbasierte
Arbeitsumgebung. Der Browser ist die Oberfläche; die Anwendung und die
SQLite-Datenbank laufen auf dem gestarteten Rechner.

## 1. Orientierung und gemeinsame Bedienregeln

### 1.1 Kopfzeile und Arbeitsräume

Die Projektauswahl in der Kopfzeile bestimmt, auf welchen Stand sich alle
Arbeitsräume beziehen. Daneben liegen Projektprofil, vollständiger JSON-Export,
JSON-Import, neues Projekt, Projektlöschung, Administrations-PIN,
KI-Konfiguration, Assistent, Hilfe, Dokumentation, Revision und Historie.
Der darunterliegende Arbeitsbereich gliedert sich in Prozessübersicht,
Quellen & Analyse, Requirements, Architektur, HW / ECAD, Mechanik / CAD,
Software / Firmware und Normen & Standards. Beim ersten Öffnen eines Projekts
führt ein Requirements-orientiertes Profil zur Prozessübersicht, der direkte
Architekturstart zum Architekturarbeitsraum.

Links steht ein zum Arbeitsraum passender Navigator, in der Mitte die
Bearbeitungsfläche und rechts der Inspektor. Eine Auswahl im Navigator oder
in der Grafik fokussiert ein Objekt; die Inspektor-Aktionen gelten für dieses
Objekt. Suche und Filter ändern die Sicht auf das Modell und löschen keine
Objekte. Die Revision in der Kopfzeile legt einen benannten Zwischenstand an;
automatisches Speichern erhöht den laufenden Projektstand.

### 1.2 Projekt anlegen und Profil wählen

Beim Anlegen sind Name und Projekttyp auszuwählen. Der Name muss innerhalb der
lokalen Installation eindeutig sein. Ein Start mit Beispielarchitektur ist
optional. Die vier Profilarten sind direkter Architekturstart, integrierte
Entwicklung mit Requirements, Redesign und Studie/Prototyp. Das Profil lenkt
Hinweise und fachliche Prüfungen; alle Arbeitsräume stehen weiterhin zur
Verfügung. Ein späterer Wechsel erfolgt über **Projektprofil** in der
Kopfzeile und verlangt eine Begründung. Die Wechselhistorie bleibt am Projekt.
Das Ändern des Typs erzeugt keine fehlenden Requirements, Tests oder
Bestandsnachweise.

### 1.3 Was ein gespeicherter Stand umfasst

Im Projektmodell liegen die Identitäten und Beziehungen der fachlichen
Objekte: Domains, Elemente, elektrische Signale und Ports, Requirements,
Quellverweise, Beobachtungen, Realisierungen, Komponenten, Varianten,
Fachinterfaces, Prüfungen und Metadaten. Revisionen enthalten Snapshots in
SQLite. Hochgeladene Originaldokumente und extrahierte Kontexte sind separat
im lokalen Datenverzeichnis hinterlegt. Ein JSON-Export ersetzt deshalb keine
vollständige Datensicherung des Datenverzeichnisses.

## 2. Prozessübersicht

Die Prozessübersicht zeigt den aktuellen Projektkontext und markiert offene
Arbeit. Sie ist eine Einstiegshilfe, keine Freigabeinstanz: eine grüne Karte
ersetzt weder eine fachliche Bewertung noch einen Testbericht. Von dort in den
betroffenen Arbeitsraum wechseln und das konkrete Objekt mit seinen Quellen,
Zuordnungen und Nachweisen öffnen. Im Projekt mit manuellem Architekturstart
kann die Architektur sofort erstellt werden; Herkunft und Designentscheidung
sollten für manuelle Objekte später ergänzt werden.

## 3. Quellen & Analyse

### 3.1 Quellmaterial erfassen

Eine Quelle dient als nachvollziehbarer Ausgangspunkt. Die Anwendung kann
PDF, DOCX, TXT, Markdown, CSV/TSV sowie unterstützte XML-, JSON- und
textuelle Netzlistenformate lesen. Beim Hochladen Dokumentprofil, Kontext und
Analyseauftrag je Datei prüfen. Ein Lastenheft, eine Stückliste, ein
Schaltplan und eine Netzliste beantworten verschiedene Fragen und müssen
passend gekennzeichnet werden. Für Schaltplan-PDFs gilt: Aus grafischen Linien
lässt sich eine belastbare elektrische Connectivity nicht immer rekonstruieren;
eine strukturierte Netzliste oder ein ECAD-Export verbessert die Aussage.

### 3.2 Ergebnis und Fundstelle

Die Analyse ermittelt Kandidaten für Requirements, Funktionen, Interfaces,
Bauteile, Normen und Architektur. Sie hält Fundstellen und offene Fragen fest.
Die Analyse läuft serverseitig weiter, wenn der Browser geschlossen wird,
solange der Anwendungsprozess läuft. Eine Fundstelle beschreibt, woher eine
Aussage stammt; der fachliche Status beschreibt, ob sie geprüft wurde.
Veraltete, mehrdeutige oder widersprüchliche Quellen erfordern eine
menschliche Entscheidung. Ein erkannter Begriff allein ist kein genehmigtes
Requirement und kein Nachweis einer technisch richtigen Verschaltung.

### 3.3 Bestandsbeobachtung und Übernahme

Im Redesign kann ein Bauteil oder ein Netz zuerst als Beobachtung des
Iststands erfasst werden. Dazu gehören Quelle, Fundstelle, Bezeichnung und
offene Klärung. Anschließend kann daraus mit Begründung und fachlicher
Prüfung eine neue Anforderung abgeleitet werden. Die Herkunft des Befunds
bleibt sichtbar. Analysierte Kandidaten werden angenommen, korrigiert oder
verworfen. Bei der kontrollierten Übernahme legt die Anwendung eine Revision
an und kompiliert nur ausgewählte Vorschläge. Ein Vorschlag mit ungeklärter
Namenskollision bleibt offen.

## 4. Requirements: Struktur, Eingabe und Ableitung

### 4.1 Bedeutung der Ebenen

L1 beschreibt Kundenbedarf; L2 beschreibt daraus abgeleitetes
Systemverhalten; L3 präzisiert technische Systemanforderungen; L4 beschreibt
Anforderungen an Fachdisziplinen. Die Ebenen sind eine Ableitungskette und
keine Qualitätsnoten. Konkrete Lösungsobjekte, Varianten und Parts sind
keine fünfte Requirements-Ebene. Ein Requirement trägt eine stabile Identität,
Text, Klassifizierung, Kategorie, Reife, Herkunft und gegebenenfalls
Akzeptanzkriterien, Verantwortung, Quelle und Fundstelle. Der interne
Kennungspräfix ergibt sich bei Anlage aus Klassifizierung und Kategorie; die
vergebene Kennung bleibt danach stabil.

### 4.2 Erfassen und bearbeiten

Im Requirements-Arbeitsraum **Requirement hinzufügen** wählen oder ein
bestehendes Objekt öffnen und bearbeiten. Aussage so formulieren, dass sie
prüfbar ist. Herkunft und Akzeptanzkriterien explizit eintragen, falls
bekannt. Eltern- und Kindbeziehungen sind fachliche Ableitungen, keine
reinen Anzeigeverbindungen. Bei einem Ebenensprung ist eine Begründung nötig;
Ableitungszyklen sind unzulässig. Ein manuelles Requirement erhält seine
Herkunft erst durch die angegebene Quelle oder bewusste Designentscheidung.

### 4.3 Navigation in großen Modellen

Ein Kartenklick zeigt die Details rechts. **Abhängigkeitsfokus** wählt dagegen
explizit ein Requirement, Architekturobjekt, FE oder eine Realisierung aus.
**Direkte Beziehungen** zeigt dessen unmittelbare Nachbarn; **Vollständige Kette**
zeigt Vorfahren und Nachfahren, ohne andere Ableitungszweige einzublenden.
**Fokus zurücksetzen** zeigt wieder das gesamte gefilterte Modell. Suche und
Fachfilter bleiben verfügbar. **Große Grafik** schafft mehr Zeichenfläche.
Schnittstellenzuordnungen in der Architekturspalte sind zunächst eingeklappt;
leere Anforderungsebenen bleiben als schmale Spalten sichtbar.

### 4.4 Beziehungen und fachliche Schnittstellen

**Beziehung anlegen** erzeugt eine gerichtete fachliche Kante zwischen
benannten Objekten. Eine Beziehung hält Typ, Endpunkte, Begründung,
Quellreferenz, Status und Historie. **Beziehung ansehen** öffnet ihre Angaben,
ohne die aktuelle Hauptauswahl zu verändern. Erst **Zielobjekt fokussieren**
wechselt die Auswahl. Das gemeinsame Verknüpfen zweier Objekte mit demselben
Requirement erzeugt keine Beziehung zwischen den Objekten. Eine
fachübergreifende Schnittstelle muss selbst als Beziehung oder
Interfaceobjekt beschrieben werden.

### 4.5 Getrennte Aussagen über den Fortschritt: Zuordnung, Erfüllung und Test

**Requirement zuordnen** verbindet eine Anforderung mit Architektur,
Realisierung oder anderen passenden Lösungsobjekten. Das sagt zunächst nur,
welches Objekt die Umsetzung leisten soll. **Technische Erfüllung bewerten**
wählt eine konkrete Realisierung, bewertet die Akzeptanzkriterien und
hinterlegt Entscheidung, Begründung und Ergebnisbeleg. Änderungen an
Anforderung, Realisierung oder gewählter Variante können eine zuvor positive
Bewertung prüfbedürftig machen. Die Testdefinition enthält Ziel, Methode,
Ablauf und erwartetes Ergebnis. Erst eine Ausführung mit tatsächlichem
Ergebnis, Evidenz, Zeitpunkt und geprüfter Revision kann als verifiziert
gelten. „Definiert“, „bestanden“, „fehlgeschlagen“ und „blockiert“ sind
unterschiedliche Zustände. Ein dokumentierter Test darf deshalb nicht durch
eine bloße Zuordnung ersetzt werden.

### 4.6 Konflikte, Normen und technische Quellen

Umsetzungskonflikte verbinden widersprüchliche technische Aussagen mit einer
Entscheidung oder einem offenen Klärpunkt. Normen und Standards bestehen aus
Quelle und gegebenenfalls genauer Klausel; der Normenbezug eines Requirements
wird ausdrücklich zugeordnet. Technische Quellen können separat erfasst und
lokal geöffnet werden, wenn ihre Datei vorhanden ist. Ein Normenbezug sagt,
welche Vorgabe berücksichtigt werden soll; Konformität benötigt eine eigene
Bewertung und geeignete Evidenz.

## 5. Technische Realisierungen und Parts

Eine technische Realisierung bündelt eine mögliche Lösung zu Requirements
oder die beobachtete Umsetzung eines FE aus dem ECAD-Design. Varianten dokumentieren Alternativen und ihren
jeweiligen Entscheidungsstatus. Komponenten oder A-Parts können mit Rolle in
der Realisierung, Bezeichnung, RefDes, MPN, Herkunft und weiteren Merkmalen
zugeordnet werden. Eine direkte Requirement-Zuordnung an einem Part ist von
einer Zuordnung über eine Variante zu unterscheiden. Bei der Suche im
Requirements-Arbeitsraum nach Name, RefDes oder MPN kann auch unzugeordneter
Bestand betrachtet werden. Ein Part belegt seine Existenz im Iststand erst
mit einer passenden Quelle, nicht allein durch seine manuelle Benennung.

Eine Realisierung darf vor Abschluss der Requirement-Prüfung beschrieben
werden, muss dann aber als geplanter Lösungsansatz erkennbar bleiben.
Variantenwechsel können frühere Erfüllungsbewertungen entwerten. Vor der
Freigabe die gewählte Variante, beteiligte Parts und alle betroffenen
Akzeptanzkriterien erneut prüfen.

## 6. Architektur → Hardware / ECAD: logische Architektur

### 6.1 Domain, AE und Eigenschaften

Eine Domain ordnet einen Systembereich. Ein Architecture Element (AE) ist ein
logischer Baustein innerhalb einer Domain. Im Arbeitsraum nacheinander
**Domain**, **Architecture Element**, **Interface-/Signal-Wizard** und
**Host / Teilnehmer** verwenden. Das Navigator-Menü bietet kontextbezogene
Bearbeitung. Im Objektinspektor Namen, Klassifikation, Beschreibung,
die Anforderungs- und Realisierungsattribute unter Eigenschaften prüfen.
Fachliche Domain- und Elementtypen stammen aus dem Architekturkatalog;
technische Namen bleiben für die Weiterverarbeitung eindeutig.

### 6.2 Interfaces, Signale, Busse und Ports

Der Wizard bietet die Familien Interface, Control, Status, Analog, Power und
Memory. Interface-Templates können aus dem eingebauten Katalog oder dem
Projektkatalog stammen. Ein Interface-Link erhält einen Instanzindex und
untergeordnete Mitgliedssignale. Control-, Status-, Analog- und Power-Namen
werden aus dem jeweiligen Template und den eingegebenen Domänen-, Zusatz-
oder Spannungsangaben gebildet. Bei einem busartigen Link wird der Host
festgelegt und die Teilnehmer werden ergänzt; bei einem einzelnen Netz gilt
dasselbe Prinzip. Ein Port ist die Verbindungssicht eines AE; Port Type
beschreibt die fachliche Art, Pin Type die elektrische Rolle. Die
Implementierungssicht der Port-Signale ist von der übergeordneten
Signaldefinition zu unterscheiden.

Bei neu erzeugten sowie aus JSON importierten Signalen entfernt die Suite wiederholte,
identische Unterstrichsegmente ohne Beachtung der Großschreibung:
`Spannung_5V0_5V0` wird `Spannung_5V0`. Die ursprüngliche generierte
Bezeichnung bleibt als beobachteter Name oder Metadatum erhalten. Entsprechende
Port- und Verbindungsnamen werden beim Import mitbereinigt. Bereits gespeicherte
Projekte werden beim ersten Laden bereinigt und vorher als Revision gesichert;
IDs und Topologiebeziehungen bleiben erhalten. Bei unterschiedlichen Signalen,
die auf dieselbe Kurzbezeichnung fallen, wird ein eindeutiger Zusatz vergeben.
Andere Namensbestandteile werden nicht pauschal umbenannt. Wenn die bereinigte
Bezeichnung bei einer KI-Übernahme schon mit abweichender Host-/Teilnehmer-
Topologie existiert, wird die Übernahme als Konflikt
markiert; der manuelle Wizard verweigert denselben Signalnamen. Die
Schnittstelle fachlich prüfen und danach gezielt benennen.

### 6.3 Topologie und grafische Darstellung

Mit **Host / Teilnehmer** die tatsächlichen AEs auswählen. Danach erstellt
die Suite die Modellverbindungen aus der Signalzuordnung. Im Canvas Domains
öffnen oder einklappen und Signaltypen filtern; der Filter ist reine Anzeige.
**Auswahl fokussieren** zentriert ein Objekt. Die separate Funktion
**Verbindung** bearbeitet eine konkrete Verbindung, ersetzt aber nicht die
Definition eines katalogisierten Signals. Die Architektur-PDF zeigt eine
vektorbasierte Gesamtansicht und Detailseiten. Sie dokumentiert den aktuellen
logischen Stand; sie ist kein fertiger Schaltplan und keine Leiterplatte.

### 6.4 Herkunft und Traceability

Über **Traceability bearbeiten** dem ausgewählten Objekt eine bewusste
Requirement-Verknüpfung oder eine Designentscheidung mit Begründung zuweisen.
Ein aus dem Bestand übernommenes AE sollte seine Beobachtung und Fundstelle
behalten. Der Objektinspektor weist auf fehlende Herkunft hin. Löschaktionen
zeigen Abhängigkeiten, die vor Bestätigung geprüft werden müssen.

## 7. Mechanik / CAD

Unter **Komponenten** Gehäuse, Halterung, Kühlkörper oder andere mechanische
Objekte erfassen und bearbeiten. **Randbedingungen** bilden etwa Bauraum,
Masse, Schutz und Umgebungsbedingungen ab. **Mechanische Interfaces**
beschreiben die Berührungs- oder Befestigungsschnittstelle zwischen benannten
Objekten. **Thermik & PCB-Kopplung** zeigt thermische Eckdaten und die
Übergabe von Outline, Keep-outs oder Höhenzonen an die HW-Seite, soweit
diese Angaben erfasst wurden. Die Oberfläche ist ein Koordinationsmodell;
eine CAD-Geometrie entsteht durch das Eintragen der Merkmale nicht.
Technische Werte und Herkunft nach der Eingabe auf Plausibilität prüfen.

## 8. Software / Firmware

Software-, Firmware- und HDL-Komponenten lassen sich mit Rolle, Beziehungen,
Protokollmerkmalen und Deployment-Zuordnung erfassen. **Protokolle & APIs**
zeigt Schnittstellen; **Deployment** die Zuordnung zu Zielsystemen.
**Arbeitspakete** halten Umsetzungsschritte und ihre Beziehung zu
Requirements fest; **Backlog & Tests** macht diese Arbeit sichtbar.
SW_IF und FW_IF erzeugen Fachinterfaces, die im jeweiligen Modell
nachvollziehbar bleiben. Eine eingetragene Komponente oder ein Arbeitspaket
ist noch kein ausgeführter Softwaretest.

## 9. Normen & Standards

Eine Normenquelle enthält ihre Identität, Geltung und Referenz. Die einzelne
Klausel möglichst konkret benennen. Requirement und Normenquelle bewusst
verknüpfen; dann die Umsetzung in Realisierung, Architektur und Test
nachverfolgen. Verweise auf lokale Originaldateien funktionieren nur, wenn
die Datei im Datenverzeichnis verfügbar ist. Ein allgemeiner Normtitel ohne
Klausel oder Nachweis ist ein offener Arbeitsauftrag.

## 10. KI-Assistent und kontrollierte Vorschläge

Die KI-Konfiguration in der Kopfzeile bestimmt Provider und Zugang.
Unterstützt werden OpenAI, ein OpenAI-kompatibler oder lokaler Endpunkt und
ein experimenteller Copilot-Zugang mit passender Lizenz und delegiertem
Graph-Token. Zugangsdaten liegen in der Sitzung oder im Credential Manager;
im Projekt-JSON werden sie nicht exportiert. Der Assistent kann Fragen zum
Projekt beantworten und aus Quellen Vorschläge für Requirements,
Architektur oder Änderungen erzeugen. Prüfen Sie vor Übernahme Herkunft,
Template, Namensregeln, Topologie und offene Fragen. Eine erzeugte
Architektur wird auf einer Kopie kompiliert und nur als vollständig gültiges
Projektmodell übernommen. Offene Kollisionen bleiben Vorschläge. Eine
KI-Antwort ersetzt keine technische Prüfung, Freigabe oder Messung.

## 11. Vollständiger JSON-Austausch

### 11.1 Export

Das Downloadsymbol an der Projektauswahl exportiert die fachlichen Daten des
aktuellen Projektstands als lesbares JSON. Der Dateiname enthält den
Projektnamen und die Standnummer. Die Datei transportiert Referenzen auf
Quellen, aber keine binären Anhänge, keine Datenbankrevisionen und keine
geheimen Zugangsdaten. Für einen vollständigen Rechnerwechsel auch das
lokale Datenverzeichnis sichern.

### 11.2 Import mit ausdrücklicher Projekttypwahl

Das Uploadsymbol öffnet einen Importdialog. JSON-Datei hochladen und die
Prüfvorschau mit Projektname, ursprünglichem Projekttyp und Objektzahlen
lesen. Anschließend **einen der vier Projekttypen ausdrücklich auswählen**.
Ohne Auswahl erfolgt kein Import. Die Auswahl gilt sowohl für **In dieses
Projekt als Revision** als auch für **Als neues Projekt**. Der ursprüngliche
Typ der Datei dient nur zur Orientierung. Beim Import als Revision bleibt die
Identität und der Name des aktuellen Projekts erhalten; die importierte
Objektstruktur ersetzt dessen laufenden Inhalt in einem neuen Stand. Beim
Import als neues Projekt erhält der Import eine neue Projekt-ID und bei
Namensgleichheit einen eindeutigen Namenszusatz. Der gewählte Profiltyp
löscht keine fachlichen Objekte. Das Verfahren prüft das Paket vor dem
Speichern; bei Versionskonflikt erneut laden und prüfen. Referenzierte
Originaldokumente sind nur nutzbar, wenn ihre Anhänge lokal existieren.
Gleiche, direkt aufeinanderfolgende Unterstrichsegmente in Namen von Signalen,
Ports und Verbindungen werden bei der Importprüfung entfernt. Beispielsweise
wird `VCC_Power_LOCAL_5V_5V` zu `VCC_Power_LOCAL_5V`. Unterschiedliche
Signalobjekte und ihre Referenzen bleiben getrennt.

### 11.3 Requirements-Teilaustausch

**Requirements → Importieren / exportieren** unterstützt ReqIF, XLSX, CSV,
DOCX und eine lesbare Review-PDF. Für den Import kann ein Spaltenmapping
`Originalspalte = Zielfeld` vorgegeben werden. Die Vorschau zeigt erkannte
Spalten und problematische Elternkennungen. Ungeklärte Eltern werden vor der
Übernahme abgewiesen. Austauschprofile für DOORS, Polarion und Jama sind
Feldvorlagen; das Zielformat im jeweiligen Produkt prüfen. Teilformate
können Eigenschaften, explizite Beziehungen, Evidenz oder Varianten
verlieren. Der Dialog nennt diese Grenzen. Die Review-PDF ist kein
Rückimportformat; für verlustarmen Gesamtaustausch das Projekt-JSON wählen.

## 12. Revisionen, Wiederherstellung und Löschung

Eine Revision benennt einen fachlichen Zwischenstand. Die Historie zeigt
vorhandene Snapshots. Beim gesicherten Wiederherstellen wird der bisherige
laufende Stand zuerst als Revision gesichert; danach wird ein alter Snapshot
als neuer laufender Stand übernommen. In einem parallel geöffneten Browser
kann ein Versionskonflikt entstehen, wenn die zugrunde liegende Version
inzwischen geändert wurde. In diesem Fall Projektstand erneut öffnen und die
Änderung bewusst wiederholen. Löschvorgänge sind durch die
Administrations-PIN geschützt. Auswirkungen auf verknüpfte Objekte vorher
prüfen. Die PIN schützt lokale Bedienaktionen; sie ist keine umfassende
Mehrbenutzer-Authentifizierung.

## 13. Technische Grundlagen und Betrieb

`main.py` startet die NiceGUI-App. Pydantic validiert das Projektmodell.
SQLite speichert Projekte, laufende Stände und Revisionen. Originaldateien
liegen getrennt im Datenverzeichnis; die Architektur- und
Requirements-Exporte werden serverseitig erzeugt. `Interface_Template_File.json`
und `Architecture_Catalog.json` enthalten Katalog- und Naming-Vorgaben.
`architecture_app/project_import.py` hält die Projekttypregel,
`project_import_ui.py` den Importdialog und `signal_naming.py` die
konservative Prüfung neu erzeugter Signalnamen. Fachlogik für Requirements,
Traceability, Topologie und Austausch liegt in den entsprechend benannten
Modulen. Die Modullandkarte unter `docs/ARCHITEKTUR.md` erklärt die
Entwicklungsgrenzen.

Die sichtbare **SHA-256-Objektkennung** ist bei neu angelegten Objekten zugleich
die interne ID: Sie entsteht aus zufälligen Bytes mit dem jeweiligen Objekttyp
als Domänentrennung und bleibt danach unverändert. Importierte oder ältere
Objekte können intern weiterhin eine sprechende Referenz-ID wie
`ae-cell-monitor` besitzen. Für die einheitliche Anzeige wird aus dieser
stabilen Referenz eine SHA-256-Kennung berechnet; die ursprüngliche ID steht
weiterhin unter **Interne Referenz-ID** und wird nicht automatisch ersetzt.
Eine SHA-256-Prüfsumme einer Quelldatei beschreibt hingegen ihren **Inhalt**.
Sie hat eine andere Aufgabe und kann sich beim Ändern des Inhalts ändern.

Für Windows das ZIP vollständig entpacken und `start_windows.bat` im
Projektordner starten. Der Starter prüft Abhängigkeiten aus
`requirements.txt`; alternativ eine Python-Umgebung anlegen und
`python -m pip install -r requirements.txt` sowie `python main.py`
ausführen. Die App läuft lokal unter `http://127.0.0.1:8080`.
`ISD_SUITE_DATA_DIR` erlaubt ein anderes Datenverzeichnis. Beim Sichern die
SQLite-Datei und die Anhänge gemeinsam kopieren, möglichst bei gestoppter
Anwendung. Einen JSON-Export zusätzlich als lesbaren Austauschstand
aufbewahren.

## 14. Häufige Prüffälle

| Beobachtung | Bedeutung und nächster Schritt |
| --- | --- |
| Importdatei ist gültig, Schaltflächen übernehmen aber nichts | Einen Projekttyp im Importdialog auswählen und erneut übernehmen. |
| Quelle ist im JSON sichtbar, Original lässt sich nicht öffnen | Anhang fehlt lokal; Datenverzeichnis beziehungsweise Original erneut bereitstellen. |
| Signalname kollidiert nach Bereinigung | Bestehende Topologie und vorgeschlagenen Host/Teilnehmer vergleichen; bewusst eindeutig umbenennen. |
| Requirement zeigt ein Part, aber keinen erfüllten Status | Zuordnung ist dokumentiert; Kriterien und Ergebnisbeleg gesondert bewerten. |
| Testdefinition erscheint, aber kein Nachweis | Tatsächliches Ergebnis, Evidenz, Zeitpunkt und geprüfte Revision ergänzen. |
| Architektur aus Schaltplan-PDF ist unvollständig | Netzliste/ECAD-Export beistellen und Topologie an Quelle prüfen. |
| Alte Revision wird wiederhergestellt | Der bisherige Stand wird gesichert; alle neuen Änderungen auf dem wiederhergestellten Stand bewusst prüfen. |
| PDF- oder XLSX-Export scheitert wegen Modul | Verwendete Python-Umgebung und `requirements.txt` mit dem Windows-Starter oder `pip` aktualisieren. |

---

# Funktionsreferenz nach Arbeitsbereich

Dieser Teil beantwortet für jede sichtbare Arbeitsfunktion vier Fragen: Wo wird
sie aufgerufen? Welches Objekt verändert sie? Was ist danach im Modell zu
sehen? Was muss vor einer fachlichen Freigabe noch geprüft werden? Die
Kurzbedienhilfe in der Anwendung dient nur als Einstieg; dieses Handbuch ist
die ausführliche Arbeitsreferenz.

## 15. Kopfzeile, Projekt und Arbeitsstände im Detail

### 15.1 Projektauswahl und neue Projekte

Die Projektauswahl zeigt lokale Systemprojekte. Nach einem Projektwechsel werden
Navigator, Grafik und Detailbereich mit dessen Arbeitsstand neu geladen.
**Neues Projekt** öffnet den Eingabedialog für einen eindeutigen Namen, den
Startkontext und optional eine Beispielarchitektur. Der Startkontext ist eine
Arbeitsvorgabe: **Direkt mit HW-/ECAD-Architektur beginnen**, **Integrierte
Systementwicklung mit Requirements**, **Redesign eines bestehenden Systems**
oder **Architekturstudie / Prototyp**. Auch ein mit Architektur gestartetes
Projekt kann später Requirements enthalten. Die Beispielarchitektur ist eine
bewusste Startoption und kein automatisch aus Quellen erstellter Befund.

**Projektprofil** zeigt das aktuelle Profil und seine Wechselhistorie. Ein
Profilwechsel verlangt eine Begründung. So lässt sich ein ursprünglich als
Studie gestartetes Projekt später als integrierte Entwicklung führen, ohne
Objekt-IDs oder Quelldaten umzuschreiben. Vor einem Wechsel prüfen, ob
Quellenart, Reife und geplante Nachweise zum neuen Arbeitskontext passen.

### 15.2 Die Kopfzeilenaktionen im Überblick

| Aktion | Eingabe und Wirkung | Ergebnis und Grenze |
| --- | --- | --- |
| Projektauswahl | Anderes lokales Projekt wählen | Der gesamte sichtbare Modellstand wechselt. |
| Projektprofil | Anderen Startkontext samt Begründung speichern | Hinweise und Prüfkontext ändern sich; fehlende Evidenz entsteht nicht automatisch. |
| JSON herunterladen | Export des aktuellen fachlichen Projektpakets | JSON enthält keine hochgeladenen Binärdateien und keine API-Schlüssel. |
| Projekt-JSON importieren | Datei prüfen, Startkontext auswählen, Importmodus wählen | Neues Projekt oder neue Revision im aktuellen Projekt. |
| Neues Projekt | Eindeutigen Namen und Startkontext eingeben | Leeres Projekt oder bewusste Beispielarchitektur. |
| Projekt löschen | Admin-PIN und Rückfrage | Projekt mitsamt seinen Revisionen entfernen; Auswirkungen vorher prüfen. |
| Admin-PIN | PIN ändern | Lokale Schutzfunktion für destruktive Aktionen. |
| KI-Zugang | Provider, Modell und Zugang konfigurieren | Konfiguration der laufenden KI-Funktionen; Schlüssel nicht im Projektmodell. |
| KI-Assistent | Frage oder kontrollierten Auftrag öffnen | Antwort/Vorschlag prüfen, bevor Modelländerungen übernommen werden. |
| Hilfe / Doku | Kurzbedienhilfe beziehungsweise dieses Handbuch öffnen | Keine Modelländerung. |
| Revision | Benannten Zwischenstand festhalten | Snapshot in der lokalen Historie. |
| Historie | Revisionen ansehen oder gesichert wiederherstellen | Der bisherige Stand wird vor der Wiederherstellung gesichert. |

### 15.3 Speichern, Revision und Konflikt

Jede erfolgreiche fachliche Aktion speichert einen neuen laufenden
Versionsstand. Eine bewusst angelegte Revision trägt zusätzlich einen Namen
und dient als wieder auffindbarer Meilenstein. Die Historie ist je Projekt
getrennt. Beim Wiederherstellen einer alten Revision erstellt die Suite zuerst
eine Sicherung der bisherigen Arbeitskopie. Dann wird die ausgewählte
Revision zum neuen laufenden Stand; alte Revisionsnummern werden nicht
überschrieben. Wenn zwei Browserfenster denselben Projektstand parallel
ändern, kann die Versionsprüfung den späteren Speicherversuch abweisen. Den
aktuellen Stand neu laden und die abgewiesene Änderung anhand der inzwischen
gespeicherten Daten erneut entscheiden.

## 16. Quellenanalyse als Arbeitsprozess

### 16.1 Mehrere Dokumente und Kontext je Datei

**Anforderungsdokumente importieren und analysieren** nimmt mehrere Dateien
als Importserie auf. Vor der Analyse werden zu jeder Datei Dokumentprofil,
zusätzlicher Kontext und Analyseauftrag angegeben. Ein Lastenheft kann
Kundenanforderungen liefern; eine BOM liefert Part- und Herstellerangaben;
eine Netzliste liefert konkrete Netzverbindungen. Der Analyseauftrag sollte
daher die Herkunft nennen und klären, ob Iststand, Zielanforderung oder
Referenzmaterial vorliegt. Eine Serie wird dokumentweise abgearbeitet;
zwischenzeitliche Analysestände bleiben im Projekt sichtbar. Der ursprüngliche
Dateiname und die Quelle gehören zum Nachweis und sollten nicht nachträglich
durch eine generische Bezeichnung ersetzt werden.

### 16.2 Dokumentkarte und Analysebefund

Im Arbeitsraum **Quellen & Analyse** erhält jedes Quelldokument eine eigene
Karte mit Import- und Analysezustand. Dort werden je nach Material Kernidee,
Funktionen, erkannte Anforderungen, technische Beobachtungen, Parts, Netze,
Schnittstellen, Normen sowie offene Fragen gezeigt. **Analysebefund anpassen**
erlaubt eine fachliche Korrektur des konkreten Befunds. Für erkannte
Verbindungen oder Netze gibt es **Bestätigen**, **Anpassen**, **Verwerfen** und
**Als Konflikt**. „Bestätigt“ sagt, dass der Befund als Beobachtung akzeptiert
wurde; es ist noch keine Aussage über die technische Eignung einer späteren
Lösung.

**Originaldokument und KI-Kontext nachreichen** ergänzt Material, wenn zum
Beispiel erst ein Textauszug vorlag. **Bestehende Requirements dem Dokument
zuordnen** verknüpft bereits vorhandene Anforderungen mit einer neuen Quelle.
**Bestehende Requirements prüfen und freigeben** betrifft die fachliche
Einordnung dieser Objekte. **Technische Ableitung starten** führt aus
ausgewählten, überprüften Informationen zu Vorschlägen für die nächste
Entwicklungsstufe. Werden Quelle oder Analyse verworfen, bleiben bereits
separat gespeicherte Projektobjekte nur dann nachvollziehbar, wenn ihre
Referenzen weiterhin gültig sind; verknüpfte Objekte vorher prüfen.

### 16.3 Prüfung einer Redesign-Quelle

Ein Redesign startet regelmäßig mit nachweisbarem Bestand. Für jeden Befund
sollten folgende Angaben überprüft werden:

1. Welches Original und welche Fundstelle belegen Bauteil, Netz oder Funktion?
2. Ist die Information aus einer BOM, einer Netzliste, einem Schaltplan oder
   einer textlichen Aussage abgeleitet?
3. Beschreibt sie einen vorhandenen Istzustand oder eine gewünschte
   Eigenschaft des nächsten Designs?
4. Welche Konnektivität ist sicher und welche aus einem Bild lediglich
   vermutet?
5. Sind alternative Bestückungen, Varianten und unbekannte Komponenten als
   offene Punkte dokumentiert?

Aus dem Bestandsbefund kann eine neue Anforderung mit eigener Begründung
entstehen. Umgekehrt kann ein vorhandenes Part einer erst später formulierten
Anforderung zugeordnet werden. Diese beiden Richtungen unterscheiden sich
hinsichtlich Herkunft und fachlicher Aussage.

## 17. Requirements-Ansicht und Datenfelder

### 17.1 Systemdefinition und Ableitungsbild

Die **Kernidee und Systemgrenze** hält fest, welches System betrachtet wird,
welche Aufgabe es erfüllen soll und was außerhalb der Systemgrenze liegt.
**Systemdefinition bearbeiten** ändert diese Beschreibung. Sie soll den
Leser vor einer detaillierten Requirements-Betrachtung orientieren. Das
kaskadierte Ableitungsbild führt von Quellen über Anforderungen und
Fachdisziplinen bis zu Realisierungen und Nachweisen. Es zeigt vorhandene
Modellobjekte und offene Schritte, ersetzt aber weder eine formale Abnahme
noch einen Test.

### 17.2 Requirement anlegen und fachlich klassifizieren

**Requirement hinzufügen** erstellt ein fachliches Objekt mit Titel und
Aussage. Die vier Ebenen L1 bis L4, Klassifizierung nach System, Hardware,
Mechanik oder Software/Firmware, Kategorie, Herkunft, Reife, Priorität,
Akzeptanzkriterien und weitere Attribute werden im Bearbeitungsdialog
geführt. Der interne Identifier wird bei Anlage gebildet und bleibt danach
stabil. Eine Kundenforderung sollte als Quelle eine belastbare Fundstelle
haben; eine interne technische Forderung braucht eine nachvollziehbare
Ableitung oder Designentscheidung. Das Nachtragen einer Quelle ändert nicht
von selbst die fachliche Reife.

Für die Ableitung die Elternanforderung angeben. Ein Kind beschreibt einen
prüfbaren Teil der übergeordneten Aussage. Zum Beispiel kann aus „14
Zellspannungen überwachen“ eine technische Genauigkeitsanforderung und
daraus eine Hardwareanforderung an den Messpfad entstehen. Anforderungstext,
Akzeptanzkriterium und technische Umsetzung sind getrennte Felder. Eine
benannte Lösung im Anforderungstext ist nur dann sinnvoll, wenn sie selbst
verbindliche Vorgabe ist; sonst gehört sie zur Realisierung.

### 17.3 Suche, Filter, Pfad und Detailbereich

Die linke Navigation gliedert nach Systembereichen und Fachklassifikation.
Suche und Filter schränken die angezeigten Karten ein. **Abhängigkeitsfokus**
und **Beziehungstiefe** steuern die sichtbaren Beziehungen unabhängig vom
Kartenklick. Ein Klick öffnet die Details im rechten Inspektor; auch unter
**Architekturverantwortung** erscheint kein automatisches Attributfenster.
Bearbeitet wird über **Objekt bearbeiten** und die objektbezogene Eingabemaske. Langtexte, Quellen und Statusdetails stehen
im Inspektor. Die kompakte Grafik zeigt L1–L4, Verantwortung, Realisierung
und systemdefinierende Parts. **Große Grafik**, **Normalansicht** und **Details**
verändern die Darstellung. Linien enden horizontal an den Kartenrändern;
kleine Pfeilspitzen und getrennte Anschlussstellen helfen beim Verfolgen.

Vier Statusdimensionen stehen nebeneinander: **fachliche Reife**,
**Lösungszuordnung**, **bewertete Erfüllung** und **Verifikation**. Bei einer
fehlenden Dimension zeigt die Ansicht einen offenen Punkt. Eine Zuordnung
kann bestehen, während die Erfüllungsbewertung noch fehlt. Ein definiertes
Prüfverfahren kann bestehen, ohne dass es bereits erfolgreich ausgeführt
wurde. Diese Unterscheidung ist für Projektberichte entscheidend.

### 17.4 Beziehungen, Schnittstellen und Beobachtungen

**Beziehung anlegen** speichert eine gerichtete Beziehung zwischen zwei
benannten Objekten. Für die fachliche Aussage sind Typ, Richtung, rationale
Begründung, Quelle und Status zu prüfen. Eine grafische Linie ist nur dann
belastbar, wenn die gespeicherte Beziehung diesen Kontext tatsächlich trägt.
**Beziehung ansehen** lässt den ursprünglichen Knoten ausgewählt und zeigt
die Beziehungsdaten im Inspektor. **Zielobjekt fokussieren** öffnet das andere
Ende. **Bestandsbefund** hält eine Beobachtung mit Quelle fest; damit werden
vermutete Soll-Anforderungen und beobachtete Ist-Technik nicht vermischt.

### 17.5 Nachweise und Qualität

**Requirement-Test definieren** erfasst Ziel, Methode, erwartetes Ergebnis
und Bezug zur Anforderung. Ein ausgeführter Test ergänzt tatsächliches
Ergebnis, Prüfzeit, Report und die geprüfte Projektversion. Historisch als
„bestanden“ markierte Fälle mit unvollständigem Ergebnisnachweis werden als
prüfbedürftig angezeigt. **Technische Erfüllung bewerten** ist die davon
getrennte Beurteilung, ob eine konkrete Realisierung die Akzeptanzkriterien
einer Anforderung erfüllt. Bei einer Änderung der Realisierung oder Variante
muss die Bewertung erneut betrachtet werden. **Umsetzungskonflikt erfassen**
hält widersprüchliche Forderungen, betroffene Lösungsobjekte und eine
geplante Klärung sichtbar.

## 18. Realisierungen, Varianten und konkrete Komponenten

### 18.1 Warum es eine Lösungsebene gibt

Eine technische Realisierung beantwortet, mit welchem fachlichen Konzept ein
Requirement umgesetzt werden soll. Eine Variante beantwortet, welche
Alternative innerhalb dieser Realisierung betrachtet oder ausgewählt wird.
Eine Komponente oder ein A-Part beschreibt ein konkreteres Bauteil, Modul
oder eine Bestandsposition. Ein AE bleibt grundsätzlich ein generischer
Architekturbaustein; die Auswahl einer konkreten Komponente wird als
technische Referenz zugeordnet. So kann der logische Architekturblock bei
einem Bauteiltausch stabil bleiben.

### 18.2 Realisierung anlegen und Varianten pflegen

**Technische Realisierung anlegen** erfasst Titel, technische Aussage,
Status, Herkunft und Requirement-Bezug. Der Dialog zeigt vorhandene
Varianten; **Lösungsvariante hinzufügen/bearbeiten** pflegt Status und
Komponentenrollen. Eine Komponentenrolle gilt innerhalb der betrachteten
Realisierung und ist keine globale Eigenschaft des Parts. Vor der Auswahl
einer Variante die Abdeckung der Anforderungen und offenen Konflikte prüfen.
Eine Realisierung benötigt mindestens einen Requirement-Bezug oder ein FE.
Ein aus ECAD zurückgelesenes FE kann zunächst ohne Requirements bestehen;
diese Zuordnung ist dann offen und belegt keine Anforderungserfüllung.

### 18.3 Part- und Komponenteninformationen

**Komponente / A-Part hinzufügen** erfasst zum Beispiel Bezeichnung,
Hersteller, Herstellerteilenummer und gegebenenfalls Referenzdesignator.
Weitere Merkmale dokumentieren Herkunft, Status, Eignung und Nachweise.
Eine Eignungsmatrix kann Kriterien und Belege zeilenweise enthalten. Ein
Bauteil aus einer Bestands-BOM ist zunächst belegt vorhanden, aber nicht
zwingend weiterverwendbar. Eine Alternativensuche bleibt sichtbar, solange
Datenblatt, Verfügbarkeit oder Zuordnung noch offen sind. Die Detailansicht
unterscheidet direkte Requirement-Links von solchen über eine
Realisierungsvariante. Systemdefinierende Bestandsobjekte ohne fachliche Zuordnung bleiben sichtbar.
Detailbauteile gehören in die vollständige ECAD-BOM und werden in der
Architektur- und Realisierungsgrafik nicht einzeln aufgeführt.

## 19. Architektur → Hardware / ECAD: Navigator, Signalkatalog und Canvas

### 19.1 Domain und Architecture Element

**Domain** fügt einen Bereich zum Projekt hinzu. Im Dialog Name, Domain
Type, Farbe und Beschreibung wählen. **Architecture Element** fügt einen
logischen Block in die ausgewählte Parent Domain ein; neben dem eindeutigen
Namen werden Rollenklasse und Beschreibung geführt. Ein Domain- oder
AE-Name darf nicht mit einem anderen Domain- oder AE-Namen kollidieren. Der
technische ECAD-Key besitzt ein eigenes Format und muss systemweit eindeutig
bleiben. Ein AE kann später in eine andere Domain verschoben werden, ohne
seine Objekt-ID zu verlieren. Seine Ports und Signalverbindungen folgen der
unveränderten AE-Identität.

Der Navigator kann Domains und AEs unabhängig vom Canvas ein- oder
ausklappen. Die Suche nach Objekten wählt einen Treffer, ohne den
Eingabetext ungewollt zu verändern. Das Aktionsmenü bietet Kontextaktionen
wie Bearbeiten, Löschen und Auf-/Zuklappen. Farbwahl erfolgt über eine
sichtbare Palette. Zusätzlich haben Domains und AEs im rechten Inspektor
eigene Bearbeitungsaktionen. Ein Port hat im Navigator ein eigenes
Stiftsymbol, das direkt seinen Bearbeitungsdialog öffnet. Projektvorlagen
können freie Port Types enthalten; das Feld akzeptiert daher auch Bezeichnungen
außerhalb der eingebauten Vorschlagsliste.

### 19.2 Interface-/Signal-Wizard und Projektvorlagen

Der Wizard führt durch sechs Signalfamilien:

| Familie | Erzeugtes Modell | Angaben vor Übernahme |
| --- | --- | --- |
| Interface | Nummerierter Link mit templategebundenen Mitgliedssignalen | Interfacevorlage, Anzahl, optionale Beschreibung |
| Control | Einzelnes Steuer- oder Statusnetz | Busgruppe, Signalvorlage, Zusatz, Pegelangabe, Active Low |
| Status | Einzelnes Rückmeldesignal | Busgruppe, Signalvorlage, Zusatz, Pegelangabe |
| Analog | Ein oder mehrere analoge Signale | Analogbus, Vorlage, technische Domain, Zusatz, differenziell, Frequenz |
| Power | Ein Versorgungssignal | Versorgungstyp, Domain, Zusatz, Spannungsangabe |
| Memory | Speicherschnittstelle als Bus | Technologie, Untertechnologie, Konfiguration, Host-Kennung |

Die eingebaute `Interface_Template_File.json` liefert die standardisierten
Mitglieder und Namen. In der Projektbibliothek kann eine Vorlage geklont
oder eine Projektvorlage mit Port Type, Signal Type, Richtung, Pin Type,
Aktiv-Low-Status und Mitgliedern bearbeitet werden. Die Wizard-Vorschau vor
Übernahme prüfen: Bei einem Interface sind Link und Port nummeriert; ein
Einzelsignal bildet den Portnamen 1:1. Ein semantischer Use Case gehört in
die Beschreibung und nicht in den nummerierten Linknamen. Projektbezogene
Anpassungen an einer gebundenen Definition werden als **Customized** geführt;
die ursprüngliche Objekt-ID bleibt erhalten.

### 19.3 Signalkatalog und Topologie

**Signale & Interfaces** öffnet die katalogisierte Liste. Signale sind nach
Signaltyp gruppiert. Die Karte zeigt Anzahl der Teilnehmer, Netz oder Bus,
Mitgliedssignale, Richtung, Pin Type und Active Low. **Definition** ändert
die Signaldefinition; **Topologie** bearbeitet Quelle und Teilnehmer;
**Im Canvas zeigen** fokussiert die betroffene Architektur. Ein einzelnes
Mitgliedssignal kann gesondert bearbeitet werden. Ein gelöschtes
Mitgliedssignal kann die Template-Bindung beeinflussen und sollte vor der
nächsten Weitergabe fachlich überprüft werden.

Für die Topologie ist genau ein Host und eine beliebige Anzahl von
Teilnehmern möglich. Im Zuordnungsbereich den Host setzen, Teilnehmer
suchen und einzeln oder domainweise auswählen. Die Canvas-Zuweisung nimmt
AE- oder Port-Klicks als Host- oder Teilnehmerauswahl an. Ein Host kann nicht
zugleich Teilnehmer sein. Erst wenn Host und mindestens ein Teilnehmer
vorhanden sind, entsteht eine grafisch dargestellte Verbindung. Eine
Signalkarte ohne vollständige Topologie bleibt als Definition sichtbar.
Filter auf Signaltypen bestimmen nur, welche Verbindungen im Canvas
angezeigt werden; sie löschen keine Signale.

### 19.4 Signalwahl, Hervorhebung und Ansichtsarten

Ein Klick auf ein Signal im linken Navigator hebt die zugehörigen
Verbindungszüge im Canvas hervor. Bei verzweigten Netzen betrifft dies alle
Äste desselben Signals. Ist sein Signaltyp ausgefiltert oder sind die
betroffenen Gruppen eingeklappt, macht die Auswahl diese Verbindung wieder
sichtbar. Andere Verbindungen treten optisch zurück. Eine
Verbindung lässt sich weiterhin direkt anklicken und im Inspektor betrachten.
Wenn ein Signal noch keinen Host und Teilnehmer besitzt, meldet die
Kontextleiste **Topologie noch offen**; dann existiert noch kein Zug zum
Hervorheben. **Systemübersicht** fasst Verbindungen zwischen Domains
zusammen; bei Auswahl eines Einzelsignals wechselt die Ansicht zur
Architektur, in der die konkrete Verbindung dargestellt werden kann.
**Domain-Fokus** schränkt die Ansicht auf eine Domain ein.
**Auswahlfokus** zeigt das ausgewählte Objekt und seine direkten
Verbindungen. Zoom, **Einpassen**, **Neu anordnen**, Minimap, Strg + Mausrad
und Scrollbars erleichtern die Navigation. Domain- und AE-Gruppen können
im Canvas separat eingeklappt werden. Ein Klick auf einen Port im Navigator
öffnet gegebenenfalls seine eingeklappte Domain und sein AE, zeigt einen
ausgefilterten zugehörigen Signaltyp wieder an, markiert den konkreten Port
und zoomt sowie scrollt zu ihm. Die Auswahl im Detailbereich bleibt auf
diesem Port; ein Klick auf das Stiftsymbol öffnet dessen Bearbeitung.

### 19.5 Objektbezogene Eingabemasken

**Bearbeiten** öffnet die zum Objekt passende Maske. Domänen und AEs enthalten
Name, Aufgabe/Verantwortung, Beschreibung, Typ und ECAD-Key; Domänen zusätzlich
Farbe, AEs ihre Domänenzuordnung. Ports enthalten Namen, Beschreibung und
Host-/Teilnehmer-Rolle. Ein verbundener Port übernimmt Name und Rolle aus Netz
und Topologie. Host wird rechts, Teilnehmer links dargestellt. Die Topologie
wird über ihre eigene Bearbeitungsfunktion geändert.

Netze und Busse enthalten Signaltyp, Vorlage, Inhalt und Netzklassenzuordnung.
**Busmitglied bearbeiten** erlaubt eine eigene Netzklasse und Signalrichtung.
Unter **Requirements und konkrete Umsetzung zuordnen** werden verantwortete
Requirements und konkrete Kennwertquellen ausgewählt. Eigene Attribute werden
in der Maske typisiert eingegeben; Definitionen verwaltet der Property Manager.

Die Objektidentität bleibt unveränderlich. Die SHA-256-Kennung steht einmal im
Detailbereich am ausgewählten Objekt. Speichern prüft einen Projektkandidaten.
Ungültige Typen, Namen und Beziehungen werden abgewiesen. Elemente und Ports
können über ihre Parent-Auswahl verschoben werden; Kollisionen müssen zuerst
in der Topologie bereinigt werden.

### 19.6 Objektinspektor und Löschung

Der Inspektor zeigt Typ, Name, Beschreibung, technische Klassifikation,
SHA-256-Kennung, interne Referenz-ID, Eigenschaften, Topologie und verknüpfte Requirements des
ausgewählten Objekts. **Traceability bearbeiten** weist eine bestehende
Anforderung zu, leitet bei Bedarf eine neue ab oder dokumentiert eine
Designentscheidung. **Löschen** verlangt eine Bestätigung und zeigt
Auswirkungen auf verknüpfte Objekte. Ein Link kann automatisch erzeugte
Ports und Verbindungen besitzen; deshalb vor dem Löschen die Folgen prüfen.

### 19.7 ECAD-Konnektor und KiCad-Projekt

Im Architekturarbeitsraum öffnet **ECAD-Konnektor** die explizite Übergabe.
KiCad ist der aktive Adapter. **Forward Annotation** bietet die explizite
Verknüpfung mit einem vorhandenen Projekt, einen geprüften Änderungslauf und
getrennte Aktionen zur Neuanlage. Änderungen werden in einem eigenen
maximierten Fenster geprüft. Ein bestehender Projektordner wird bei einer
Neuanlage nicht überschrieben; verknüpfte Projekte können nach Prüfung
gezielt aktualisiert werden. Weitere Einzelheiten stehen in Kapitel 27.

Bei lokaler ISD-Installation sucht die Suite KiCad automatisch. Falls die
Erkennung fehlschlägt, **Programm manuell auswählen …** verwenden; der Pfad
wird arbeitsplatzbezogen gespeichert. **Neues Projekt lokal anlegen …** öffnet erst
beim Klick einen Ordnerdialog. Ein erreichbarer Share ist als Ziel möglich.
Wenn ein nativer Dialog auf diesem Rechner nicht verfügbar ist, erscheint
eine Pfadeingabe als Ausweichmöglichkeit. Das Projekt kann anschließend im
KiCad-Projektmanager geöffnet werden. Ein Browser kann Desktopprogramme
nicht selbst suchen oder starten. Bei zentralem Hosting muss ein eigener
Arbeitsplatz-Connector diese Aktionen ausführen; bis dahin den ZIP-Export
verwenden. Die Betriebsart des Servers wird mit
`ISD_ECAD_WORKSTATION_MODE=central` festgelegt.

Das erzeugte Projekt enthält eine Wurzelseite, Domain- und AE-Seiten sowie
die hierarchischen Verbindungen ohne physikalische Bauteile. Die Blocksheets
erhalten Architekturfarben, größere Titel und einen separaten inneren
grafischen Rahmen. Anschlussnamen liegen im Block; die Netznamen stehen
über verlängerten Anschlussleitungen. Der Generator meldet rechnerisch
erkannte Textkollisionen im Projekt-Mapping. Der innere Rahmen ist ein
eigenes KiCad-Objekt und folgt einer späteren manuellen Größenänderung des
Sheets nicht automatisch.

Eigenschaften werden direkt am ausgewählten Architekturobjekt gepflegt.
KiCad speichert freie Felder am Label und am Sheet, nicht als gemeinsame
Eigenschaft sämtlicher Liniensegmente. Backannotation verändert
Realisierungsattribute, während bestehende Anforderungsattribute erhalten bleiben.
**Backward Annotation** liest die ausgewählte `.kicad_pro` und rekursiv ihre
referenzierten Schaltplanblätter. Im lokalen Betrieb: **ECAD-Konnektor →
Backward Annotation → Projektdatei auswählen → Projekt einlesen**. Zuvor
alle Änderungen in KiCad speichern. Im zentralen Betrieb den Projektordner
als ZIP einschließlich Projektdatei und aller referenzierten Blätter hochladen.

Ab v0.39.0 enthält die Projektdatei die ISD-Zuordnung und den Exportstand.
Für vorhandene v0.38.x-Projekte muss `isd_kicad_bindings.json` weiterhin im
Projektordner liegen. Die tatsächliche Sheet-Hierarchie bestimmt die Zugehörigkeit:
Root-Unterblätter sind Domänen, deren Unterblätter AEs. Weitere Ebenen und
physikalische Bauteile werden nicht als neue AEs zurückgespielt.

Die Vorschau zeigt neue, geänderte, verschobene und entfernte Domänen/AEs,
Ports, Netznamen, HOST/Teilnehmer, Busmitglieder und unterstützte Metadaten.
Objekte werden über stabile ISD-IDs beziehungsweise KiCad-UUIDs zugeordnet,
nicht über ihren Namen. Für neue native Blätter und Pins entstehen stabile IDs.
Gleichzeitige Änderungen in ISD und KiCad werden einzeln entschieden. Die
Übernahme erfolgt atomar in den vorhandenen SPOT-Stand und wird gespeichert.
Ein unverändertes erneutes Einlesen erzeugt keine weiteren Änderungen.

HW-Ports tragen den angeschlossenen Netz- beziehungsweise Busnamen. Ein
unverbundener Blatt-Pin mit passendem hierarchischem Label bleibt als Port ohne
Link erhalten. Eine Verbindung entsteht erst mit eindeutigem HOST und mindestens
einem weiteren AE. Die Blatt-Pin-Richtung `output` kennzeichnet einen HOST;
mehrere HOSTs und mehrdeutige Rollen müssen zunächst in KiCad geklärt werden.
Eine Umbenennung eines gebundenen HW-Ports in ISD benennt auch das zugehörige
Netz und dessen übrige HW-Ports um.

Die Rückübertragung prüft Hierarchie, Bus-Aliase, Busmitglieder und geschützte
Kennungen. Sie ersetzt keinen KiCad-ERC. Unterschiedliche Aliasdefinitionen,
fehlende Blätter/Labels und das Zusammenführen mehrerer bereits gebundener
SPOT-Netze werden zur Klärung gemeldet. Löschungen mit weiterhin vorhandenen
fachlichen Referenzen können nicht als ungültiger Projektstand gespeichert werden.
Funktions Elemente (FE) und der KiCad Bus Content Wizard folgen in einem späteren
Schritt; die funktionalen Port-Instanzen gehören zu dieser FE-Ebene.

### Architektur aus einem vorhandenen Schaltplan erstellen

Seit v0.39.1 kann eine SCM-Struktur ohne vorausgegangenen ISD-Export importiert werden:

1. In ISD ein neues Projekt mit leerer HW-Architektur anlegen.
2. **ECAD-Konnektor → Backward Annotation** öffnen.
3. Importmodus **Architektur aus Schaltplan erstellen** wählen.
4. Die Zuordnung der SCM-Blätter prüfen: oberste Blätter als Domänen und deren
   Unterblätter als AEs, oder oberste Blätter als AEs in einer gemeinsamen Domäne.
   „Automatisch vorschlagen“ verwendet die erste Variante, wenn jedes oberste Blatt
   Unterblätter enthält; andernfalls die zweite. Die fachliche Bedeutung der Blätter
   wird damit nicht automatisch bewiesen.
5. `.kicad_pro` auswählen oder den vollständigen Projektordner als ZIP hochladen.
6. Vorschau prüfen. Bei unklarer Richtung pro Netz den HOST aus den beteiligten AEs
   auswählen oder offen lassen. Ohne eindeutigen HOST bleiben Ports und Netzzuordnung
   erhalten; es entsteht zunächst keine gerichtete Verbindung.
7. **Geprüfte Änderungen in SPOT übernehmen** ausführen.

Eine vorhandene ISD-Binding-Datei ist beim Erstimport nicht erforderlich. IDs werden
im neuen Projekt aus KiCad-UUIDs stabil abgeleitet; Kennungen eines fremden
ISD-Projekts werden nicht als Identität des neuen Projekts übernommen. Namen,
Grenzports, elektronische Netze und Busmitglieder bilden die HW-Architektur.
Physikalische Einzelbauteile werden nicht zu AEs. Tiefere Implementierungsblätter
bleiben unterhalb der gewählten AE-Ebene. Doppelte Blattnamen erhalten im neuen
ISD-Projekt einen eindeutigen Namenszusatz.

Bei einem flachen Schaltplan entsteht eine gemeinsame Domäne mit einem AE für das
gesamte Blatt; explizite hierarchische Anschlüsse werden als Ports übernommen. Eine
fachliche Blockaufteilung muss anschließend vorgenommen werden. Mehrfach verwendete
Architekturblätter müssen vor dem Import eindeutig aufgeteilt werden.

Die Original-Schaltplandateien werden nicht verändert. ISD speichert die
Quellzuordnung, so dass spätere Rückübertragungen im Modus **Bestehende Architektur
aktualisieren** dieselben Objekte wiederfinden. Der Erstimport überschreibt keine
bereits gefüllte HW-Architektur. Requirements im neu angelegten Projekt bleiben
bestehen; ihre Verknüpfung mit den importierten AEs ist ein eigener Arbeitsschritt.

Für künftige Bauteile sind RefDes projektweit je Präfix fortlaufend vorgesehen
(`R1`, `R2`, `C1` usw.). Bereits vergebene Kennungen bleiben beim Verschieben
zwischen Domains und AEs erhalten. Diese Zugehörigkeit steht in eigenen
Feldern; der gegenwärtige bauteilfreie Export vergibt noch keine Referenzen.

## 20. Mechanik-, Software- und Normenfunktionen

### 20.1 Mechanik / CAD

Unter **Komponenten** mechanische Objekte mit Art, Material, Geometrie,
Befestigung, Kühlung und zugeordnetem Requirement anlegen. Im Reiter
**Randbedingungen** Bauraum, Umgebungsgrenzen und weitere Anforderungen
pflegen. **Mechanische Interfaces** können die Beziehung von Gehäuse,
Befestigung oder Kühlkontakt zu einem Partner dokumentieren. Die Ansicht
**Thermik & PCB-Kopplung** fasst vorhandene thermische Eckdaten und
PCB-Randbedingungen wie Outline, Keep-out und Höhenzonen zusammen. Eine
Änderung an diesen Einträgen erzeugt noch kein CAD-Modell und keine neue
Leiterplattengeometrie; sie erzeugt eine nachvollziehbare Übergabeaufgabe.

### 20.2 Software / Firmware

**Komponente** erstellt ein Software-, Firmware- oder HDL-Objekt. Es kann
Protokollmerkmale, physische Zuordnung, Deploymentbezug und
Requirement-Verknüpfung besitzen. **Protokolle & APIs** zeigt die
fachlichen Schnittstellen. **SW_IF** und **FW_IF** trennen API,
Nachrichten oder Zustandsübergänge von der elektrischen Schnittstelle im
HW-Modell. **Deployment** ordnet eine Komponente dem Zielsystem zu.
**Arbeitspaket** hält Umsetzungsschritte als Backlog; **Backlog & Tests**
zeigt ihre Verknüpfung mit Anforderungen. Ein offenes Arbeitspaket ist keine
bestätigte Implementierung. Ein protokolliertes Testziel ist noch kein
ausgeführter Test.

### 20.3 Normen & Standards

Im Normenkatalog Ausgabe, Gültigkeit, Anwendbarkeit und gegebenenfalls
Klauseln erfassen. **Norm oder Standard zuordnen** verknüpft das konkrete
Requirement. Im Inspektor zeigen offene Normenbezüge, was noch geprüft
werden muss. **Technische Quelle hinzufügen** kann ein Datenblatt, einen
Herstellerhinweis oder einen Link mit Gültigkeitskontext und lokalem
Original ablegen. Herstellerangaben können zur Bewertung beitragen; sie
sind nicht automatisch ein rechtlicher oder technischer Konformitätsnachweis.

## 21. KI-Konfiguration und Assistent im Detail

Über das Schlüsselsymbol Provider und Modell auswählen. Zur Auswahl stehen
OpenAI, ein OpenAI-kompatibler oder lokaler Dienst sowie eine experimentelle
Microsoft-365-Copilot-Variante. Bei einem kompatiblen Dienst die Basis-URL,
Modellkennung und dessen Authentifizierungsanforderungen prüfen. OpenAI
benötigt einen passenden API-Schlüssel und ein für das Konto freigeschaltetes
Modell. Die Copilot-Variante setzt eine geeignete Lizenz und ein delegiertes
Graph-Token voraus; sie ist kein automatischer Ersatz für eine
OpenAI-kompatible API. Schlüssel entweder für die laufende Sitzung oder im
Credential Manager speichern; nach Auswahl von Provider und Modell muss
die Verbindung für neue Aufträge nutzbar sein. Die Oberfläche kann den
Verbrauch der ISD-Sitzung anzeigen; eine vollständige Abrechnung des
Providers sollte im jeweiligen Konto geprüft werden.

Der KI-Assistent ist als Gespräch mit Frage, Antwort und kontrollierter
Aktion ausgelegt. **Enter** sendet, **Umschalt + Enter** erzeugt eine neue
Zeile. Antworten lassen sich kopieren. Eine angezeigte Arbeitsmeldung
signalisiert laufende Anfrage. Ein Änderungsauftrag erzeugt zunächst einen
prüfbaren Vorschlag; erst nach bewusster Übernahme entstehen Änderungen im
Projektmodell. Gerade bei Redesign-Analysen Netznamen, Pinrichtungen,
Host-/Teilnehmer-Zuordnung und Partidentität vor der Übernahme mit dem
Original abgleichen. KI-Ausgaben können Lücken, Doppelbenennungen oder
falsche technische Schlüsse enthalten.

## 22. Im- und Exportformate und ihre Grenzen

| Format | Ein- oder Ausgabe | Enthaltene Aussage | Vor Weitergabe prüfen |
| --- | --- | --- | --- |
| Projekt-JSON | Import und Export | Fachliches Gesamtmodell mit IDs, Beziehungen, Revision im aktuellen Stand | Originaldateien und Schlüssel fehlen; Startkontext beim Import ausdrücklich wählen. |
| ReqIF | Requirements-Import und -Export | Strukturierte Anforderungen und ausgewählte Austauschfelder | Toolprofil und nicht abgebildete Evidenz prüfen. |
| XLSX | Requirements-Import und -Export | Tabellenförmige Requirements | Spaltenmapping, Elternkennungen und Zelltypen prüfen. |
| CSV | Requirements-Import und -Export | Tabellenförmige Requirements | Trennzeichen, Zeichensatz, Hierarchie und Feldgrenzen prüfen. |
| DOCX | Requirements-Import und -Export | Konventionelle Dokumentensicht | Tabellenstruktur und fehlende Spezialbeziehungen prüfen. |
| Requirements-PDF | Review-Export | Lesbare Zusammenstellung | Kein Rückimportformat. |
| Architektur-PDF | Export | System-, HW-, Mechanik- und Software-/Firmwarearchitektur, einzeln oder gemeinsam | Übersichten, Beziehungen und Detailseiten prüfen. |
| `busconts.ini` | Export | Bus-Content für die ECAD-Weiterverarbeitung | Template- und Pinzuordnung im Zielwerkzeug prüfen. |

Beim vollständigen JSON-Import stehen zwei Übernahmearten zur Wahl. Für das
**aktuelle Projekt als Revision** bleiben Projekt-ID und Projektname
bestehen, während der importierte fachliche Inhalt zum neuen Arbeitsstand
wird. Für **neues Projekt** entstehen neue Projekt-ID und gegebenenfalls
ein eindeutiger Namenszusatz. **Vor jeder Übernahme** ist das Feld
**Startkontext des importierten Projekts (Pflichtfeld)** auszuwählen.
Der in der Datei enthaltene alte Kontext wird in der Vorschau gezeigt, aber
nicht still als Entscheidung übernommen. Die beiden Übernahmeaktionen
werden erst nach der Auswahl bedienbar. Beim partiellen
Requirements-Import Änderungen in der Vorschau prüfen und unbekannte
Elternkennungen korrigieren; die Übernahme sichert vorher eine Revision.

## 23. Reproduzierbarer Prüfdurchlauf

Die folgenden Schritte eignen sich, um die wesentlichen Funktionen nach
einer Installation im eigenen Projekt nachzuvollziehen:

1. Ein leeres Projekt mit passendem Startkontext anlegen. Den Namen in der
   Projektauswahl wiederfinden und das Profil in der Kopfzeile ansehen.
2. Eine Domain und darin zwei AEs anlegen. Die Anzeige im Navigator und im
   Canvas prüfen; den technischen ECAD-Key und die Farbe bearbeiten.
3. Über den Signal-Wizard ein Signal aus dem Katalog erzeugen. Host und
   Teilnehmer zuweisen. Danach im Navigator den Signalnamen anklicken: alle
   zugehörigen Züge sollen hervorgehoben werden.
4. Die Definition und einen automatisch erzeugten AE-Port öffnen. Namen,
   Port Type oder Beschreibung ändern; den gespeicherten Stand erneut laden
   und prüfen, ob die Änderung erhalten blieb. Über die Eingabemaske
   Aufgabe und Netzklasse bearbeiten. Die Objekt-ID bleibt dabei unverändert.
5. Eine Requirements-Aussage mit Quelle, Ebene und Akzeptanzkriterium
   erfassen. Ein AE oder eine Realisierung zuordnen und kontrollieren, dass
   die Erfüllungsbewertung weiterhin offen ist.
6. Einen Test definieren. Erst nach einer tatsächlichen Ausführung Ergebnis,
   Evidenz und geprüfte Revision eintragen. Den Unterschied der
   Statusdimensionen im rechten Detailbereich nachvollziehen.
7. Eine benannte Revision speichern und das ganze Projekt als JSON
   exportieren. Beim Reimport die Datei prüfen, **Startkontext** bewusst
   wählen und zwischen neuem Projekt und Import als Revision entscheiden.
8. Anforderungen als Teilformat exportieren und die angezeigten
   Informationsgrenzen mit dem vollständigen Projekt-JSON vergleichen.
9. Die Architektur-PDF öffnen: Gesamtbild und Domain-Details gegen den
   Canvas-Stand prüfen. Originaldokumente separat mit dem Datenverzeichnis
   sichern.

## 24. Fachliche Grenzen des Modells

Die ISD Suite verwaltet eine logische, fachübergreifende
Entwicklungsarchitektur. Für ein vollständiges ECAD-Design werden später
Symbole, echte Pins, Schaltplan, physische Netze, Footprints und PCB im
Zielwerkzeug benötigt. Die Suite kann Übergabedaten und Bindungen vorbereiten,
aber ein dargestellter Architekturzug ist noch kein elektrisch verifizierter
Schaltplan. Ebenso ersetzen mechanische Randbedingungen keine CAD-Geometrie
und ein Softwaremodul keinen implementierten Quellcode. SPOT-JSON hält die
gemeinsame fachliche Wahrheit der Suite; andere Werkzeuge müssen bei einer
Integration dieselben IDs, Typen und Referenzen respektieren. Eine
Rückannotierung gehört erst nach expliziter Prüfung in den Arbeitsstand.

## 27. Gemeinsame Architektur und Realisierungen (v0.40.0)

Der Reiter **Architektur** enthält eine Auswahl zwischen Systemarchitektur,
Hardware/ECAD, Mechanik/CAD und Software/Firmware. Die Hardwareansicht enthält
weiterhin die gewohnten Domänen, AEs, Ports, Netze, Busse und ECAD-Werkzeuge.
**HW / ECAD**, **Mechanik / CAD** und **Software / Firmware** sind die
Realisierungsräume.

### Systemarchitektur aufbauen

1. In **Architektur → Systemarchitektur** wechseln.
2. Systemdomänen und Systemelemente mit eindeutigen Namen und einer
   Aufgabenbeschreibung anlegen. Externe Systeme/Akteure als extern markieren.
3. Schnittstellen und Beziehungen mit Quelle, Ziel und Typ anlegen.
   Information, Energie, Material und Abhängigkeit können einzeln gefiltert werden.
4. Ein Systemelement auswählen und **Realisierungen zuordnen** öffnen.
   Vorhandene HW-AEs, technische HW-Realisierungen, Mechanikobjekte und
   SW/FW-Komponenten auswählen. Mehrere Objekte pro Funktion sowie gemeinsam
   genutzte Realisierungen sind möglich.
5. Navigator oder Diagramm zur Auswahl nutzen. Auswahl hebt zugeordnete
   Systemelemente hervor. Über die Details zu HW-AEs oder Realisierungen springen.

Domänen sind einklappbar. **Anforderung** zeigt die funktionale Systemstruktur,
**Realisierung** ihre technischen Zuordnungen, **Vergleich** beide Perspektiven.
Es werden keine elektrischen Netzdetails automatisch als Systemfunktionen
interpretiert. Fehlende Realisierungen oder entfallene Zielobjekte werden angezeigt.
Das Entfernen einer Zuordnung löscht die Realisierung nicht.

### Zwei Attributräume und ein Objektkern

Objekte besitzen genau eine stabile Identität. **Anforderungsattribute** und
**Realisierungsattribute** gehören zum selben Objekt; sie erzeugen keine Kopie
und keine zweite UUID. Ein eigenständiges Systemelement und ein zugeordnetes
HW-AE besitzen dagegen eigene Identitäten und eine explizite Beziehung.
Die Kennungen werden wie bisher als SHA-256 angezeigt.

Unter **Eigenschaften** werden Werte typisiert eingegeben: Textfeld,
Zahl beziehungsweise Wertebereich mit Einheit, Ja/Nein und Dropdown.
Strukturierte Angaben nutzen JSON. Im SPOT werden beispielsweise gespeichert:

- Text: `"Temperaturüberwachung"`
- Zahl: `3`
- Wert mit Einheit: `{"value": 5, "unit": "V"}`
- Vorgabe mit Grenzen: `{"min": 4.75, "max": 5.25, "unit": "V"}`

Der Vergleich prüft explizite Werte und Grenzen. Unterstützte Einheiten
derselben Größe werden für den Vergleich normiert, etwa mV/V oder mA/A;
die gespeicherten Werte behalten ihre Einheit. Unbekannte Einheiten und
abweichende Bedingungen bleiben zur Prüfung offen. Der Vergleich ist kein
Verifikationsnachweis. Fehlende Werte bleiben als offen gekennzeichnet.

Explizite KiCad-Vorgaben können auf der Realisierungsseite als `ecad`-Objekt
gepflegt werden, zum Beispiel `{"kicad": {"netClass": "Measurement",
"constraints": {"trackWidthMm": 0.4}}}`. Alte Angaben unter
`attributes.ecad.kicad` bleiben als Rückfall erhalten. Es werden ausschließlich
explizite Werte übertragen; die automatische Ableitung von Netzklassen aus
Anforderungen ist weiterhin ein späterer Schritt.

Ältere Attributes/Properties bleiben im SPOT verlustfrei erhalten.
Nicht mehr passende Systemwerte werden als technische Bestandsmetadaten
archiviert. Eigene Attributdefinitionen werden im Property Manager verwaltet;
eine automatische fachliche Einstufung alter Freitextangaben findet nicht statt.
Kennungen und interne Synchronisationsdaten bleiben geschützt.

### Realisierungsräume

- **HW / ECAD:** technische Realisierungen mit generischer Funktion,
  Anforderungen, AE-Zuordnung, Varianten und ausgewählter Bauteilbesetzung.
  Von dort die bestehende Hardwarearchitektur oder den ECAD-Konnektor öffnen.
- **Mechanik / CAD:** bestehende Komponenten, Baugruppen und Randbedingungen;
  Systembezug und beide Attributräume an den Komponenten.
- **Software / Firmware:** bestehende Module, Deploymentbezüge, Schnittstellen
  und Arbeitspakete; Systembezug und beide Attributräume an den Komponenten.

FE-Objekte aus dem Schaltplan werden in einer späteren Version ergänzt.

### ECAD-Projekt ausdrücklich verknüpfen

**ECAD-Konnektor → Forward Annotation → Bestehendes Projekt auswählen** liest
zunächst die Projektdatei. Bei einer vorhandenen ISD-Bindung werden die
Identitäten erkannt. Für native Projekte ohne Bindung werden Architekturblätter
angezeigt; deren Zuordnung zu vorhandenen Domänen/AEs muss bestätigt werden.
Die Zuordnung ist eindeutig pro Blatt. Verknüpfen ändert weder Schaltplan noch
Architekturobjekte und ersetzt nur die aktive Projektverknüpfung.

Ein neues Projekt entsteht ausschließlich über **Neues Projekt lokal anlegen**
oder **Neues Projekt als ZIP herunterladen**. Das lokal erzeugte Projekt wird
aktiv verknüpft; ZIP-Erzeugung allein ändert keine lokale Projektzuordnung.
Die höchste installierte KiCad-Version wird numerisch ausgewählt. Ein explizit
gewählter Programmpfad gilt für den jeweiligen Aufruf.

### Änderungen im eigenen Fenster prüfen

Forward- und Backannotation öffnen separate maximierte Prüffenster. Dort stehen
Objektgruppen, Suche, Statusfilter, neue/geänderte/gelöschte Angaben und
Vorher-/Nachher-Spalten bereit. Identität und vollständige Werte sind in den
Details erreichbar. Einzeländerungen können ausgewählt oder ausgelassen werden;
Konflikte müssen für die Übernahme ausdrücklich gelöst werden.

Die ausgewählte Menge wird gemeinsam validiert. Zusammengehörige Änderungen
müssen gemeinsam ausgewählt werden, wenn ansonsten beispielsweise ein AE ohne
Domäne oder ein Blattverweis ohne Schaltplandatei entstehen würde. Nicht
unterstützte Änderungen können nicht übernommen werden. Ausgelassene
Forward-Änderungen bleiben für eine spätere Prüfung offen.

In ISD-generierten Projekten vergleicht Forward die gemeinsame Basis, die
aktuelle Architektur und den aktuellen Schaltplan. Unabhängige native
Schaltplanobjekte und Feldänderungen bleiben erhalten. Bei konkurrierenden
Änderungen wird ein Konflikt angezeigt. Vor dem Schreiben werden Dateiänderungen
seit der Prüfung abgefangen und betroffene Dateien in einem eigenen
`isd_forward_backup_…`-Ordner gesichert. Entfallene Blattdateien bleiben erhalten;
der geprüfte Elternverweis kann entfernt werden.

In nativen SCM-Projekten werden zugeordnete Blattnamen/-Eigenschaften sowie
bekannte Signalnamen/-Eigenschaften aktualisiert. Änderungen der nativen
Blockhierarchie, Busstruktur oder Verdrahtung werden nicht automatisch
konstruiert: im Schaltplan bearbeiten und anschließend zurücklesen.

Backannotation liest weiterhin `.kicad_pro` und die referenzierten Blätter oder
ein vollständiges Projekt-ZIP. Die Erstimportfunktion erzeugt eine HW-Architektur
in einem Projekt mit leerer HW-Struktur. Andere Disziplinen bleiben erhalten.
Bestehende Anforderungsattribute werden durch Backannotation nicht verändert.
Unverbundene Ports bleiben zulässig. HW-Portnamen entsprechen den Netz- oder
Busnamen; funktionale `…Port…`-Benennungen bleiben späteren FEs vorbehalten.

Für lokale Programme und Dateien ist lokaler Betrieb beziehungsweise ein
Arbeitsplatz-Connector nötig. In zentralem Betrieb bleibt der ZIP-Austausch
verfügbar. Die eigene KiCad-ERC-Prüfung bleibt erforderlich; ISD ersetzt sie nicht.

## 28. Property Manager und Netzklassen (v0.42.0)

### 28.1 Definitionen und Objektwerte

Der Property Manager in der Kopfzeile verwaltet projektweit **Attribute** und **Netzklassen**. Attributwerte bearbeiten Sie am jeweiligen Objekt, getrennt für Anforderung und Realisierung. Definitionen enthalten Schlüssel, Anzeigename, Beschreibung, Objekttypen, Attributräume, Datentyp, Einheit, Auswahlquelle, Grenzen, Standardwert und Austauschrichtung. Die Übersicht zeigt die Bedeutung in der mittleren Spalte. Suche und Objekttypfilter reduzieren die Auswahl; ein Klick auf den Namen öffnet das Detailfenster.

Systemdefinitionen sind geschützt und nicht löschbar. Ihre Werte bleiben bearbeitbar, sofern das jeweilige Feld nicht ausdrücklich nur lesbar ist. Eigene Definitionen können angelegt, geändert und gelöscht werden. Schlüssel und Kennung bleiben nach der Anlage unveränderlich. Änderungen an Typ oder Geltungsbereich werden gegen vorhandene Werte geprüft. Eine Löschung mit belegten Werten benötigt eine Rückfrage mit den betroffenen Objekten.

Netzklassen erscheinen nur an Netzen und Busmitgliedern. Am Bus dienen sie als Vorgabe für Mitglieder ohne eigene Zuweisung. Ports zeigen die Klasse des angeschlossenen Netzes, ohne sie selbst zu besitzen. Mechanik- und Softwarearchitekturelemente erhalten fachlich passende Felder; Repository, Build und CAD-Referenz gehören zur konkreten Realisierung.

Eingabeformen: Text, Zahl oder Bereich mit Einheit, Ja/Nein, Auswahlliste, Mehrfachwerte, Referenz und strukturierte Angaben. Dropdowns verwenden feste Werte, den Signal-/Interfacekatalog, den Netzklassenkatalog, Projektobjekte oder Signalrollen zum gewählten Schnittstellentyp. Bestehende freie Werte werden nicht stillschweigend ersetzt. Leere Werte bleiben offen und sind keine Nullwerte.

Die bisherigen Managerreiter Bestandsangaben und Templateprüfung entfallen. Ältere Angaben bleiben im SPOT erhalten. Nicht mehr passende oder entfernte Speed-/Power-Werte werden unter den technischen Bestandsmetadaten archiviert. Die Vorlagenhinweise finden Sie unter **Signale & Interfaces → Vorlagen → Signal- und Interfacevorlagen prüfen**.

### 28.2 Netzklassen zuweisen

Netzklassen beschreiben im ISD den Verwendungszweck. Das Klassenfenster enthält Name und Beschreibung; bereits übernommene ECAD-Regelparameter werden lesbar mit Herkunft angezeigt. Die Klassenkennung bleibt bei einer Umbenennung erhalten, und ISD-Zuweisungen werden konsistent aktualisiert. Das ECAD-Projekt wird erst bei einer geprüften Forward Annotation geändert.

| Netzklasse | Verwendung |
|---|---|
| POWER_SUPPLY | Elektronik- und Logikversorgung, etwa MCU und Sensoren |
| POWER_LOAD | Leistungspfad zu Verbraucher oder Energiespeicher, etwa Batterie-Lade-/Entladepfad |
| POWER_SWITCHING | Eigentlicher Schaltknoten zwischen Transistor, Diode und Spule |
| POWER_SENSE | Mess- und Rückmeldeleitung im Leistungspfad, etwa Kelvin-Sense |
| POWER_RETURN | Dedizierte Last-Rückleitung |
| GROUND | Allgemeine Masse und Versorgungsrückleitung der Elektronik |

Eine geschaltete Verbraucher-Versorgung bleibt POWER_LOAD. Zellspannungs- und Temperatursignale sind Messsignale, keine Lastpfade. Weitere Klassen unterscheiden digitale Signale, Takte, analoge Messpfade, Referenzen, Quarze, Gate-Ansteuerung und Schnittstellenprofile. Gemischte Busse werden pro Mitglied betrachtet, etwa PCIe-Daten, Referenztakt, Reset und Versorgung.

Eindeutige Rollen aus dem Signaltemplate erhalten eine passende Klasse. Vorhandene Zuweisungen bleiben erhalten; absichtlich geleerte Werte werden nicht automatisch erneut gesetzt. Unklare physikalische Varianten oder Leistungsfunktionen bleiben **Offen**. Unter **Property Manager → Netzklassen → Netzzuordnungen prüfen** sehen Sie jedes Einzelnetz und Busmitglied, die aktuelle Zuweisung und die offenen Fälle. Filter und Dropdown unterstützen die vollständige Zuordnung.

Es gibt keine separate Geschwindigkeits- oder Leistungsklassifizierung. Strom, Spannung, Frequenz oder Flankenzeit können als Engineering-Angaben am passenden Objekt dokumentiert werden. Die genaue Typisierung durch Constraints und Design Rules erfolgt im ECAD-Tool. Aus einer Klassenzuweisung werden keine PCB-Maße berechnet.

### 28.3 Annotation und Migration

Die Forward Annotation überträgt Klassendefinitionen und Zuordnungen. Die Backannotation bietet geänderte Klassen, Prioritäten und explizite Regelparameter im separaten Prüffenster an. Übernommene Regeln werden gespeichert und bei späterer Forward Annotation erhalten. Anforderungswerte werden nicht durch Designangaben überschrieben.

Alte ISD-Präfixe werden im Projektkatalog entfernt, Klassenkennungen und ECAD-Parameter bleiben erhalten. Unbenutzte und unkonfigurierte allgemeine Low/Mid/High-Vorgaben entfallen. Benutzte oder konfigurierte Altkategorien bleiben getrennt erhalten; ihre bisherigen Regelunterschiede werden nicht zusammengeführt. Die Migration schreibt keine verknüpften ECAD-Dateien ohne Annotation.

Die native KiCad-DRC bleibt maßgeblich für die Wirksamkeit von Regeln. Komplexe Regelbereiche und nicht exportierte effektive Klassenzuweisungen müssen im ECAD-Tool geprüft werden. Der spätere Übersetzer von Anforderungen in Layoutregeln bleibt eine eigene Funktion.

## 29. Software- und Mechanikarchitektur bearbeiten

Unter **Architektur** die Fachsicht wählen. **Element hinzufügen** öffnet Name, Funktion/Beschreibung, Elementtyp, Hierarchie, Requirementsbezug, Systemelemente und konkrete Realisierungen. Architekturblöcke und Realisierungen besitzen unabhängige stabile Kennungen. Ein Architekturblock kann mehrere Realisierungen referenzieren, und eine Umsetzung kann mehreren Architekturblöcken dienen.

**Beziehung hinzufügen** verlangt zwei vorhandene Elemente und einen passenden Typ. Mechanik: Befestigung, Einbau, Kontaktfläche, Wärmeweg, Abhängigkeit. Software/Firmware: API, Datenfluss, Ereignis, Kommunikation, Abhängigkeit. Beziehung und Elemente sind im Inspektor bearbeitbar und mit Rückfrage löschbar. Hierarchiezyklen und Selbstbeziehungen sind unzulässig.

Die Sicht Anforderung zeigt das Architekturdiagramm. Realisierung zeigt die zugeordneten konkreten Objekte; Vergleich führt beide zusammen. **Aus Realisierungen übernehmen** erzeugt ausdrücklich eigenständige Architekturblöcke für bislang nicht verknüpfte Umsetzungen. Bestehende Realisierungen und ihre Kennungen bleiben unverändert; der Aufruf ist wiederholbar und erzeugt keine Duplikate. Fehlende Realisierungen bleiben als Lücke sichtbar.

Die Realisierungsreiter Mechanik/CAD und Software/Firmware dienen weiterhin der konkreten Umsetzung. Die Hardwarearchitektur bleibt unverändert als Domänen-/AE-/Port-/Netzmodell die ECAD-Schnittstelle.

## 30. Die vollständige Requirementskette

### 30.1 Fachliche Ebenen und Verantwortlichkeit

| Schritt | Aussage | BMS-Beispiel |
|---|---|---|
| Quelle / Systemidee | Zweck, Herkunft und Geltungsbereich | Lastenheft zur Batterieüberwachung |
| L1 Kundenanforderung | Erwarteter Nutzen des Systems | 14S-Batteriesystem überwachen |
| L2 Systemanforderung | Erforderliches Systemverhalten | 14 Zellspannungen und relevante Temperaturen erfassen |
| L3 Technische Anforderung | Messbare technische Eigenschaft | Zellspannungen über 15 Abgriffe mit definierter Genauigkeit erfassen |
| L4 Disziplinanforderung | Beitrag von HW, Mechanik, SW/FW | HW-Messpfad, FW-Abtastrate, sichere Steckermontage |
| Architekturzuordnung | Verantwortliches Objekt | AE Zellmessung, FW-Messmodul, mechanischer Anschluss |
| Realisierung | Gewählte konkrete Umsetzung | Messbaustein und Schaltung, Code/Build, CAD-Ausführung |
| Bewertung / Verifikation | Ergebnisbeleg für den betrachteten Stand | Kriterienbewertung und Prüfbericht zur Messgenauigkeit |

Architektur und Realisierung sind keine weiteren Anforderungsebenen. Objekte können Anforderungen aus unterschiedlichen Ebenen tragen. Gemeinsame Zuordnung zu einem Requirement erzeugt keine zusätzliche Beziehung zwischen den Objekten; Abhängigkeiten und Schnittstellen müssen ausdrücklich gespeichert sein. Auch beim Redesign bleibt ein Bestandsbefund eine Beobachtung, bis daraus eine Anforderung formuliert wird.

### 30.2 Beziehungen, Regeln und Darstellung

Die Grafik enthält L1–L4, **Architekturverantwortung**, technische Realisierungen und systemdefinierende Bauteile/Module. Der Abhängigkeitsfokus zeigt direkte Beziehungen oder die vollständige Kette. Ein Kartenklick zeigt die Details rechts; Bearbeiten öffnet die zum Objekt passende Eingabemaske. **Vollständige Requirementskette** im Requirement-Inspektor öffnet ein separates maximiertes Fenster für Quellen, Ebenen, Zuordnungen, Bewertungen, offene Stellen und Testbelege.

Historische Elternreferenzen, Ableitungsobjekte und typisierte Beziehungen werden gemeinsam ausgewertet und dedupliziert. Die gleiche Beziehungsauswertung gilt für Grafik, Detailansichten, Status und Requirements-Export. Neue Ableitungen führen auf tiefere Ebenen. Benachbarte Ebenen sind der Normalfall; ein Ebenensprung benötigt eine Begründung. Zyklen werden über sämtliche gespeicherten Formen hinweg abgewiesen. Importierte alte Ebenensprünge bleiben sichtbar und werden zur Prüfung gekennzeichnet. ReqIF bildet für seine Baumhierarchie einen Elternpfad ab; zusätzliche Eltern bleiben im exportierten Elternfeld erhalten.

### 30.3 Fortschritt und Nachweisaktualität

Sechs Aussagen sind getrennt zu lesen: **fachliche Freigabe**, **Ableitung**, **Objektzuordnung**, **bewertete Erfüllung**, **Testdefinition**, **Testergebnis**. Eine Zuordnung allein belegt keine Erfüllung. Ein definierter Test allein belegt kein bestandenes Ergebnis. Der Soll-/Ist-Attributvergleich ist ebenfalls kein Verifikationsnachweis.

Eine positive Erfüllungsbewertung verlangt Akzeptanzkriterien, deren Bewertung, Begründung und Ergebnisbeleg. Ihr Objektstand umfasst Requirement, Realisierung, Variante und referenzierte Umsetzungsobjekte. Änderungen am betroffenen Stand kennzeichnen die Bewertung als prüfbedürftig. Fehlende oder geänderte Bauteile werden dabei berücksichtigt.

Ein bestandener Test benötigt tatsächliches Ergebnis, Beleg, Zeitpunkt und geprüfte Revision. Die Option **Ergebnis gilt für den aktuellen Anforderungs- und Umsetzungsstand** bestätigt beim Speichern ausdrücklich, dass der Nachweis zur aktuellen Konfiguration gehört. ISD speichert dazu den betreffenden Objektstand. Spätere Änderungen an Anforderung, Architektur, Implementierung oder Testdefinition führen zu **Nachweis erneut prüfen**. Bestehende Ergebnisse und Reports bleiben erhalten. Altnachweise ohne gespeicherten Objektstand werden nicht automatisch als aktuell eingestuft. Die Bestätigung ist eine fachliche Nutzerentscheidung und ersetzt keine erneute Prüfung des realen Systems.

Die Auswertung verfolgt gespeicherte Abhängigkeiten. Änderungen außerhalb des Projekts, etwa im Repository, CAD-Modell oder ECAD-Design, werden erst nach Übernahme des geänderten Stands im ISD erkannt. Ein ausdrücklich dokumentierter Ebenensprung ersetzt keinen fehlenden Testbeleg.

## 31. Architektur-PDF für alle Fachsichten

In **Architektur → Architektur-PDF** öffnet sich die Auswahl der Sichten. Die aktuelle Sicht ist vorausgewählt. System-, Hardware-, Mechanik- und Software-/Firmwarearchitektur können einzeln, zusammen oder über **Alle Architekturen auswählen** exportiert werden. Jede Sicht erhält eigene Seiten und Lesezeichen; Titel und Legende erklären die Darstellung. Knoten sind anklickbar und führen zu Detailseiten. Beziehungen und Realisierungszuordnungen werden vollständig im zugehörigen Verzeichnis aufgeführt. Große Übersichten wachsen in der Papierhöhe, ohne alle Inhalte auf eine zu kleine Schrift zu reduzieren.

Das PDF ist ein Review-Export, kein Rückimportformat. Maßgeblich für die Datenhaltung bleibt das vollständige SPOT-JSON. Elektrische Schaltungsdetails und native Layoutregeln werden im ECAD-Tool geprüft.

Die Hardware-PDF enthält ab v0.43.0 eigene FE-Detailseiten mit vollständiger
Funktionsbeschreibung, Schnittstellen, Abhängigkeiten und ECAD-Herkunft.
Bauteildetails bleiben im Realisierungskontext.


## 32. Objektbezogene Attribute und Requirements (v0.43.0)

### 32.1 Attributdefinition, Wert und Objektidentität

Jeder Objekttyp besitzt die für ihn vorgesehenen Systemattribute; offene
Werte bleiben leer. Die Übersicht filtert nach Objekttyp, Attributraum und
bei Requirements nach Disziplin. **Netzklasse** gehört ausschließlich zu
Netzen, Bussen und Busmitgliedern. Ein Block erhält keine Netzklasse; ein
HW-Port zeigt die Klasse seines angeschlossenen Netzes. Aliasfelder wie
`Netclass` und `interfaceKind` werden beim Laden normalisiert. Gefüllte alte
Werte außerhalb des neuen Geltungsbereichs bleiben als `legacyPropertyValues`
im Projekt erhalten und erscheinen nicht als aktive Objektattribute.

Die SHA-256-Kennung steht einmal am übergeordneten Objekt. Attributeditoren
zeigen Beschreibung, Typ, Einheit, Austauschrichtung und den Wert. Auswahlen
nutzen feste Optionen, Projektkataloge oder abhängige Listen: beispielsweise
Netzklasse, Signalrolle und Beziehungspartner. Bestehende unpassende Werte
werden zur Prüfung gekennzeichnet. Neue Referenzen dürfen weder auf das
Objekt selbst noch auf unzulässige Zieltypen zeigen. Software kann bewusst
an HW gekoppelt werden; eine solche Kopplung wird als Beziehung gespeichert.

**Property Manager** verwaltet eigene Definitionen einschließlich Typ,
Attributräumen, Objekttypen, Disziplinen, Auswahlquelle und Zielobjekttypen.
Systemdefinitionen und Identitäten bleiben geschützt. Werte können im
Objektdialog geändert oder geleert werden; Definitionen werden dort nicht
angelegt oder gelöscht.

### 32.2 Disziplinspezifische Requirement-Eingabe

**Requirement** beziehungsweise **Requirement hinzufügen** öffnet den
Eingabedialog. Die Wahl der **Disziplin** bestimmt Kategorien und fachliche
Anforderungsattribute. Hardware: elektrische Größen und Übertragung;
Mechanik: Geometrie, Masse, Lasten, Toleranzen und Thermik; Software/Firmware:
Ressourcen, Timing, Protokoll und Datenvertrag. Gemeinsame Angaben wie
Titel, Anforderung, Herkunft, Priorität und Akzeptanzkriterien bleiben
verfügbar. Die fachlichen Felder stehen unter **Fachliche Anforderungsattribute**.

Bei Mechanik und Software/Firmware ist **ECAD-Relevanz** zunächst ausgeblendet.
**Expliziter Bezug zu HW / ECAD** blendet die Auswahl bei Bedarf ein.
Ohne diese Kopplung wird `Not Applicable` gespeichert. Vorgänger werden nur
aus höheren Anforderungsebenen angeboten. Veraltete Zuordnungen müssen vor
dem Speichern geprüft werden; Ausnahmebegründungen für direkte Erfüllung
erscheinen auf Systemebene. Ein Disziplinwechsel archiviert vorhandene Werte,
die anschließend nicht mehr zum Requirement passen.

## 33. FE, eingesetzte Kernbauteile und vollständige BOM

### 33.1 Funktionale Abstraktion und ECAD-Rückimport

Ein **Funktions Element (FE)** enthält Aufgabe, Schnittstellen und
Abhängigkeiten. Es ist mit einem HW-Architekturelement und einer oder mehreren
technischen Realisierungen verbunden. Das FE zeigt in der Architektur keine
vollständige Bauteilliste. Unter **HW / ECAD** ist dieselbe FE-Identität mit
konkreten Varianten und Kernbauteilen sichtbar. **Funktions Element anlegen**
und **FE bearbeiten** erlauben eine manuelle Beschreibung und Zuordnung.
Beim Löschen eines FE bleiben Bauteile und Dokumentquellen im Katalog;
Realisierungen ohne verbleibenden Requirement-Bezug werden ebenfalls entfernt.

Die Back Annotation über `.kicad_pro` oder das Projekt-ZIP bietet
Funktionsblöcke unterhalb der gewählten AE-Grenze als FE an. Für ein flaches
AE mit Komponenten wird ein abstraktes FE vorgeschlagen. Die Herkunft hält
Block-UUID, Projekt, Blatt und Schaltplanrevision. Explizite Verbindungen
zwischen Blattpins liefern funktionale Abhängigkeiten; unklare
Schnittstellen bleiben offen. Beobachtete Portnamen bleiben nachvollziehbar.
Die äußere HW-Schnittstelle verwendet Netz-/Busnamen; `*_Port_*` ist für
Schnittstellen innerhalb des ECAD-Funktionsblocks vorgesehen.

Das maximierte Annotationfenster zeigt FE, Kernbauteile, Dokumentreferenzen
und Realisierungen getrennt. Nur ausgewählte, gültige Änderungen werden
übernommen. Bei unabhängigen Änderungen in ISD und ECAD bleibt der
ISD-Wert erhalten; Änderungen am selben Feld werden als Konflikt angeboten.
Identitäten bleiben über wiederholte Rückübernahmen stabil.

### 33.2 Technologie und Bauteilobjekte

**Kernbauteil anlegen** erzeugt ein eigenes Objekt mit Hersteller, exakter
MPN, Bauteilrevision, Gehäuse und Beschreibung. Fehlende Daten bleiben offen.
**Bedeutung für das System** unterscheidet systemdefinierend, Detailbauteil
und noch zu bewerten; die Begründung beschreibt den Systembeitrag.
Eine Variante darf mehrere Kernbauteile besitzen. A-/B-Rollen gelten innerhalb
der Variante; ein begründetes B-Bauteil kann ebenfalls systemdefinierend sein.
**Bauteil aus Katalog** öffnet auch bereits vorhandene, noch nicht eingeordnete
Bauteile zum Prüfen und Bearbeiten, ohne die gesamte BOM in der Übersicht anzuzeigen.
Bei alten unklassifizierten A-Parts bleibt die Einordnung als Prüfpunkt offen.
RefDes ist eine informative Bestandsangabe und keine Objektidentität.

Ein Bauteilklick öffnet Details mit MPN, **Alternative Bauteile**, Quellen und
**Normen und Bauteilqualifikation**. Alternativen sind eigene Bauteilobjekte
mit eigenen MPNs, Entscheidungen und Dokumenten. Datenblätter und Application
Notes halten Typ, Quelle, URL oder externe Referenz, Revision, Dokumentdatum,
Freigabestand und Fundstelle. Als Zugriffskanäle stehen auch **PLM**, **ERP**
und **DMS** zur Verfügung. Dies speichert strukturierte Referenzen; ein
automatischer Abruf oder eine Synchronisation mit diesen Systemen ist noch
kein Bestandteil des Connectors.

### 33.3 Normenabgleich und Nachweisstand

**Qualifikation bearbeiten** verbindet das Bauteil mit einer konkreten
Normausgabe, Geltungsbereich, Bewertung, Begründung und eigenen Belegen.
Der Vergleich berücksichtigt auch die Requirements der Realisierungen.
Ein fehlender Hersteller/MPN, eine fehlende Normausgabe, Dokumentrevision
oder Fundstelle lässt den Abgleich offen. Ein Metadatenlink allein reicht
nicht aus. Die gespeicherte fachliche Bewertung gilt für den geprüften
Bauteil-, Dokument- und Normstand. Änderungen an MPN, Package, Bauteilrevision,
Dokumentreferenz oder Normausgabe verlangen eine erneute Prüfung.
Bauteilqualifikation erzeugt keinen bestandenen Systemtest.

### 33.4 Vollständige BOM ausdrücklich exportieren

**Vollständige BOM exportieren** im lokalen KiCad-Projektzugriff beziehungsweise
im Rückimportfenster liest alle für die BOM freigegebenen Symbole der
Schaltplanhierarchie. Die CSV enthält Menge, Referenzbezeichner, Wert,
Hersteller/MPN soweit vorhanden, Footprint, DNP-Kennzeichnung, Blätter und
Datenblattreferenz. Mehrteilige Symbole mit demselben annotierten RefDes
werden als ein physisches Bauteil gezählt; wiederverwendete Blätter nutzen
die projektbezogenen Instanzreferenzen. Projekt, Schaltplanrevision und
Variantenbezeichnung stehen im Export. Der aktuelle Export entspricht dem
Schaltplanstand einschließlich DNP; separate bestückungsabhängige
Produktvarianten sind noch kein eigenständiges ISD-Variantenmodell.
Die vollständige BOM wird nicht automatisch in die Architektur übernommen.

### 33.5 Übernahme vorhandener Bewertungen

Leere neue Attribute verändern bei der Übernahme eines v0.42-Projekts den
gespeicherten Objektfingerprint nicht. Die erweiterte Nachweiskette verfolgt
zusätzlich FE, deren Schnittstellen und Bauteildokumente. Wenn solche
Abhängigkeiten in einer alten Bewertung noch nicht geprüft wurden, erscheint
**Erneut prüfen**. Vorhandene Bewertungen und Ergebnisbelege bleiben erhalten.

## 34. KI und navigierbare Hilfe

### 34.1 Gemeinsamer Projektkontext und kontrollierte Aktionen

Alle KI-Arbeitsweisen erhalten den typisierten Projektgraphen mit L1–L4,
Architektur, FE, Realisierungen, Varianten, Bauteilen, Software/Mechanik,
Normausgaben, aktuellen Nachweiszuständen und Attributregeln. Die Auswahl
**Aktuelles Objekt** begrenzt Änderungsvorschläge auf diese Objektidentität.
Der Economy-Kontext kennzeichnet ausgelassene Objekte und gekürzte Inhalte.
Quellenmetadaten sind von tatsächlich extrahiertem Dokumentinhalt getrennt;
Fundstellen und Revisionen bleiben für die fachliche Prüfung erforderlich.

**Nur antworten** verändert das Modell nicht. Formulierungen wie „noch nichts
ändern“, „nicht übernehmen“ und Fragen nach einem Vorgehen bleiben ebenfalls
im Lesemodus. **Auftrag vorbereiten** erzeugt Vorschläge. Feldänderungen werden
einzeln geprüft; objektbezogene Attribute müssen Typ und Dropdownauswahl
entsprechen. Identitäten und Verifikationsbehauptungen sind keine unterstützten
KI-Änderungsfelder. Architekturvorschläge können System-, Mechanik-, Software-
und FE-Elemente enthalten; ihre Aktionen sind einzeln auswählbar.

Ein KI-Integrationsauftrag öffnet **KI-Integration · Änderungen prüfen** mit
Vorher-/Nachher-Darstellung. Nach Änderung des Projektstands muss die Vorschau
neu erzeugt werden. Fehlende Beziehungspartner verhindern eine unvollständige
Übernahme. Unter dem Quelldokument lässt sich die Vorschau mit
**KI-Integrationsänderungen prüfen** wieder öffnen. Die ursprüngliche
Dokumentanalyse bleibt direkt nutzbar: neue Requirements erscheinen als
**Detected** und werden im Requirements-Arbeitsraum fachlich bewertet.

### 34.2 Handbuch bedienen

Links stehen die Kapitel und Unterkapitel. **Handbuch durchsuchen** sucht in
allen Kapiteln, nicht nur im gerade geöffneten Text. Treffer zeigen Kapitel
und Textausschnitt. Ein Klick öffnet das Kapitel und markiert die Suchwörter.
**Vorheriges Kapitel**, **Nächstes Kapitel** und **Kapitel-Link** unterstützen
Navigation und direkte Verweise. **Doku** öffnet dieses vollständige Handbuch.
**Hilfe** zeigt kompakte, kontextbezogene Voraussetzungen, Handlungsschritte
und Hinweise auf offene Fälle mit Verweis zum passenden Handbuchkapitel.


## 35. Schlanke Architektur und technische Gegenüberstellung (v0.44.0)

### 35.1 Objektkern und Attributräume

Jedes Objekt behält eine UUID und eine daraus abgeleitete SHA-256-Anzeige.
Anforderung und Realisierung bleiben getrennte Perspektiven. Technische
Sollwerte stehen am Requirement, belegte Istwerte an der konkreten Umsetzung.
Die Architektur zeigt diese Quellen über explizite Zuordnungen.

| Objekt | Eigene Angaben | Zuordnungen / angezeigte Angaben |
|---|---|---|
| HW-Domäne | Name, Aufgabe/Verantwortung, Beschreibung, Typ, Farbe, ECAD-Key | HW-systemische Requirements; zugeordnete Umsetzung und Kennwertquellen |
| HW-AE | Name, Aufgabe/Verantwortung, Beschreibung, Rolle/Typ, ECAD-Key | Domäne, Ports, Requirements, FE und Realisierungen |
| Port | Netz-/Busname oder vorläufiger Name, optionale Beschreibung, ECAD-Key, Host/Teilnehmer | Host rechts, Teilnehmer links; gebundene Rolle aus Topologie; wirksame Netzklassen vom Netz/Bus |
| Netz | Name, Beschreibung, Signaltyp/Vorlage, Netzklasse, ECAD-Key | Host, Teilnehmer, Requirements und Design-/Kennwertquellen |
| Bus | Name, Beschreibung, Vorlage/Inhalt/Vektoren, Standardnetzklasse, ECAD-Key | Mitgliedssignale mit wirksamer Klasse und eigenen Requirements; gebündelte Architekturgrenze |
| Systemelement | Name, Aufgabe/Verantwortung, Beschreibung, Elementtyp | Systemdomäne, Requirements und fachliche Realisierungen |
| SW/FW-AE, Mechanik-AE | Name, Aufgabe/Verantwortung, Beschreibung, Elementtyp | Hierarchie, Requirements, FE, fachliche Beziehungen und konkrete Realisierungen |
| FE | Name, Funktionsbeschreibung, Disziplin; bei ECAD-FE Herkunft und Key | Übergeordnetes AE, Requirements, funktionale Schnittstellen, FE-Abhängigkeiten und Umsetzung |

Ein FE ist ein eigenständiges abstraktes Funktionsobjekt. Architektur und
Realisierungsansicht zeigen dieselbe Identität. Nur systemdefinierende Bauteile
gehören in den Architekturkontext; die vollständige BOM bleibt über ECAD
zugänglich. Interne Interface-Port-Instanzen wie `SPI_Port_1` sind den
Funktionsblöcken im Schaltplan vorbehalten.

Im Architektur-PDF erscheinen nur die FE der gewählten Facharchitektur.
Die SW-/Mechanik-Exporte führen auch FE-Abhängigkeiten, das übergeordnete AE
und die zugeordneten konkreten Realisierungen auf.

Alle passenden Systemfelder bestehen auch mit offenem Wert. Eigene Attribute
werden im **Property Manager** mit Typ, Einheit, Geltungsbereich und
Auswahlquelle angelegt. Systemdefinitionen bleiben gegen Löschen/Umdefinieren
geschützt. Bearbeiten erfolgt über die Eingabemaske des Objekts.

### 35.2 Soll und Ist vergleichen

**Technischer Vergleich** ist zunächst eingeklappt. Der Titel nennt Anzahl
relevanter Kennwerte, offene Fälle und Abweichungen. Die Tabelle enthält
**Kennwert | Soll | Ist | Vergleich**. **Offen / prüfen** und **Abweichend**
grenzen die Tabelle ein. Ein Klick auf die Tabellenzeile öffnet Quellen,
Bedingungen, Herkunft, Revision und Bewertungs-/Nachweisstatus darunter.
Requirement und Realisierungsquelle sind direkt aufrufbar.

Es werden nur gefüllte technische Vorgaben und zugeordnete belegte Werte
angezeigt. Die aktive HW-Realisierungsvariante bestimmt die betrachteten
Variantenwerte. Ein Ist-Kennwert kann zusätzlich für ein bestimmtes
Architekturobjekt, Netz oder Busmitglied gelten. Fehlender Soll-/Ist-Wert bleibt
**Offen**. Unklare Einheit, unterschiedliche Bedingungen und strukturierte
fachliche Angaben bleiben zur Prüfung. Mehrere Quellen bleiben sichtbar;
sie werden nicht zu einem scheinbar eindeutigen Wert überschrieben.

**Passend** bedeutet ausschließlich, dass explizite Werte/Grenzen rechnerisch
passen. Erfüllungsbewertung, Dokumentbeleg und ausgeführter Test bleiben eigene
Aussagen. Eine überholte bewertete Revision erscheint als **Erneut prüfen**.

Unter **Belegte technische Kennwerte** einer Realisierung werden Werte mit
Typ, Einheit, Herkunft (Designangabe/berechnet/simuliert/gemessen), Bedingungen,
Variante, Quellen, Revision und Begründung erfasst. Requirements enthalten
weiterhin die Vorgaben. Bei Bussen zeigt **Businhalt / Mitgliedsdetails** pro
Mitglied Beschreibung, wirksame Netzklasse und eigenen technischen Vergleich.
Requirement-Zuordnungen sind auch direkt zu einem Busmitglied möglich.

### 35.3 Migration und Netzklassen

Gefüllte technische Architekturattribute früherer Stände bleiben mit ihrem
Attributraum in `legacyPropertyValues` erhalten. Im Vergleich erscheinen sie
als **Bestand prüfen**. Die Migration erzeugt daraus keine vermeintlich
freigegebenen Requirements oder belegten Messwerte. Frühere Domänenzuständigkeit
wird mit der Aufgabe zusammengeführt. Eigene Attribute bleiben erhalten.
Erneutes Laden desselben Stands ist idempotent.

Eine gewählte Verbindung oder ein Port zeigt die Klasse des zugehörigen
Netzobjekts. Busse zeigen **Gemischt**, wenn Mitglieder verschiedene wirksame
Klassen haben; offene Mitglieder bleiben sichtbar. Eine Standardklasse wird
nur für Mitglieder ohne eigene Klasse verwendet. Versorgung, Leistungspfad
und Rückleitung verwenden die vorhandenen passenden Netzklassen; konkrete
PCB-Regeln und Constraints werden im ECAD-Tool gepflegt. Mehrdeutige Signale
werden nicht pauschal einer Leistungsklasse zugeordnet.

## 36. Disziplinübergreifende Schnittstellen

### 36.1 Hardware Software Interface (HSI)

**HSI anlegen** steht unter **Disziplinübergreifende Schnittstellen** in HW-
und SW/FW-Architektur sowie den Realisierungsansichten. Ein HSI verknüpft
explizit HW-AEs, Netze/Busse, konkrete Bauteile, SW/FW-AEs, logische Schnittstellen,
Treiber/Firmwarekomponenten und Requirements. Mehrere Partner sind möglich.
Name und Beschreibung erklären den Schnittstellenvertrag. Unter
**Konkrete Implementierung / Konfiguration** stehen Peripherieinstanz, Adresse,
Chip Select, IRQ, Pinmux, Protokoll, Timing und Implementierungsrevision.
Diese Angaben bleiben leer, solange die Lösung offen ist.

Gleiche Namen verbinden keine Objekte. Eine noch unvollständige Schnittstelle
ist zulässig; Referenzen auf unbekannte oder disziplinfremde Ziele werden
abgewiesen. Das HSI erscheint in beiden Disziplinen mit derselben UUID. Es
ersetzt weder die elektrische Netzdefinition noch den Software-Datenvertrag.

### 36.2 HW-Mechanik-Schnittstelle

**HW-Mechanik anlegen** verknüpft HW-AE/Netze/konkrete Bauteile mit Mechanik-AE,
CAD-Teil/Baugruppe und mechanischer Schnittstelle. Beispiele sind PCB und
Gehäusebefestigung, Steckverbinder und Gehäusedurchbruch, Leistungsbauteil und
Kühlkörper. Requirements bleiben zugeordnet. Befestigung, Bauraum,
Kontaktfläche, Wärmeweg, Lastfall, Montage und Referenzsystem stehen als
aufklappbare Implementierungsangaben bereit. Belegte Kennwerte nutzen dieselbe
Soll-/Ist-Gegenüberstellung.

## 37. Konkrete Software- und Mechanikumsetzung

Softwarekomponenten unterscheiden Anwendung, Dienst, Library, Package, Treiber,
Firmwaremodul, **Bootloader**, Task, Plattform, Build und **Firmware Image**.
Repository, Code-/Modulpfad, Commit/Tag und Version identifizieren den Stand.
Packages tragen ihre Kennung; Builds und Firmware Images ihren Build-/
Artefaktbezug und enthaltene Komponenten. Das Deployment verweist auf das
Ziel-HW-AE. Verwendete Packages/Komponenten und Buildbestandteile werden als
Objekte zugeordnet; Zyklen in der Buildzusammensetzung werden abgewiesen.
Bootloader sind eigene Firmwarekomponenten und können über HSI gekoppelt werden.

Mechanische Teile und Baugruppen tragen Teilenummer/MPN, Hersteller,
Teilrevision, CAD-Modell/Zeichnung mit CAD-Revision, PLM-/ERP-Referenz,
alternative Teile und Referenzen auf Berechnungen/Simulationen. Quellen und
Requirements bleiben nachvollziehbar. CAD-, PLM-, ERP- und Codeangaben sind
Referenzen; ein automatischer Zugriff auf externe Systeme ist nicht enthalten.

FE können für Hardware, SW/FW oder Mechanik angelegt werden. Der Wechsel der
Disziplin erneuert die passenden Auswahllisten für AE, Schnittstellen und
Realisierungen. ECAD-importierte FE behalten ihre Hardwaredisziplin. In den
Realisierungsreitern stehen Funktionsbeschreibung und systemdefinierende
Umsetzung; die Architektur wird nicht auf jedes Einzelteil heruntergebrochen.

## 38. ECAD-Hierarchieanschlüsse und Hilfe

Hierarchische Busanschlüsse werden aus den Mitgliedssignalen abgeleitet:
alle Signale Host→Teilnehmer ergeben Host **Output**, Teilnehmer **Input**;
gemischte Richtungen oder bidirektionale Mitglieder ergeben auf beiden Seiten
**Bidirectional**. Explizite Rückrichtung wird entsprechend umgekehrt.
Unbekannte Fälle erhalten **Passive** und **Offen: Signalrichtung prüfen**.
Eindeutige SPI-, UART-, I2C- und PWM-Mitglieder können über eine gebundene
Vorlage eingeordnet werden. Weitere Richtungen werden am Signal geprüft. Im Busmitglieddialog bestätigt
**Signalrichtung geprüft** ausdrücklich eine gewählte bidirektionale Richtung;
eine reine Netzklassenänderung bestätigt keine Signalrichtung.

Das gilt entsprechend für Einzelsignale. Host/Teilnehmer bestimmt die
Zeichenseite unabhängig vom Pintyp. Hierarchieanschlussform und elektrischer
Bauteil-Pintyp sind getrennt: vorhandene Bibliothekspintypen und physische
Bauteilsymbole bleiben erhalten. Busse werden erst am Bestimmungsort aufgefächert.
Das Binding-Manifest und Labelmetadaten führen den Mappingstatus mit.

Zuordnete technische Vorgaben und belegte Werte werden mit Quellidentität und
Bedingungen als ECAD-Metadaten bereitgestellt. Vorhandene technische Altwerte
bleiben für bestehende Connectorbindungen erhalten. Backannotation verändert
die Requirement-Vorgaben nicht. Änderungen werden weiterhin im separaten
Reviewfenster geprüft. Ein nativer KiCad-Buscontent-Wizard und eine automatische
Requirement→PCB-Constraint-Ableitung sind weiterhin zurückgestellt.

**Hilfe** nennt zum aktuellen Arbeitsraum Voraussetzungen, nächste Aktionen,
Fehler-/Offenfälle und das passende Handbuchkapitel. **Doku** bietet das
vollständige Handbuch mit Navigator, Volltextsuche und Kapitelverweisen.
KI-Kontexte enthalten auch HSI, HW-Mechanik-Zuordnungen, disziplinbezogene FE
und Kennwertquellen; ausführbare Änderungen bleiben typgeprüfte Vorschläge.

## 39. Objektattribute und Realisierungskontext (v0.49.0)

Wählen Sie in der Hardwarearchitektur eine Domäne, ein AE, einen Port, ein Netz,
einen Bus oder eine Verbindung. Die Details zeigen alle zum Objekttyp passenden
System- und eigenen Attribute in getrennten Anforderungs- und Realisierungsräumen.
Ein fehlender Wert heißt **Offen**. Das ist kein Fehler und keine automatisch
angenommene Vorgabe. Die SHA steht einmal am Objekt; der ECAD-Key bleibt erhalten.
Technische Requirement-Vorgaben und belegte Kennwerte stehen weiterhin im
aufklappbaren Vergleich mit ihren Quellen. Das verhindert einen zweiten Schaltplan.

**Objekt bearbeiten** öffnet die Eingabemaske. Auswahlfelder verwenden die
hinterlegten Typen und Auswahllisten. Für zusätzliche Attribute verwalten Sie die
Definition im Property Manager; Systemdefinitionen sind geschützt.

**Netzklasse bearbeiten** führt vom gewählten Netz/Bus sowie vom angeschlossenen
Port oder der Verbindung zur Netzmaske. Bei Bussen zeigen **Businhalt /
Mitgliedsdetails** die wirksamen Mitgliedsklassen. **Mitglied bearbeiten** setzt
eine eigene Klasse; ein leerer Mitgliedswert übernimmt die Busklasse. Ein bewusst
geleerter Bus-/Netzwert bleibt offen. Die Klasse ist eine Zuordnung, keine bereits
geprüfte Leiterbahnbreite oder elektrische Constraint. Diese Regeln legen Sie im
ECAD-Layout fest. Eine Klassenänderung bestätigt keine Signalrichtung.

Der HW-Realisierungsbereich gruppiert konkrete Realisierungen nach Domäne und AE.
An jedem Eintrag stehen Aufgabe, FE-Bezug, aktive Variante und aufklappbare
Umsetzung. Die Bestandteile der aktiven Variante zeigen nur systemdefinierende
Kernbauteile. Weitere Architekturbezüge bleiben sichtbar, ohne eine zweite
Realisierungsidentität anzulegen. Fehlende Zuordnungen und Varianten bleiben
Offen. In Software und Mechanik nennen die Umsetzungskarten ihre verknüpften
Architekturelemente und FE. Ein verknüpftes FE bleibt dasselbe Architektur- und
Funktionsobjekt. Die vollständige BOM wird über ECAD bezogen.

## 40. Requirements lesen und Architektur ableiten

### 40.1 Liste, Kette und Gesamtübersicht

Der Requirementsbereich startet mit **Anforderungsliste**. L1 zeigt die
Kundenanforderungen mit Verweisen auf ihre abgeleiteten L2-Systemanforderungen.
Ein L2 mit mehreren Kundenursprüngen bleibt ein Objekt; die mehreren Einträge
sind Verweise. Weitere L2 sowie L3/L4 sind separat erreichbar. Nach Auswahl zeigt
der Zusammenhang unmittelbare Ursprünge, Ableitungen und zugeordnete Architektur
bzw. konkrete Umsetzung. Ein Klick zeigt Details im vorgesehenen Detailbereich.

Für eine ausgewählte Anforderung wählen Sie **Anforderungskette** und grenzen den
Zusammenhang mit Fokus/Tiefe ein. **Gesamtübersicht** zeigt das vollständige
Beziehungsbild ausdrücklich. Karten behalten ihre Breite; größere Bilder können
horizontal gescrollt werden. Filter beschränken die angezeigten Objekte, ohne
fachliche Beziehungen oder Objektidentitäten zu ändern.

| Angabe | Bedeutung |
|---|---|
| Ebene L1–L4 | Kunde, System, Technik oder Disziplin; keine Annahmeentscheidung |
| Kundenentscheidung (L1) | Annahme offen, angenommen oder abgelehnt; Ablehnung verlangt eine Begründung |
| Prüfstand | Erfasst, in Prüfung, freigegeben, abgelehnt oder obsolet |
| Zuordnung | Geplante Verantwortung bzw. Umsetzung |
| Erfüllung/Nachweis | Separat bewertete Kriterien und revisionsbezogene Evidenz |

Bestehende L1 erhalten eine offene Kundenentscheidung. Eine vorhandene Freigabe
wird nicht nachträglich als Kundenannahme interpretiert. Der Filter
**Kundenentscheidung (L1)** berücksichtigt L1 und direkt verknüpfte Ableitungen.
L1 und L2 unterscheiden sich fachlich: L2 beschreibt Systemverantwortung und
-abstraktion, nicht nur die Annahme eines Kundenwunschs.

### 40.2 Architektur aus Requirements erzeugen

1. Öffnen Sie **Architektur aus Requirements erzeugen** im Requirementsbereich.
2. Filtern Sie nach Ebene, Disziplin und Prüfstand. Standardmäßig sind freigegebene
   aktive Requirements sichtbar. Markieren Sie die gewünschten Einträge ausdrücklich.
   Eine Filteränderung löscht die Auswahl, damit keine unsichtbaren Einträge mitlaufen.
3. Wählen Sie die Zielarchitekturen System, Hardware, Software und/oder Mechanik.
4. Ergänzen Sie Vorgaben und bestätigen Sie Auswahl und Erzeugung.
5. Prüfen Sie den gespeicherten Vorschlag im KI-Assistenten. Der bestätigte Umfang
   und die Requirement-Bezüge stehen an der Vorschau. Wählen Sie die gewünschten
   Aktionen und übernehmen Sie diese erst nach Prüfung.

Ein konfigurierter KI-Provider ist erforderlich. Die Anfrage enthält nur die
bestätigten Requirement-Inhalte als Vorgaben; vorhandene Umsetzung bleibt als
Kontext erhalten. Abgelehnte oder obsolete Requirements sind ausgeschlossen.
Kandidaten für nicht gewählte Zielarchitekturen oder mit fremden Requirement-
Bezügen werden zurückgewiesen. Änderungen am Projekt während der Anfrage oder
nach Erzeugung der Vorschau verhindern die Übernahme eines veralteten Vorschlags.
Erzeugen Sie dann eine neue Vorschau. Das Umstellen der Vorschlagsauswahl selbst
ändert den zugrunde liegenden Projektstand nicht.

Eindeutig identifizierte vorhandene Architekturobjekte werden wiederverwendet.
Mehrdeutige Gleichnamigkeit muss vor der Übernahme aufgelöst werden. FE erhalten
explizit ihre Disziplin und verknüpfen passende konkrete Umsetzungen. Die
Erzeugung liefert einen prüfbaren Arbeitsvorschlag, keine automatisch verifizierte
Architektur und keine vollständige Stückliste.

### 40.3 Hilfe zur aktuellen Anzeige

**Hilfe** berücksichtigt den aktiven Arbeitsraum, das gewählte Objekt und eine
geöffnete Eingabemaske. Sie nennt konkrete Aktionen und passende Kapitel.
**Hilfe zur Eingabemaske** erläutert den geöffneten Dialog. **Doku** öffnet das
vollständige Handbuch mit Navigator und Suche. Hilfe ersetzt keine fehlenden
Projektwerte und bestätigt keine technischen Ergebnisse.

## 41. Konsolidierung und Auslieferung (v0.46.0)

Die Fachfunktionen und das Projektformat bleiben erhalten. Bearbeiten, typisierte
Auswahlfelder, Requirements-Auswahl, Vorschlagsprüfung und ECAD-Annotation
verwenden weiterhin die gleichen Projektobjekte. Die internen Zuständigkeiten
sind in kleinere Fachmodule gegliedert. Referenz- und Attributprüfungen bleiben
an den Modell-/Speichergrenzen erhalten; schnellere Prüfung bedeutet keine
schwächere fachliche Validierung.

### 41.1 Welches Paket verwenden?

| Paket | Inhalt und Verwendung |
|---|---|
| Anwendung | Vollständige ausführbare Suite mit Quellcode, Katalogen, aktueller Hilfe/Dokumentation, aktuellem Changelog/Prüfbericht und Lizenztexten; für den normalen Betrieb |
| Entwickler | Zusätzlich sämtliche Tests, Release-/Benchmarkwerkzeuge, Entwicklerabhängigkeiten und erhaltene historische Dokumentation; für Weiterentwicklung und Nachprüfung |

Entpacken Sie das Paket und starten Sie unter Windows `start_windows.bat`.
Alternativ installieren Sie `requirements.txt` in einer Python-Umgebung und
starten `python main.py`. Der Runtime-ZIP enthält keine installierte Python-
Umgebung. Vorhandene Projektdateien und das separate Datenverzeichnis verwenden
Sie wie bisher. Anwendungs- und Entwicklerpaket enthalten denselben Anwendungscode.
Das Manifest im Paket dokumentiert Version, Dateiauswahl und Inhaltsprüfsummen.

Historische Handbücher sind im normalen Anwendungspaket nicht mehr enthalten.
Das aktuelle Handbuch ist die verbindliche Funktionsbeschreibung; alte Stände
bleiben im Entwicklerpaket unter `docs/archive` und `changelogs` erhalten.

### 41.2 Was wurde optimiert?

Die Anwendung liest gebündelte Migrationskataloge einmal pro Prozess ein und
prüft Attribute anhand der tatsächlich passenden Objekttypen. Systemdefinitionen
werden unabhängig zurückgegeben; eine lokale Änderung kann keine andere
Projektinstanz beeinflussen. Das Handbuch verwendet unveränderliche Kapitel
mit einem begrenzten Cache. Ändert sich die Datei, wird der Inhalt neu gelesen.

Die ZIP-Größe ist kein Maß für die fachliche Leistung. Das normale Paket ist
kleiner, weil Entwicklungsmaterial getrennt ausgeliefert wird. Die Quellcode-
Konsolidierung dient Wartbarkeit und gezielter Prüfung; Kataloge, Migrationen,
Connectoren und notwendige Bibliothekslizenzen werden weiterhin mitgeliefert.

### 41.3 Entwicklungsprüfungen

Im Entwicklerpaket installieren Sie `requirements-test.txt`. `python -m pytest -q`
prüft Modell, Migration, Connector und Bedienung. `python -m pyflakes architecture_app`
prüft zusätzlich unter anderem undefinierte Namen und ungenutzte Imports.
Die JavaScript-Prüfungen verwenden Node:
`node --test tests/test_canvas_selection.js tests/test_requirements_routes.js`.

`python scripts/build_release.py --output-dir dist` baut beide Paketvarianten
mit identischen Inhaltsprüfsummen bei unveränderten Dateien. Mit
`python scripts/benchmark_project.py PROJEKT.json --repeats 15` messen Sie
Modellprüfung, Laden/Vorbereitung und Handbuchzugriff auf Ihrem Rechner.
Das Werkzeug verändert weder Projektdatei noch Datenbank.

## 42. KiCad-Projektanlage und sichere Netzklassenübertragung

### 42.1 Neues Projekt lokal oder als ZIP

Öffnen Sie den ECAD-Konnektor. **Neues Projekt lokal anlegen …** fragt den
Zielordner ab und öffnet anschließend ein separates maximiertes Prüffenster.
Dort erscheinen Domänen, AEs, Netze/Busse sowie der Netzklassenkatalog. Erst
**Geprüftes Projekt erzeugen** schreibt die Projekt- und Schaltplandateien.
Das neue lokale Projekt wird als aktive Verknüpfung gespeichert. Wenn ausgewählt,
öffnet ISD danach den KiCad-Projektmanager; standardmäßig wird die höchste
installierte Version gewählt. Bestehende Projektordner werden nicht überschrieben.

**Neues Projekt als ZIP herunterladen** öffnet dieselbe Prüfung und liefert nach
Bestätigung ein ZIP mit `.kicad_pro`, hierarchischen `.kicad_sch`-Dateien und
Bindungsinformationen. Alle Dateien gemeinsam entpacken. Ein ZIP-Export setzt
keine lokale Verknüpfung. Über **Bestehendes Projekt auswählen …** kann das
entpackte Projekt anschließend ausdrücklich verknüpft werden.

Fehler beim Aufbau der Projektprüfung erscheinen als sichtbare Meldung.
Die Ordnerauswahl allein ist noch keine Projektanlage.

### 42.2 Netzklassen und vorhandene Regeln

ISD überträgt den Netzklassenkatalog und die Zuweisungen in die
`net_settings` der KiCad-Projektdatei. Einzelnetze erhalten ihre zugewiesene
Klasse. Busmitglieder verwenden ihre eigene Klasse oder, wenn diese leer ist,
die Standardklasse des Busses. Muster erfassen sowohl unqualifizierte Netznamen
als auch Namen in hierarchischen Blättern. Der abstrakte Bus ersetzt keine
Mitgliedsnetze im PCB; die Zuweisung erfolgt pro tatsächlichem Mitgliedsnamen.

Leiterbreiten, Abstände und andere Fertigungsregeln werden im ECAD gepflegt.
Eine reine ISD-Klassenzuweisung berechnet keine Maße. Bei der Forward Annotation
werden gemeinsame Basis, ISD-Stand und KiCad-Stand verglichen. Unabhängige
KiCad-Regeländerungen bleiben erhalten; konkurrierende Änderungen erscheinen
als Konflikt im Prüffenster. Die Projektanlage zeigt den Klassenkatalog;
Änderungen an bestehenden Projekten zeigen die betroffenen Projekteinstellungen.

### 42.3 Businhalt sicher zurücklesen

Ein Bus-Alias muss seine tatsächlichen Mitgliedsnetze enthalten und auf den
verbundenen Blättern konsistent sein. ISD erkennt sowohl Aliasnamen als auch
Busgruppen. Fehlt bei einem bestehenden Bus mit mehreren Mitgliedern die
Aliasauflösung und wird nur dessen Busname zurückgeliefert, stoppt die
Backannotation mit einer Fehlermeldung. Der Projektstand bleibt unverändert.
Der Alias ist in KiCad zu korrigieren, anschließend ist die Prüfung zu wiederholen.

Bewusste Änderungen an Mitgliedern werden weiterhin als Änderungen geprüft.
Bereits beschädigte ältere JSON-Dateien werden nicht ohne Beleg überschrieben;
für das BMS-Projekt steht der neu analysierte Importstand v023 zur Verfügung.

Die automatisierten Prüfungen umfassen UI-Aktionen, lokale Dateierzeugung,
ZIP-Inhalt, Klassenmuster, Regelerhalt und Bus-Aliasfehler. Der native
Windows-Dateidialog und KiCad 10 ERC/DRC müssen am Zielarbeitsplatz geprüft werden.

## 43. Realisierung mit Kontextfokus und Part View

Unter **Realisierung → HW / ECAD** gewichtet **Kontext** dieselben zusammengehörigen
Informationen. Der gewählte Bereich steht zuerst und ist aufgeklappt; die anderen
Bereiche bleiben ausklappbar verfügbar.
Der optionale **Architekturbezug** beschränkt die Übersicht auf eine Domäne,
ein AE oder ein Hardware-FE. **Gesamtes HW-Projekt** entfernt diese Beschränkung.
Die Suche durchsucht die Objekte des jeweiligen Kontexts.

| Kontext | Darstellung |
| --- | --- |
| Architektur | Domänen, Hardware-AEs und abstrakte Funktionselemente; konkrete Umsetzungen sind zusätzlich aufklappbar. |
| Parts | Systembestimmende Bauteile als Tabelle mit Hersteller, MPN, Teilrevision, AE-/FE-Zuordnung und Dokumentständen. |
| Requirements | Nur unmittelbare Requirement-Zuordnungen zu Realisierungen und Kernbauteilen; keine übernommenen AE-/FE- oder Elternanforderungen. |
| ECAD | Verknüpfte Projektdatei und Schaltplanbezüge der Hardware-FEs; Annotation wird ausdrücklich aufgerufen. |

Auswahl im Navigator, auf einer Objektkarte oder in der Part-Tabelle zeigt die
Details **rechts**. Ein Klick auf ein Objekt öffnet kein Attributfenster.
Beim Kontextwechsel bleiben Fokus, Detailauswahl und Architekturbezug erhalten.
Zugehörige Objekte lassen sich rechts prüfen, ohne den Fokus zu wechseln.
**Fokus zurücksetzen** öffnet die Übersicht wieder. Beim Wechsel von einer ausgewählten Hardwaredomäne oder einem AE im
Architekturreiter zur Realisierung wird dieser Bezug übernommen.

Die Part View verwendet bestehende Bauteilobjekte, keine Kopien. Systembestimmende
Bauteile werden anhand ihrer Kennung einmal angezeigt. Für eine aktive
Realisierungsvariante zählen explizite Kernbauteile und noch nicht eingeordnete
A-Parts. Explizit nicht systembestimmende Bauteile werden ausgeblendet. Nicht
aktive Varianten machen ihre Bauteile nicht automatisch zu eingesetzten Parts.
Systembestimmende Bauteile ohne Zuordnung bleiben im gesamten Projekt sichtbar
und tragen **Zuordnung offen**. Die Part View ist keine vollständige Stückliste;
diese wird über das ECAD-Design abgerufen.

Die rechte Detailansicht zeigt Hersteller, MPN, Teilrevision, Gehäuse,
Systembeitrag, Architektur- und Realisierungsbezüge, alternative Bauteile,
Datenblätter/Application Notes mit Revision sowie Normen und Standards.
Dokumentquellen können Weblinks oder PLM-/ERP-Referenzen sein. Ein Verweis
stellt noch keine automatisierte PLM-/ERP-Synchronisierung und keinen
Normerfüllungsnachweis dar. **Dokumente und Qualifikation verwalten** öffnet die
bestehende Verwaltung. **Bearbeiten** öffnet die jeweilige Eingabemaske.
Die kontextbezogene Hilfe erklärt die aktuelle Sicht; das Handbuch enthält
zusätzlich diese vollständige Funktionsbeschreibung.

## 44. Masse und abgeleitete Domänenanschlüsse

Masse ist auf Funktionsebene ein globales Netz. GND, AGND, DGND, PGND und
benannte Bereiche wie ISO_GND erhalten keine Anschlüsse an Domänen- oder
AE-Blöcken. Die Hardwaregrafik, ihr Navigator und der PDF-Export lassen diese
Blockanschlüsse weg. Im Signalkatalog bleiben die Netzobjekte, Kennungen,
Netzklassen und bisherigen Zuordnungen erhalten. Alte Projektdateien werden
nicht destruktiv bereinigt.

Die KiCad-Erzeugung legt die entsprechenden globalen Masse-Labels auf den
zugeordneten Funktionsblättern an. **GND und ISO_GND bleiben unterschiedliche
Netze**; es erfolgt keine Zusammenführung. Vorhandene Schaltpläne werden erst
nach expliziter Forward Annotation und Prüfung geändert. Masse-Messsignale
wie GND_SENSE sowie sonstige Rückleitungen bleiben normale Signale.

Für domänenübergreifende Netze und Busse wird die Anschlussseite aus den AEs
abgeleitet: Mindestens ein Host in der Domäne bedeutet **Host rechts**. Ohne
internen Host liegt der Anschluss auf der **Teilnehmerseite links**.
Lokale AE-Teilnehmer bleiben weiterhin links. Ein interner Teilnehmer erzeugt
keinen zweiten Teilnehmeranschluss an einer eingeklappten Host-Domäne. Rein
interne Verbindungen erzeugen keine äußeren Domänenanschlüsse.


## 45. Gemeinsamer Fokus und direkte Requirement-Zuordnung

In **Realisierung → HW / ECAD** bereitet Kontext denselben Bezugsrahmen aus
vier Perspektiven auf: Architekturbezug, Parts, direkt verknüpfte Requirements
und ECAD-Bezug. Der gewählte Bereich steht zuerst und ist aufgeklappt; weitere
Bereiche sind platzsparend ausklappbar. Eine gewählte Realisierung bleibt beim
Kontextwechsel der Fokus. Das Anklicken eines zugehörigen Bauteils, Requirements
oder Architekturbezugs zeigt dessen Details rechts und erhält den Fokus.
**Fokus zurücksetzen** führt zur Übersicht zurück. Ein neuer Architekturbezug
setzt den Fokus zurück und filtert die Übersicht; die Detailauswahl bleibt erhalten.

Die Requirementsliste berücksichtigt ausschließlich unmittelbare Zuordnungen zu
FEs, ihren Implementierungen und eingesetzten Kernbauteilen. Unterstützt werden
requirement_ids, explizite RequirementLinks sowie allocated_to-Modellbeziehungen;
Doppelzuordnungen erscheinen einmal. Requirements an AEs und Domänen sowie
übergeordnete Kundenanforderungen werden nicht automatisch hineingemischt.
Übergeordnete Zusammenhänge bleiben in der Requirements-Traceability erhalten.
Mechanik- und Softwareobjekte zeigen ebenfalls ausschließlich ihre direkten
Requirement-Zuordnungen in einem ausklappbaren Detailbereich.

### 45.1 Schaltplanlegenden

Die KiCad-Wurzelseite besitzt unten rechts oberhalb des Schriftfeldbereichs
zwei getrennte Legenden: **Blocklegende · Domänen** mit rechteckigen Symbolen
und **Signallegende · Netze / Busse** mit Linienmustern (Busse stärker).
Domänenfarben stammen aus der Architektur, Signalfarben entsprechen der
Schaltplandarstellung. Bei einem belegten Legendenbereich wird die Wurzelseite auf A0 vergrößert.
Ist auch dort kein freier Platz vorhanden, meldet die Prüfung einen Fehler;
Blöcke werden nicht überdeckt. Bestehende verknüpfte Projekte
übernehmen die Änderung über die explizite Forward Annotation mit Prüffenster.


## 46. Attributmatrix und führendes Funktionselement

Ein **FE** beschreibt eine realisierte Funktion. Es erscheint als dasselbe Objekt
in der Facharchitektur und im Realisierungskontext. Name, Funktionsbeschreibung,
Systembeitrag, Disziplin, Betriebsbedingungen und Betriebsmodi gehören zum FE.
Es verweist auf Architekturelement, Schnittstellen, funktionale Abhängigkeiten
und konkrete Implementierungen. Nur systembestimmende Kernbauteile stehen im
Architektur- und Part-Kontext; die vollständige BOM stammt aus dem ECAD-Design.

**Implementierungen / Variantencontainer** werden unter dem FE aufgeklappt.
Dort bleiben Status, Auswahlbegründung, aktive Variante und technische Istwerte.
Bei alten HW-Realisierungen erzeugt die Projektvorbereitung bei Bedarf ein stabiles
FE und behält alle bisherigen Implementierungskennungen, Varianten, Requirements-
und Nachweisreferenzen. Vorhandene FE-Zuordnungen werden wiederverwendet; mehrere
historische Besitzer bleiben erhalten. Software- und Mechanikzuordnungen eines
Architekturelements werden in einem zugehörigen FE gebündelt. Unzugeordnete Teile
werden nicht ohne fachlichen Architekturbezug zu Funktionen erklärt.

### 46.1 Vollständige objektbezogene Angaben

Die Details zeigen **Objektangaben**, getrennte **Anforderungsattribute** und
**Realisierungsattribute** sowie ausklappbare **Verknüpfungen und Bestandteile**.
Leere Felder bleiben **Offen**; Null und Nein bleiben tatsächliche Werte.
Native Angaben wie MPN, Codepfad, CAD-Revision oder Host/Teilnehmer werden direkt
aus dem Objektmodell angezeigt und nicht nochmals in Attributräumen gespeichert.
Busmitglieder besitzen dieselbe vollständige Anzeige ihrer eigenen Angaben.

Technische Sollwerte liegen am fachlich passenden Requirement; technische Istwerte
an der konkreten Implementierung oder an einem Kennwert mit Quelle, Revision,
Bedingungen und gegebenenfalls Variante. Ein FE zeigt auch die unmittelbar seinen
Implementierungen zugeordneten Requirements mit dem ursprünglichen Zuordnungsziel.
Domänen-/AE-Anforderungen und übergeordnete Kundenanforderungen werden nicht
als direkte Realisierungsanforderungen ausgegeben. Der technische Vergleich zeigt
auch noch offene Felder der zugeordneten Quellen, ist standardmäßig geschlossen
und kann auf **Offen / prüfen** oder **Abweichend** eingeschränkt werden.

**FE bearbeiten**, **Objekt bearbeiten** beziehungsweise **Bearbeiten** öffnen die
bestehende Eingabemaske. Dropdowns verwenden objekt- und disziplinbezogene Kataloge.
Die Auswahl eines Software- oder Mechanik-FEs zeigt die Angaben rechts; erst die
Bearbeitungsaktion öffnet eine Maske. Kennungen, Topologieableitungen und importierte
Quellenkennungen bleiben geschützt.

### 46.2 Property Manager

Der Property Manager führt native Objektfelder und zusätzliche Attribute in einem
Katalog. Filtern Sie nach Objekttyp, Attributart oder Text. Die mittlere Spalte
beschreibt die Bedeutung; ein Klick öffnet die Definition mit Datentyp, Einheit,
Attributraum, Auswahlquelle / Werten, Beziehungspartnern, führender Pflegequelle,
Austauschrichtung, ECAD-Ziel und Abbildung. Identität, Beschreibung, Beziehung,
technischer Kennwert, Klassifikation, Werkzeugregel, Quelle / Nachweis,
Prozess / Bewertung und abgeleitete Anzeige sind getrennte Attributarten.

Systemdefinitionen und native Objektfelder lassen sich nicht umdefinieren oder
löschen. Werte werden über die Objektmaske gepflegt, soweit sie bearbeitbar sind.
Eigene Attribute können mit ihrer Metadatenbeschreibung ergänzt und verwaltet
werden. Eine ECAD-Abbildungsbeschreibung dokumentiert die Zuständigkeit; sie
programmiert keinen neuen Connector und erzeugt keine PCB-Regel automatisch.

Netzklasse und weitere Klassenzuweisungen gehören ausschließlich zu Netzen und
Busmitgliedern. Die Bus-Standardklasse gilt für Mitglieder ohne eigene Klasse.
KiCad-Netzklassenzuordnungen werden weiterhin in die Projektdatei übertragen;
Prioritäten und bestehende Layoutregeln stammen aus dem ECAD-Projekt. Technische
Soll-/Ist-Angaben in Projektmetadaten ersetzen keine Design Rules oder Constraints.

### 46.3 Bestehende Projekte

Die Migration ist wiederholbar. Fachlich nicht mehr passende Systemwerte bleiben
unter **Erhaltene Bestandswerte** mit bisherigem Attributraum erhalten. Technische
Altwerte erscheinen im Vergleich als **Bestand prüfen**. Es werden keine
Anforderungen als erfüllt gesetzt und keine ECAD-Dateien beim Öffnen verändert.
Nach ausdrücklichem Löschen eines FEs bleibt eine dadurch offene Zuordnung offen.

## 47. Xpedition: SPOT JSON, Projektanlage und COM-Prüfung

### Arbeitsplatz und Verbindung

Im ECAD-Dialog **ECAD-System → Xpedition** wählen. Der Connector verwendet dieselbe SPOT JSON wie Architektur und KiCad. Es gibt kein zweites dauerhaft gepflegtes Xpedition-Projektmodell. Native UIDs und Hierarchieinstanzen werden getrennt unter `properties.ecadConnectors.xpedition.nativeBindings` gespeichert; die ISD-SHA-Identität bleibt unverändert.

Direkter COM-Zugriff benötigt eine Windows-Installation mit Xpedition Designer. `start_windows.bat` installiert die Plattformabhängigkeit `pywin32`. Der Connector erzeugt seine Python-Bindings aus der installierten Typbibliothek (`ViewDraw.Application`), statt den alten, versionsgebundenen `ifc.py` mitzuliefern. Ein COM-Test ist kein automatischer Nachweis für alle Designer- und Constraint-Manager-Funktionen.

Unter **Projekt / COM** eine vorhandene `.prj` eintragen und **COM und Projekt prüfen** aufrufen. Der Bericht nennt Version, verfügbare Einstiegspunkte, Rootblock und auslesbare Objektzahlen. Ein anderes geöffnetes Projekt wird nicht automatisch geschlossen oder gewechselt: speichern, schließen und die Prüfung wiederholen. COM-Aufrufe laufen in einer initialisierten STA des ausführenden Threads.

### Neues Projekt und vorhandenes Projekt

**Bestehendes Projekt verknüpfen** liest die Struktur und speichert ausdrücklich die Projektzuordnung. Existieren auf beiden Seiten Objekte ohne gemeinsame ISD-IDs, wird keine automatische Zuordnung anhand ähnlicher Namen durchgeführt. Den Schaltplan zuerst in ein neues ISD-Projekt zurücklesen. Eine manuelle Zuordnung fremder Bestandsobjekte zu bereits vorhandenen AEs ist in diesem Stand noch nicht enthalten.

**Neues Projekt anlegen und verknüpfen** benötigt Zielordner und Projektname; Zentralbibliothek, Projektvorlage und iCDB-Server richten sich nach der lokalen Xpedition-Konfiguration. Die native Anlage verwendet `NewProject(ProjectPath, CentralLibraryPath, ServerName, ProjectTemplatePath)` und kontrolliert anschließend die tatsächlich geöffnete `.prj`. Fehlt ein iCDB-Design, wird es über `AddiCDBDesign` angelegt. Der Projektordner darf noch nicht existieren. Bei fehlgeschlagener nativer Anlage bleibt ein möglicher Teilstand für die Diagnose erhalten.

Das neue Projekt wird als aktives verknüpftes Projekt gespeichert. Anschließend **Forward Annotation** öffnen. Projektanlage und Architekturübernahme sind getrennte Schritte: Die Projektanlage erzeugt keine ungeprüfte Schaltplanstruktur.

### Forward Annotation und Rücklesen

**Forward-Änderungen über COM prüfen** öffnet das separate, maximierte Prüffenster mit Vorher/Nachher-Werten. Der Vergleich verwendet den letzten gemeinsamen Stand. Beidseitig geänderte Felder sind Konflikte; unveränderte ISD-Werte überschreiben keine zwischenzeitlichen ECAD-Änderungen. Ausgelassene Unterschiede bleiben für spätere Prüfungen erhalten. Vor einer nativen Übernahme werden ISD- und ECAD-Prüfstand erneut kontrolliert.

Die Generierung verwendet hierarchische Funktionsblöcke für Domänen, AEs und Hardware-FEs, Architekturports und beschriftete Netz-/Bussegmente mit Hierarchieanschlüssen. Businhalte werden in der tatsächlichen Projekt-Buscontent-Datei materialisiert; andere vorhandene Busdefinitionen bleiben erhalten. Mindestens ein interner Host bestimmt die Hostseite einer Domäne. Anforderungsattribute dürfen durch die Back Annotation nicht überschrieben werden.

Vor nativen Änderungen wird das Projekt gespeichert und ein ZIP des Projektordners als Sicherung daneben angelegt. Nach der Übernahme wird gespeichert und über COM erneut gelesen. Alle angeforderten Objektwerte müssen bestätigt sein. Ein Fehler meldet den Sicherungspfad; er wird nicht als erfolgreiche Annotation gespeichert. Die Sicherung wird nicht automatisch über eine laufende Xpedition-Sitzung zurückkopiert.

Unter **Backward Annotation** kann ein bestehendes Projekt aktualisiert oder eine leere Hardwarearchitektur aus einem Schaltplan aufgebaut werden. Alle Symbolpins werden unabhängig von ihren Verbindungen gelesen. Ein nicht angeschlossener Port bleibt somit erhalten. Explizite Host-/Teilnehmerrollen werden übernommen; fehlende Rollen bleiben offen. Mehrere Hosts an einem Netz oder widersprüchliche Namen zu derselben ISD-Netz-ID führen zu einer Fehlermeldung.

Funktionsblöcke unter einem AE werden als Hardware-FE mit Schaltplanreferenz zurückgelesen und erscheinen im vorhandenen FE-Kontext der Architektur und Realisierung. Ein FE bleibt eine funktionale Abstraktion. Der Connector führt in diesem Stand keinen automatischen Import aller physischen Bauteile, Datenblätter oder einer vollständigen Xpedition-BOM durch.

Bei unmarkierten Schaltplänen wird die Hierarchietiefe als Domäne → AE → FE interpretiert. Abweichende Bestandsstrukturen müssen mit `ISD_KIND` eindeutig gekennzeichnet werden. Native Instanz und UID bestimmen die neue stabile SHA-Identität. Wiederverwendete Instanzen dürfen nicht dieselbe explizite `ISD_ID` tragen.

### Netzklassenvorgabe und Grenzen dieses Stands

Busmitglieder behalten ihre eigenen Netzklassenvorgaben; SPOT transportiert auch die Standardklasse des Busses. `ISD_NETCLASS` am nativen Netz kennzeichnet die Vorgabe. **Dieses Attribut ist kein Nachweis, dass eine Net Class im Constraint Manager angelegt oder einem elektrischen Netz zugewiesen wurde.** Die wirksame CM-Übertragung und ihre Rücklese-API sind bis zum Installationstest als `unverified` gekennzeichnet. Constraints und Designregeln werden nicht erzeugt.

Native Löschungen, das Verschieben eines bestehenden AE zwischen Domänen und Änderungen an der Topologie eines bestehenden Netzes sind in der Forward-Vorschau als nicht unterstützt gekennzeichnet. Sie dürfen nicht als erfolgreich angewendet bestätigt werden. Diese Änderungen zunächst in Xpedition durchführen und zurücklesen. Bei bestehenden Requirements-/Realisierungsreferenzen kann die ISD eine Löschung als ungültig zurückweisen; Beziehungen zuerst fachlich bereinigen.

### Serverbetrieb: SPOT-Bridge am Windows-Arbeitsplatz

Wenn die ISD auf einem Server läuft, kann dessen Browser nicht direkt auf Windows-COM zugreifen. **SPOT-Austauschpaket herunterladen** liefert `ISD_SPOT.json` und die Aufrufe. Die ISD Suite am ECAD-Arbeitsplatz entpacken und in deren Python-Umgebung ausführen:

```powershell
python -m architecture_app.xpedition_cli diagnose --project "C:\Design\Design.prj" --output diagnose.json
python -m architecture_app.xpedition_cli create --spot ISD_SPOT.json --parent "C:\Designs" --name NeuesDesign --library "C:\Libraries\Central.lmc" --output ISD_SPOT_verknuepft.json
python -m architecture_app.xpedition_cli preview --spot ISD_SPOT_verknuepft.json --project "C:\Designs\NeuesDesign\NeuesDesign.prj" --output review.json
```

Ein vorhandenes Projekt wird über `python -m architecture_app.xpedition_cli link --spot ISD_SPOT.json --project "C:\Design\Design.prj" --output ISD_SPOT_verknuepft.json` ausdrücklich verknüpft.

`review.json` ist ein temporäres Prüfdokument. Es enthält Änderungen, Warnungen und `decisions`: `apply`, `skip` oder `open`. Alle Werte ansehen, Konflikte ausdrücklich lösen und erst dann anwenden. Änderungspayloads aus diesem Dokument werden nicht direkt ausgeführt; die Bridge berechnet die Vorschau erneut aus SPOT und COM und kontrolliert den Prüfstand.

```powershell
python -m architecture_app.xpedition_cli apply --spot ISD_SPOT_verknuepft.json --review review.json --output ISD_SPOT_bestaetigt.json
python -m architecture_app.xpedition_cli read --spot ISD_SPOT_bestaetigt.json --project "C:\Designs\NeuesDesign\NeuesDesign.prj" --output ISD_SPOT_ruecklesen.json
```

Die zurückgelesene SPOT JSON im Xpedition-Dialog hochladen und die Backward-Änderungen prüfen. Für einen neuen Import zuerst ein neues ISD-Projekt anlegen. Lokale Pfade beziehen sich auf den Windows-Arbeitsplatz; der Server greift bei diesem Import nicht auf sie zu.

### Nativer Austauschtest

Ein separates Testprojekt mit zwei Domänen, mehreren AEs, offenen Ports, Einzelsignalen, einem Bus mit unterschiedlichen Mitgliedsklassen und einem FE verwenden. Diagnose ausführen, Projekt anlegen, Forward-Vorschau prüfen und übertragen. Dann speichern, schließen und in Xpedition erneut öffnen. Den lesenden Vergleich aufrufen:

```powershell
python -m architecture_app.xpedition_cli roundtrip --spot ISD_SPOT_bestaetigt.json --project "C:\Designs\NeuesDesign\NeuesDesign.prj" --output roundtrip.json
```

Zusätzlich Netznamen, offene Ports und Blocknamen in Xpedition ändern und zurücklesen. Zweiter unveränderter Lauf darf keine neuen Objekte erzeugen. Einen beidseitig geänderten Wert als Konflikt testen. Elektrische Hierarchiekonnektivität und Busauflösung auch mit Xpeditions eigenen Prüfungen prüfen: Ein erfolgreicher COM-Wertevergleich ersetzt keine ERC-/Netlistprüfung. CM-Klassenzuordnungen separat am tatsächlichen Constraint Manager prüfen.

Die automatisierten Tests der Suite prüfen SPOT-Abgleich und die COM-Verträge mit Testobjekten. Sie ersetzen diesen Installationstest nicht.

## 48. KI-Anbindungen: Provider, Modelle und Verbindung

### 48.1 Konfigurieren und prüfen

**KI-Zugang konfigurieren** in der Kopfzeile öffnen. Provider wählen: die
Verbindungshilfe, der Standardendpunkt und die Modellvorschläge folgen dieser
Auswahl. Beim Wechsel wird das eingegebene Geheimnis entfernt. Der bisher
aktive Zugang bleibt bis **Zugang übernehmen** erhalten; **Abbrechen** verwirft
den Entwurf. Die ISD speichert ein aktives Profil, keine Sammlung unabhängiger
Providerprofile.

1. Zugang beim gewählten Anbieter einrichten und API-Key bzw. Token eingeben.
2. Den Standardendpunkt verwenden oder einen ausdrücklich gewünschten API-Endpunkt
   eintragen. Bei Ollama liegt dieser auf dem Rechner des ISD-Servers.
3. **API-Modelle laden** ergänzt die Dropdownliste um den accountabhängigen Katalog.
   Die dokumentierten Vorschläge bleiben sichtbar. Diese Vorschläge sind keine Zugriffsgarantie und wählen nicht automatisch
   das teuerste oder neueste Modell. **Alternativer Modellname** nimmt eine exakte
   Modell-ID an und hat Vorrang vor dem Dropdown.
4. **Verbindung testen** führt eine kleine strukturierte Modellanfrage ohne
   Projektinhalt aus. Sie kann kostenpflichtig sein. Ein erfolgreicher
   Katalogabruf allein bestätigt weder JSON-Unterstützung noch Inferenzzugriff.
5. Kontextprofil **Sparsam** oder **Vollständiger Kontext** wählen und Zugang
   übernehmen. Der Verbindungstest verändert den aktiven Zugang nicht.

Der API-Key bleibt im laufenden ISD-Prozess oder wird im Credential Manager
abgelegt. Nur das Profil ohne Geheimnis liegt in der Anwendungsdatenbank;
SPOT JSON und Revisionen enthalten keine Zugangsdaten. Der Credential Manager
speichert den Schlüssel des aktiven Profils. Microsoft-Graph-Token sind
kurzlebig und nur für die Sitzung zulässig. Schlüssel werden bei Wechsel des
Providers oder Endpunkts nicht automatisch weitergereicht.

### 48.2 Unterstützte Anbindungen und Einrichtung

| Provider | Einrichtung | Protokoll / Modellwahl |
|---|---|---|
| OpenAI | API-Key und API-Abrechnung in der [Platform](https://platform.openai.com/docs) einrichten. ChatGPT-Abonnement ist kein API-Zugang. | Responses mit strukturiertem Schema; accountabhängiger Modellkatalog. |
| Anthropic / Claude | API-Key und Budget in der [Claude Console](https://platform.claude.com/docs/en/api/overview). | Native Messages API; paginierter Modellkatalog; Text und visuelle PDF-Analyse. |
| Google Gemini | Key und Projektkontingent in [Google AI Studio](https://ai.google.dev/gemini-api/docs/openai) einrichten. | Gemini OpenAI-kompatibler Endpunkt; keine Vertex-AI-Anmeldung. |
| xAI / Grok | Key und API-Budget in der [xAI Console](https://docs.x.ai/overview). | OpenAI-kompatible Chat Completions und Modellkatalog. |
| Ollama | [Ollama](https://docs.ollama.com/api/openai-compatibility) installieren/starten; `ollama pull <Modell>` ausführen. | Lokale installierte Modelle; `http://127.0.0.1:11434/v1`; lokal kein Key nötig. |
| Mistral | Key und API-Abrechnung in [La Plateforme](https://docs.mistral.ai/api/endpoint/models). | Chat Completions und Modellkatalog. |
| DeepSeek | Key und Guthaben auf der [API Platform](https://api-docs.deepseek.com/api/list-models/). | Chat Completions und Modellkatalog. |
| Groq | Key und Kontingent in der [Groq Console](https://console.groq.com/docs/openai). | Chat Completions und Modellkatalog. |
| OpenRouter | Key und Budget bei [OpenRouter](https://openrouter.ai/docs/api_reference/overview). | Anbieterpräfix in der Modell-ID beachten; JSON-Fähigkeit ist modellabhängig. |
| GitHub Copilot | [Python SDK](https://github.com/github/copilot-sdk/tree/main/python) und Runtime installieren; Copilot-Zugang und zugelassenes GitHub-Token. | SDK-Modellkatalog und strukturierte Sitzung; kein generischer HTTP-Endpunkt. |
| Microsoft 365 Copilot | Copilot-Lizenz, Entra-App und delegiertes Graph-Token entsprechend der [Chat API Preview](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/ai-services/chat/overview). | Dienst wählt das Modell; keine externe Modellauswahl. |
| Eigener kompatibler Endpunkt | Vollständige Base URL mit API-Prefix und gegebenenfalls Key. | Chat Completions mit JSON-Modus; Modellliste optional, manuelle ID möglich. |

GitHub Copilot benötigt das **optionale** Paket und dessen Runtime:

```text
pip install github-copilot-sdk
python -m copilot download-runtime
```

Das SDK nutzt ein zugelassenes GitHub-Token und die Berechtigungen des
Copilot-Kontos. ISD stellt keine Agentenwerkzeuge bereit und lehnt angeforderte
Werkzeug-/Dateiberechtigungen ab. Sitzungsdaten laufen in einem temporären,
separaten Verzeichnis ohne den ISD-Projektordner. Das SDK-Paket und seine native
Runtime werden nicht in das ISD-ZIP aufgenommen. GitHub Models ist ein anderer
Dienst und wird nicht als Copilot-Anbindung angeboten; laut GitHub wurde er am
30. Juli 2026 eingestellt.

### 48.3 Workflow und Grenzen

Dokumentanalyse, Requirements-Ableitung, Architektursynthese, Beratung und
Änderungsvorschläge nutzen denselben gewählten Provider. Antworten werden vor
Übernahme gegen dieselben ISD-Datenverträge validiert. Ungültige oder
abgeschnittene Ergebnisse werden nicht übernommen. KI-Vorschläge durchlaufen
weiterhin die vorhandene Prüfung; eine Antwort bestätigt keine Erfüllung.
Kontextbegrenzung und Antwortcache bleiben erhalten. Provider-, Modell- und
Endpunktwechsel leeren den Cache.

Visuelle PDF-Schaltplananalyse ist für OpenAI und Claude angebunden; andere
Provider nutzen die extrahierten Texte. Unterstützt ein Modell JSON nicht,
wechseln Sie das Modell oder den Provider. Für Copilot liefert die ISD die
Requestzahl, aber keine vollständige Tokenabrechnung. Kontostand, Kosten und
Organisationsbudget werden beim jeweiligen Anbieter geprüft. Der separate
Verbindungstest zählt nicht zum Verbrauch der aktiven Analyse-Sitzung.

### 48.4 Umgebungsvariablen und Fehlerbehebung

`ISD_SUITE_AI_PROVIDER`, `ISD_SUITE_AI_MODEL`, `ISD_SUITE_AI_BASE_URL` und
`ISD_SUITE_AI_CONTEXT_PROFILE` konfigurieren den Serverstart. Der generische
`ISD_SUITE_AI_API_KEY` oder der providerspezifische Schlüssel wird genutzt:
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`,
`MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`,
`GH_TOKEN` beziehungsweise `MICROSOFT_GRAPH_TOKEN`. Ollama benötigt lokal
keinen Schlüssel. Ein Modell ohne initialen Vorschlag muss ausdrücklich
gewählt oder in `ISD_SUITE_AI_MODEL` eingetragen werden. Alte ECAD-/XPED-
Variablen bleiben als Fallback lesbar.

- **Kein Katalog:** Zugang, API-Prefix, Netzwerk und Kontingent prüfen; exakte ID
  manuell eintragen, falls der Endpunkt keinen Katalog bereitstellt.
- **Modell gefunden, Analyse scheitert:** Text-/JSON-Fähigkeit und Accountfreigabe
  prüfen; ein Katalog kann auch Bild-, Sprach- oder Embeddingmodelle enthalten.
- **Ollama nicht erreichbar:** Läuft der Dienst auf dem ISD-Server? Ist das Modell
  tatsächlich geladen? Ein anderer Rechner benötigt dessen freigegebenen Endpunkt.
- **Copilot:** SDK/Runtime beziehungsweise Graph-Lizenz, Tokenablauf und aktuelle
  delegierte Berechtigungen prüfen. GitHub- und Microsoft-Token sind verschieden.
- **Credential Manager nicht verfügbar:** Sitzungsspeicherung verwenden oder
  ein unterstütztes Betriebssystem-Backend einrichten.

### 48.5 Vollständigkeit eines neuen Stands

Jeder neue Stand enthält alle seit dem vorherigen Stand vereinbarten Änderungen,
sofern sie nicht ausdrücklich zurückgestellt wurden. Changelog und Prüfbericht
nennen Umsetzung und noch fehlende native Nachweise. v0.51.0 baut vollständig auf
v0.50.0 einschließlich Xpedition/SPOT/COM auf; dessen dokumentierte native Grenzen
werden durch die KI-Erweiterung nicht als erledigt gewertet.

### 48.6 Microsoft-Graph-Zugang im Detail

Entra-App für den Organisationsmandanten registrieren. Für den delegierten
Arbeits-/Schulkonto-Zugang nennt Microsoft aktuell gemeinsam `Sites.Read.All`,
`Mail.Read`, `People.Read.All`, `OnlineMeetingTranscript.Read.All`, `Chat.Read`,
`ChannelMessage.Read.All` und `ExternalItem.Read.All`. Die erforderliche Zustimmung
im Mandanten einholen und über einen von Microsoft unterstützten delegierten
OAuth-Ablauf ein Graph-Zugriffstoken beziehen. Kein App-Secret oder ID-Token im
ISD-Tokenfeld verwenden. Das Bearer-Zugriffstoken ohne das Präfix `Bearer` eintragen.
Persönliche Konten und reine Application-Permissions werden für diese API nicht
angeboten. Nach Tokenablauf ein neues Token für die Sitzung übernehmen.

Die ISD schaltet Web-Grounding für jeden Aufruf aus. Der Microsoft-Dienst kann
weiterhin Enterprise-Grounding verwenden; das ist kein von ISD eingelesener
Quellenbeleg. Die gemeinsamen Regeln verlangen deshalb belegte Projektquellen,
offene Unsicherheiten und Prüfung vor Übernahme. Die Graph-Schnittstelle bleibt
Beta/Preview. Aktuelle Anleitung und Berechtigungen:
[Microsoft Chat API](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/ai-services/chat/copilotconversation-chat).

Dokumentierte Modellvorschläge, geprüft am 8. Oktober 2026:
OpenAI GPT-6.1 Sol / GPT-6 Astra / GPT-6 Luna, Claude Sonnet / Opus / Haiku 5.5,
Gemini 3.8 Flash und Grok 4.7. Gespeicherte Modell-IDs werden nicht umgestellt.
Die jeweils zugänglichen Modelle müssen über den API-Katalog und den
Verbindungstest bestätigt werden. Quellen:
[OpenAI](https://developers.openai.com/api/docs/models),
[Claude](https://platform.claude.com/docs/en/models/overview),
[Gemini](https://ai.google.dev/gemini-api/docs/openai),
[xAI](https://docs.x.ai/overview).

## 49. Modell- und ECAD-Auswahl prüfen

Im KI-Konfigurator sind die dokumentierten Modellvorschläge sofort im Dropdown
**API-Modell** sichtbar, auch ohne API-Key und mit einem älteren gespeicherten
Modell. Das Eingabefeld im Dropdown filtert nach Modell-ID. **API-Modelle laden**
ergänzt weitere Modelle; es entfernt keine Vorschläge und keine aktuell gewählte
ID. Eine alte Auswahl wird beim Öffnen oder Aktualisieren nicht umgestellt.

Gemini zeigt zusätzlich Flash-Lite und Pro Preview; Mistral, DeepSeek, Groq und
OpenRouter haben ebenfalls Vorschläge. Die Liste ist keine Accountfreigabe:
**Verbindung testen** prüft den Zugriff auf die ausgewählte ID. Ollama zeigt
die tatsächlich installierten Modelle nach dem Laden seiner lokalen API-Liste.
Eigene kompatible Endpunkte bleiben ohne erfundene Modell-IDs.

Unter **ECAD-Konnektor → ECAD-System** sind **KiCad** und **Xpedition** unmittelbar
im Dropdown wählbar. Die Auswahl öffnet den passenden Dialog. Hin- und
Rückwechsel sind möglich; der vorige Dialog wird entfernt. Die Auswahl der
Ansicht allein verändert keine Projektverknüpfung. Xpedition kann auch auf einer
Serverinstallation ohne COM gewählt werden: Dort stehen der SPOT-Austausch und
die Windows-Bridge im Vordergrund; native COM-Aktionen benötigen Windows.

### 49.1 Läuft tatsächlich der neue Stand?

KI-Konfigurator und ECAD-Dialog zeigen ihre **ISD-Suite-Version**. Bei v0.51.1
muss dort **ISD Suite v0.51.1** stehen. Nach einem Update die laufende ISD im
Startfenster mit **Strg+C** beenden, den neu entpackten Stand über
`start_windows.bat` starten und die Anwendungsseite neu laden. Nur das
Browserfenster zu aktualisieren lädt keinen neuen Python-Prozess; der Server
läuft ohne automatisches Neuladen. Die bestehenden Projekte liegen separat im
Anwendungsdatenverzeichnis.

Zusätzliche Modell-IDs wurden am 8. Oktober 2026 anhand der offiziellen
Anbieterdokumentation geprüft:
[Mistral](https://docs.mistral.ai/models),
[DeepSeek](https://api-docs.deepseek.com/api/list-models/),
[Groq](https://console.groq.com/docs/models),
[OpenRouter](https://openrouter.ai/openai/gpt-6.1-sol),
[Gemini](https://ai.google.dev/gemini-api/docs/models).
