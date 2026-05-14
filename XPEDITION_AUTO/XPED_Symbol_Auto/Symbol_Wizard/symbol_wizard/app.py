import sys
from PySide6.QtWidgets import QApplication
from symbol_wizard.gui.main_window import MainWindow

def main():
    app=QApplication(sys.argv); w=MainWindow(); w.show(); sys.exit(app.exec())
