"""Obsidian 风格主窗口：文件侧栏 + 阅读工作区 + 上下文面板。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.gui.chat_panel import ChatPanel
from app.gui.context import AppContext
from app.core.config import AI_PROVIDERS
from app.gui.explorer import ExplorerSidebar
from app.gui.reader_panel import FileDescriptor, ReaderWorkspace
from app.gui.settings_dialog import SettingsDialog
from app.gui.theme import BackgroundHost, GLOBAL_QSS, background_stylesheet
from app.gui.workers import TaskThread


class ContextPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.title = QLabel("引用上下文")
        self.title.setStyleSheet("font-weight:700;color:#586a82;")
        self.collapse = QToolButton()
        self.collapse.setText("›")
        self.collapse.clicked.connect(self.hide)
        head = QHBoxLayout()
        head.addWidget(self.title)
        head.addStretch(1)
        head.addWidget(self.collapse)

        self.source_name = QLabel("未打开文档")
        self.source_name.setWordWrap(True)
        self.source_name.setStyleSheet("font-weight:700;color:#52627a;font-size:12px;")
        self.source_meta = QLabel("暂无来源")
        self.source_meta.setWordWrap(True)
        self.source_meta.setStyleSheet("color:#a0abba;font-size:11px;")
        self.quote = QLabel("从 AI 回答点击引用后，这里会显示命中的原文片段。")
        self.quote.setWordWrap(True)
        self.quote.setStyleSheet("color:#69758a;font-size:11px;line-height:1.6;")
        self.insight = QLabel("阅读位置会自动保存。")
        self.insight.setWordWrap(True)
        self.insight.setStyleSheet("color:#568f85;font-size:11px;")

        body = QVBoxLayout()
        body.addWidget(QLabel("当前来源"))
        body.addWidget(self.source_name)
        body.addWidget(self.source_meta)
        body.addSpacing(12)
        body.addWidget(QLabel("命中片段"))
        body.addWidget(self.quote)
        body.addSpacing(12)
        body.addWidget(QLabel("上下文"))
        body.addWidget(self.insight)
        body.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 16, 15, 12)
        layout.addLayout(head)
        layout.addLayout(body)

    def update_source(self, descriptor: FileDescriptor | None, page: int = 0) -> None:
        if descriptor:
            suffix = Path(descriptor.path).suffix.lstrip(".").upper()
            self.source_name.setText(descriptor.filename)
            self.source_meta.setText(f"{suffix} · 第 {page} 页" if page else suffix)
            self.quote.setText("这是当前正在阅读的原始文档。")
        else:
            self.source_name.setText("未打开文档")
            self.source_meta.setText("暂无来源")


class KnowledgeBaseDialog(QDialog):
    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("知识库")
        self.setMinimumWidth(360)
        self.combo = QComboBox()
        self.new_btn = QPushButton("新建")
        self.rename_btn = QPushButton("重命名")
        self.delete_btn = QPushButton("删除")
        self.select_btn = QPushButton("选择")
        self.cancel_btn = QPushButton("取消")
        self.new_btn.clicked.connect(self._new)
        self.rename_btn.clicked.connect(self._rename)
        self.delete_btn.clicked.connect(self._delete)
        self.select_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(self.new_btn)
        buttons.addWidget(self.rename_btn)
        buttons.addWidget(self.delete_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.select_btn)
        buttons.addWidget(self.cancel_btn)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("选择或管理知识库"))
        layout.addWidget(self.combo)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self) -> None:
        self.combo.clear()
        repo = self.context.repository()
        try:
            for kb in repo.list_kbs():
                self.combo.addItem(kb.name, kb.id)
        finally:
            repo.close()

    def selected_id(self) -> int | None:
        return self.combo.currentData()

    def _new(self) -> None:
        name, ok = self._ask_name()
        if not ok or not name:
            return
        repo = self.context.repository()
        try:
            repo.create_kb(name)
        except Exception as exc:
            QMessageBox.critical(self, "创建失败", str(exc))
            return
        finally:
            repo.close()
        self.refresh()

    def _rename(self) -> None:
        kb_id = self.selected_id()
        if not kb_id:
            return
        name, ok = self._ask_name("新名称")
        if not ok or not name:
            return
        repo = self.context.repository()
        try:
            repo.rename_kb(kb_id, name)
        finally:
            repo.close()
        self.refresh()

    def _delete(self) -> None:
        kb_id = self.selected_id()
        if not kb_id:
            return
        if QMessageBox.question(self, "删除知识库", "将删除全部文档、向量与对话，是否继续？") != QMessageBox.Yes:
            return
        self.context.delete_kb(kb_id)
        self.refresh()

    def _ask_name(self, title: str = "名称") -> tuple[str, bool]:
        from PySide6.QtWidgets import QInputDialog

        return QInputDialog.getText(self, title, f"{title}：")


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.setWindowTitle("本地文档知识库桌面助手")
        self.resize(1440, 860)
        self.current_kb_id: int | None = None
        self.last_document_id: int | None = None
        self._active_reader_tab: int | None = None
        self._thread: TaskThread | None = None
        self._busy = False

        self.sidebar = ExplorerSidebar(context)
        self.sidebar.document_activated.connect(self.open_document_by_id)
        self.sidebar.document_reprocess.connect(self.reprocess_document)
        self.sidebar.document_delete.connect(self.delete_document)
        self.sidebar.conversation_activated.connect(self.open_conversation)
        self.sidebar.upload_requested.connect(self.import_documents)
        self.sidebar.new_requested.connect(self.create_new_markdown)
        self.sidebar.vault_requested.connect(self.open_vault_dialog)

        self.reader = ReaderWorkspace()
        self.reader.ask_requested.connect(self.open_ai_side_panel)
        self.chat = ChatPanel(context)
        self.chat.citation_requested.connect(self.open_document_by_id)
        self.ai_side_panel = ChatPanel(context)
        self.ai_side_panel.citation_requested.connect(self.open_document_by_id)
        self.ai_side_panel.hide()
        self.ai_side_panel.setFixedWidth(360)
        self.workspace_stack = QStackedWidget()
        self.workspace_stack.addWidget(self.reader)
        self.workspace_stack.addWidget(self.chat)
        self.workspace_stack.setCurrentWidget(self.reader)

        self.model_label = QToolButton()
        self.model_label.setText(context.config.config.display_model_name)
        self.model_label.setToolTip("当前 AI 模型，点击切换")
        self.model_label.clicked.connect(self.open_settings)
        self.tier_combo = QComboBox()
        self.tier_combo.setMinimumWidth(150)
        self.tier_combo.currentIndexChanged.connect(self._tier_changed)
        topbar = QWidget()
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(18, 10, 18, 8)
        top_layout.addWidget(QLabel(context.config.data_dir.name or "本地知识库"))
        top_layout.addStretch(1)
        top_layout.addWidget(self.tier_combo)
        top_layout.addWidget(self.model_label)
        workspace_column = QWidget()
        workspace_layout = QVBoxLayout(workspace_column)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        workspace_layout.addWidget(topbar)
        workspace_layout.addWidget(self.workspace_stack, 1)

        self.context_panel = ContextPanel()
        self.context_panel.hide()

        rail = self._build_rail()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(rail)
        layout.addWidget(self.sidebar, 0)
        layout.addWidget(workspace_column, 1)
        layout.addWidget(self.ai_side_panel, 0)
        layout.addWidget(self.context_panel, 0)
        self.background_host = BackgroundHost()
        self.background_host.setLayout(layout)
        self.setCentralWidget(self.background_host)

        self._setup_state_file()
        self.refresh_kbs()
        self._apply_theme()
        self.refresh_model_selector()
        self.statusBar().showMessage("就绪")

    def _build_rail(self) -> QWidget:
        brand = QLabel("W")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet(
            "background:#ff7da8;color:white;font-weight:800;font-size:18px;"
            "border-radius:12px;min-height:38px;min-width:38px;max-width:38px;"
        )
        self.kb_btn = self._rail_button("库", "知识库")
        self.search_btn = self._rail_button("搜", "搜索文件")
        self.chat_btn = self._rail_button("聊", "对话")
        self.settings_btn = self._rail_button("设", "设置")
        self.kb_btn.clicked.connect(self.open_vault_dialog)
        self.search_btn.clicked.connect(lambda: self.sidebar.search.setFocus())
        self.chat_btn.clicked.connect(lambda: self.switch_workspace("chat"))
        self.settings_btn.clicked.connect(self.open_settings)
        self.kb_btn.setProperty("active", True)

        box = QWidget()
        box.setFixedWidth(62)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 16, 10, 12)
        layout.setSpacing(10)
        layout.addWidget(brand)
        layout.addWidget(self.kb_btn)
        layout.addWidget(self.search_btn)
        layout.addWidget(self.chat_btn)
        layout.addStretch(1)
        layout.addWidget(self.settings_btn)
        return box

    def _rail_button(self, text: str, title: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(title)
        button.setFixedSize(42, 42)
        button.setStyleSheet(
            "QToolButton { color:#8f9cb0; font-size:13px; border-radius:12px; }"
            "QToolButton:hover { background:#fff0f5; color:#ff7da8; }"
        )
        return button

    def _setup_state_file(self) -> None:
        self.state_file = self.context.config.data_dir / "ui_state.json"

    def refresh_kbs(self, keep_document: bool = False) -> None:
        repo = self.context.repository()
        try:
            kbs = repo.list_kbs()
        finally:
            repo.close()
        current = self.current_kb_id
        if current not in {kb.id for kb in kbs}:
            current = kbs[0].id if kbs else None
        self.current_kb_id = current
        if current:
            kb_name = next((kb.name for kb in kbs if kb.id == current), "")
        else:
            kb_name = ""
        self.sidebar.set_kb(current, kb_name)
        self.chat.set_kb(current)
        self.ai_side_panel.set_kb(current)
        if keep_document:
            return
        state = self._load_state()
        if state.get("kb_id") == current and state.get("doc_id"):
            self.last_document_id = state.get("doc_id")
            self.open_document_by_id(state["doc_id"], state.get("page", 1))

    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_state(self) -> None:
        data = {
            "kb_id": self.current_kb_id,
            "doc_id": self.last_document_id,
            "page": self.reader.active_page(),
        }
        try:
            self.state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def open_vault_dialog(self) -> None:
        dialog = KnowledgeBaseDialog(self.context, self)
        if dialog.exec() and dialog.selected_id():
            self.current_kb_id = dialog.selected_id()
            self.refresh_kbs()
        else:
            self.refresh_kbs()

    def import_documents(self) -> None:
        if self._busy:
            QMessageBox.information(self, "任务进行中", "请等待当前文档处理完成。")
            return
        if not self.current_kb_id:
            QMessageBox.information(self, "提示", "请先选择或创建知识库。")
            return
        paths, _filter = QFileDialog.getOpenFileNames(
            self,
            "导入文档",
            "",
            "文档 (*.pdf *.docx *.pptx *.txt *.md *.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not paths:
            return
        self.statusBar().showMessage("准备导入…")
        kb_id = self.current_kb_id
        self._run_worker(
            lambda progress: self.context.import_files(kb_id, [Path(p) for p in paths], progress),
            self._import_done,
        )

    def _import_done(self, result) -> None:
        self.statusBar().showMessage("导入完成")
        self.sidebar.refresh()
        if result:
            self.open_document_by_id(result[0].id)

    def open_document_by_id(self, document_id: int, page: int = 1) -> None:
        repo = self.context.repository()
        try:
            doc = repo.get_document(document_id)
            if not doc:
                return
            descriptor = FileDescriptor(
                id=doc.id,
                filename=doc.filename,
                path=doc.file_path,
                file_type=doc.file_type,
                status=doc.status,
                created_at=doc.created_at.strftime("%Y-%m-%d %H:%M") if doc.created_at else "",
            )
        finally:
            repo.close()
        self.last_document_id = document_id
        self.reader.open_document(descriptor, page)
        self.context_panel.update_source(descriptor, self.reader.active_page())
        self.switch_workspace("reader")
        self.context_panel.show()
        self._save_state()

    def open_conversation(self, conversation_id: int) -> None:
        self.switch_workspace("chat")
        self.chat.open_conversation(conversation_id)

    def open_ai_side_panel(self, descriptor: FileDescriptor) -> None:
        if not self.current_kb_id:
            QMessageBox.information(self, "提示", "请先创建或选择知识库。")
            return
        self.ai_side_panel.set_kb(self.current_kb_id)
        if not self.ai_side_panel.current_conversation_id:
            self.ai_side_panel.new_conversation()
        self.ai_side_panel.show()
        page = self.reader.active_page()
        prompt = f"请结合当前文档《{descriptor.filename}》"
        if page:
            prompt += f"第 {page} 页"
        prompt += "，帮我解释或整理这部分内容。"
        self.ai_side_panel.focus_question(prompt)

    def switch_workspace(self, name: str) -> None:
        if name == "chat":
            self.workspace_stack.setCurrentWidget(self.chat)
            self.chat_btn.setProperty("active", True)
        else:
            self.workspace_stack.setCurrentWidget(self.reader)
            self.chat_btn.setProperty("active", False)

    def reprocess_document(self, document_id: int) -> None:
        self.statusBar().showMessage("正在重新处理…")
        self._run_worker(
            lambda progress: self.context.reprocess(document_id, progress),
            lambda _result: self._after_change("重新处理完成"),
        )

    def delete_document(self, document_id: int) -> None:
        if QMessageBox.question(self, "删除文档", "确认删除该文档及其索引？") != QMessageBox.Yes:
            return
        try:
            self.context.delete_document(document_id)
        except Exception as exc:
            QMessageBox.critical(self, "删除失败", str(exc))
        self._after_change("已删除")

    def create_new_markdown(self) -> None:
        if not self.current_kb_id:
            QMessageBox.information(self, "提示", "请先创建知识库。")
            return
        directory = self.context.config.generated_dir / f"kb_{self.current_kb_id}"
        directory.mkdir(parents=True, exist_ok=True)
        target, _filter = QFileDialog.getSaveFileName(
            self,
            "新建 Markdown",
            str(directory / "未命名.md"),
            "Markdown (*.md)",
        )
        if not target:
            return
        path = Path(target)
        path.write_text("# 未命名文档\n\n请开始写作。\n", encoding="utf-8")
        repo = self.context.repository()
        try:
            doc = repo.add_document(
                self.current_kb_id,
                path.name,
                path,
                "md",
                path.stat().st_size,
                source_type="generated",
            )
        finally:
            repo.close()
        self.open_document_by_id(doc.id)
        self.sidebar.refresh()

    def _after_change(self, message: str) -> None:
        self.statusBar().showMessage(message, 3000)
        self.sidebar.refresh()

    def _run_worker(self, task, success) -> None:
        self._set_busy(True)
        self._thread = TaskThread(task)
        self._thread.progress.connect(lambda step, index, total: self.statusBar().showMessage(f"{step} {index}/{total}"))
        self._thread.succeeded.connect(success)
        self._thread.failed.connect(self._worker_failed)
        self._thread.finished.connect(lambda: self._set_busy(False))
        self._thread.start()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.sidebar.upload_btn.setDisabled(busy)
        self.sidebar.new_btn.setDisabled(busy)
        self.sidebar.upload_btn.setText("处理中…" if busy else "＋ 上传文件")

    def _worker_failed(self, message: str) -> None:
        self.statusBar().showMessage("处理失败")
        QMessageBox.critical(self, "处理失败", message)
        self.sidebar.refresh()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.context, self.current_kb_id, self)
        if dialog.exec():
            self.model_label.setText(self.context.config.config.display_model_name)
            self._apply_theme()
            self.refresh_model_selector()

    def refresh_model_selector(self) -> None:
        self.tier_combo.blockSignals(True)
        self.tier_combo.clear()
        cfg = self.context.config.config
        preset = AI_PROVIDERS.get(cfg.provider_id, AI_PROVIDERS["custom"])
        for tier in preset.get("tiers", []):
            self.tier_combo.addItem(f"{tier['name']} · {tier['model']}", tier["id"])
        if not preset.get("tiers"):
            self.tier_combo.addItem("自定义模型", "custom")
            self.tier_combo.setEnabled(False)
        else:
            self.tier_combo.setEnabled(True)
            current = self.tier_combo.findData(cfg.model_tier)
            if current < 0:
                current = 0
                for index, tier in enumerate(preset["tiers"]):
                    if tier["model"] == cfg.model_name:
                        current = index
                        break
            self.tier_combo.setCurrentIndex(current)
        self.tier_combo.blockSignals(False)
        self.model_label.setText(cfg.display_model_name)

    def _tier_changed(self) -> None:
        tier_id = self.tier_combo.currentData()
        if not tier_id:
            return
        cfg = self.context.config.config
        preset = AI_PROVIDERS.get(cfg.provider_id, AI_PROVIDERS["custom"])
        tier = next((t for t in preset.get("tiers", []) if t["id"] == tier_id), None)
        if not tier:
            return
        cfg.model_tier = tier_id
        cfg.model_name = tier["model"]
        if cfg.provider_id == "deepseek":
            cfg.deepseek_model = tier["model"]
        self.context.config.save()
        self.model_label.setText(cfg.display_model_name)

    def _apply_theme(self) -> None:
        cfg = self.context.config.config
        path = cfg.appearance.background_path if cfg.appearance.background_enabled else ""
        mode = cfg.appearance.background_mode
        self.background_host.set_background(path)
        self.setStyleSheet(GLOBAL_QSS + background_stylesheet(path, mode))

    def closeEvent(self, event) -> None:
        self._save_state()
        self.context.vector_store.close()
        super().closeEvent(event)
