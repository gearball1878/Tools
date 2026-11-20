# Attribute Profile Manager v3

This version refines attribute profiles around two concepts:

## PinType Attributes

Pin metadata is defined per electrical pin type (`IN`, `OUT`, `BIDI`, `PASSIVE`, `POWER`, `GROUND`, `ANALOG`). Select a pin type in the dropdown and edit its dedicated attributes below it. These attributes are intended for DRC and metadata workflows, for example:

- `POWER`: `Max Voltage`, `Power Rating`
- `GROUND`: `Ground Domain`
- `IN`: `Input Voltage Max`, `Input Threshold`

## BODY / Part Attributes

BODY attributes are split into:

- Core BODY attributes, valid for all symbols.
- Component class / PartType attributes, selected through the `CLASS` attribute.

`RefDes` is a locked core attribute and cannot be deleted. `CLASS` is also locked because it selects the component class / PartType-specific profile.

The manager can derive component class profiles from the current library and from the compressed Template Editor library archive `mentor_known_templates.tar.xz`.
