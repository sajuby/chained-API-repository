"""P4 GUI 冒烟测试。"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from app.core.config import ConfigManager
from app.data.database import Database
from app.gui.chat_panel import ChatPanel
from app.gui.context import AppContext
from app.gui.main_window import MainWindow
from app.gui.motion import SmoothInteractionFilter
from app.gui.reader_panel import PdfReader, TextReader
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
        pdf_reader = getattr(self, "pdf_reader", None)
        if pdf_reader is not None:
            pdf_reader.close_document()
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
        window.open_ai_side_panel(descriptor, "这是选中的内容")
        self.app.processEvents()
        self.assertFalse(window.ai_side_panel.isHidden())
        self.assertEqual(window.ai_side_panel.current_kb_id, kb.id)
        self.assertIn("这是选中的内容", window.ai_side_panel.input.toPlainText())
        window.close()

    def test_pdf_wheel_switches_page_and_zoom_changes_size(self) -> None:
        import pymupdf

        pdf_path = self.root / "pages.pdf"
        pdf = pymupdf.open()
        pdf.new_page()
        pdf.new_page()
        pdf.save(pdf_path)
        pdf.close()
        reader = PdfReader()
        self.assertTrue(reader.open(pdf_path))
        self.addCleanup(reader.close_document)
        old_page = reader.page
        old_width = reader.page_label.pixmap().width()
        wheel = QWheelEvent(
            QPointF(5, 5),
            QPointF(5, 5),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollUpdate,
            False,
        )
        self.assertTrue(reader.eventFilter(reader.scroll.viewport(), wheel))
        self.assertEqual(reader.page, old_page + 1)
        self.assertTrue(reader.eventFilter(reader.scroll.viewport(), wheel))
        self.assertEqual(reader.page, old_page + 1)
        reader.zoom_in()
        self.assertEqual(reader.zoom, 110)
        self.assertGreater(reader.page_label.pixmap().width(), old_width)
        reader.close_document()

    def test_pdf_text_selection_can_ask_ai(self) -> None:
        import pymupdf

        pdf_path = self.root / "selectable.pdf"
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text((72, 72), "Hello knowledge base", fontsize=14)
        pdf.save(pdf_path)
        pdf.close()
        reader = PdfReader()
        self.pdf_reader = reader
        self.assertTrue(reader.open(pdf_path))
        captured: list[str] = []
        reader.ask_requested.connect(captured.append)
        selected = reader._update_selection(QPointF(60, 60), QPointF(300, 100))
        text = reader.ask_selection()
        self.assertIn("knowledge", text)
        self.assertEqual(captured, [text])

    def test_empty_knowledge_base_disables_chat(self) -> None:
        repo = self.context.repository()
        try:
            kb = repo.create_kb("空知识库")
        finally:
            repo.close()
        panel = ChatPanel(self.context)
        panel.set_kb(kb.id)
        self.assertFalse(panel.input.isEnabled())
        self.assertFalse(panel.send_button.isEnabled())
        self.assertIn("暂无已索引文档", panel.status.text())

    def test_selected_text_can_ask_ai(self) -> None:
        path = self.root / "selection.md"
        path.write_text("# 标题\n这是需要询问的内容。", encoding="utf-8")
        reader = TextReader()
        self.assertTrue(reader.open(path))
        reader.browser.selectAll()
        captured: list[str] = []
        reader.ask_requested.connect(captured.append)
        text = reader.ask_selection()
        self.assertIn("需要询问的内容", text)
        self.assertEqual(captured, [text])
        reader.close_document()

    def test_button_motion_filter_animates_shadow(self) -> None:
        button = QPushButton("测试")
        button.resize(100, 32)
        button.show()
        motion = SmoothInteractionFilter(self.app)
        motion.eventFilter(button, QEvent(QEvent.Enter))
        QTest.qWait(220)
        self.assertIsNotNone(button.graphicsEffect())
        self.assertGreater(button.graphicsEffect().blurRadius(), 0)
        motion.eventFilter(button, QEvent(QEvent.Leave))
        QTest.qWait(220)
        self.assertLess(button.graphicsEffect().blurRadius(), 1)
        button.close()

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

    def test_background_host_default_is_light(self) -> None:
        host = BackgroundHost()
        host.resize(300, 200)
        self.app.processEvents()
        grabbed = host.grab().toImage()
        self.assertEqual(grabbed.pixelColor(5, 5).name(), "#fbfcff")


if __name__ == "__main__":
    unittest.main()
