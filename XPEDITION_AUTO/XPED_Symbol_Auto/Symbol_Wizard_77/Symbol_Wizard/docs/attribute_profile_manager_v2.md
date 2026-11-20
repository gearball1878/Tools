# Attribute Profile Manager v2

The Attribute Profile Manager is now organized around the concepts used in the symbol workflow instead of a technical flat table.

## PinType Attributes

The **PinType Attributes** tab has a `Pin Type` dropdown. Each pin type has its own dedicated attribute list.

Examples:

- `POWER`: `Max Voltage`, `Power Rating`
- `GROUND`: `Ground Domain`
- `IN`: `Input Voltage Max`, `Input Threshold`
- `BIDI`: `IO Voltage Max`, `Drive Strength`

These attributes are global profile data and are intended for DRC checks, export metadata, and downstream metaprocesses. Attributes can be added, deleted, imported, exported, and applied to the current symbol.

## BODY / PartType Attributes

The BODY profile is split into two layers:

1. **Core BODY Attributes**  
   The smallest common denominator for every part, for example `Package`, `Datasheet-Link`, `TYPE`, or `RefDes`.

2. **PartType-specific BODY Attributes**  
   A dropdown selects a component type. Each selected part type has its own attribute set. Part types can be derived from the currently loaded/custom library where possible.

## JSON format

The full profile file uses this schema:

```json
{
  "version": 1,
  "core_part_attributes": [
    {
      "name": "Package",
      "value": "",
      "visible": true,
      "required": false,
      "description": "Common package metadata."
    }
  ],
  "part_types": {
    "RELAY": {
      "attributes": [
        {
          "name": "Coil Voltage",
          "value": "",
          "visible": false,
          "required": false,
          "description": "Relay coil voltage."
        }
      ]
    }
  },
  "pin_types": {
    "POWER": {
      "attributes": [
        {
          "name": "Max Voltage",
          "value": "",
          "visible": false,
          "required": false,
          "description": "Maximum power pin voltage for DRC."
        }
      ]
    }
  }
}
```

Single PinType or PartType import/export is also supported with either the complete nested profile shape or a simple object containing an `attributes` list.
