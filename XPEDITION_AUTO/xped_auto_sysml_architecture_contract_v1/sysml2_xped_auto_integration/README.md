# SysML Architecture GUI + xped_auto

Die Architektur-GUI ist der Einstiegspunkt. Ihr versioniertes JSON-Modell ist
die einzige Datenquelle für die Xpedition-Schaltplanerzeugung.

## Installation und Start

```bash
python -m pip install -r requirements.txt
python main.py
```

Die Architektur-GUI und die JSON-Prüfung sind plattformunabhängig. Eine echte
Forward Annotation benötigt Windows, Xpedition Designer und die registrierte
COM-Klasse `ViewDraw.Application`.

## Datenfluss

```text
Architektur-GUI
  -> ArchJsonWriter
  -> arch_export_format_json_schema.json / JSONValidator
  -> sysml2-architecture/v1 JSON
  -> ArchJsonReader
  -> auto_scheme
  -> Xpedition COM
```

Es gibt kein zweites Xpedition-Exchange-JSON, keine ID-Map und keine
Enterprise-Architect-Anbindung. Die IDs der SysML-Architekturobjekte werden in
Xpedition als unsichtbares Attribut `Architecture UID` gespeichert.

| Architektur-JSON | Übergabe an `auto_scheme` | Xpedition |
| --- | --- | --- |
| `name` | Systemname | Projektkontext |
| Domain-Block | Domain-Abfragen | hierarchischer Domain-Block |
| Architecture Element | AE-Abfragen | Functional Block |
| Port `id`/`port_type` | Pin-ID/Kategorie/Richtung | Pin + `Architecture UID` |
| `net_id`/Net Reference | Netzname, Typ und ID | Net/Bus + `Architecture UID` |
| `attributes.xpedScmId` | vorhandene Xpedition-ID | Bestandszuordnung |

Die vier zentralen Vertragsdateien liegen direkt unter `xped_auto/`:

- `arch_export_format_json_schema.json`: striktes Schema für
  `sysml2-architecture/v1`.
- `json_validator.py`: bricht mit präzisem JSON-Pfad ab, bevor COM aufgerufen
  werden kann.
- `arch_json_reader.py`: stellt Domains, Architecture Elements, Ports und
  Netze für die Schematic-Routinen bereit.
- `arch_json_writer.py`: schreibt das GUI-Modell und bildet einen aus
  Xpedition gelesenen Snapshot wieder auf denselben JSON-Vertrag ab.

## Forward Annotation aus der GUI

Die GUI prüft die Xpedition-COM-Registrierung, ohne Xpedition zu starten. Nur
bei einer nutzbaren Installation wird **Forward Annotation...** aktiviert.
Nach Auswahl einer vorhandenen `.prj`-Datei und ausdrücklicher Bestätigung wird
das aktuelle Modell validiert gespeichert und an den Runner übergeben.

Der gleiche, standardmäßig nicht schreibende Aufruf ist auch direkt möglich:

```bash
python -m xped_auto.runner \
  --architecture-json architecture.json \
  --project C:\XpeditionLocal\Project\Project.prj
```

Erst `--apply` öffnet und verändert das Xpedition-Projekt. Dafür zunächst immer
eine Projektkopie verwenden.

## Rückweg aus Xpedition

```bash
python -m xped_auto.snapshot \
  --project C:\XpeditionLocal\Project\Project.prj \
  --out xpedition_snapshot.json \
  --architecture-out architecture_from_xpedition.json \
  --system-name Vehicle_Architecture
```

`--architecture-out` schreibt direkt `sysml2-architecture/v1`. Xpedition-IDs
werden getrennt als `xpedScmId`-Attribute geführt. Ein bereits erzeugter
Snapshot lässt sich in der GUI über **Import Xpedition Snapshot** öffnen.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q main.py sysml2_arch_builder xped_auto tests
```

Der reale COM-Schreiblauf kann nur auf einem Windows-System mit Xpedition
verifiziert werden.
