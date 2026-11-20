# Split Pin Manager: Bulk Pin Type edit

The Split Pin Manager bulk editor now includes a `Pin Type` combo next to the existing `Pin Function Text` controls.

Available modes:

- `Unchanged`: leave the pin type as-is.
- `IN`, `OUT`, `BIDI`, `PASSIVE`, `POWER`, `GROUND`, `ANALOG`: apply the selected pin type to all targeted pins.

The bulk operation works for the same target scopes as the existing visibility/function edits:

- marked rows
- currently filtered rows
- all pins

When a pin type is changed in bulk, the dialog also updates the pin metadata that depends on the type:

- `pin.pin_type`
- `pin.attributes['PINTYPE']`
- pin line/color metadata
- pin label and number font colors

This keeps the table, canvas rendering, and Mentor export metadata consistent after a bulk edit.
