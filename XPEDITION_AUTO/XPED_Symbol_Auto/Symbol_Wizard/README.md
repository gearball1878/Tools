# Symbol Wizard - How To Guide

## 1. Purpose

Symbol Wizard is a grid-based editor for creating, editing, validating, importing, and exporting electronic symbols for Xpedition/Mentor-oriented workflows. It supports both single symbols and split symbols with multiple units/parts.

The main design goals are:

- consistent grid-based symbol construction
- reliable pin and attribute management
- Mentor/Xpedition ASCII import/export
- split-symbol handling through ZIP archives
- reusable templates
- fast multi-edit workflows for large FPGA symbols

## 2. Main Window Overview

The window is divided into three areas:

- **Left workspace**: symbol lists, split-symbol units, pin overview, and object tree.
- **Center canvas**: graphical editor with grid, sheet/format preview, origin, body, pins, text, attributes, and graphics.
- **Right properties panel**: properties for the selected object or selection.

The ribbon contains drawing tools, grid/sheet/origin settings, style controls, transform controls, and pin actions.

## 3. File Menu Structure

The **File** menu is grouped by workflow.

### New

- **New Symbol** creates a single symbol.
- **New Split Symbol** creates a split symbol with one or more units.

### Project / JSON

- **Open Library JSON** loads a previously saved Wizard library.
- **Save Current Symbol JSON** saves only the active symbol.
- **Save All Symbols JSON** saves the complete library.
- **Import Symbol JSON** imports one Wizard JSON symbol into the current library.

### Mentor Import

- **Import Mentor Single Symbol** imports one `.sym` or `.1` Mentor/Xpedition ASCII file as a single symbol.
- **Import Mentor Split ZIP** imports a ZIP archive as one split symbol. Each Mentor file in the ZIP becomes one split part/unit.

### Mentor Export

- **Export Mentor Single Symbol** exports the current single symbol as one native Mentor ASCII file.
- **Export Mentor Split ZIP** exports the current split symbol as a ZIP archive. Each split part/unit is written as one native Mentor ASCII file.

### Other Imports

- **Import PINMUX CSV** imports pin data from a CSV file.

## 4. Single Symbols and Split Symbols

A **single symbol** is one graphical symbol file.

A **split symbol** is one logical component split into multiple units/parts. Split-symbol validation is performed across all units, because pin numbers must be unique across the complete component.

For Mentor/Xpedition workflows:

- Split symbols are imported and exported as `.zip` files.
- Every file inside the ZIP is one split part/unit.
- Single symbols are imported and exported as one `.sym` or `.1` file.

## 5. Grid, Sheet Format, Drawing Area, and Origin

Use **Grid inch** to define the working grid. Mentor symbols commonly use a 10 mil internal grid (`Z 10`) with pin anchors on grid coordinates.

Use **Format** to show A0/A1/A2/A3/A4/A5 sheet guides. The canvas shows the sheet/format frame and the drawing/usable region so symbols can be checked visually against the selected format.

Use **Zoom Fit** to fit the current symbol and sheet preview into the view.

### Origin behavior

Imported symbols are initially aligned to the selected origin by the **body itself**, not by pins, labels, or stray graphics. This keeps the body placement predictable.

For native Mentor/Xpedition symbols, the Wizard preserves the Mentor coordinate origin. The Mentor origin is the symbol placement origin from the `.sym/.1` file. The body may start at an offset such as `b 30 30 ...`; this is normal for Mentor symbols. Pin electrical anchors remain the most important grid points.

## 6. Creating and Editing Objects

Use the draw tools:

- **Select/Edit**: select and edit existing objects.
- **Pin L / Pin R**: create left- or right-oriented pins.
- **Text**: create plain text.
- **Line, Rect, Ellipse**: create graphic objects.

The **Selectable** dropdown limits selection to specific object types. This helps when editing dense symbols.

Objects can be moved, resized, rotated, flipped, scaled, copied, pasted, and deleted. Deleting a symbol or split part asks for confirmation because the changes are destructive.

## 7. Body Editing

The body is the main symbol container. Its size, position, style, line width, and attributes can be edited from the properties panel.

When the body moves or is resized, related pins, text, graphics, and body attributes are kept consistent with the body.

The body does not have to lie on the same visual offset as pins. For Mentor compatibility, the important electrical rule is that **pin connection points** stay on the Mentor grid.

## 8. Pin Editing

Pins can be edited from:

- the canvas
- the left pin overview
- the object tree
- the properties panel
- the Split Pin Manager

Common pin fields are:

- **Pin Number**: physical pin / ball number
- **Pin Name**: visible logical label
- **Pin Function**: functional signal description
- **Pin Type**: electrical type, e.g. `IN`, `OUT`, `BIDI/BI`, `POWER`, `GROUND`, `ANALOG`
- **Side**: left/right/top/bottom placement direction
- **Inverted**: pin inversion flag
- **Show #**, **Show Name**, **Show Function**: visibility controls

Pin Name and Pin Function are independent. If both are visible, both may be shown in the Wizard.

## 9. Pin Colors

Mentor `.sym/.1` files normally do not store RGB object colors. The Wizard therefore colors pins semantically by pin type for editing clarity:

- `IN` = blue
- `OUT` = red
- `BIDI` / `BI` = violet
- `POWER` = orange
- `GROUND` = green
- `ANALOG` = cyan
- `PASSIVE` / unknown = black

These are Wizard UI colors. Native Mentor export does not write RGB colors unless a future format extension explicitly supports it.

## 10. Split Pin Manager / Multi-Edit Pins

Open **Tools → Split Pin Manager / Multi-Edit Pins** to view and edit all pins of the current symbol or split symbol in one table.

### Table features

- Shows all pins across all split units.
- Supports marking rows for later bulk operations.
- Supports sorting by clicking column headers.
- Double-click a pin row to jump to that pin on the canvas.
- Use **Marked only** to display only marked pins.

### Embedded column filters

Filters are integrated directly into the table as the first row below the column headers.

Text columns use text filters:

- Unit
- Pin Number
- Pin Name
- Pin Function
- Type

Boolean columns use dropdown filters:

- **Inverted**: `All`, `Inverted`, `Not inverted`
- **Show #**: `All`, `Shown`, `Hidden`
- **Show Name**: `All`, `Shown`, `Hidden`
- **Show Function**: `All`, `Shown`, `Hidden`

The global filter searches across unit, pin number, pin name, pin function, type, and state. Global and column filters are combined.

Use **Clear filters** to remove all active filters.

### Bulk-edit display attributes

The bulk area at the bottom can apply changes to:

- marked pins
- currently filtered pins
- all pins

Bulk-edit fields include:

- **Show #**: `Unchanged`, `Show`, `Hide`
- **Show Name**: `Unchanged`, `Show`, `Hide`
- **Show Function**: `Unchanged`, `Show`, `Hide`
- **Inverted**: `Unchanged`, `Inverted`, `Not inverted`

### Bulk-edit Pin Function text

The Pin Function Text controls allow mass-editing of the actual Pin Function value:

- `Unchanged`: leave existing function values untouched
- `Set to text`: write the entered text to all target pins
- `Clear`: clear the function text
- `Copy from Pin Name`: copy each pin name into its pin function
- `Copy from Pin Number`: copy each pin number into its pin function

## 11. Mentor/Xpedition Import

Mentor ASCII files use records such as:

- `V` version
- `K` internal key / ID
- `|R` timestamp
- `F` symbol type
- `D` drawing bounds
- `Y`, `Z`, `i` metadata/grid/object count
- `U` symbol/body attributes
- `b` body rectangle
- `T` text
- `P` pin geometry
- `L` pin label
- `A` object/pin attributes
- `E` end marker

During import, the Wizard reads pins, pin labels, pin numbers, pin types, symbol attributes, texts, and geometry. Mentor colors are not read because they are normally not encoded in the `.sym/.1` file.

Imported Mentor split ZIPs are treated as one split symbol, with each file becoming one unit.

## 12. Mentor/Xpedition Export

The Mentor exporter writes native ASCII records in Mentor style.

For split symbols:

- one ZIP is written
- every split unit becomes one `.1`/symbol file inside the ZIP

For single symbols:

- one `.sym`/`.1` file is written

Export behavior:

- `K` ID is generated dynamically/stably from the symbol/unit name.
- `|R` timestamp is generated in Mentor-style format `H:MM:SS_M-D-YY`.
- Pin number is exported as `#=<pin number>`.
- Pin type is exported as `PINTYPE=<type>`.
- Pin label is exported as the native `L` record.
- Pin Function is additionally exported as an invisible pin attribute at the same coordinates as the pin name label:

```text
A <PinName-X> <PinName-Y> <size> <rotation> <alignment> 0 PINFUNCTION=<pin.function>
```

Additional invisible pin attributes stored on the pin model can also be exported as native `A` records.

## 13. Invisible Attributes

Mentor supports visible and invisible attributes.

- `U` records are symbol/body attributes.
- `A` records are object or pin attributes.

The Wizard uses this for metadata such as `PINFUNCTION`, pin type, pin number, and custom pin metadata. Invisible attributes can be preserved without changing the visible drawing.

## 14. Text and Attribute Anchors

Text and attributes use anchor-based placement. The green anchor point is the grid reference.

Horizontal modes:

- Left
- Center
- Right

Vertical modes:

- Upper
- Center
- Lower

The same anchor logic applies to normal text and attributes.

## 15. Alignment, Distribution, and Transformations

Multi-selection operations use anchor positions where possible so text and attributes remain grid-aligned.

Transform tools include:

- rotate clockwise/counter-clockwise
- flip horizontal / vertical
- scale up / down
- color changes for selected objects

## 16. Template Editor

Open **Tools → Edit Symbol Templates** to edit reusable templates.

The template editor supports:

- body editing
- pins
- text
- graphics
- body attributes
- copy/cut/paste/select all
- undo/redo
- grid-based placement

A save prompt appears only when the current template has actually changed. Simply selecting or viewing a template should not trigger a save prompt.

## 17. Autosave and Restore

The Wizard can restore the last working state on startup. The autosaved workspace should be stored in the user configuration area, not inside the installation ZIP. This avoids permission problems and prevents temporary session data from being shipped with releases.

Recommended paths:

- Windows: `%APPDATA%/SymbolWizard/`
- Linux: `~/.config/SymbolWizard/`
- macOS: `~/Library/Application Support/SymbolWizard/`

## 18. Validation

Use **Tools → Validate Pins** to check pin consistency.

Validation includes:

- duplicate pin numbers
- duplicate pin names
- split-symbol-wide uniqueness checks
- incomplete or inconsistent pin data

For split symbols, validation runs across all units because the complete component must have unique physical pins.

## 19. PINMUX CSV Import

Use **File → Import PINMUX CSV** to import pin data from a CSV file.

Expected columns:

```csv
Pin Name|Pin Type|Pin Function|Pin Number
VDD|POWER||1
PA0|BIDI|ADC_IN0|A1
```

Supported separators include comma, semicolon, pipe, and tab.

## 20. Keyboard Shortcuts

- **Ctrl + A**: select all canvas objects
- **Ctrl + C**: copy selected objects
- **Ctrl + X**: cut selected objects
- **Ctrl + V**: paste copied objects
- **Ctrl + Z**: undo
- **Ctrl + Y**: redo
- **Delete**: delete selected objects
- **Ctrl + S**: save current symbol JSON
- **Ctrl + Shift + S**: save all symbols JSON
- **Ctrl + O**: open library JSON
- **Ctrl + F**: zoom to fit
- **F5**: refresh canvas

## 21. Recommended Mentor Workflow

1. Import Mentor single symbol or split ZIP.
2. Check the origin and body placement.
3. Verify that pin anchors lie on the expected grid.
4. Use Split Pin Manager for filtering, marking, and bulk edits.
5. Adjust Pin Function visibility or text if needed.
6. Validate pins.
7. Export as Mentor single file or split ZIP.
8. Re-import into Mentor/Xpedition and verify pin connectivity.

## 22. About

**Editor:** Christian Hopper  
**Company:** QAVION Consulting GmbH  
**Customer:** Liebherr Electronics and Drives  
**Year:** 2026
