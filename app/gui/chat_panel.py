"""对话面板。"""

from __future__ import annotations

import html
import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.gui.context import AppContext
from app.gui.workers import TaskThread


class ChatPanel(QWidget):
    citation_requested = Signal(int, int)
    close_requested = Signal()

    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.current_kb_id: int | None = None
        self.current_conversation_id: int | None = None
        self.thread: TaskThread | None = None

        self.title = QLabel("对话")
        self.title.setStyleSheet("font-size:18px;font-weight:700;color:#334259;")
        self.back_button = QPushButton("返回")
        self.back_button.clicked.connect(self.close_requested)
        self.conversations = QComboBox()
        self.conversations.setMinimumWidth(180)
        self.conversations.currentIndexChanged.connect(self._conversation_selected)
        new_btn = QPushButton("新建")
        delete_btn = QPushButton("删除")
        export_btn = QPushButton("导出 MD")
        generate_btn = QPushButton("AI 生成文档")
        new_btn.clicked.connect(self.new_conversation)
        delete_btn.clicked.connect(self.delete_conversation)
        export_btn.clicked.connect(self.export_markdown)
        generate_btn.clicked.connect(self.generate_document)

        top = QHBoxLayout()
        top.addWidget(self.back_button)
        top.addWidget(self.title)
        top.addWidget(self.conversations, 1)
        top.addWidget(new_btn)
        top.addWidget(delete_btn)
        top.addWidget(generate_btn)
        top.addWidget(export_btn)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.anchorClicked.connect(self._anchor_clicked)
        self.input = QTextEdit()
        self.input.setPlaceholderText("输入问题，Enter 发送；Shift+Enter 换行")
        self.input.setFixedHeight(90)
        self.send_button = QPushButton("发送")
        self.send_button.setFixedWidth(90)
        self.send_button.clicked.connect(self.send)
        bottom = QHBoxLayout()
        bottom.addWidget(self.input, 1)
        bottom.addWidget(self.send_button, 0, Qt.AlignBottom)
        self.status = QLabel("就绪")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 10)
        layout.addLayout(top)
        layout.addWidget(self.browser, 1)
        layout.addLayout(bottom)
        layout.addWidget(self.status)

    def set_kb(self, kb_id: int | None) -> None:
        self.current_kb_id = kb_id
        self._refresh_conversations()

    def open_conversation(self, conversation_id: int) -> None:
        index = self.conversations.findData(conversation_id)
        if index >= 0:
            self.conversations.setCurrentIndex(index)

    def focus_question(self, text: str = "") -> None:
        if text:
            self.input.setPlainText(text)
        if self.input.isEnabled():
            self.input.setFocus()

    def _refresh_conversations(self) -> None:
        self.conversations.blockSignals(True)
        self.conversations.clear()
        if self.current_kb_id:
            repo = self.context.repository()
            try:
                for conversation in repo.list_conversations(self.current_kb_id):
                    self.conversations.addItem(conversation.title, conversation.id)
            finally:
                repo.close()
        self.conversations.blockSignals(False)
        if self.conversations.count():
            self.current_conversation_id = self.conversations.itemData(0)
            self._load_messages()
        else:
            self.current_conversation_id = None
            self.browser.clear()
        self._update_availability()

    def _has_documents(self) -> bool:
        if not self.current_kb_id:
            return False
        return self.context.vector_store.count(self.current_kb_id) > 0

    def refresh_availability(self) -> None:
        self._update_availability()

    def _update_availability(self) -> None:
        has_kb = self.current_kb_id is not None
        has_documents = self._has_documents()
        enabled = has_kb and has_documents
        self.input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        if not has_kb:
            self.input.setPlaceholderText("请先创建或选择知识库")
            self.status.setText("未选择知识库")
        elif not has_documents:
            self.input.setPlaceholderText("当前知识库暂无已索引文档，请先上传或处理文档")
            self.browser.setHtml(
                "<div style='color:#8a97a8;line-height:1.8'>"
                "当前知识库还没有完成索引的文档。请先返回阅读器或侧栏上传文档，并等待处理完成。"
                "</div>"
            )
            self.status.setText("当前知识库暂无已索引文档")
        else:
            self.input.setPlaceholderText("输入问题，Enter 发送；Shift+Enter 换行")
            self.status.setText("就绪")

    def new_conversation(self) -> None:
        if not self.current_kb_id:
            QMessageBox.information(self, "提示", "请先创建或选择知识库。")
            return
        repo = self.context.repository()
        try:
            conversation = repo.create_conversation(self.current_kb_id)
            conversation_id = conversation.id
        finally:
            repo.close()
        self._refresh_conversations()
        index = self.conversations.findData(conversation_id)
        if index >= 0:
            self.conversations.setCurrentIndex(index)

    def delete_conversation(self) -> None:
        if not self.current_conversation_id:
            return
        if QMessageBox.question(self, "删除会话", "确认删除当前会话？") != QMessageBox.Yes:
            return
        repo = self.context.repository()
        try:
            repo.delete_conversation(self.current_conversation_id)
        finally:
            repo.close()
        self._refresh_conversations()

    def _conversation_selected(self) -> None:
        self.current_conversation_id = self.conversations.currentData()
        self._load_messages()

    def _load_messages(self) -> None:
        self.browser.clear()
        if not self.current_conversation_id:
            return
        repo = self.context.repository()
        try:
            for message in repo.list_messages(self.current_conversation_id):
                self._append(message.role, message.content, message.citations or [])
        finally:
            repo.close()

    def _append(self, role: str, content: str, citations: list | None = None) -> None:
        import markdown

        if role == "user":
            body = f"<p style='color:#6e9cff'><b>问：</b></p><p>{html.escape(content).replace(chr(10),'<br>')}</p>"
        else:
            rendered = markdown.markdown(content, extensions=["fenced_code", "tables"])
            if citations:
                links = []
                for citation in citations:
                    document_id = citation.get("document_id", "")
                    page = citation.get("page", "")
                    filename = citation.get("filename", "文档")
                    links.append(
                        f"<a href='app://citation?doc={document_id}&page={page}' "
                        f"style='color:#6e9cff'>{html.escape(filename)} 第{page}页</a>"
                    )
                rendered += "<p>来源：" + " · ".join(links) + "</p>"
            body = f"<p style='color:#ff7da8'><b>答：</b></p>{rendered}"
        self.browser.append(f"<div style='margin-bottom:14px'>{body}</div>")

    def _anchor_clicked(self, url) -> None:
        link = url.toString()
        match = re.search(r"doc=(\d+)&page=(\d+)", link)
        if match:
            self.citation_requested.emit(int(match.group(1)), int(match.group(2)))

    def send(self) -> None:
        question = self.input.toPlainText().strip()
        if not question:
            return
        if not self._has_documents():
            QMessageBox.information(self, "暂无文档", "当前知识库没有文档，请先上传文档。")
            return
        if not self.current_conversation_id:
            self.new_conversation()
        if not self.current_conversation_id:
            return
        if not self.context.config.config.is_llm_configured():
            QMessageBox.warning(self, "未配置 AI", "请先在设置中选择 AI 并填写 API Key。")
            return
        self.input.clear()
        self._append("user", question)
        self.status.setText("正在生成回答…")
        self.thread = TaskThread(
            lambda _progress: self.context.ask(question, self.current_conversation_id)
        )
        self.thread.succeeded.connect(self._answer_done)
        self.thread.failed.connect(self._answer_failed)
        self.thread.start()

    def _answer_done(self, result) -> None:
        self.status.setText("完成")
        self._append("assistant", result.answer, result.citations)

    def _answer_failed(self, message: str) -> None:
        self.status.setText("失败")
        if "API Key" in message or "未配置" in message:
            QMessageBox.warning(self, "无法问答", message)
        else:
            QMessageBox.critical(self, "问答失败", message)

    def export_markdown(self) -> None:
        if not self.current_conversation_id:
            QMessageBox.information(self, "提示", "当前没有可导出的会话。")
            return
        from app.core.markdown_service import export_conversation

        target, _filter = QFileDialog.getSaveFileName(
            self, "导出 Markdown", "对话记录.md", "Markdown (*.md)"
        )
        if not target:
            return
        repo = self.context.repository()
        try:
            path = export_conversation(repo, self.current_conversation_id, Path(target))
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        finally:
            repo.close()
        QMessageBox.information(self, "导出成功", f"已保存：\n{path}")

    def generate_document(self) -> None:
        if not self.current_conversation_id:
            QMessageBox.information(self, "提示", "当前没有可生成文档的会话。")
            return
        if not self.context.config.config.is_llm_configured():
            QMessageBox.warning(self, "未配置 AI", "请先选择 AI 并配置 API Key。")
            return
        target, _filter = QFileDialog.getSaveFileName(
            self, "AI 生成 Markdown", "知识文档.md", "Markdown (*.md)"
        )
        if not target:
            return
        self.status.setText("正在生成 Markdown…")
        conversation_id = self.current_conversation_id
        self.thread = TaskThread(
            lambda _progress: self.context.generate_markdown(conversation_id, Path(target))
        )
        self.thread.succeeded.connect(lambda path: self._notice("生成成功", str(path)))
        self.thread.failed.connect(lambda message: self._notice("生成失败", message))
        self.thread.start()

    def _notice(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)
        self.status.setText("就绪")
