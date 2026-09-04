"""GUI 应用入口。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.data.database import Database
from app.gui.context import AppContext
from app.gui.main_window import MainWindow
from app.gui.theme import GLOBAL_QSS


def run_application(
    database: Database,
    data_dir: Path,
) -> int:
    from app.core.config import ConfigManager

    app = QApplication(sys.argv)
    app.setApplicationName("本地文档知识库桌面助手")
    app.setStyle("Fusion")
    app.setStyleSheet(GLOBAL_QSS)
    config = ConfigManager(data_dir)
    context = AppContext(config, database)
    window = MainWindow(context)
    window.show()
    return app.exec()
