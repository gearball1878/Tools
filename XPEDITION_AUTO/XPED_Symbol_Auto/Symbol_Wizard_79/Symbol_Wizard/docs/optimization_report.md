# Optimization report

This build reduces the former historical patch stream into deterministic compatibility modules and removes the loose Mentor template JSON payloads from the source tree.

## Current structure

- `symbol_wizard/gui/main_window.py` remains the main UI orchestration class.
- `symbol_wizard/gui/legacy_pipeline/` contains the remaining active compatibility chain, split by domain.
- `symbol_wizard/graphics/items.py`, `view.py`, and `scene.py` contain the readable native graphics classes.
- `symbol_wizard/graphics/item_update_code.py` and `view_update_code.py` contain the remaining active compatibility code for item/view behavior.
- `symbol_wizard/symbol_templates/mentor_known_templates.tar.xz` stores the Mentor-derived template catalogue as a packed archive.
- `symbol_wizard/symbol_templates/.template_manifest.json` stores the template index used for fast key lookup.

## Runtime behavior

The compatibility modules are composed on temporary shadow classes first. Only explicit canonical class methods are copied to the real runtime classes. This keeps the former repeated overwrite stream out of the real classes.

## Size reduction

The original loose Mentor template directory used roughly 79 MB uncompressed. It is now stored as a single xz-compressed archive of roughly 1.8 MB, while the manifest keeps the template keys available without parsing the archive at startup.

## Remaining work

The next true semantic migration would move the remaining compatibility domains into normal modules:

1. BODY / transform / resize
2. Pin docking and grid snapping
3. Selection and grouping
4. Property panel synchronization
5. Graphics item and view interactions

This build is therefore a substantially smaller and cleaner delivery point, but not a complete rewrite of every remaining compatibility method.
