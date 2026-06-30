"""ASUS Control Desktop GUI package."""

from __future__ import annotations

import os
import sys
from PySide6.QtCore import QTranslator, QLocale, QLibraryInfo, Qt
from PySide6.QtWidgets import QWidget, QApplication
from .main_window import MainWindow

def run_gui() -> int:
    """Launch the PySide6 Desktop GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("ASUS Control")
    app.setApplicationVersion("0.2.0")
    

    # 1. Load system Qt translations (for standard dialog buttons like OK, Cancel)
    qt_translator = QTranslator()
    translations_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(QLocale.system(), "qt", "_", translations_dir):
        app.installTranslator(qt_translator)

    # 2. Load application-specific translations from the translations/ folder
    app_translator = QTranslator()
    app_translations_dir = os.path.join(os.path.dirname(__file__), "translations")
    if app_translator.load(QLocale.system(), "asus-control", "_", app_translations_dir):
        app.installTranslator(app_translator)

    window = MainWindow()
    window.show()
    return app.exec()
