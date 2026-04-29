# THOR draw.io UML Objects

This variant renders architecture elements as UML-like objects/classes.

## Mapping

- Level 1 → `<<Domain>>`
- Level 2 → `<<ArchitectureElement>>`
- Level 3 → `<<Configuration>>`
- Level 4 → `<<ReusableFunctionalInstance>>`
- Net → `<<Net>>`
- Bus → `<<Bus>>`

## Readable attributes

Each UML object is wrapped in draw.io `<object>` metadata.

Open in draw.io and use:

- Right click object → Edit Data
- or Format Panel → Data

You will see:

- `kind`
- `object_id`
- `object_name`
- `stereotype`
- `level`
- `attr_*`
- `attributes_json`

## Run

```bash
python example_uml.py
```
