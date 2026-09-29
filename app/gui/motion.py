"""Smooth hover and press motion for Qt buttons."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractButton, QGraphicsDropShadowEffect


class SmoothInteractionFilter(QObject):
    """Animate a subtle shadow so button feedback feels softer without resizing widgets."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._effects: dict[QAbstractButton, QGraphicsDropShadowEffect] = {}
        self._animations: list[QPropertyAnimation] = []

    def eventFilter(self, watched, event) -> bool:
        if not isinstance(watched, QAbstractButton) or not watched.isEnabled():
            return False
        target = None
        if event.type() == QEvent.Enter:
            target = 12
        elif event.type() == QEvent.Leave:
            target = 0
        elif event.type() == QEvent.MouseButtonPress:
            target = 4
        elif event.type() == QEvent.MouseButtonRelease:
            target = 10
        elif event.type() == QEvent.FocusIn:
            target = 7
        elif event.type() == QEvent.FocusOut:
            target = 0
        if target is not None:
            self._animate(watched, target)
        return False

    def _animate(self, button: QAbstractButton, target: int) -> None:
        effect = self._effects.get(button)
        if effect is None:
            effect = QGraphicsDropShadowEffect(button)
            effect.setColor(QColor(255, 125, 168, 100))
            effect.setOffset(0, 2)
            effect.setBlurRadius(0)
            button.setGraphicsEffect(effect)
            self._effects[button] = effect
        animation = QPropertyAnimation(effect, b"blurRadius", effect)
        animation.setDuration(180)
        animation.setStartValue(effect.blurRadius())
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animations.append(animation)
        animation.finished.connect(lambda: self._forget(animation))
        animation.start()

    def _forget(self, animation: QPropertyAnimation) -> None:
        if animation in self._animations:
            self._animations.remove(animation)