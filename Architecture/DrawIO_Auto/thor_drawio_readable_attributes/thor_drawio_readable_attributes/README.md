# THOR draw.io with readable proprietary attributes

This version stores custom attributes on draw.io `<object>` wrappers.

That is important because draw.io shows these fields directly in:

- Right click object → Edit Data
- Format Panel → Data

Each object contains readable flat fields like:

- `kind`
- `object_id`
- `object_name`
- `level`
- `type`
- `attr_domain`
- `attr_voltage`
- `attr_constraint_class`
- `attributes_json`

The `attributes_json` field keeps the full structured proprietary attribute set.
The flattened `attr_*` fields make the data readable immediately after opening the file.
