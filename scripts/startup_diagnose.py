"""Timed startup smoke test for the desktop application."""

from __future__ import annotations

import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def mark(label: str, started: float) -> float:
    now = time.perf_counter()
    print(f"{label}: {now - started:.3f}s", flush=True)
    return now


def main() -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    mark("import Qt", time.perf_counter())
    from app.core.config import ConfigManager
    from app.data.database import Database
    from app.gui.context import AppContext
    from app.gui.main_window import MainWindow
    from app.gui.motion import SmoothInteractionFilter
    from app.gui.theme import GLOBAL_QSS

    started = time.perf_counter()
    data_dir = ROOT / "data"
    config = ConfigManager(data_dir)
    mark("config", started)
    database = Database(config.data_dir / "app.db")
    database.initialize()
    mark("database", started)
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(GLOBAL_QSS)
    motion = SmoothInteractionFilter(app)
    app.installEventFilter(motion)
    mark("application", started)
    context = AppContext(config, database)
    mark("context/chroma", started)
    window = MainWindow(context)
    mark("main window", started)
    window.show()
    app.processEvents()
    mark("show", started)
    print(f"visible={window.isVisible()} title={window.windowTitle()}", flush=True)
    QTimer.singleShot(2500, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
