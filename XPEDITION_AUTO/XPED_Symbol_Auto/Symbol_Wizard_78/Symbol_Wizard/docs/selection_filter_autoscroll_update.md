# Selection filter and canvas autoscroll update

## Selection filter

The canvas selection filter now distinguishes between plain text and generated
attribute text.

Selectable modes:

- `ALL`
- `BODY`
- `PIN`
- `TEXT` for plain user text
- `ATTRIBUTES` for body/pin attribute text (`ATTR_REF_DES`, `ATTR_BODY` and
  attribute-backed text models)
- `GRAPHIC`
- `Custom`

The shared mapping lives in `symbol_wizard/gui/selection_filter.py` and is used
by the Symbol Wizard, the Template Editor and rubber-band selection.

## Canvas autoscroll

`SymbolView` now starts a lightweight timer while the user is left-dragging in
Select/Edit mode near a viewport edge.  The timer scrolls the horizontal and/or
vertical scrollbars until the cursor leaves the edge zone or the mouse button is
released.  This enables rubber-band selection beyond the currently visible
canvas area.
