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


def save_symbol_type_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SYMBOL_TYPES_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
