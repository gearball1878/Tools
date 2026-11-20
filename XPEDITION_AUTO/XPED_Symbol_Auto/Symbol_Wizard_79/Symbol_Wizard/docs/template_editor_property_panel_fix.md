# Template Editor property panel fix

## Problem

In the Template Editor, editing a property widget in the right panel could leave
that panel empty even though the selected canvas object remained selected. The
issue was easiest to reproduce with a selected GRAPHIC object by changing values
such as X, Y, Width, Height, Line width, Line style or Rotation.

## Root cause

The Template Editor refresh path could rebuild the form while a spin box, combo
box or line edit inside the same form still had focus. Removing the old rows could
emit late widget signals from controls that were about to be destroyed. Those
signals could schedule another canvas/property refresh in the middle of the
current refresh. If one of the compatibility refresh paths then returned early or
aborted after clearing the form, the side panel stayed blank.

Programmatic canvas updates from property widgets also moved `QGraphicsItem`s via
`update_current_unit_canvas_positions()`. That can trigger item-change callbacks,
which in turn request property refreshes. For property-panel edits this is not a
user canvas edit and should not recursively rebuild the property panel.

## Fix

- Form clearing in the active Template Editor compatibility layer now goes
  through `_template_editor_clear_form_safely(...)`.
- Existing form widgets and their child widgets have their signals blocked before
  rows are removed.
- The final `TemplateEditorDialog.refresh_properties()` target now has a
  re-entrancy guard.
- If a refresh path ever ends with an empty form while a selection still exists,
  `_template_editor_render_empty_panel_if_needed(...)` repairs the panel instead
  of leaving it blank.
- Property-widget model writes temporarily defer recursive property refreshes
  while `update_current_unit_canvas_positions()` synchronizes the canvas.
- The native Template Editor renderer now calls `clear_properties()` when the
  structured pipeline has installed one, so fallback refreshes use the same safe
  clear behavior.

## Regression coverage

`tests/test_legacy_pipeline.py` verifies that the Template Editor refresh path
uses safe form clearing, has the empty-panel repair guard, and keeps the original
Template Editor refresh fallback separated from the MainWindow renderer.
