# Progressive Change Log – xped_auto Integration

## 2026-08-05 – Architektur-GUI als Einstieg und bedingte Forward Annotation

- `python main.py` öffnet jetzt standardmäßig die Architektur-GUI; `--gui`
  bleibt weiterhin verfügbar.
- Nicht-invasive Xpedition-Erkennung über die Windows-COM-Registrierung
  `ViewDraw.Application` ergänzt, einschließlich 32-/64-Bit-Registry-Views und
  Erkennung veralteter Registrierungen.
- Die GUI zeigt den Xpedition-Status und aktiviert **Forward Annotation...**
  sowie die `.prj`-Projektauswahl ausschließlich bei nutzbarer Installation
  und vorhandenen Python-COM-Abhängigkeiten.
- Vor dem schreibenden Lauf werden Projekt und `busconts.ini` angezeigt und
  eine explizite Bestätigung verlangt.
- Das aktuelle, gegebenenfalls noch nicht manuell gespeicherte Architekturmodell
  wird temporär als natives JSON direkt an `xped_auto.runner --apply` übergeben;
  die temporäre Datei wird danach bereinigt.
- Der Runner prüft vor jedem `--apply` dieselbe Xpedition-Verfügbarkeit wie die
  GUI. Dry-runs bleiben plattformunabhängig möglich.
- Drei Tests für gültige, veraltete und sicher geparste COM-Registrierungen
  ergänzt; insgesamt 10 Tests erfolgreich.

## 2026-08-05 – Direkter SysML-Architekturpfad, EA-Kopplung entfernt

- Das native JSON des SysML2 Architecture Builders ist jetzt die primäre
  Eingabe von `xped_auto.runner` und `auto_scheme.py` (`--architecture-json`).
- `ArchJsonReader` erkennt native Builder-JSONs und `ArchitectureModel`-Objekte
  und stellt Domains, Architecture Elements, Ports und Netze direkt den
  vorhandenen `auto_schem`-Abfragen bereit.
- `ArchJsonWriter` kann ein Architekturmodell übernehmen, das interne
  Xpedition-Format schreiben und wieder natives Builder-/SysML-JSON ausgeben.
- Der Xpedition-Snapshot-Reader kann mit `--architecture-out` direkt natives
  Architektur-JSON für den Rückweg erzeugen.
- Die frühere list-basierte Exchange-Struktur bleibt ausschließlich als
  internes Kompatibilitätsformat; eine Enterprise-Architect-Anbindung ist nicht
  mehr Bestandteil des Datenflusses.
- Neue Xpedition-Attribute heißen `Architecture UID`. Beim Rücklesen werden
  vorhandene `EA UID`-Attribute nur noch zur Bestandskompatibilität akzeptiert.
- Der nicht benötigte Laufzeit-Import von `deepdiff` wurde entfernt.
- Tests auf 7 Fälle erweitert, einschließlich direktem Reader-Objektpfad,
  Writer-Rückweg und Formatnormalisierung.

## 2026-08-05 – Initiale bidirektionale Integration

- `xped_auto` als bereinigtes Legacy-Laufzeitmodul extrahiert; manuelle Test- und
  personenbezogene Beispielartefakte wurden nicht übernommen.
- `sysml2_arch_builder/xped_adapter.py` ergänzt:
  - Builder-JSON → internes Xpedition-Exchange-JSON
  - internes Xpedition-Exchange-JSON → Builder-JSON
  - kompakter `gather_design_info`-Snapshot → Builder-JSON
  - deterministische GUIDs und separate `*.xped-map.json`
  - Erhalt von SCM-IDs, Varianten, Funktionen, Komponenten und Zusatzattributen
- GUI um **Export Xpedition JSON** und **Import Xpedition JSON** erweitert.
- CLI um `--xped-export`, `--xped-import`, `--manifest` und `--system-name`
  erweitert.
- Schreibender Xpedition-Runner mit vorgeschaltetem Dry-run und explizitem
  `--apply` ergänzt.
- Read-only Snapshot-Export aus einem realen Xpedition-Projekt ergänzt.
- Im Legacy-Code repariert:
  - harte Pfade durch Parameter ersetzt
  - Schema-Pfad relativ aufgelöst
  - Reader-Aufrufe auf die aktuelle `(system, domain, ae, ...)`-Signatur gebracht
  - immer-wahre Design-Level-Bedingungen korrigiert
  - `net_info_full()`-Einrückungs-/Verarbeitungsfehler korrigiert
  - Projektabschluss auf die aktive Connection-Instanz umgestellt
  - Interface-Template-Pfad konfigurierbar gemacht
- Vier Unit-Tests für Round-trip, Dateiautodetektion, Snapshot-Import und
  Rückwärtskompatibilität ergänzt.

## Verifikation

- `python -m unittest discover -s tests -v`: 10/10 erfolgreich.
- `python -m compileall ...`: erfolgreich.
- Demo-CLI Round-trip: erfolgreich.
- Legacy-Reader auf generiertem Exchange-JSON: erfolgreich.
- Import des vorhandenen großen Xpedition-Snapshots: 13 Domains, 14 AEs,
  182 Ports und 182 Net References erfolgreich.
- Reales Xpedition-COM-Apply: nicht ausgeführt (Windows/Xpedition erforderlich).
