"""GUI 应用入口。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from app.data.database import Database
from app.gui.context import AppContext
from app.gui.main_window import MainWindow
from app.gui.motion import SmoothInteractionFilter
from app.gui.theme import GLOBAL_QSS


def run_application(
    database: Database,
    data_dir: Path,
) -> int:
    from app.core.config import ConfigManager

    app = QApplication(sys.argv)
    app.setApplicationName("本地文档知识库桌面助手")
    app.setStyle("Fusion")
    palette = app.palette()
    palette.setColor(QPalette.Window, QColor("#fbfcff"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.Text, QColor("#27354a"))
    app.setPalette(palette)
    app.setStyleSheet(GLOBAL_QSS)
    app._smooth_interaction = SmoothInteractionFilter(app)
    app.installEventFilter(app._smooth_interaction)
    config = ConfigManager(data_dir)
    context = AppContext(config, database)
    window = MainWindow(context)
    window.show()
    return app.exec()
