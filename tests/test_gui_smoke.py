"""P4 GUI 冒烟测试。"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.config import ConfigManager
from app.data.database import Database
from app.gui.context import AppContext
from app.gui.main_window import MainWindow
from app.gui.theme import BackgroundHost


class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.config = ConfigManager(self.root)
        self.database = Database(self.root / "app.db")
        self.database.initialize()
        self.context = AppContext(self.config, self.database)

    def tearDown(self) -> None:
        self.context.vector_store.close()
        self.database.close()
        self.temp_dir.cleanup()

    def test_main_window_opens_with_empty_database(self) -> None:
        window = MainWindow(self.context)
        window.show()
        self.app.processEvents()
        self.assertEqual(window.windowTitle(), "本地文档知识库桌面助手")
        window.close()

    def test_document_opens_in_reader_workspace(self) -> None:
        repo = self.context.repository()
        try:
            kb = repo.create_kb("阅读测试库")
            source = self.root / "课程.md"
            source.write_text("# 课程\n神经网络与机器学习。", encoding="utf-8")
            doc = repo.add_document(
                kb.id,
                source.name,
                source,
                "md",
                source.stat().st_size,
            )
        finally:
            repo.close()
        window = MainWindow(self.context)
        window.show()
        window.refresh_kbs()
        window.open_document_by_id(doc.id)
        self.app.processEvents()
        self.assertEqual(window.reader.tabs.count(), 1)
        self.assertIsNotNone(window.reader.active_descriptor())
        window.close()

    def test_ask_ai_opens_side_panel(self) -> None:
        repo = self.context.repository()
        try:
            kb = repo.create_kb("侧栏问答测试")
            source = self.root / "论文.md"
            source.write_text("# 论文\n研究背景与动机。", encoding="utf-8")
            doc = repo.add_document(kb.id, source.name, source, "md", source.stat().st_size)
        finally:
            repo.close()
        window = MainWindow(self.context)
        window.show()
        window.refresh_kbs()
        window.open_document_by_id(doc.id)
        descriptor = window.reader.active_descriptor()
        window.open_ai_side_panel(descriptor)
        self.app.processEvents()
        self.assertFalse(window.ai_side_panel.isHidden())
        self.assertEqual(window.ai_side_panel.current_kb_id, kb.id)
        window.close()

    def test_background_host_paints_full_cover(self) -> None:
        from PySide6.QtGui import QImage, QPainter

        image = QImage(40, 40, QImage.Format_RGB32)
        image.fill(0xFFC0CB)
        image_path = self.root / "bg.png"
        image.save(str(image_path))
        host = BackgroundHost()
        host.resize(300, 200)
        host.set_background(str(image_path))
        self.app.processEvents()
        grabbed = host.grab().toImage()
        self.assertEqual(grabbed.pixelColor(5, 5).name(), "#ffc0cb")


if __name__ == "__main__":
    unittest.main()
