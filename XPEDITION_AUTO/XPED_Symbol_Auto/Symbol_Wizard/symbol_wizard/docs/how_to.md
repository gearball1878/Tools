# Symbol Wizard - How To Guide

## 1. Purpose and Scope

Symbol Wizard is a grid-based editor for creating, editing, validating, importing, and exporting electronic symbols for Mentor/Xpedition-oriented workflows.

It supports:

- single symbols
- split symbols with multiple units / split parts
- reusable symbol templates
- Mentor/Xpedition ASCII import and export
- split-symbol ZIP import and export
- PINMUX CSV import
- pin validation and bulk-edit workflows
- grid-based canvas editing for BODY, pins, text, attributes, and graphics

The main design goal is a consistent editing model: symbols should remain graphically stable, electrically valid, and suitable for Mentor/Xpedition symbol generation.

---

## 2. First Orientation

### 2.1 Main window areas

The main window has three main areas.

| Area | Purpose |
|---|---|
| Left workspace | Symbol tabs, split-symbol tabs, unit/split-part tabs, pin overview tables, object tree |
| Center canvas | Graphical editing of BODY, pins, text, attributes, graphics, origin, grid, and sheet preview |
| Right properties panel | Property editing for the selected object or current multi-selection |

### 2.2 Main editing idea

Most work follows this sequence:

1. Choose or import a symbol.
2. Check grid, origin, and sheet format.
3. Edit BODY geometry.
4. Place or edit pins.
5. Edit text, attributes, and graphics.
6. Validate pins.
7. Save as Wizard JSON or export to Mentor/Xpedition.

---

## 3. Symbol Types

### 3.1 Single symbols

A single symbol is one graphical symbol definition with one main unit.

Typical examples:

- resistor
- capacitor
- diode
- small IC
- simple connector

Single symbols are imported and exported as individual `.sym` or `.1` Mentor/Xpedition files.

### 3.2 Split symbols

A split symbol is one logical component divided into multiple units or parts.

Typical examples:

- FPGA
- processor
- large connector
- multifunction device

For Mentor/Xpedition workflows:

- split import uses a ZIP archive
- each file inside the ZIP becomes one unit / split part
- split export writes one ZIP archive
- each unit is exported as one `.1` file
- validation runs across all units because physical pin numbers must be unique across the complete component

---

## 4. Coordinate, Grid, Origin, and Sheet Concepts

### 4.1 Wizard grid

The Wizard model stores geometry in grid-based model coordinates. `Grid inch` defines the base drawing grid, commonly `0.100"`.

### 4.2 Dedicated pin grid

Pins use a dedicated pin raster so that electrical anchors are always placed on a clean, predictable grid.

Default behavior:

- pin anchor points snap to the dedicated pin grid
- pin docking uses the dedicated pin grid
- pin dragging uses the dedicated pin grid
- BODY-resize redocking uses the dedicated pin grid
- Mentor/template imports normalize pin anchors to the dedicated pin grid

Recommended default:

```text
Model pin grid: 0.1 model units
At grid_inch = 0.100: 0.010 inch pin grid
```

Graphic objects are not forced onto the pin grid. This prevents arcs, coils, curves, and imported Mentor graphics from being damaged by overly coarse rounding.

### 4.3 Mentor/template graphic grid

Mentor/template graphics may use finer coordinates than the coarse Wizard edit grid. This is intentional. Coils, arcs, filters, and special symbol artwork may contain endpoints such as `2.2`, `3.7`, or `4.5` model units.

Do not round these graphics to full integer coordinates unless the symbol standard explicitly requires it. Pins, however, must remain on the dedicated pin grid.

### 4.4 Origin

The origin defines the symbol reference point used for placement and transformations.

Supported origin modes include:

- center
- top left
- top right
- bottom left
- bottom right

For imported Mentor/Xpedition symbols, the Wizard should preserve the semantic placement origin while making BODY, pins, text, attributes, and graphics editable on the canvas.

### 4.5 Sheet format

The sheet / format preview is a visual guide only. It should not automatically resize or move symbol geometry.

Supported formats include A0, A1, A2, A3, A4, and A5.

---

## 5. Canvas Object Model

### 5.1 BODY

The BODY is the main graphical container of a symbol or split part.

The BODY defines:

- position
- width and height
- line style
- line width
- color
- rotation
- BODY attributes
- RefDes placement
- BODY attribute placement

The BODY should behave consistently for all symbol sources:

- newly created Wizard symbols
- template symbols
- Mentor-imported symbols
- split-symbol units

### 5.2 Pins

Pins are electrical connection objects.

Important pin fields:

- **Pin Number**: physical pin or ball number
- **Pin Name**: visible logical pin label
- **Pin Function**: functional signal description
- **Pin Type**: electrical type such as `IN`, `OUT`, `BIDI`, `POWER`, `GROUND`, `ANALOG`
- **Side**: left, right, top, or bottom orientation
- **Inverted**: inversion marker
- **Show #**, **Show Name**, **Show Function**: visibility controls

Pin Name and Pin Function are independent. If both are visible, both may be shown in the Wizard.

### 5.3 Text and attributes

Text and attributes use anchor-based placement.

Horizontal anchor modes:

- left
- center
- right

Vertical anchor modes:

- upper
- center
- lower

The anchor point is the grid reference for alignment and distribution.

### 5.4 Graphics

Graphic objects include:

- lines
- rectangles
- ellipses / circles
- arcs / curved line graphics

Graphics should keep their original vector structure during scaling. Curves and arcs should preserve start, control, and end geometry as one coherent vector shape.

---

## 6. Ribbon and Canvas Tools

### 6.1 Draw tools

Use the draw tools to create or edit canvas objects.

| Tool | Purpose |
|---|---|
| Select/Edit | Select and edit existing objects |
| Pin | Create a pin and dock it to the BODY side nearest to the mouse position |
| Text | Create plain text |
| Line | Create a line |
| Rect | Create a rectangle |
| Ellipse | Create an ellipse or circle |

Pins are initially docked to the BODY, but docking is loose. A pin can later be moved or transformed independently where allowed.

### 6.2 Selection filter

The **Selectable** dropdown limits canvas selection to object categories:

- all
- BODY
- pins
- text
- graphics
- custom combinations

This helps when editing dense imported Mentor symbols or large split symbols.

### 6.3 Transform tools

Transform tools include:

- rotate counter-clockwise / clockwise
- flip horizontal
- flip vertical
- scale up
- scale down
- color changes for selected objects

Pins can be transformed independently from the BODY when selected alone. BODY transformations should not unintentionally rotate or mirror selected pins.

---

## 7. Creating and Editing Symbols

### 7.1 Create a new symbol

1. Choose **File → New → New Single Symbol** or **New Split Symbol**.
2. Select a template.
3. Set grid, sheet format, and origin.
4. Edit BODY, pins, attributes, text, and graphics in the canvas.
5. Validate pins.
6. Save as JSON or export as Mentor/Xpedition.

### 7.2 Add pins

1. Select the **Pin** tool.
2. Click near the BODY side where the pin should be attached.
3. The pin is docked to the nearest BODY side.
4. Edit number, name, function, type, visibility, and orientation in the properties panel or pin table.

### 7.3 Move and transform pins

Pins use loose docking:

- new pins are placed on the BODY by default
- pin anchors snap to the dedicated pin grid
- pins can be moved independently
- pins can be rotated or flipped without transforming the BODY
- loose pins should remain loose during BODY resize unless explicitly redocked

### 7.4 Edit the BODY

The BODY can be selected and edited from the canvas or properties panel.

Supported BODY edits:

- width
- height
- line style
- line width
- color
- rotation
- BODY attributes
- RefDes and attribute font settings

### 7.5 Scale graphics safely

When scaling BODY-owned graphics or selected graphic objects, the structure should be treated as vector geometry.

Scaling should preserve:

- line start and end points
- rectangle proportions
- ellipse / circle structure
- arc and curve control geometry
- curve radius where applicable
- relative pin slots on the BODY side

Canvas scaling should be based on a frozen start geometry and a target geometry. It should not cumulatively distort objects during mouse movement.

---

## 8. Properties Panel

The properties panel shows editable values for the current selection.

Typical property groups:

- BODY geometry and visual style
- BODY attributes and RefDes settings
- pin number, name, function, type, side, inversion, visibility, font, and color
- text content, font, anchor, alignment, rotation, color
- graphic shape, size, line style, line width, curve radius, rotation, color

Multi-edit is available for compatible selections such as multiple pins, multiple text objects, or multiple graphics.

---

## 9. Pin Color Model

Pins are colored semantically by pin type for editing clarity.

Default colors:

| Pin type | Color |
|---|---|
| `IN` | blue |
| `OUT` | red |
| `BIDI` / `BI` | violet |
| `POWER` | orange |
| `GROUND` | green |
| `ANALOG` | cyan |
| `PASSIVE` / unknown | black |

Changing the pin type should update:

- pin line color
- pin number font color
- pin label font color
- `PINTYPE` metadata

Mentor `.sym/.1` files normally do not store RGB object colors, so these are Wizard UI colors unless a future export extension explicitly writes color data.

---

## 10. Split Pin Manager / Multi-Edit Pins

Open **Tools → Split Pin Manager / Multi-Edit Pins** to view and edit pins across the current symbol or split symbol.

### 10.1 Table features

- shows pins across split units
- supports sorting
- supports marking rows for bulk operations
- supports double-click navigation to a pin on the canvas
- supports filtering by unit, pin number, pin name, pin function, type, and state

### 10.2 Boolean filters

Boolean columns use dropdown filters:

- **Inverted**: all, inverted, not inverted
- **Show #**: all, shown, hidden
- **Show Name**: all, shown, hidden
- **Show Function**: all, shown, hidden

### 10.3 Bulk-edit operations

Bulk edit can apply changes to:

- marked pins
- currently filtered pins
- all pins

Bulk-edit fields include:

- show / hide pin number
- show / hide pin name
- show / hide pin function
- inverted / not inverted
- set, clear, or copy Pin Function text

---

## 11. File Menu and Data Workflows

### 11.1 New

- **New Single Symbol** creates a single symbol.
- **New Split Symbol** creates a split symbol with one or more units.

### 11.2 Project / JSON

- **Open Library JSON** loads a saved Wizard library.
- **Save Current Symbol JSON** saves only the active symbol.
- **Save All Symbols JSON** saves the complete library.
- **Import Symbol JSON** imports one Wizard JSON symbol into the current library.

### 11.3 Import

- **Mentor Single Symbol (.sym/.1)** imports one Mentor/Xpedition ASCII file.
- **Mentor Split Symbol ZIP** imports a ZIP archive as one split symbol.
- **PINMUX CSV** imports pin data from a CSV file.

### 11.4 Export

- **Mentor Single/Split Symbol** exports the current symbol.
- Single symbols are exported as one Mentor file.
- Split symbols are exported as a ZIP with one file per unit.

---

## 12. Mentor/Xpedition Import

Mentor ASCII files may contain records such as:

- `V` version
- `K` internal key / ID
- `|R` timestamp
- `F` symbol type
- `D` drawing bounds
- `Y`, `Z`, `i` metadata / grid / object count
- `U` symbol or BODY attributes
- `b` BODY rectangle
- `T` text
- `P` pin geometry
- `L` pin label
- `A` object or pin attributes
- `E` end marker

During import, the Wizard reads:

- pins
- pin labels
- pin numbers
- pin types
- pin functions
- symbol attributes
- text
- BODY geometry
- visible master graphics

Imported split ZIPs are treated as one split symbol, with each Mentor file becoming one unit.

### 12.1 Mentor 0° master graphics import

The Mentor/Xpedition importer keeps visible 0° master geometry instead of reducing symbols to BODY/pin rectangles.

Supported visible primitives:

- `l` line / polyline records are imported as editable line segments
- `b` box records are imported as BODY or rectangle graphics
- `c` circle records are imported as ellipse / circle graphics
- `a` arc records are imported as curved line graphics with start / control / end geometry
- `T`, `U`, `P`, `L`, and `A` remain supported as text, attributes, pins, labels, and pin attributes

Deliberate behavior:

- `|TVRNT` orientation variants are ignored on import
- only the 0° master representation is used
- style/helper records such as `Q`, `|GRPHSTL`, `|GRPHSTL_EXT01`, `|FNTSTL`, and border metadata may be retained as raw metadata where possible

---

## 13. Mentor/Xpedition Export

The Mentor exporter writes native-style ASCII records.

For single symbols:

- one `.sym` or `.1` file is written

For split symbols:

- one ZIP archive is written
- every unit becomes one `.1` / symbol file inside the ZIP

Export behavior:

- `K` ID is generated from symbol / unit name
- `|R` timestamp is generated in Mentor style: `H:MM:SS_M-D-YY`
- pin number is exported as `#=<pin number>`
- pin type is exported as `PINTYPE=<type>`
- pin label is exported as the native `L` record
- pin function is exported as an invisible `PINFUNCTION=<value>` attribute

Example invisible pin function record:

```text
A <PinName-X> <PinName-Y> <size> <rotation> <alignment> 0 PINFUNCTION=<pin.function>
```

Additional invisible pin attributes can also be exported as native `A` records.

---

## 14. Template Editor

Open **Tools → Edit Symbol Templates** to edit reusable templates.

The Template Editor supports:

- BODY editing
- pin editing
- text editing
- graphic editing
- BODY attributes
- copy / cut / paste / select all
- undo / redo
- grid-based placement

A save prompt should appear only when the current template has actually changed. Simply selecting or viewing a template should not trigger a save prompt.

### 14.1 Template catalog path

The Template Editor loads symbol types from:

```text
Symbol_Wizard/symbol_wizard/symbol_types/symbol_types.json
```

---

## 15. PINMUX CSV Import

Use **File → Import → PINMUX CSV** to import pin data from a CSV file.

Expected columns:

```csv
Pin Name|Pin Type|Pin Function|Pin Number
VDD|POWER||1
PA0|BIDI|ADC_IN0|A1
```

Supported separators:

- comma
- semicolon
- pipe
- tab

---

## 16. Validation

Use **Tools → Validate Pins** to check pin consistency.

Validation includes:

- duplicate pin numbers
- duplicate pin names
- missing pin numbers
- missing pin names
- split-symbol-wide uniqueness checks
- incomplete or inconsistent pin data

For split symbols, validation runs across all units because the complete component must have unique physical pins.

---

## 17. Recommended Workflows

### 17.1 Create a Wizard symbol

1. Create a new symbol from a template.
2. Set grid, sheet format, and origin.
3. Add or edit BODY geometry.
4. Add pins.
5. Assign pin numbers, names, functions, and types.
6. Validate pins.
7. Save as JSON.
8. Export to Mentor/Xpedition if required.

### 17.2 Import and clean a Mentor symbol

1. Import a Mentor `.sym`, `.1`, or split ZIP.
2. Check that pin anchors are on the dedicated pin grid.
3. Check the BODY origin.
4. Verify visible graphics, especially arcs and curves.
5. Use Split Pin Manager for large pin sets.
6. Validate pins.
7. Export and re-import into Mentor/Xpedition for verification.

### 17.3 Large split-symbol workflow

1. Import or create the split symbol.
2. Use split tabs to navigate parts.
3. Use Split Pin Manager for global pin review.
4. Filter or mark pins for bulk editing.
5. Validate across all units.
6. Export as split ZIP.

---

## 18. Autosave and Restore

Symbol Wizard restores the last working state on startup when an autosave exists.

Recommended autosave locations:

- Windows: `%APPDATA%/SymbolWizard/`
- Linux: `~/.config/SymbolWizard/`
- macOS: `~/Library/Application Support/SymbolWizard/`

Older builds may use:

```text
C:\Users\<USER>\.symbol_wizard_autosave.json
```

Autosave data should not be shipped inside release ZIP files.

---

## 19. Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl + A | Select all canvas objects |
| Ctrl + C | Copy selected objects |
| Ctrl + X | Cut selected objects |
| Ctrl + V | Paste copied objects |
| Ctrl + Z | Undo |
| Ctrl + Y | Redo |
| Delete | Delete selected objects |
| Ctrl + S | Save current symbol JSON |
| Ctrl + Shift + S | Save all symbols JSON |
| Ctrl + O | Open library JSON |
| Ctrl + F | Zoom to fit symbol |
| F5 | Refresh canvas |

---

## 20. Documentation Source

This file is the single source of truth for the in-application **Help → How To** dialog.

The file is located at:

```text
Symbol_Wizard/symbol_wizard/docs/how_to.md
```

The top-level `README.md` should only act as an index and should refer to this document instead of duplicating it.

---

## 21. About

**Editor:** Christian Hopper  
**Company:** QAVION Consulting GmbH  
**Customer:** Liebherr Electronics and Drives  
**Year:** 2026
