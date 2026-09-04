"""应用入口。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    from app import APP_NAME
    from app.core.config import ConfigManager
    from app.data.database import Database
    from app.utils.paths import configured_data_dir

    source_data_dir = (
        Path(sys.executable).resolve().parent / "data"
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent / "data"
    )
    default_data_dir = configured_data_dir() or source_data_dir
    data_dir = Path(os.environ.get("LOCAL_KB_DATA_DIR", default_data_dir))
    config = ConfigManager(data_dir)
    database = Database(config.data_dir / "app.db")
    database.initialize()

    # GUI 依赖缺失时给出明确提示，便于继续开发非图形部分。
    try:
        from app.gui.application import run_application
    except ImportError as exc:
        print(f"[{APP_NAME}] 无法启动图形界面：{exc}", file=sys.stderr)
        print("请先执行: python -m pip install -r requirements.txt", file=sys.stderr)
        return 1

    return run_application(database, config.data_dir)


if __name__ == "__main__":
    raise SystemExit(main())
