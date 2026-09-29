"""文档原文阅读工作区。"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QAction, QColor, QImage, QPainter, QPixmap
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class FileDescriptor:
    id: int
    filename: str
    path: str
    file_type: str
    status: str = "success"
    created_at: str = ""

    @property
    def display_type(self) -> str:
        return self.file_type or Path(self.filename).suffix.lstrip(".").lower()


class _PdfPage(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.selection_rects: list[QRectF] = []
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumSize(200, 200)
        self.setMouseTracking(True)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.selection_rects:
            return
        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(110, 156, 255, 75))
        for rect in self.selection_rects:
            painter.drawRect(rect)


class PdfReader(QWidget):
    ask_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.path: Path | None = None
        self.page_count = 0
        self.page = 1
        self.zoom = 100
        self._last_page_wheel = 0.0
        self._selection_start = None
        self._selected_text = ""
        self._words: list[tuple[object, str]] = []
        self._doc = None

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.page_label = _PdfPage()
        self.page_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.page_label.customContextMenuRequested.connect(self._show_context_menu)
        self.scroll.viewport().installEventFilter(self)
        self.page_label.installEventFilter(self)
        self.scroll.setWidget(self.page_label)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

    def open(self, path: Path, page: int = 1, zoom: int = 100) -> bool:
        import pymupdf

        try:
            doc = pymupdf.open(path)
        except Exception:
            return False
        if self._doc is not None:
            try:
                self._doc.close()
            except Exception:
                pass
        self._doc = doc
        self.path = path
        self.page_count = doc.page_count
        self.page = max(1, min(page, self.page_count))
        self.zoom = max(60, min(180, zoom))
        self._render()
        return True

    def _render(self) -> None:
        if self._doc is None or self.page_count == 0:
            self.page_label.clear()
            return
        import pymupdf

        scale = self.zoom / 100
        page = self._doc.load_page(self.page - 1)
        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(image)
        self._words = [(pymupdf.Rect(word[:4]), str(word[4])) for word in page.get_text("words")]
        self._clear_selection()
        self.page_label.setPixmap(pixmap)
        self.page_label.resize(pixmap.size())
        self.scroll.verticalScrollBar().setValue(0)

    def next_page(self) -> None:
        if self.page < self.page_count:
            self.page += 1
            self._render()

    def previous_page(self) -> None:
        if self.page > 1:
            self.page -= 1
            self._render()

    def set_page(self, page: int) -> None:
        if 1 <= page <= self.page_count:
            self.page = page
            self._render()

    def zoom_in(self) -> None:
        self.zoom = min(180, self.zoom + 10)
        self._render()

    def zoom_out(self) -> None:
        self.zoom = max(60, self.zoom - 10)
        self._render()

    def reset_zoom(self) -> None:
        self.zoom = 100
        self._render()

    def search_text(self, query: str) -> tuple[int, bool]:
        if not self._doc or not query:
            return self.page, False
        start = self.page - 1
        for offset in range(self.page_count):
            index = (start + offset) % self.page_count
            page = self._doc.load_page(index)
            if page.search_for(query):
                self.page = index + 1
                self._render()
                return self.page, True
        return self.page, False

    def eventFilter(self, watched, event) -> bool:
        if watched is self.page_label and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self._selection_start = event.position()
                self._update_selection(event.position(), event.position())
                return True
        if watched is self.page_label and event.type() == QEvent.MouseMove and self._selection_start is not None:
            if event.buttons() & Qt.LeftButton:
                self._update_selection(self._selection_start, event.position())
                return True
        if watched is self.page_label and event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.LeftButton and self._selection_start is not None:
                self._update_selection(self._selection_start, event.position())
                self._selection_start = None
                return True
        if event.type() == QEvent.Wheel and watched in {self.scroll.viewport(), self.page_label}:
            delta = event.angleDelta().y() or event.pixelDelta().y()
            if delta:
                if event.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
                    if delta > 0:
                        self.zoom_in()
                    else:
                        self.zoom_out()
                else:
                    now = time.monotonic()
                    if now - self._last_page_wheel >= 0.18:
                        self._last_page_wheel = now
                        if delta > 0:
                            self.previous_page()
                        else:
                            self.next_page()
                return True
        return super().eventFilter(watched, event)

    def _update_selection(self, start, end) -> None:
        if self._doc is None:
            return
        scale = self.zoom / 100
        x1, x2 = sorted((start.x(), end.x()))
        y1, y2 = sorted((start.y(), end.y()))
        selection_rect = (x1 / scale, y1 / scale, x2 / scale, y2 / scale)
        words: list[str] = []
        rects: list[QRectF] = []
        for word_rect, word in self._words:
            if word_rect.intersects(selection_rect):
                words.append(word)
                rects.append(
                    QRectF(
                        word_rect.x0 * scale,
                        word_rect.y0 * scale,
                        (word_rect.x1 - word_rect.x0) * scale,
                        (word_rect.y1 - word_rect.y0) * scale,
                    )
                )
        self._selected_text = " ".join(words).strip()
        self.page_label.selection_rects = rects
        self.page_label.update()

    def _clear_selection(self) -> None:
        self._selected_text = ""
        self.page_label.selection_rects = []
        self.page_label.update()

    def _show_context_menu(self, position) -> None:
        menu = QMenu(self)
        ask_action = menu.addAction("询问 AI")
        copy_action = menu.addAction("复制选中内容" if self._selected_text else "复制本页文字")
        clear_action = menu.addAction("清除选择")
        clear_action.setEnabled(bool(self._selected_text))
        selected = menu.exec(self.page_label.mapToGlobal(position))
        if selected == ask_action:
            self.ask_selection()
        elif selected == copy_action:
            QApplication.clipboard().setText(self._selected_text or self.page_text())
        elif selected == clear_action:
            self._clear_selection()

    def ask_selection(self) -> str:
        text = self._selected_text or self.page_text()[:5000]
        if text:
            self.ask_requested.emit(text)
        return text

    def ask_current_page(self) -> str:
        text = self.page_text()
        if text:
            self.ask_requested.emit(text[:5000])
        return text

    def page_text(self) -> str:
        if not self._doc or self.page < 1:
            return ""
        try:
            return self._doc.load_page(self.page - 1).get_text("text").strip()
        except Exception:
            return ""

    def close_document(self) -> None:
        if self._doc is not None:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None


class TextReader(QWidget):
    ask_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.path: Path | None = None
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setContextMenuPolicy(Qt.CustomContextMenu)
        self.browser.customContextMenuRequested.connect(self._show_context_menu)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.browser)

    def open(self, path: Path, _page: int = 1, _zoom: int = 100) -> bool:
        try:
            suffix = path.suffix.lower()
            if suffix in {".docx", ".pptx"}:
                from app.core.document_parser import DocumentParser

                parsed = DocumentParser().parse(path)
                text = "\n\n".join(
                    f"【第{page.page_number}页】\n{page.text}"
                    for page in parsed.pages
                    if page.text
                )
            else:
                text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return False
        self.path = path
        if path.suffix.lower() == ".md":
            import markdown

            html_body = markdown.markdown(text, extensions=["fenced_code", "tables"])
        else:
            import html

            html_body = f"<pre>{html.escape(text)}</pre>"
        self.browser.setHtml(html_body)
        return True

    def search_text(self, query: str) -> tuple[int, bool]:
        return 1, bool(query and query.lower() in self.browser.toPlainText().lower())

    def close_document(self) -> None:
        self.browser.clear()

    def _show_context_menu(self, position) -> None:
        menu = self.browser.createStandardContextMenu()
        menu.addSeparator()
        ask_action = QAction("询问 AI", menu)
        ask_action.setEnabled(bool(self.browser.textCursor().selectedText().strip()))
        menu.addAction(ask_action)
        selected = menu.exec(self.browser.mapToGlobal(position))
        if selected == ask_action:
            self.ask_selection()

    def ask_selection(self) -> str:
        text = self.browser.textCursor().selectedText().replace("\u2029", "\n").strip()
        if text:
            self.ask_requested.emit(text)
        return text


class ImageReader(QWidget):
    ask_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.path: Path | None = None
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.label.customContextMenuRequested.connect(self._show_context_menu)
        self.zoom = 100
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.label)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

    def open(self, path: Path, _page: int = 1, _zoom: int = 100) -> bool:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return False
        self.path = path
        self._pixmap = pixmap
        self.zoom = 100
        self._apply()
        return True

    def _apply(self) -> None:
        scale = self.zoom / 100
        scaled = self._pixmap.scaled(
            int(self._pixmap.width() * scale),
            int(self._pixmap.height() * scale),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.label.setPixmap(scaled)

    def zoom_in(self) -> None:
        self.zoom = min(240, self.zoom + 20)
        self._apply()

    def zoom_out(self) -> None:
        self.zoom = max(50, self.zoom - 20)
        self._apply()

    def reset_zoom(self) -> None:
        self.zoom = 100
        self._apply()

    def search_text(self, _query: str) -> tuple[int, bool]:
        return 1, False

    def close_document(self) -> None:
        self.label.clear()

    def _show_context_menu(self, position) -> None:
        menu = QMenu(self)
        ask_action = menu.addAction("询问 AI 关于此图片")
        selected = menu.exec(self.label.mapToGlobal(position))
        if selected == ask_action:
            self.ask_requested.emit(f"请分析图片文件：{self.path.name if self.path else ''}")


class ReaderWorkspace(QWidget):
    ask_requested = Signal(object, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.descriptors: dict[int, FileDescriptor] = {}
        self.readers: dict[int, QWidget] = {}

        self.title = QLabel("选择左侧文档开始阅读")
        self.title.setStyleSheet("font-size:18px;font-weight:700;color:#334259;")
        self.subtitle = QLabel("上传文件后会在侧栏显示，点击即可直接阅读")
        self.subtitle.setStyleSheet("color:#8a97a8;font-size:11px;")
        self.save_btn = QToolButton()
        self.save_btn.setText("另存为")
        self.save_btn.clicked.connect(self.save_current_copy)
        self.ask_btn = QToolButton()
        self.ask_btn.setText("问 AI")
        self.ask_btn.clicked.connect(self._request_ai)
        header_row = QHBoxLayout()
        header_row.addWidget(self.title, 1)
        header_row.addWidget(self.ask_btn)
        header_row.addWidget(self.save_btn)
        sub_row = QHBoxLayout()
        sub_row.addWidget(self.subtitle)
        sub_row.addStretch(1)
        sub_row.addWidget(QLabel("已自动保存"))

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        self.toolbar = QHBoxLayout()
        self.prev_btn = QToolButton(); self.prev_btn.setText("‹")
        self.next_btn = QToolButton(); self.next_btn.setText("›")
        self.prev_btn.setToolTip("上一页")
        self.next_btn.setToolTip("下一页")
        self.page_input = QLineEdit()
        self.page_input.setFixedWidth(48)
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_label = QLabel("/ 0")
        self.zoom_out_btn = QToolButton(); self.zoom_out_btn.setText("−")
        self.zoom_label = QLabel("100%")
        self.zoom_in_btn = QToolButton(); self.zoom_in_btn.setText("＋")
        self.search_btn = QToolButton(); self.search_btn.setText("搜索")
        self.search_btn.setToolTip("在原文中搜索")
        self.prev_btn.clicked.connect(self._previous)
        self.next_btn.clicked.connect(self._next)
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        self.search_btn.clicked.connect(self._search)
        self.page_input.returnPressed.connect(self._jump_page)

        self.toolbar.addWidget(self.prev_btn)
        self.toolbar.addWidget(self.next_btn)
        self.toolbar.addWidget(self.page_input)
        self.toolbar.addWidget(self.page_label)
        self.toolbar.addStretch(1)
        self.toolbar.addWidget(self.zoom_out_btn)
        self.toolbar.addWidget(self.zoom_label)
        self.toolbar.addWidget(self.zoom_in_btn)
        self.toolbar.addWidget(self.search_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 8)
        layout.addLayout(header_row)
        layout.addLayout(sub_row)
        layout.addWidget(self.tabs, 1)
        layout.addLayout(self.toolbar)
        self.current_id: int | None = None

    def open_document(self, descriptor: FileDescriptor, page: int = 1) -> None:
        self.descriptors[descriptor.id] = descriptor
        if descriptor.id in self.readers:
            self.tabs.setCurrentIndex(self.tabs.indexOf(self.readers[descriptor.id]))
        else:
            reader = self._make_reader(descriptor)
            suffix = Path(descriptor.path).suffix.lower()
            page_count = 1
            if suffix == ".pdf":
                ok = reader.open(Path(descriptor.path), page)
                page_count = reader.page_count
            else:
                ok = reader.open(Path(descriptor.path))
            if not ok:
                QMessageBox.warning(self, "无法打开", f"无法阅读文件：{descriptor.filename}")
                return
            if hasattr(reader, "ask_requested"):
                reader.ask_requested.connect(
                    lambda text, document_id=descriptor.id: self._reader_ask_requested(document_id, text)
                )
            self.readers[descriptor.id] = reader
            tab = self.tabs.addTab(reader, descriptor.filename)
            self.tabs.setTabToolTip(tab, descriptor.path)
            self.tabs.setCurrentIndex(tab)
            self.current_id = descriptor.id
            self._sync_header(page_count)
            return
        self.current_id = descriptor.id
        reader = self.readers[descriptor.id]
        page_count = getattr(reader, "page_count", 1) or 1
        if isinstance(reader, PdfReader):
            reader.set_page(page)
        self._sync_header(page_count)

    def _make_reader(self, descriptor: FileDescriptor) -> QWidget:
        suffix = Path(descriptor.path).suffix.lower()
        if suffix == ".pdf":
            return PdfReader()
        if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
            return ImageReader()
        return TextReader()

    def close_tab(self, index: int) -> None:
        widget = self.tabs.widget(index)
        for doc_id, reader in list(self.readers.items()):
            if reader is widget:
                reader.close_document()
                del self.readers[doc_id]
                break
        self.tabs.removeTab(index)
        widget.deleteLater()
        self.current_id = None
        self._sync_header(0)

    def active_descriptor(self) -> FileDescriptor | None:
        return self.descriptors.get(self.current_id)

    def active_page(self) -> int:
        reader = self.readers.get(self.current_id)
        return int(getattr(reader, "page", 1) or 1)

    def save_current_copy(self) -> None:
        descriptor = self.active_descriptor()
        if not descriptor:
            QMessageBox.information(self, "提示", "当前没有可保存的原文。")
            return
        target, _filter = QFileDialog.getSaveFileName(
            self,
            "另存为原文",
            descriptor.filename,
            "所有文件 (*.*)",
        )
        if target:
            shutil.copy2(descriptor.path, target)
            QMessageBox.information(self, "保存完成", f"原文已保存到：\n{target}")

    def _request_ai(self) -> None:
        descriptor = self.active_descriptor()
        if not descriptor:
            QMessageBox.information(self, "提示", "请先打开一份文档。")
            return
        self.ask_requested.emit(descriptor, "")

    def _reader_ask_requested(self, document_id: int, text: str) -> None:
        descriptor = self.descriptors.get(document_id)
        if descriptor:
            self.ask_requested.emit(descriptor, text)

    def _current_reader(self):
        return self.readers.get(self.current_id)

    def _previous(self) -> None:
        reader = self._current_reader()
        if isinstance(reader, PdfReader):
            reader.previous_page()
        self._sync_header()

    def _next(self) -> None:
        reader = self._current_reader()
        if isinstance(reader, PdfReader):
            reader.next_page()
        self._sync_header()

    def _zoom_out(self) -> None:
        reader = self._current_reader()
        if reader:
            reader.zoom_out()
        self._sync_header()

    def _zoom_in(self) -> None:
        reader = self._current_reader()
        if reader:
            reader.zoom_in()
        self._sync_header()

    def _jump_page(self) -> None:
        reader = self._current_reader()
        if isinstance(reader, PdfReader):
            try:
                reader.set_page(int(self.page_input.text()))
            except ValueError:
                pass
        self._sync_header()

    def _search(self) -> None:
        reader = self._current_reader()
        if not reader:
            return
        query, ok = QInputDialog.getText(self, "搜索原文", "关键词：")
        if not ok or not query:
            return
        page, found = reader.search_text(query)
        if not found:
            QMessageBox.information(self, "搜索结果", "未找到相关内容。")
        else:
            QMessageBox.information(self, "搜索结果", f"已定位到第 {page} 页。")
        self._sync_header()

    def _sync_header(self, page_count: int | None = None) -> None:
        descriptor = self.active_descriptor()
        reader = self._current_reader()
        if descriptor:
            self.title.setText(descriptor.filename)
            suffix = Path(descriptor.path).suffix.lstrip(".").upper()
            self.subtitle.setText(f"{suffix} · {descriptor.status} · 已索引")
        count = page_count or int(getattr(reader, "page_count", 0) or 0)
        current = int(getattr(reader, "page", 1) or 1)
        self.page_input.setText(str(current) if count else "-")
        self.page_label.setText(f"/ {count}")
        self.zoom_label.setText(f"{int(getattr(reader, 'zoom', 100) or 100)}%")
