"""应用入口。"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def _data_dir() -> Path:
    from app.utils.paths import configured_data_dir

    source_data_dir = (
        Path(sys.executable).resolve().parent / "data"
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent / "data"
    )
    return Path(os.environ.get("LOCAL_KB_DATA_DIR", configured_data_dir() or source_data_dir))


def _write_startup_error(data_dir: Path, exc: BaseException) -> Path:
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "startup.log"
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{datetime.now().isoformat(timespec='seconds')}]\n{details}")
    return log_path


def _show_startup_error(message: str) -> None:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, "启动失败", message)
        app.processEvents()
        return
    except Exception:
        pass
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "启动失败", 0x10)
    except Exception:
        pass


def _run() -> int:
    from app import APP_NAME
    from app.core.config import ConfigManager
    from app.data.database import Database

    data_dir = _data_dir()
    config = ConfigManager(data_dir)
    database = Database(config.data_dir / "app.db")
    database.initialize()

    try:
        from app.gui.application import run_application
    except ImportError as exc:
        raise RuntimeError(
            f"{APP_NAME} 无法加载图形界面依赖。请重新安装完整运行包。\n\n{exc}"
        ) from exc

    return run_application(database, config.data_dir)


def main() -> int:
    try:
        return _run()
    except BaseException as exc:
        try:
            data_dir = _data_dir()
        except Exception:
            data_dir = Path.cwd()
        log_path = _write_startup_error(data_dir, exc)
        _show_startup_error(
            f"应用启动失败：{exc}\n\n详细日志：\n{log_path}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())