# Snap, mirror and format-guide fixes

This update fixes three editor regressions:

1. Template Editor graphics now snap to the active edit grid when Snap is enabled, including imported/locked BODY graphics while they are edited as template primitives.
2. Horizontal/vertical flip mirrors free text, BODY attribute text and pin attribute text glyphs, not only their anchors.
3. The sheet/format guide is drawn behind symbol items instead of in the foreground, preventing the guide area from visually washing out symbols after pin/template edits.

The fixes are intentionally canonical final layers over the remaining compatibility pipeline and keep the existing data model fields (`scale_x`, `scale_y`, `x`, `y`, `w`, `h`).
