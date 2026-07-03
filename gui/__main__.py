"""Entry point: python -m gui"""
import sys
import os

# Ensure parent directory is on path so gui can import species, flow, etc.
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from .mainwindow import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SPARTA DSMC Setup")
    app.setOrganizationName("CTFL")
    app.setApplicationVersion("0.1.0")

    # Dark-ish style closer to a modern scientific tool
    app.setStyle("Fusion")

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
