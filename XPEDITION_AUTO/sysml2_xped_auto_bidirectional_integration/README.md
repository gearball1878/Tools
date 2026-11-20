# SysML2 Architecture Builder + xped_auto

Dieses Paket verbindet den SysML2 Architecture Builder bidirektional mit dem
JSON-Format des extrahierten `xped_auto`-Generators.

## Installation

```bash
python -m pip install -r requirements.txt
```

Die GUI und der JSON-Konverter sind plattformunabhängig. Das Ausführen oder
Auslesen eines realen Xpedition-Projekts benötigt Windows, Xpedition Designer
und dessen COM-Registrierung.

## GUI

```bash
python main.py --gui
```

Die GUI enthält zwei zusätzliche Aktionen:

- **Export Xpedition JSON** erzeugt `*.xped.json` und die zugehörige
  `*.xped-map.json`.
- **Import Xpedition JSON** liest sowohl das EA/Xpedition-Austauschformat als
  auch kompakte Snapshots aus `gather_design_info.py`.

Die Map-Datei hält Builder-IDs, Architektur-GUIDs und Netz-IDs stabil. Sie
sollte beim Austausch zusammen mit der Exchange-Datei aufbewahrt werden.

## Kommandozeile

Builder-JSON nach Xpedition:

```bash
python main.py --xped-export architecture.json --out exchange
```

Xpedition-/EA-Exchange zurück in den Builder:

```bash
python main.py \
  --xped-import exchange/Generic_Architecture.xped.json \
  --manifest exchange/Generic_Architecture.xped-map.json \
  --out imported
```

Kompakten Xpedition-Snapshot importieren:

```bash
python main.py \
  --xped-import xpedition_snapshot.json \
  --system-name Vehicle_Architecture \
  --out imported
```

## Xpedition-Projekt erzeugen/aktualisieren

Der Runner ist standardmäßig ein Dry-run und prüft Pfade sowie JSON-Struktur:

```bash
python -m xped_auto.runner \
  --exchange-json exchange/Generic_Architecture.xped.json \
  --project C:\XpeditionLocal\Project\Project.prj
```

Erst `--apply` startet die schreibende COM-Automation:

```bash
python -m xped_auto.runner \
  --exchange-json exchange/Generic_Architecture.xped.json \
  --project C:\XpeditionLocal\Project\Project.prj \
  --apply
```

Vor `--apply` immer eine Kopie des Xpedition-Projekts verwenden. Der extrahierte
Legacy-Generator wurde statisch repariert und mit dem neuen Adapter verbunden;
ein realer COM-Integrationstest war in dieser Umgebung nicht möglich.

## Xpedition-Projekt zurücklesen

Auf dem Windows-/Xpedition-Rechner:

```bash
python -m xped_auto.snapshot \
  --project C:\XpeditionLocal\Project\Project.prj \
  --out exchange\xpedition_snapshot.json
```

Danach den Snapshot mit `main.py --xped-import ...` öffnen. Xpedition-SCM-IDs,
Architektur-GUIDs, Komponenteninformationen und nicht nativ modellierbare
Felder bleiben in den `attributes` des Builder-Modells erhalten.

## Abbildung

| Builder | xped_auto Exchange |
| --- | --- |
| Architekturmodell | System |
| Domain | Module |
| Architecture Element | AE |
| Port | AE Port / Module Port |
| Net/Bus Reference | AE Port Cons |
| Builder-ID | stabile GUID über `*.xped-map.json` |
| Xpedition UID | `xpedScmId`-Attribut |

Legacy `xped_auto` kennt keine eigene Ground-Port-Kategorie. Ground wird beim
Export daher als `PowerIn` dargestellt und beim Round-trip über die
Source-Metadaten wiederhergestellt.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q main.py sysml2_arch_builder xped_auto tests
```

