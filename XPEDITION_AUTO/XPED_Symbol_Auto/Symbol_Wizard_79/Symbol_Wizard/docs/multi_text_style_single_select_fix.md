# Multi text style and single-select fix

- Multi-edit text style controls now use tri-state checkboxes for Bold, Italic and Underline, matching the Show Pin Attribute pattern.
- Clicking one object in an existing multi-selection now collapses the selection to that object for BODY, PIN, TEXT and GRAPHIC items.
- The single-select wrapper is installed after the canonical item compatibility methods, so later legacy mouse handlers cannot override it.
