# SysML Architecture GUI + xped_auto

Die Architektur-GUI ist der Einstiegspunkt. Ihre versionierte JSON-Ressource
ist der **Single Point of Truth (SPOT)** für SysML und Xpedition. Xpedition hat
kein eigenes Exchange-JSON und keine separate ID-Map.

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
Forward Annotation:
Architektur-GUI -> SPOT JSON -> Validator -> Reader -> auto_scheme -> Xpedition COM

Back Annotation:
Xpedition COM -> in-memory COM data -> Writer -> Attribute am bestehenden SPOT-Objekt
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
| `attributes.xpedition.uid` / `.uids` | Xpedition-COM-UID(s) | Bestandszuordnung |

Die vier zentralen Vertragsdateien liegen direkt unter `xped_auto/`:

- `arch_export_format_json_schema.json`: striktes Schema für
  `sysml2-architecture/v1`.
- `json_validator.py`: bricht mit präzisem JSON-Pfad ab, bevor COM aufgerufen
  werden kann.
- `arch_json_reader.py`: stellt Domains, Architecture Elements, Ports und
  Netze für die Schematic-Routinen bereit.
- `arch_json_writer.py`: schreibt die SPOT-Ressource atomar und hängt
  Back-Annotationen an vorhandene Architektur-Objekte.

## Forward Annotation aus der GUI

Die GUI prüft die Xpedition-COM-Registrierung, ohne Xpedition zu starten. Nur
bei einer nutzbaren Installation wird **Forward Annotation...** aktiviert.
Nach Auswahl einer vorhandenen `.prj`-Datei und ausdrücklicher Bestätigung wird
das aktuelle Modell in seiner SPOT-Datei validiert gespeichert und genau diese
Datei an den Runner übergeben. Eine temporäre Architekturkopie wird nicht erzeugt.

Der gleiche, standardmäßig nicht schreibende Aufruf ist auch direkt möglich:

```bash
python -m xped_auto.runner \
  --architecture-json architecture.json \
  --project C:\XpeditionLocal\Project\Project.prj
```

Erst `--apply` öffnet und verändert das Xpedition-Projekt. Dafür zunächst immer
eine Projektkopie verwenden.

## Back Annotation aus Xpedition

```bash
python -m xped_auto.back_annotation \
  --architecture-json architecture.json \
  --project C:\XpeditionLocal\Project\Project.prj \
  --write-back
```

Der COM-Reader hält seine Rohdaten nur im Arbeitsspeicher. Der Writer ordnet
Domain, Architecture Element, Port und Netz ausschließlich über die in
Xpedition vorhandene `Architecture UID` einem bestehenden SPOT-Objekt zu und
schreibt die Xpedition-UID unter `attributes.xpedition.uid` zurück. Ein
Architekturnetz mit mehreren hierarchischen Xpedition-Instanzen erhält die
Liste `attributes.xpedition.uids`. Struktur,
Namen und Architektur-IDs werden nie aus Xpedition erzeugt oder überschrieben.
Unbekannte beziehungsweise fehlende Architecture UIDs führen zum Abbruch; die
SPOT-Datei bleibt dabei unverändert.

Beispiel eines back-annotierten Objekts:

```json
{
  "name": "Host_Block",
  "id": "BLK-1234567890",
  "attributes": {
    "xpedition": {
      "uid": "XPD-COM-UID"
    }
  }
}
```

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q main.py sysml2_arch_builder xped_auto tests
```

Der reale COM-Schreiblauf kann nur auf einem Windows-System mit Xpedition
verifiziert werden.
