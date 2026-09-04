"""浅色二次元可爱主题与全屏背景绘制层。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


GLOBAL_QSS = """
QWidget {
    color: #27354a;
    font-family: "Segoe UI", "Microsoft YaHei";
    font-size: 13px;
    background: transparent;
}
QMainWindow, QStackedWidget, QTabWidget::pane, QSplitter {
    background: transparent;
}
QToolButton {
    border: 0;
    border-radius: 10px;
    padding: 5px 8px;
    color: #6c7b91;
    background: transparent;
}
QToolButton:hover { background: #fff0f5; color: #ff7da8; }
QToolButton#brand {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #ff9fc1, stop:0.55 #8ab6ff, stop:1 #7ee2cf);
    color: white;
    border-radius: 14px;
    font-weight: 800;
    font-size: 18px;
}
QPushButton {
    border: 1px solid #f0dce8;
    background: #ffffff;
    border-radius: 9px;
    padding: 6px 11px;
    color: #65758b;
}
QPushButton:hover { border-color: #ffb7ce; color: #ff7da8; background: #fff8fb; }
QPushButton:pressed { background: #fff0f5; }
QTreeWidget, QListWidget, QTableWidget, QTextBrowser, QTextEdit, QLineEdit, QComboBox {
    border: 1px solid #f0e2eb;
    border-radius: 10px;
    background: rgba(255, 255, 255, 244);
}
QTreeWidget::item { min-height: 30px; border-radius: 8px; }
QTreeWidget::item:hover { background: #fff5f8; }
QTreeWidget::item:selected { background: #fff0f5; color: #27354a; }
QComboBox QAbstractItemView { background: white; border: 1px solid #f0dce8; selection-background-color: #eaf4ff; }
QHeaderView::section {
    background: #fff7fa;
    border: 0;
    border-bottom: 1px solid #f0dce8;
    padding: 6px;
    color: #a06f86;
}
QTabBar::tab {
    background: transparent;
    color: #95a0b0;
    padding: 8px 14px;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #ff7da8;
    font-weight: 600;
}
QTabBar::tab:hover { color: #ff9fbe; }
QScrollBar:vertical { width: 9px; background: transparent; }
QScrollBar::handle:vertical { background: #f5c8d8; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #ffb7ce; }
QScrollBar:horizontal { height: 9px; background: transparent; }
QScrollBar::handle:horizontal { background: #f5c8d8; border-radius: 5px; min-width: 30px; }
QMenu { background: #ffffff; border: 1px solid #f0dce8; border-radius: 10px; padding: 5px; }
QMenu::item { padding: 6px 18px; border-radius: 7px; }
QMenu::item:selected { background: #fff0f5; color: #ff7da8; }
QDialog { background: #fbfcff; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #d7e3f5; border-radius: 5px; background: white;
}
QCheckBox::indicator:checked { background: #8ab6ff; border-color: #8ab6ff; }
QProgressBar {
    border: 0; border-radius: 6px; background: #f0e7f2; text-align: center; color: #52627a;
}
QProgressBar::chunk { border-radius: 6px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff9fc1, stop:1 #8ab6ff); }
QToolTip { background: white; color: #27354a; border: 1px solid #f0dce8; padding: 4px; }
"""


class BackgroundHost(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()

    def set_background(self, path: str) -> None:
        self._pixmap = QPixmap(path) if path and Path(path).exists() else QPixmap()
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._pixmap.isNull():
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#fbfcff"))
            return
        painter = QPainter(self)
        target = self.rect()
        source = self._pixmap.size()
        scale = max(target.width() / max(1, source.width()), target.height() / max(1, source.height()))
        size = source * scale
        x = (target.width() - size.width()) / 2
        y = (target.height() - size.height()) / 2
        painter.drawPixmap(int(x), int(y), int(size.width()), int(size.height()), self._pixmap)


def background_stylesheet(path: str, mode: str = "cover") -> str:
    """保留透明层样式；背景绘制由 BackgroundHost 完成。"""
    return (
        "QListWidget, QTableWidget, QTreeWidget, QTextBrowser, QTextEdit, QComboBox { "
        "background-color: rgba(255, 255, 255, 238); "
        "} "
        "QPushButton { background-color: rgba(255, 255, 255, 244); }"
    )
