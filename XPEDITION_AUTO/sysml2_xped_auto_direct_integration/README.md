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

Die native Builder-JSON-Datei ist zugleich die primäre Eingabe für
`auto_schem`; eine Enterprise-Architect-Anbindung ist nicht enthalten und wird
nicht benötigt. Die GUI enthält zusätzlich zwei Austausch-/Diagnoseaktionen:

- **Export Xpedition JSON** erzeugt `*.xped.json` und die zugehörige
  `*.xped-map.json`.
- **Import Xpedition JSON** liest das interne Xpedition-Austauschformat sowie
  kompakte Snapshots aus `gather_design_info.py`.

Die Map-Datei hält Builder-IDs, Architektur-GUIDs und Netz-IDs stabil. Sie
sollte beim Austausch zusammen mit der Exchange-Datei aufbewahrt werden.

## Kommandozeile

Builder-JSON nach Xpedition:

```bash
python main.py --xped-export architecture.json --out exchange
```

Xpedition-Exchange zurück in den Builder:

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

Der Runner übernimmt die Objekte direkt aus dem nativen Architektur-JSON. Er
ist standardmäßig ein Dry-run und prüft Pfade, Objektabbildung und JSON-Struktur:

```bash
python -m xped_auto.runner \
  --architecture-json Generic_Architecture.json \
  --project C:\XpeditionLocal\Project\Project.prj
```

Erst `--apply` startet die schreibende COM-Automation:

```bash
python -m xped_auto.runner \
  --architecture-json Generic_Architecture.json \
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
  --out exchange\xpedition_snapshot.json \
  --architecture-out exchange\Generic_Architecture.json \
  --system-name Generic_Architecture
```

`--architecture-out` erzeugt direkt wieder das native Architektur-JSON. Ohne
diesen Parameter kann der kompakte Snapshot weiterhin mit
`main.py --xped-import ...` geöffnet werden. Xpedition-SCM-IDs,
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

Der extrahierte `xped_auto`-Kern kennt keine eigene Ground-Port-Kategorie. Ground wird beim
Export daher als `PowerIn` dargestellt und beim Round-trip über die
Source-Metadaten wiederhergestellt.

Der frühere Parameter `--exchange-json` wird nur noch als Kompatibilitätspfad
akzeptiert. Neue Integrationen verwenden `--architecture-json`. Der Reader
akzeptiert außerdem ein `ArchitectureModel` direkt im Speicher; der Writer kann
das interne Xpedition-Modell wieder als natives Builder-/SysML-JSON ausgeben.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q main.py sysml2_arch_builder xped_auto tests
```
