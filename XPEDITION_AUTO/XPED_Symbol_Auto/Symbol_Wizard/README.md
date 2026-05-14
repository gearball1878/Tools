# Symbol Wizard

PySide6 MVP for creating/editing electronic symbols with single-symbol and split-symbol workflows.

## Start

```bash
pip install -r requirements.txt
python main.py
```

## Current MVP features

- Separate workspaces: **Symbols** for single symbols and **Split Symbols** for multi-unit symbols.
- Each symbol has its own tab; default names are generated as `Symbol {n}`.
- New imports with the same name are renamed using `_{n}` suffixes.
- JSON exchange format:
  - Save current symbol as JSON.
  - Save all symbols as JSON library.
  - Import symbol JSON.
  - Open JSON library.
- Verification: pin numbers must be unique across the whole symbol.
  - For split symbols, all units are checked together.
  - Copy/paste of pins assigns the next free pin number automatically.
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
- Use `Ctrl + mouse wheel` to scale selected objects.
- Use `R` / `Q` for rotate clockwise/counterclockwise.
- Use `+` / `-` to scale selected objects.

## Notes

This is still an MVP. The next useful step is replacing the simple corner handles with a dedicated transform overlay/gizmo for precise CAD-like manipulation.

## Update

- Canvas-Selektion bleibt jetzt nach Live-Refresh, Properties-Änderungen und Copy/Paste erhalten.
- Das Linienwerkzeug fügt neue Linien initial gerade/horizontal ein (`h = 0`, Länge 2 Rastereinheiten). Danach kann die Linie wie andere Zeichenobjekte verschoben, skaliert oder gedreht werden.
