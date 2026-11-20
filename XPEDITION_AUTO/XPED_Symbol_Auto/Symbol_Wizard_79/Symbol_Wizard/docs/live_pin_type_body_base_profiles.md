# Live PinType attributes and BODY base classes

## PinType attributes

PinType attributes from the Attribute Profile Manager are now applied immediately when:

- a new pin is placed in the Symbol Wizard,
- a new pin is placed in the Template Editor,
- a single pin's `Pin Type` is changed,
- multiple pins are changed through Multi-Edit,
- pins are changed through the Split Pin Manager.

Built-in Mentor pin attributes such as `PINTYPE` remain internal. Custom PinType profile attributes are refreshed from the selected electrical pin type so later DRC/export/meta processes see the correct metadata.

## BODY base classes

The Attribute Profile Manager now supports an optional BODY base-class layer:

1. Core BODY Attributes: always valid for every symbol.
2. BODY Base Classes: reusable middle layer, for example common attributes for families of parts.
3. PartType-specific BODY Attributes: concrete component-class attributes selected by `CLASS`.

A PartType can select a base class in the BODY / PartType Attributes tab. When profiles are applied to a symbol, attributes are merged in the order Core -> Base Class -> PartType.
