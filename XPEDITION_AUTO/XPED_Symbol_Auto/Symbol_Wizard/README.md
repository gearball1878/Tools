# Symbol_Wizard

PySide6 MVP for an automated schematic symbol editor.

## Run

```bash
pip install -r requirements.txt
python main.py
```

## Current MVP features

- Grid-based 2D editor with 0.100 inch default grid and 0.050 inch minimum grid
- Symbol body with editable body attributes
- Per-attribute visibility checkboxes for symbol body attributes
- Visible body attributes rendered in the drawing canvas
- Pins left/right, pin attributes, visibility flags and inverted pin marker
- Text objects with font and RGB color
- Additional drawing objects: line, rectangle, ellipse/circle
- Insert panel for adding drawing objects later
- Dedicated pin tab/table
- Unit/SplitSymbol tabs
- Object tree per unit: Body, Attributes, Pins, Text and Graphics
- Copy/Paste/Delete for selected canvas objects
- Extendable main menu bar
- JSON open/save as initial exchange format

## Project structure

```text
symbol_wizard/
  app.py
  config.py
  gui/
    main_window.py
    properties_panel.py
  graphics/
    scene.py
    view.py
    items.py
  io/
    json_store.py
  models/
    document.py
  rules/
    grid.py
    placement.py
```
