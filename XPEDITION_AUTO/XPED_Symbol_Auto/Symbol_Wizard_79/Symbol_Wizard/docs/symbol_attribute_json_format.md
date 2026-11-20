# Symbol Attribute JSON Format

Symbol Wizard can export and import BODY/symbol attributes as a plain JSON list. Import is a complete overwrite of the current symbol's BODY attributes and is applied to all split parts of the symbol.

```json
{
  "format": "symbol_wizard.symbol_attributes.v1",
  "symbol": "example_symbol",
  "scope": "body",
  "attributes": [
    {
      "name": "TYPE",
      "value": "TYPE",
      "visible": true
    },
    {
      "name": "Package",
      "value": "BGA",
      "visible": true
    }
  ]
}
```

The importer also accepts a minimal list-only form:

```json
[
  {"name": "TYPE", "value": "TYPE", "visible": true},
  {"name": "Package", "value": "BGA", "visible": true}
]
```

If exported text placement data is present in the optional `text` field, it is restored; otherwise Symbol Wizard creates default text anchors and applies the current BODY attribute fonts.
