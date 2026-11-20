# Default / NONE symbol creation fix

Single and split symbol creation now both offer a real `<NONE>` / default symbol type.
This allows users to start from the native Symbol Wizard body outline without selecting a template from the catalog.

Changes:

- `available_template_keys(False)` includes `<NONE>` for single symbols.
- The New Symbol dialog sorts `<NONE>` first for single and split creation.
- Split `<NONE>` creation creates two starter split parts with native body outlines.
- Adding a new split part also uses the same native blank body template.

The blank body uses the normal `BodyItem` path, so the BODY outline is visible and editable like a normal Symbol Wizard body.
