# Multi-Pin, Enter Commit and Undo Fix

This update fixes three runtime issues reported in the Symbol Wizard UI.

## Multi-pin property editing

The multi-pin property panel no longer captures live `PinItem` / `QGraphicsItem`
wrappers in property callbacks.  Those wrappers can become invalid after a scene
refresh and PySide then raises `RuntimeError: Internal C++ object already deleted`.

The panel now captures stable `PinModel` references and the setters also accept
model references directly.  This affects:

- Pin Function bulk edit
- Show Number / Show Name / Show Function
- Pin Length
- Pin Style
- Pin Width
- Color

Both the main Symbol Wizard and the Template Editor use the same model-reference
approach.

## Enter commits property editors

Line edits and multi-line text fields now commit with Enter and then leave edit
mode.  Spin boxes and combo editor line edits also lose focus after Enter through
the global value-widget event filter.  Shift+Enter remains available for text
line breaks where the editor supports it.

## Undo after BODY/origin edits

BODY drag now has a final undo safeguard in the graphics item update layer: if
no existing BODY mouse-press handler pushed an undo snapshot, one is created
before the drag starts.  Origin reset/change also returns focus to the canvas so
Ctrl+Z is handled by the Symbol Wizard instead of remaining in the combo/editor
that initiated the change.
