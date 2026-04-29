# THOR hierarchical draw.io object model

This example separates the architecture into three Python files:

- `model.py` — directly readable architecture objects:
  - `Design`
  - `Block`
  - `Port`
  - `Connection`
- `drawio_renderer.py` — renderer from Python objects to draw.io XML
- `example_thor.py` — concrete hierarchical THOR example

## Run

```bash
python example_thor.py
```

This creates:

- `thor_hierarchical_object_model.drawio`
- `thor_hierarchical_object_model.json`

The `.drawio` file can be opened directly in diagrams.net / draw.io.

## Object idea

The architecture is not stored primarily in draw.io.
The source of truth is the Python object model.

draw.io is only the visualization/export target.
