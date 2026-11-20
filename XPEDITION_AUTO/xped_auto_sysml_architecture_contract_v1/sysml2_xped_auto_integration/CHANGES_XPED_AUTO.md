# Progressive Change Log – XPED_AUTO

## 2026-08-05 – Einheitlicher Architekturvertrag und bereinigter COM-Pfad

- Die Architektur-GUI bleibt der Standard-Einstiegspunkt (`python main.py`).
- Einziger JSON-Vertrag ist jetzt `sysml2-architecture/v1` aus dem
  SysML-Architekturmodell.
- Das frühere listenbasierte Xpedition-Exchange-JSON, Map-Dateien und die
  zugehörigen GUI-/CLI-Aktionen wurden entfernt.
- `arch_export_format_json_schema.json` vollständig auf das native Modell
  umgestellt: Pflichtfelder, feste Ebenen, Enums und `additionalProperties`
  werden geprüft.
- `json_validator.py` bricht bei Schema-, Datei- oder JSON-Fehlern mit dem
  genauen Datenpfad ab; Validierung wird nie still übersprungen.
- `arch_json_reader.py` liest ausschließlich validierte Architekturmodelle und
  übergibt Domain-, AE-, Port- und Netzdaten direkt an `auto_scheme`.
- `arch_json_writer.py` schreibt ausschließlich denselben Architekturvertrag
  und unterstützt den Rückweg eines Xpedition-Snapshots.
- Reader, Writer, Validator, Schema und `auto_scheme` liegen nun direkt unter
  `xped_auto`; die alte Verzeichnis- und Importstruktur wurde entfernt.
- Nicht verwendete Hilfsprogramme, UI-Dateien, Farbcodetabellen und manuelle
  Testeinstiege wurden entfernt.
- Xpedition verwendet nur noch `Architecture UID`; alte EA-Bezeichnungen und
  Rückfallattribute wurden aus dem aktiven Code entfernt.
- Der Runner validiert Schema und Modell vollständig, bevor Installation oder
  COM angesprochen werden; `--apply` bleibt die einzige schreibende Freigabe.
- Die GUI-Projektauswahl bleibt nur bei erkannter Xpedition-Installation aktiv.
- Abhängigkeit `pandas` entfernt; die Übergabeobjekte sind kleine, explizite
  Python-Dictionaries.

## Verifikation

- 10 Unit-/Integrationsnahe Tests erfolgreich.
- Schema-Ablehnung des früheren Array-Formats getestet.
- Writer -> JSON -> Validator -> Reader -> Runner-Dry-run getestet.
- Xpedition-Snapshot -> Writer -> natives Architektur-JSON getestet.
- Python-Syntaxprüfung und Paketabhängigkeitsprüfung erfolgreich.
- Reale Xpedition-COM-Ausführung in dieser Umgebung nicht möglich.
