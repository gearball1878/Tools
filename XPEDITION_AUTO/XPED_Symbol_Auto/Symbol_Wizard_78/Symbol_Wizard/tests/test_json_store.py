from pathlib import Path

from symbol_wizard.io.json_store import load_library, save_library
from symbol_wizard.models.document import LibraryModel, SymbolModel


def test_library_roundtrip(tmp_path: Path):
    library = LibraryModel(symbols=[SymbolModel(name="Example")], current_symbol_index=0)
    target = tmp_path / "library.json"

    save_library(target, library)
    loaded = load_library(target)

    assert loaded.current_symbol_index == 0
    assert len(loaded.symbols) == 1
    assert loaded.symbols[0].name == "Example"
