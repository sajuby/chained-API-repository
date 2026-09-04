"""生成主界面预览截图，用于本地视觉检查。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os = sys.modules["os"]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.config import ConfigManager
from app.data.database import Database
from app.gui.context import AppContext
from app.gui.main_window import MainWindow


def main() -> int:
    app = QApplication([])
    root = Path(__file__).resolve().parents[1] / "data" / "_ui_preview"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    config = ConfigManager(root)
    database = Database(root / "app.db")
    database.initialize()
    context = AppContext(config, database)
    repo = context.repository()
    try:
        kb = repo.create_kb("机器学习课程")
        source = root / "反向传播.md"
        source.write_text(
            "# 反向传播\n\n反向传播通过链式法则计算梯度。\n\n- 前向传播\n- 损失计算\n- 反向更新",
            encoding="utf-8",
        )
        doc = repo.add_document(kb.id, source.name, source, "md", source.stat().st_size)
    finally:
        repo.close()

    window = MainWindow(context)
    window.show()
    window.refresh_kbs()
    window.open_document_by_id(doc.id)
    app.processEvents()
    window.grab().save(str(root.parent / "ui_preview.png"))
    window.close()
    context.vector_store.close()
    database.close()
    shutil.rmtree(root, ignore_errors=True)
    print("preview saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
