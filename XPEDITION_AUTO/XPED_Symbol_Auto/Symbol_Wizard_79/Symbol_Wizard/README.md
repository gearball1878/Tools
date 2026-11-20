# Symbol Wizard

Symbol Wizard is a grid-based editor for creating, editing, validating, importing, and exporting electronic symbols for Mentor/Xpedition-oriented workflows.

## Documentation

The in-application documentation is the single source of truth:

- `symbol_wizard/docs/how_to.md` → loaded by **Help → How To**
- `symbol_wizard/docs/class_model.md` → loaded by **Help → Class Model**

Please update the Markdown files in `symbol_wizard/docs/` instead of duplicating documentation in Python source code or this README.

## Start

```bash
python main.py
```


## Development and quality checks

Install runtime dependencies:

```bash
python -m pip install -r requirements.txt
```

Optional development setup:

```bash
python -m pip install -e .[dev]
python tools/quality_check.py
python -m pytest
```

`tools/quality_check.py` uses only the Python standard library. It verifies that the Python source compiles and that bundled JSON assets are valid, so it can be run before installing PySide6.

## Optimized project layout

This delivery keeps the application behavior but removes the biggest packaging and legacy-structure problems:

- The former loose Mentor template catalogue is bundled as `symbol_wizard/symbol_templates/mentor_known_templates.tar.xz`.
- `.template_manifest.json` keeps template names/indexes available without parsing the archive at startup.
- The remaining compatibility layer is composed on shadow classes and copied to real runtime classes only once per canonical method.
- Historical patch labels were removed from active compatibility identifiers; remaining code is grouped by domain.
- Details are documented in `docs/optimization_report.md`.
