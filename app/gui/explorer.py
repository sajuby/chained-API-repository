"""Obsidian 风格知识库文件侧栏。"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.data.repository import Repository


class ExplorerSidebar(QWidget):
    document_activated = Signal(int)
    document_reprocess = Signal(int)
    document_delete = Signal(int)
    conversation_activated = Signal(int)
    upload_requested = Signal()
    new_requested = Signal()
    vault_requested = Signal()

    def __init__(self, context, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.current_kb_id: int | None = None
        self._ids: dict[int, tuple[str, int]] = {}

        eyebrow = QLabel("MY LIBRARY")
        eyebrow.setStyleSheet("color:#a7b1bf;font-size:10px;font-weight:700;letter-spacing:1px;")
        vault_icon = QLabel("✦")
        vault_icon.setFixedSize(30, 30)
        vault_icon.setAlignment(Qt.AlignCenter)
        vault_icon.setStyleSheet(
            "background:#eafaf7;color:#5bc8b4;border-radius:10px;"
            "font-size:16px;font-weight:700;"
        )
        self.vault_name = QLabel("未选择知识库")
        self.vault_name.setStyleSheet("font-size:16px;font-weight:700;color:#27354a;")
        vault_button = QPushButton("切换")
        vault_button.setFixedHeight(28)
        vault_button.clicked.connect(self.vault_requested)
        vault_row = QHBoxLayout()
        vault_row.addWidget(vault_icon)
        vault_row.addWidget(self.vault_name, 1)
        vault_row.addWidget(vault_button)

        self.upload_btn = QPushButton("＋ 上传文件")
        self.new_btn = QPushButton("新建")
        self.upload_btn.clicked.connect(self.upload_requested)
        self.new_btn.clicked.connect(self.new_requested)
        actions = QHBoxLayout()
        actions.addWidget(self.upload_btn)
        actions.addWidget(self.new_btn)

        self.search = QLineEdit()
        self.search.setPlaceholderText("筛选当前知识库")
        self.search.textChanged.connect(self._filter)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemClicked.connect(self._item_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 10, 10)
        layout.addWidget(eyebrow)
        layout.addLayout(vault_row)
        layout.addLayout(actions)
        layout.addWidget(self.search)
        layout.addWidget(self.tree, 1)

    def set_kb(self, kb_id: int | None, kb_name: str = "") -> None:
        self.current_kb_id = kb_id
        self.vault_name.setText(kb_name or ("未选择知识库" if kb_id is None else "知识库"))
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        if not self.current_kb_id:
            empty = QTreeWidgetItem(["先创建或选择知识库"])
            self.tree.addTopLevelItem(empty)
            return
        repo = self.context.repository()
        try:
            documents = repo.list_documents(self.current_kb_id)
            conversations = repo.list_conversations(self.current_kb_id)
            imported = [d for d in documents if d.source_type == "imported"]
            generated = [d for d in documents if d.source_type == "generated"]
            self._add_section("文档", self._doc_items(imported))
            self._add_section("生成内容", self._doc_items(generated))
            self._add_section("最近打开", self._doc_items(documents[:5]))
            self._add_section("会话", self._conversation_items(conversations))
        finally:
            repo.close()
        self.tree.expandToDepth(1)

    def _doc_items(self, documents) -> list[tuple[str, int, str]]:
        items: list[tuple[str, int, str]] = []
        for doc in documents:
            label = f"{doc.filename}    {doc.status}"
            items.append((label, doc.id, "document"))
        return items

    def _conversation_items(self, conversations) -> list[tuple[str, int, str]]:
        items: list[tuple[str, int, str]] = []
        for conversation in conversations:
            items.append((f"{conversation.title}    {conversation.updated_at.strftime('%m-%d %H:%M')}", conversation.id, "conversation"))
        return items

    def _add_section(self, title: str, children: list[tuple[str, int, str]]) -> None:
        section = QTreeWidgetItem([f"{title}   {len(children)}"])
        section.setData(0, Qt.UserRole, "section")
        if not children:
            section.addChild(QTreeWidgetItem(["（暂无）"]))
        for label, object_id, kind in children:
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.UserRole, kind)
            item.setData(0, Qt.UserRole + 1, object_id)
            self._ids[object_id] = (kind, object_id)
            section.addChild(item)
        self.tree.addTopLevelItem(section)

    def _filter(self, keyword: str) -> None:
        keyword = keyword.lower()
        for index in range(self.tree.topLevelItemCount()):
            section = self.tree.topLevelItem(index)
            for child_index in range(section.childCount()):
                child = section.child(child_index)
                visible = not keyword or keyword in child.text(0).lower()
                child.setHidden(not visible)
            any_visible = any(not section.child(i).isHidden() for i in range(section.childCount()))
            section.setHidden(not any_visible and bool(keyword))

    def _item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        kind = item.data(0, Qt.UserRole)
        object_id = item.data(0, Qt.UserRole + 1)
        if kind == "document":
            self.document_activated.emit(int(object_id))
        elif kind == "conversation":
            self.conversation_activated.emit(int(object_id))

    def _context_menu(self, position) -> None:
        item = self.tree.itemAt(position)
        if not item:
            return
        kind = item.data(0, Qt.UserRole)
        object_id = item.data(0, Qt.UserRole + 1)
        if kind == "document":
            menu = QMenu(self)
            open_action = menu.addAction("打开原文")
            reprocess_action = menu.addAction("重新处理")
            delete_action = menu.addAction("删除")
            action = menu.exec(self.tree.mapToGlobal(position))
            if action == open_action:
                self.document_activated.emit(int(object_id))
            elif action == reprocess_action:
                self.document_reprocess.emit(int(object_id))
            elif action == delete_action:
                self.document_delete.emit(int(object_id))
        elif kind == "conversation":
            menu = QMenu(self)
            open_action = menu.addAction("打开会话")
            action = menu.exec(self.tree.mapToGlobal(position))
            if action == open_action:
                self.conversation_activated.emit(int(object_id))
