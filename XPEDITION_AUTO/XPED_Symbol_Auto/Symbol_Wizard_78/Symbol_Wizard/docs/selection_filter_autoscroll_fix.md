# Selection Filter and Canvas Auto-scroll Fix

Version 67 adds a dedicated selection category for generated attributes.

## Selection filters

The Selectable combo now exposes:

- `ALL`
- `BODY`
- `PIN`
- `PLAIN TEXT` for plain, user-created text only
- `ATTRIBUTES` for generated body/refdes/attribute text
- `GRAPHIC`
- `Custom`

The same categories are used by the main Symbol Wizard, the Template Editor,
rubber-band selection and Select All.

## Shared helper

Selection mapping is centralized in:

```text
symbol_wizard/gui/selection_filter.py
```

This prevents the old behaviour where `ATTR_BODY` and `ATTR_REF_DES` were folded
into `TEXT` and could not be selected independently from plain text.

## Rubber-band auto-scroll

`SymbolView` now starts a timer while a rubber-band selection is dragged from an
empty canvas area. When the cursor reaches the edge of the viewport, the view
scrolls automatically and the rubber-band selection is recomputed against the
current scene rectangle.

The auto-scroll path is installed at the end of:

```text
symbol_wizard/graphics/view_update_code.py
```
