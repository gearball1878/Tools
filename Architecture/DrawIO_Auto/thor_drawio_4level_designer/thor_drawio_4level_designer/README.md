# THOR 4-Level Top-Down draw.io Designer

## Struktur

- Level 1: Domänen  
  Beispiel: `PSU_THOR`, `PSU_ETH`, `SoM`, `SafetyMicro`, `Radar`

- Level 2: Architekturelemente  
  Beispiel: `PSU_THOR_Core_Voltage_1`, `PSU_ETH_VDDIO_1`

- Level 3: Konfigurationsebene  
  Hier werden externe funktionale Bauteile an funktionale Instanzen angeschlossen.

- Level 4: Funktionale Instanzen wiederverwendbarer Objekte  
  Beispiel: `OBJ_Buck_Controller_Reusable_1`, `OBJ_EEPROM_Reusable_1`

## Anforderungen

Jeder Block hat:

- eindeutige `id`
- eindeutigen `name`
- `level`
- beliebige proprietäre `attributes`

Jeder Port hat:

- eindeutige `id`
- `name`
- `type`: `in`, `out`, `bidi`, `power`, `ground`, `analog`
- beliebige proprietäre `attributes`

Jede Verbindung hat:

- eindeutige `id`
- eindeutigen `name`
- `type`: `net` oder `bus`
- `source`: `BLOCK_ID.PORT_ID`
- `target`: `BLOCK_ID.PORT_ID`
- beliebige proprietäre `attributes`

## Top-Down Navigation

Die erzeugte draw.io Datei enthält mehrere Pages:

- `L1_Domains`
- eine Page pro Block mit Kindern, z. B. `PSU_THOR`, `SoM`, `CFG_SoM_Boot_1`

Damit sieht man zunächst nur Level 1 und kann dann über die Page-Tabs bzw. Links tiefer gehen.

## Run

```bash
python example_thor_4level.py
```

Erzeugt:

- `thor_4level_topdown.drawio`
- `thor_4level_topdown.json`
