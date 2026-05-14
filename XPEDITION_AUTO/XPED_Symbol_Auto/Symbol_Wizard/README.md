# Symbol Wizard

PySide6 MVP for creating/editing electronic symbols with single-symbol and split-symbol workflows.

## Start

```bash
pip install -r requirements.txt
python main.py
```

## Current MVP features

- Separate workspaces: **Symbols** for single symbols and **Split Symbols** for multi-unit symbols.
- The separate **Pins** tab was removed; pins are now shown as child objects inside the Symbols/Split Symbols trees.
- Each symbol has its own canvas tab; split-symbol canvas tabs show the active part as `SplitSymbol.PartName` such as `AURIX.AURIX_1`.
- Default names are generated as `Symbol {n}`.
- New imports with the same name are renamed using `_{n}` suffixes.
- JSON exchange format:
  - Save current symbol as JSON.
  - Save all symbols as JSON library.
  - Import symbol JSON.
  - Open JSON library.
- Verification: pin numbers must be unique across the whole symbol.
  - For split symbols, all units are checked together.
  - Copy/paste of pins assigns the next free pin number automatically.
- Left workspace trees:
  - **Symbols** shows every single symbol with body, attributes, pins, text and graphics.
  - **Split Symbols** keeps the split-symbol selector and unit/split-part tabs; the split tree shows symbols with their corresponding pins.

- Canvas editing:
  - Select, move, resize and rotate objects.
  - Body and its related pins/text/graphics move as a grouped unit.
  - Body attributes are rendered in the drawing area and follow the body.
  - Body resize keeps pins docked to the selected side.
  - Multi-select copy/paste.
- Draw Ribbon:
  - Select/Edit, Pin L, Pin R, Text, Line, Rect, Ellipse.
  - Line style and line width.
  - RGB stroke color.
  - Rotate and scale buttons.
- Format preview:
  - A0/A1/A2/A3/A4/A5 landscape preview.
  - Red dashed usable region: max symbol area = 40% sheet width and 80% sheet height.
  - Zoom to fit symbol and sheet.

## Editing hints

- Drag object body/center to move.
- Drag corner/edge handles to resize rectangular bodies and graphic objects.
- Drag object body/center to move.
- Drag corner handles to resize in two directions; drag edge handles to resize in one direction.
- Double-click a text field to edit its text; single-click/drag keeps it movable.
- Use `Ctrl + mouse wheel` to zoom around the cursor.
- Use plain mouse wheel to pan up/down.
- Use `Shift + mouse wheel` to pan left/right.
- Use `R` / `Q` for rotate clockwise/counterclockwise.
- Use `+` / `-` or the ribbon buttons to scale selected objects.

## Notes

This is still an MVP. The next useful step is replacing the simple corner handles with a dedicated transform overlay/gizmo for precise CAD-like manipulation.

## Update

- Canvas-Selektion bleibt jetzt nach Live-Refresh, Properties-Änderungen und Copy/Paste erhalten.
- Das Linienwerkzeug fügt neue Linien initial gerade/horizontal ein (`h = 0`, Länge 2 Rastereinheiten). Danach kann die Linie wie andere Zeichenobjekte verschoben, skaliert oder gedreht werden.


## Latest update

- Sheet origin is now centered in the selected A-format.
- Canvas zoom is cursor-centered with `Ctrl + mouse wheel`.
- Mouse wheel pans vertically; `Shift + mouse wheel` pans horizontally.
- Text objects are movable by default and enter text editing only on double-click.
- Resize handling no longer rebuilds the whole scene during drag, which makes scaling smoother and avoids stale drawing remnants.

## PINMUX CSV Import

Menu: `File -> Import PINMUX CSV`

Expected columns:

```csv
Pin Name|Pin Type|Pin Function|Pin Number
VDD|POWER||1
PA0|BIDI|ADC_IN0|A1
```

Supported separators are comma, semicolon, pipe, and tab. If `Pin Function` is empty, the editor displays `Pin Name`; otherwise it displays `Pin Function`.


## Origin default

New symbols place the symbol origin at the center of the symbol body by default. Pins and body attributes remain grouped with the body during moves/resizes. Pins are constrained to 0°/180° rotation and their length snaps to full grid units.


## Mentor/Xpedition import and export notes

### Split versus single files

- Mentor split symbols are imported and exported as ZIP archives. Each file inside the ZIP is one split part/unit.
- Mentor single symbols are imported and exported as one `.sym` or `.1` file.

### Native Mentor origin

For Mentor/Xpedition symbols the Wizard keeps the native Mentor coordinate origin. The canvas origin `(0,0)` is the Mentor placement origin and is not moved to the body center. Imported Mentor symbols therefore keep their original offsets, for example a body may start at `b 30 30 ...` while pin electrical anchors stay at `P ... 0 ...`.

The A-format guide is hidden for native Mentor symbols so the visible crosshair shows only the true Mentor origin.

### Pin colors

Mentor `.sym/.1` files normally do not store RGB object colors. The Wizard colors pins in the UI semantically from `PINTYPE`:

- `IN` = blue
- `OUT` = red
- `BIDI`/`BI` = violet
- `POWER` = orange
- `GROUND` = green
- `ANALOG` = cyan
- `PASSIVE` = black

These colors are Wizard UI colors only. Native Mentor export remains colorless/standard because Mentor normally applies colors from its own display palette/theme.

### Pin name and pin function

Pin name and pin function are independent fields. If both are visible, both are rendered in the Wizard label. This is intentional.
