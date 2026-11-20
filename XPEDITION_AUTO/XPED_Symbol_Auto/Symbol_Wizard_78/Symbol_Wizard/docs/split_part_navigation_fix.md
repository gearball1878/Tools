# Split-Part Navigation Fix

Version 63 restores the active split-part navigation in the Symbol Wizard toolbar.

## Problem

The toolbar area already contained controls for the current symbol and split part, but the split-part selector could remain disabled and show `No split part` even when the current model was effectively a split symbol. This happened mainly for legacy/imported symbols whose data was inconsistent:

- `kind` could still be `single`, while
- `is_split` was true, or
- the symbol contained more than one unit / split part.

The legacy compatibility layer only checked `kind == split`, so these symbols were treated as single symbols by the toolbar.

## Fix

The split-part toolbar is now native `MainWindow` code:

- `build_active_navigation_toolbar()` creates the combined symbol / split-part selector.
- `is_split_symbol_model()` recognizes split symbols by `kind`, `is_split`, or multiple units.
- `sync_active_navigation_controls()` keeps the symbol and split-part controls synchronized after tab switches, undo/redo, imports, and workspace rebuilds.
- `step_active_split_part()` switches split parts with wrap-around.
- `Ctrl+Alt+Left` and `Ctrl+Alt+Right` switch to previous / next split part.

The legacy wrapper functions now delegate to the native implementation instead of creating separate patch-owned toolbars.

## User-visible behavior

For split symbols, the top toolbar shows:

```text
Symbol: [active symbol]    Split Part:  ◀ [active unit / split part] ▶
```

For single symbols, the split-part selector is disabled and shows `No split part`.
