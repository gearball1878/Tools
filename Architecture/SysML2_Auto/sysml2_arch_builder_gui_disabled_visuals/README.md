# SysML2 Architecture Builder Wizard

Start:
```bash
pip install -r requirements.txt
python main.py --gui
```

Demo:
```bash
python main.py --demo --out out
```

Changes:
- Wizard signal preview with exact BusContent names
- Manual actions moved to fallback area
- Host is unique per domain for architecture elements
- Port type, side override, and power direction can be changed via right-click workflows
- Power has `powerDirection` attribute: `PowerIn` / `PowerOut`
- Port drawing order: Power, Control/Status, Interface/Memory, Analog
- Default port placement:
  - PowerIn left, PowerOut right
  - Inputs left, outputs right
  - Interface/Memory/Bidi right unless overridden
  - Analog left unless overridden
