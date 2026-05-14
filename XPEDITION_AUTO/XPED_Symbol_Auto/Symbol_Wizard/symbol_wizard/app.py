import sys
from PySide6.QtWidgets import QApplication

from .config import APP_NAME
from .gui.main_window import SymbolEditorWindow


def run() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = SymbolEditorWindow()
    window.show()
    sys.exit(app.exec())
