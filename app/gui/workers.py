"""基于 QThread 的后台任务封装。"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal


ProgressCallback = Callable[[str, int, int], None]


class TaskThread(QThread):
    progress = Signal(str, int, int)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        task: Callable[[ProgressCallback], object],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.task = task

    def run(self) -> None:
        try:
            result = self.task(self.progress.emit)
            self.succeeded.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

