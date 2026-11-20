# Attribute Profile Manager - Core BODY Attribute Derivation

The Attribute Profile Manager now scans the full Template Editor library when
`Derive profiles from library` is used.

## Core BODY Attributes

The derivation collects BODY attributes from the current/custom library and from
`symbol_wizard/symbol_templates/mentor_known_templates.tar.xz`. Attributes are
promoted to **Core BODY Attributes** when they are common across the library
(for example by appearing on most BODY templates or most discovered component
classes). Locked core attributes such as `RefDes` and `CLASS` are always kept as
core attributes.

Core attributes are intentionally removed from every PartType-specific profile.
This keeps the profile model clean:

- Core BODY Attributes = common denominator for all parts.
- PartType-specific BODY Attributes = only metadata that is specific to that
  selected component class / part type.

## PartType-specific Attributes

After core promotion, the PartType profiles are pruned. If an attribute already
exists as a core attribute, it is not listed again under a specific PartType.
This applies both to newly derived profiles and to saved/imported profile data
when the dialog collects its current state.

## Protected Attributes

`RefDes` and `CLASS` remain protected:

- `RefDes` cannot be deleted.
- `CLASS` cannot be deleted because it controls the component class / PartType
  mapping.
