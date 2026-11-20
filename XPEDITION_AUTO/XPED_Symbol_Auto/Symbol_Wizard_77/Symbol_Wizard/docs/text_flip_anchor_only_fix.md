# Text flip handling

Flip operations now keep every text glyph readable.  Horizontal and vertical
mirror commands move the text grid anchor and alignment, but they no longer
apply negative `scale_x` or `scale_y` to plain text, body attributes, pin labels,
pin numbers, or pin-owned attributes.

This matches the requested Symbol Wizard/Xpedition behavior: text is never drawn
mirrored; only the anchor follows the flipped BODY/group geometry.
