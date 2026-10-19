from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QHideEvent, QMouseEvent, QShowEvent
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from .settings import SettingsStore
from .theme import DIALOG_STYLE
from .widgets import NoWheelSpinBox


class StatusOverlay(QWidget):
    position_changed = pyqtSignal(QPoint)
    size_changed = pyqtSignal(QSize)

    LEFT, TOP, RIGHT, BOTTOM = 1, 2, 4, 8
    RESIZE_MARGIN = 9

    def __init__(self, hotkey: str) -> None:
        super().__init__()
        self._editing = False
        self._position_set = False
        self._drag_offset: QPoint | None = None
        self._resize_edges = 0
        self._resize_origin: QRect | None = None
        self._resize_pointer: QPoint | None = None
        self.setWindowTitle("AOE4 自动训练村民悬浮提示")
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMinimumSize(280, 72)
        self.setMaximumSize(1200, 500)
        self.resize(340, 88)
        self.setMouseTracking(True)
        self.setAccessibleName("自动训练村民全局悬浮提示")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("overlayCard")
        card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        card.setStyleSheet(
            "QFrame#overlayCard {"
            " background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #354960,stop:1 #26374b);"
            " border: 1px solid #c7a263; border-radius: 8px; }"
            "QLabel { color: #edf1f4; border: none; background: transparent; }"
        )
        outer.addWidget(card)
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(12)
        self.dot = QLabel("◆")
        self.dot.setStyleSheet("color: #c8a767; font-size: 21px")
        row.addWidget(self.dot)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        self.title = QLabel("自动训练村民已就绪")
        self.title.setStyleSheet("color: #f5dfa9; font-size: 15px; font-weight: 700")
        self.hint = QLabel(f"按 {hotkey} 开始")
        self.hint.setStyleSheet("color: #c5d0dd; font-size: 12px")
        copy.addWidget(self.title)
        copy.addWidget(self.hint)
        row.addLayout(copy, 1)
        self.keycap = QLabel(hotkey)
        self.keycap.setStyleSheet(
            "background: #202f42; color: #f5dfa9; border: 1px solid #ac8952;"
            "border-radius: 6px; padding: 5px 9px; font-weight: 700"
        )
        row.addWidget(self.keycap)

    def set_status(self, running: bool, mode: str, hotkey: str) -> None:
        label = "简单模式" if mode == "simple" else "自定义模式"
        self.title.setText(f"正在训练村民 · {label}" if running else f"训练已就绪 · {label}")
        self.hint.setText(f"按 {hotkey} {'停止' if running else '开始'}")
        self.keycap.setText(hotkey)
        self.dot.setStyleSheet(f"color: {'#a8e1ba' if running else '#c8a767'}; font-size: 21px")

    def set_editable(self, editable: bool) -> None:
        if self._editing == editable:
            return
        self._editing = editable
        visible, position, size, opacity = self.isVisible(), self.pos(), self.size(), self.windowOpacity()
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, not editable)
        self.setToolTip("拖动移动，拖动边缘改变大小" if editable else "")
        if visible:
            self.resize(size)
            self.move(position)
            self.show()
            self.setWindowOpacity(opacity)
            self.raise_()

    def set_saved_position(self, position: QPoint | None) -> None:
        if position is not None and self._position_visible(position):
            self.move(position)
            self._position_set = True

    def ensure_position(self) -> None:
        if self._position_set:
            return
        screen = QApplication.screenAt(self.cursor().pos()) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - 24, area.top() + 24)
            self._position_set = True
            self.position_changed.emit(self.pos())

    def reset_position(self) -> None:
        self._position_set = False
        self.ensure_position()

    def set_overlay_position(self, position: QPoint) -> None:
        self.move(position)
        self._position_set = True
        self._clamp_to_screen()
        self.position_changed.emit(self.pos())

    def set_overlay_size(self, size: QSize) -> None:
        self.resize(size)
        if self._position_set:
            self._clamp_to_screen()
            self.position_changed.emit(self.pos())
        self.size_changed.emit(self.size())

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        self.ensure_position()
        super().showEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._editing or event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self._resize_edges = self._edges_at(event.position().toPoint())
        if self._resize_edges:
            self._resize_origin = self.geometry()
            self._resize_pointer = event.globalPosition().toPoint()
        else:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._editing:
            event.ignore()
            return
        pointer = event.globalPosition().toPoint()
        if (self._resize_edges and self._resize_origin is not None and self._resize_pointer is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            self._resize_from(pointer - self._resize_pointer)
            event.accept()
        elif self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(pointer - self._drag_offset)
            event.accept()
        else:
            self._update_cursor(self._edges_at(event.position().toPoint()))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._editing or event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        if self._drag_offset is not None or self._resize_edges:
            self._drag_offset = None
            self._resize_edges = 0
            self._resize_origin = None
            self._resize_pointer = None
            self._clamp_to_screen()
            self.position_changed.emit(self.pos())
            self.size_changed.emit(self.size())
            self._update_cursor(self._edges_at(event.position().toPoint()))
            event.accept()

    def _edges_at(self, point: QPoint) -> int:
        edges = 0
        if point.x() < self.RESIZE_MARGIN:
            edges |= self.LEFT
        elif point.x() >= self.width() - self.RESIZE_MARGIN:
            edges |= self.RIGHT
        if point.y() < self.RESIZE_MARGIN:
            edges |= self.TOP
        elif point.y() >= self.height() - self.RESIZE_MARGIN:
            edges |= self.BOTTOM
        return edges

    def _update_cursor(self, edges: int) -> None:
        if edges in (self.LEFT | self.TOP, self.RIGHT | self.BOTTOM):
            shape = Qt.CursorShape.SizeFDiagCursor
        elif edges in (self.RIGHT | self.TOP, self.LEFT | self.BOTTOM):
            shape = Qt.CursorShape.SizeBDiagCursor
        elif edges & (self.LEFT | self.RIGHT):
            shape = Qt.CursorShape.SizeHorCursor
        elif edges & (self.TOP | self.BOTTOM):
            shape = Qt.CursorShape.SizeVerCursor
        else:
            shape = Qt.CursorShape.SizeAllCursor
        self.setCursor(shape)

    def _resize_from(self, delta: QPoint) -> None:
        origin = self._resize_origin
        if origin is None:
            return
        left, top, right, bottom = origin.left(), origin.top(), origin.right(), origin.bottom()
        if self._resize_edges & self.LEFT:
            left = max(right - self.maximumWidth() + 1, min(left + delta.x(), right - self.minimumWidth() + 1))
        if self._resize_edges & self.RIGHT:
            right = min(left + self.maximumWidth() - 1, max(right + delta.x(), left + self.minimumWidth() - 1))
        if self._resize_edges & self.TOP:
            top = max(bottom - self.maximumHeight() + 1, min(top + delta.y(), bottom - self.minimumHeight() + 1))
        if self._resize_edges & self.BOTTOM:
            bottom = min(top + self.maximumHeight() - 1, max(bottom + delta.y(), top + self.minimumHeight() - 1))
        self.setGeometry(QRect(QPoint(left, top), QPoint(right, bottom)))

    def _clamp_to_screen(self) -> None:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            x = min(max(self.x(), area.left()), max(area.left(), area.right() - self.width() + 1))
            y = min(max(self.y(), area.top()), max(area.top(), area.bottom() - self.height() + 1))
            self.move(x, y)

    def _position_visible(self, position: QPoint) -> bool:
        middle = position + QPoint(self.width() // 2, self.height() // 2)
        return any(screen.availableGeometry().contains(middle) for screen in QApplication.screens())


class OverlaySettingsDialog(QDialog):
    def __init__(
        self,
        overlay: StatusOverlay,
        store: SettingsStore,
        set_visible: Callable[[bool], None],
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.overlay = overlay
        self.store = store
        self._set_visible = set_visible
        self.setWindowTitle("设置 · 悬浮提示")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(470)
        self.setStyleSheet(DIALOG_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(13)
        eyebrow = QLabel("DISPLAY  /  FLOATING STATUS")
        eyebrow.setStyleSheet("color: #c8a767; font-size: 10px; font-weight: 700")
        layout.addWidget(eyebrow)
        title = QLabel("悬浮提示")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        hint = QLabel("仅打开此设置窗口时，悬浮窗可拖动或拉伸；关闭后鼠标点击会穿透。")
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        controls = QFrame()
        controls.setObjectName("dialogCard")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 17, 18, 17)
        controls_layout.setSpacing(14)
        self.visible = QCheckBox("显示悬浮提示")
        self.visible.setAccessibleName("显示或隐藏悬浮提示")
        self.visible.toggled.connect(self._set_visible)
        controls_layout.addWidget(self.visible)

        grid = QGridLayout()
        self.width_spin = self._spin(280, 1200, " px", "悬浮窗宽度")
        self.height_spin = self._spin(72, 500, " px", "悬浮窗高度")
        self.x_spin = self._spin(-32768, 32767, "", "悬浮窗 X 位置")
        self.y_spin = self._spin(-32768, 32767, "", "悬浮窗 Y 位置")
        for row, (left, left_spin, right, right_spin) in enumerate((
            ("宽度", self.width_spin, "高度", self.height_spin),
            ("X 位置", self.x_spin, "Y 位置", self.y_spin),
        )):
            grid.addWidget(QLabel(left), row, 0)
            grid.addWidget(left_spin, row, 1)
            grid.addWidget(QLabel(right), row, 2)
            grid.addWidget(right_spin, row, 3)
        controls_layout.addLayout(grid)

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("不透明度"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setAccessibleName("悬浮窗不透明度滑块")
        opacity_row.addWidget(self.opacity_slider, 1)
        self.opacity_spin = self._spin(20, 100, " %", "悬浮窗不透明度")
        opacity_row.addWidget(self.opacity_spin)
        controls_layout.addLayout(opacity_row)
        layout.addWidget(controls)
        actions = QHBoxLayout()
        reset = QPushButton("移到当前屏幕右上角")
        reset.clicked.connect(overlay.reset_position)
        actions.addWidget(reset)
        actions.addStretch()
        close = QPushButton("完成")
        close.setObjectName("dialogPrimary")
        close.clicked.connect(self.close)
        actions.addWidget(close)
        layout.addLayout(actions)

        self.width_spin.valueChanged.connect(self._apply_size)
        self.height_spin.valueChanged.connect(self._apply_size)
        self.x_spin.valueChanged.connect(self._apply_position)
        self.y_spin.valueChanged.connect(self._apply_position)
        self.opacity_slider.valueChanged.connect(self.opacity_spin.setValue)
        self.opacity_spin.valueChanged.connect(self.opacity_slider.setValue)
        self.opacity_spin.valueChanged.connect(self._apply_opacity)
        overlay.size_changed.connect(self._sync_size)
        overlay.position_changed.connect(self._sync_position)
        self.sync_from_overlay()

    @staticmethod
    def _spin(minimum: int, maximum: int, suffix: str, name: str) -> NoWheelSpinBox:
        spin = NoWheelSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(False)
        spin.setAccessibleName(name)
        return spin

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        self.overlay.set_editable(True)
        super().showEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self.overlay.set_editable(False)
        super().hideEvent(event)

    def sync_from_overlay(self) -> None:
        self.overlay.ensure_position()
        self._sync_size(self.overlay.size())
        self._sync_position(self.overlay.pos())
        for widget in (self.opacity_spin, self.opacity_slider):
            widget.blockSignals(True)
            widget.setValue(self.store.values.overlay_opacity)
            widget.blockSignals(False)
        self.visible.blockSignals(True)
        self.visible.setChecked(self.store.values.overlay_visible)
        self.visible.blockSignals(False)

    def _sync_size(self, size: QSize) -> None:
        for widget, value in ((self.width_spin, size.width()), (self.height_spin, size.height())):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)

    def _sync_position(self, position: QPoint) -> None:
        for widget, value in ((self.x_spin, position.x()), (self.y_spin, position.y())):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)

    def _apply_size(self) -> None:
        self.overlay.set_overlay_size(QSize(self.width_spin.value(), self.height_spin.value()))

    def _apply_position(self) -> None:
        self.overlay.set_overlay_position(QPoint(self.x_spin.value(), self.y_spin.value()))

    def _apply_opacity(self, percent: int) -> None:
        self.overlay.setWindowOpacity(percent / 100.0)
        self.store.set_overlay_opacity(percent)
