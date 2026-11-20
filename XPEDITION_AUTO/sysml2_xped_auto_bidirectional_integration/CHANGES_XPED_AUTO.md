# Progressive Change Log – xped_auto Integration

## 2026-08-05 – Initiale bidirektionale Integration

- `xped_auto` als bereinigtes Legacy-Laufzeitmodul extrahiert; manuelle Test- und
  personenbezogene Beispielartefakte wurden nicht übernommen.
- `sysml2_arch_builder/xped_adapter.py` ergänzt:
  - Builder-JSON → EA/Xpedition-Exchange-JSON
  - EA/Xpedition-Exchange-JSON → Builder-JSON
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

- `python -m unittest discover -s tests -v`: 4/4 erfolgreich.
- `python -m compileall ...`: erfolgreich.
- Demo-CLI Round-trip: erfolgreich.
- Legacy-Reader auf generiertem Exchange-JSON: erfolgreich.
- Import des vorhandenen großen Xpedition-Snapshots: 13 Domains, 14 AEs,
  182 Ports und 182 Net References erfolgreich.
- Reales Xpedition-COM-Apply: nicht ausgeführt (Windows/Xpedition erforderlich).

