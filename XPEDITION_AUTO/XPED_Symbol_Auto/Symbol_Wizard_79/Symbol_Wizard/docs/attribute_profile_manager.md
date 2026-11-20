# Attribute Profile Manager

Adds a global Attribute Profile Manager for Symbol Wizard.

## PinType custom attributes

Pin custom attributes are now managed globally by `pin_type`. Built-in Mentor pin attributes (`#`, `NAME`, `PIN / FUNC`, `PINTYPE`) are not shown in the Custom Pin Attributes property panel because they are intrinsic pin fields and are synchronized from the pin model.

The profile JSON uses this structure:

```json
{
  "version": 1,
  "pin_types": {
    "IN": {
      "attributes": [
        {"name": "MY_ATTR", "value": "", "visible": false}
      ]
    }
  },
  "core_part_attributes": [
    {"name": "RefDes", "value": "U?", "visible": true}
  ],
  "part_types": {
    "TYPE": {
      "attributes": [
        {"name": "Package", "value": "", "visible": true}
      ]
    }
  }
}
```

## PartType / BODY attributes

Core part attributes apply to every symbol. PartType attributes are applied based on the BODY attribute `TYPE` when updating the current symbol from profiles.

## UI actions

Tools menu:

- Attribute Profile Manager
- Update Current Symbol Attributes From Profiles
- Import/Export Symbol Attributes JSON remain available for current symbol BODY attributes.

## Pin font bulk edit

Pin font bulk edit now shows the actual common font/size. If selected/all pins have mixed values, the UI shows `<multiple>`. Size fields use grid units.
