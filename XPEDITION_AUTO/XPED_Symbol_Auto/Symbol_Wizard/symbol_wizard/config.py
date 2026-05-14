PX_PER_INCH = 960.0
APP_NAME = "Symbol Wizard"


from pathlib import Path
import json

CONFIG_DIR = Path(__file__).resolve().parent / "data"
SYMBOL_TYPES_FILE = CONFIG_DIR / "symbol_types.json"

def load_symbol_type_config():
    try:
        return json.loads(SYMBOL_TYPES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"global_attributes": ["RefDes", "Package", "Order Code", "Value"], "types": {}}
