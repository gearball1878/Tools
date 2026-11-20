# Attribute Profile Manager - SymbolLibs seed profiles

The Attribute Profile Manager now includes a bundled profile seed derived from the uploaded `SymbolLibs.zip`.

Scan summary:

- 3,026 Mentor symbol files scanned
- 3,026 BODY records evaluated
- 45 PartType profiles derived from library folders
- 9 Core BODY attributes derived / protected

Core BODY attributes are kept only in the Core section and are removed from PartType-specific profiles. PartType-specific profiles now keep the remaining attributes found for each library folder, for example `TYPE`, `TYP`, `VOLTAGE`, `FREQUENCE`, `COLOUR`, `SLOT`, `SLOT1`, `SLOT2`, `PRESSURE`, and similar component-class metadata.

Use **Derive profiles from library** in the Attribute Profile Manager to merge these profiles into the current project defaults.
