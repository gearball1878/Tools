# Symbol Wizard - Klassenmodell

Dieses Klassenmodell beschreibt die wichtigsten Daten-, UI-, Grafik- und Import/Export-Klassen des Tools. Es ist als Architekturübersicht gedacht und ergänzt das HowTo.

## 1. Architekturüberblick

```text
LibraryModel
└── SymbolModel [single | split]
    └── SymbolUnitModel [eine Unit / ein Split-Part]
        ├── SymbolBodyModel
        ├── PinModel[]
        ├── TextModel[]
        └── GraphicModel[]

MainWindow
├── SymbolScene / SymbolView
├── PropertiesPanel
├── SplitPinManagerDialog
├── TemplateEditorDialog
└── Import/Export Services
```

Die wichtigste Trennung ist:

- **Model-Klassen** speichern die Symbolsemantik.
- **Graphics-Klassen** rendern und editieren diese Modelle im Canvas.
- **GUI-Klassen** stellen Werkzeuge, Dialoge, Menüs und Properties bereit.
- **IO-Klassen** lesen und schreiben JSON sowie Mentor/Xpedition ASCII.
- **Rules-Klassen** enthalten Grid-, Placement- und Validierungslogik.

## 2. Datenmodell

### LibraryModel

Root-Container der Anwendung.

| Feld / Methode | Bedeutung |
|---|---|
| `symbols: list[SymbolModel]` | alle geladenen Symbole |
| `current_symbol_index` | aktives Symbol |
| `add_symbol()` | neues Single- oder Split-Symbol erzeugen |
| `current_symbol()` | aktives Symbol sicher zurückgeben |
| `unique_symbol_name()` | eindeutige neue Namen erzeugen |
| `unique_import_name()` | Importkonflikte vermeiden |

### SymbolModel

Ein komplettes Symbol oder Split-Symbol.

| Feld | Bedeutung |
|---|---|
| `name` | Symbolname |
| `kind` | `single` oder `split` |
| `is_split` | Legacy-Kompatibilität für Split-Symbole |
| `grid_inch` | Arbeitsraster, z. B. `0.100` inch |
| `sheet_format` | A0 bis A5 |
| `origin` | Origin-Modus |
| `template_name` | genutztes Template / Importmodus |
| `units` | Symbolteile / Split-Parts |

### SymbolUnitModel

Eine logische Unit. Bei Mentor-Split-Symbolen entspricht eine Unit genau einer Datei im ZIP.

| Feld | Bedeutung |
|---|---|
| `name` | Unit-/Split-Part-Name |
| `body` | Symbolkörper |
| `pins` | Pins der Unit |
| `texts` | normale Texte |
| `graphics` | Linien, Rechtecke, Ellipsen |

### SymbolBodyModel

Grafischer und semantischer Hauptkörper einer Unit.

| Feld | Bedeutung |
|---|---|
| `x`, `y`, `width`, `height` | Body-Geometrie |
| `color`, `line_width`, `line_style` | Body-Darstellung |
| `attributes` | Symbolattribute, z. B. `RefDes`, `Value`, `Package` |
| `visible_attributes` | Sichtbarkeit der Body-Attribute |
| `attribute_texts` | persistente Positionen der Attributtexte |
| `attribute_font`, `refdes_font` | Fonts für Attribute und RefDes |
| `refdes_align`, `body_attr_align` | Ausrichtung |

### PinModel

Semantisches Pinmodell. Es ist die wichtigste Klasse für Mentor-Kompatibilität.

| Feld | Bedeutung |
|---|---|
| `number` | physikalische Pin-/Ballnummer |
| `name` | sichtbarer Pinname |
| `function` | Pin-Funktion / Signalbeschreibung |
| `pin_type` | `IN`, `OUT`, `BIDI`, `POWER`, `GROUND`, `ANALOG`, ... |
| `side` | `left` oder `right` |
| `x`, `y`, `length` | Pin-Anker und Länge im Wizard-Modell |
| `inverted` | invertierter Pin |
| `visible_number` | Pin Number anzeigen |
| `visible_name` | Pin Name anzeigen |
| `visible_function` | Pin Function anzeigen |
| `number_font`, `label_font` | Fonts für Nummer und Label/Funktion |
| `attributes` | zusätzliche sichtbare/unsichtbare Pinattribute |
| `visible_attributes` | Sichtbarkeit zusätzlicher Pinattribute |

Mentor-Export nutzt daraus u. a.:

```text
P ...
L ... <pin.name>
A ... #=<pin.number>
A ... PINTYPE=<pin.pin_type>
A ... PINFUNCTION=<pin.function>   ; unsichtbar
```

### TextModel

Normale Texte und Textattribute im Symbol.

| Feld | Bedeutung |
|---|---|
| `text` | Textinhalt |
| `x`, `y` | Textanker |
| `font_family`, `font_size_grid` | Font |
| `color` | Textfarbe |
| `h_align`, `v_align` | Ausrichtung |
| `wrap_text` | mehrzeiliger Umbruch |

### GraphicModel

Grafische Zusatzobjekte.

| Feld | Bedeutung |
|---|---|
| `shape` | `line`, `rect`, `ellipse`, ... |
| `x`, `y`, `w`, `h` | Geometrie |
| `curve_radius` | Rundung / Kurvenradius |
| `style` | Stroke, Fill, Line Width, Line Style |

### TransformModel

Basisklasse für transformierbare Modelle.

| Feld | Bedeutung |
|---|---|
| `rotation` | Rotation in Grad |
| `scale_x`, `scale_y` | Skalierung |

### FontModel

Gemeinsames Fontmodell.

| Feld | Bedeutung |
|---|---|
| `family` | Fontfamilie |
| `size_grid` | Größe in Grid-Einheiten |
| `color` | RGB-Farbe |

### StyleModel

Gemeinsames Linien-/Füllmodell.

| Feld | Bedeutung |
|---|---|
| `stroke` | Linienfarbe |
| `fill` | Füllfarbe oder `None` |
| `line_width` | Linienbreite in Grid-Einheiten |
| `line_style` | solid, dash, dot, dash_dot |

## 3. Enumerations

| Enum | Werte / Zweck |
|---|---|
| `PinType` | IN, OUT, BIDI, PASSIVE, POWER, GROUND, ANALOG |
| `PinSide` | left, right |
| `OriginMode` | bottom_left, bottom_right, center, top_left, top_right |
| `DrawTool` | select, pin, text, line, rect, ellipse |
| `SymbolKind` | single, split |
| `SheetFormat` | A0, A1, A2, A3, A4, A5 |
| `LineStyle` | solid, dash, dot, dash_dot |
| `TextHAlign` | left, center, right |
| `TextVAlign` | upper, center, lower |

## 4. GUI-Klassen

### MainWindow

Zentrale Anwendungsklasse.

Aufgaben:

- Menüstruktur und Ribbon aufbauen
- Symbol-/Unit-/Canvas-Tabs verwalten
- Zeichenwerkzeuge steuern
- Undo/Redo, Copy/Paste, Delete
- Import/Export auslösen
- Properties, Pin-Tabelle und Objektbaum synchronisieren
- Canvas neu aufbauen
- Autosave/Restore verwalten
- Help/HowTo/Klassenmodell anzeigen

### PropertiesPanel

Eigenschaftseditor rechts im Hauptfenster.

Aufgaben:

- ausgewählte Objekte lesen
- editierbare Felder anzeigen
- Änderungen ins Modell zurückschreiben
- Body-, Pin-, Text- und Grafikattribute bearbeiten

### SplitPinManagerDialog

Zentrales Multi-Edit-Fenster für Pins.

Aufgaben:

- alle Pins eines Single- oder Split-Symbols tabellarisch anzeigen
- spaltenweise Filter unter den Spaltenüberschriften anbieten
- Bool-Filter für `Show #`, `Show Name`, `Show Function`, `Inverted`
- Sortieren, Markieren, Doppelklick-Navigation
- Bulk-Edit für Sichtbarkeit, Inverted und Pin Function

### TemplateEditorDialog

Editor für wiederverwendbare Symboltemplates.

Aufgaben:

- Template-Body, Pins, Texte und Grafiken bearbeiten
- nur bei echten Änderungen Save-Prompt auslösen
- Template-Daten für neue Symbole bereitstellen

### PinComboDelegate

Qt-Delegate für Dropdown-Zellen in Pin-Tabellen.

Aufgaben:

- ComboBox nur während der Bearbeitung erzeugen
- doppelte Textdarstellung vermeiden
- saubere Darstellung für Pin-Typen oder Bool-Felder

### NoWheelOnValueWidgets

Globaler Eventfilter.

Aufgaben:

- verhindert versehentliche Wertänderungen per Mausrad in ComboBoxen und SpinBoxen
- Scrollen in Panels bleibt möglich

## 5. Grafik-/Canvas-Klassen

### SymbolScene

QGraphicsScene für das aktive Symbol.

Aufgaben:

- Sheet-/Formatrahmen und Zeichenbereich rendern
- Origin und Grid darstellen
- Body-, Pin-, Text- und Grafikitems verwalten
- Selektion und Geometrieänderungen an MainWindow melden

### SymbolView

QGraphicsView für die Scene.

Aufgaben:

- Zoom, Pan, Viewport-Darstellung
- Maus-/Keyboard-Interaktion weiterreichen
- Canvas angenehm navigierbar machen

### TransformMixin

Gemeinsame Transformationslogik für Canvas-Items.

Aufgaben:

- Rotation, Skalierung und Flip anwenden
- Modell und grafisches Item synchron halten

### BodyItem

Grafische Darstellung von `SymbolBodyModel`.

Aufgaben:

- Body-Rechteck rendern
- Body verschieben/skalieren
- Attribute und RefDes passend positionieren

### PinItem

Grafische Darstellung von `PinModel`.

Aufgaben:

- Pinlinie, Pin Number, Pin Name und Pin Function zeichnen
- Pinfarben nach PinType-Palette darstellen
- Pinanker auf Grid halten
- Inverted-Status visualisieren

### TextItem

Grafische Darstellung von `TextModel`.

Aufgaben:

- Textanker und Ausrichtung rendern
- Fontgröße, Farbe, Rotation und Umbruch anwenden

### GraphicItem

Grafische Darstellung von `GraphicModel`.

Aufgaben:

- Linien, Rechtecke und Ellipsen zeichnen
- Style, Breite, Fill und Transformation anwenden

## 6. Import-/Export-Klassen und Funktionen

### json_store

Funktionen:

| Funktion | Zweck |
|---|---|
| `save_library()` | komplette Library als JSON speichern |
| `load_library()` | Library JSON laden |
| `save_symbol()` | einzelnes Symbol speichern |
| `load_symbol()` | einzelnes Symbol laden |

### mentor_sym

Funktionen:

| Funktion | Zweck |
|---|---|
| `import_mentor_sym()` | einzelne `.sym/.1` oder Split-ZIP importieren |
| `export_mentor_sym()` | Single-Datei oder Split-ZIP exportieren |
| `_import_native_single()` | natives Mentor-ASCII parsen |
| `_export_native_unit()` | eine Unit als Mentor-ASCII schreiben |
| `_mentor_key_id()` | stabile CRC32-basierte `K`-ID erzeugen |
| `_mentor_revision_timestamp()` | Mentor-Zeitstempel `H:MM:SS_M-D-YY` erzeugen |

Mentor-Split-Regel:

- Split Import: ZIP-Datei, jede Datei = eine `SymbolUnitModel`
- Split Export: eine ZIP-Datei, jede Unit = eine `.1` Datei
- Single Import/Export: eine einzelne `.sym` oder `.1` Datei

## 7. Rules-Klassen / Logikmodule

### grid.py

Aufgaben:

- Grid-Konstanten wie `PX_PER_INCH`
- Pin-Validierung, z. B. doppelte Pin-Nummern
- nächste freie Pin-Nummer bestimmen

### placement.py

Aufgaben:

- automatische Pin-Erzeugung
- Standardpositionen für neue Pins
- Platzierungsregeln relativ zum Body

## 8. Typische Datenflüsse

### Wizard JSON laden

```text
JSON file
→ json_store.load_library/load_symbol
→ LibraryModel / SymbolModel
→ MainWindow.rebuild_all()
→ SymbolScene + PropertiesPanel + Pin-Tabellen
```

### Mentor Split ZIP importieren

```text
ZIP
→ import_mentor_sym()
→ jede Datei parsen
→ SymbolUnitModel pro Datei
→ SymbolModel(kind='split')
→ Canvas/Pin Manager
```

### Mentor Split ZIP exportieren

```text
SymbolModel(kind='split')
→ export_mentor_sym()
→ jede Unit durch _export_native_unit()
→ ZIP mit einer .1 Datei pro Unit
```

### Pin im Split Pin Manager ändern

```text
SplitPinManagerDialog
→ PinModel ändern
→ MainWindow.mark_dirty()
→ rebuild_scene/rebuild_pin_table
→ optional Mentor Export
```

## 9. Mentor-relevante Designregeln

- Mentor-Dateien enthalten normalerweise keine RGB-Farben; Pinfarben sind Wizard-UI-Palette.
- Elektrisch entscheidend sind Pin-Ankerkoordinaten.
- `PinModel.number` wird als `#=` exportiert.
- `PinModel.pin_type` wird als `PINTYPE=` exportiert.
- `PinModel.function` wird als unsichtbares `PINFUNCTION=` exportiert.
- Zusätzliche `PinModel.attributes` können als unsichtbare `A`-Records exportiert werden.
- Split-Symbole kommen und gehen als ZIP.
- Einzelne Symbole kommen und gehen als einzelne Dateien.

## 10. Erweiterungspunkte

| Bereich | Erweiterung |
|---|---|
| Pinmodell | weitere Pinattribute, Diffpair, Swapgroup, Bank |
| Mentor Export | zusätzliche native `A`-/`U`-Records |
| Split Pin Manager | weitere Bulk-Edit-Felder |
| Templates | Firmenstandards, Body-Stile, Attributlayouts |
| Validation | ERC-Regeln, Bankregeln, DDR-/Diffpair-Prüfung |
| UI | weitere Filter, Farbschemata, Theme-Unterstützung |
