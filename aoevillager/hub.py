"""Extensible desktop shell for the AOE4 tools."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from .settings import SettingsStore
from .theme import TOOLBOX_STYLE
from .ui import TrainingPage


class ToolboxWindow(QMainWindow):
    TOOL_NAMES = ("自动训练村民工具", "快捷键练习")

    def __init__(self, store: SettingsStore, practice_html: Path) -> None:
        super().__init__()
        self._practice_html = practice_html
        self.setWindowTitle("帝国时代 4 工具箱")
        self.setMinimumSize(680, 670)
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        width = min(1060, max(680, available.width() - 40)) if available else 1060
        height = min(740, max(670, available.height() - 40)) if available else 740
        self.resize(width, height)
        self.setStyleSheet(TOOLBOX_STYLE)
        self._pending_index: int | None = None
        self._nav_buttons: list[tuple[QPushButton, QPushButton]] = []

        root = QWidget()
        root.setObjectName("toolboxRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)

        header = QFrame()
        header.setObjectName("shellHeader")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(15, 9, 15, 9)
        header_row.setSpacing(11)
        self.mark = QLabel()
        self.mark.setPixmap(QApplication.instance().windowIcon().pixmap(42, 42))
        self.mark.setAccessibleName("IV 应用图标")
        header_row.addWidget(self.mark)
        header_copy = QVBoxLayout()
        header_copy.setSpacing(1)
        title = QLabel("帝国时代 4 工具箱")
        title.setObjectName("shellTitle")
        header_copy.addWidget(title)
        self.subtitle = QLabel("自动训练村民 · 快捷键练习")
        self.subtitle.setObjectName("shellMuted")
        header_copy.addWidget(self.subtitle)
        header_row.addLayout(header_copy, 1)
        outer.addWidget(header)

        self.top_nav = QFrame()
        self.top_nav.setObjectName("toolTopNav")
        top_row = QHBoxLayout(self.top_nav)
        top_row.setContentsMargins(5, 5, 5, 5)
        top_row.setSpacing(5)
        outer.addWidget(self.top_nav)

        body = QHBoxLayout()
        body.setSpacing(10)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("toolSidebar")
        self.sidebar.setFixedWidth(186)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(10, 15, 10, 12)
        side_layout.setSpacing(7)
        side_heading = QLabel("工具列表")
        side_heading.setObjectName("shellMuted")
        side_layout.addWidget(side_heading)

        for index, name in enumerate(self.TOOL_NAMES):
            side_button = self._nav_button(name, index)
            top_button = self._nav_button(name, index)
            side_layout.addWidget(side_button)
            top_row.addWidget(top_button, 1)
            self._nav_buttons.append((side_button, top_button))
        side_layout.addStretch(1)
        count = QLabel(f"已收录 {len(self.TOOL_NAMES)} 个工具")
        count.setObjectName("shellMuted")
        side_layout.addWidget(count)
        body.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        self.training = TrainingPage(store)
        self.practice = None
        self._practice_slot = QWidget()
        self.pages.addWidget(self.training)
        self.pages.addWidget(self._practice_slot)
        body.addWidget(self.pages, 1)
        outer.addLayout(body, 1)

        self.training.engine.state_changed.connect(self._on_training_state_changed)
        self._mark_selected(0)
        self._update_navigation(self.width())

    def _nav_button(self, name: str, index: int) -> QPushButton:
        button = QPushButton(name)
        button.setObjectName("toolNav")
        button.setCheckable(True)
        button.setAccessibleName(f"打开{name}")
        button.clicked.connect(lambda checked=False, target=index: self.select_tool(target))
        return button

    def _mark_selected(self, index: int) -> None:
        for position, pair in enumerate(self._nav_buttons):
            for button in pair:
                button.setChecked(position == index)

    def select_tool(self, index: int) -> None:
        if index == self.pages.currentIndex():
            self._pending_index = None
            self._mark_selected(index)
            return
        if index == 1 and self.training.engine.is_running:
            self._pending_index = index
            self.training.engine.stop()
            return
        self._activate_tool(index)

    def _on_training_state_changed(self, running: bool) -> None:
        if not running and self._pending_index is not None:
            QTimer.singleShot(0, self._finish_pending_switch)

    def _finish_pending_switch(self) -> None:
        index = self._pending_index
        if index is None or self.training.engine.is_running:
            return
        self._pending_index = None
        self._activate_tool(index)

    def _activate_tool(self, index: int) -> None:
        if index == 1:
            try:
                self._ensure_practice()
            except Exception as exc:
                QMessageBox.warning(self, "快捷键练习无法打开", str(exc))
                self._mark_selected(0)
                return
            self.training.set_tool_active(False)
            self.pages.setCurrentIndex(1)
            QTimer.singleShot(0, self.practice.activate)
        else:
            if self.practice is not None:
                self.practice.pause()
            self.pages.setCurrentIndex(0)
            self.training.set_tool_active(True)
        self._mark_selected(index)

    def _ensure_practice(self) -> None:
        if self.practice is not None:
            return
        from .practice import HotkeyPracticePage

        self.practice = HotkeyPracticePage(self._practice_html)
        self.pages.removeWidget(self._practice_slot)
        self._practice_slot.deleteLater()
        self.pages.insertWidget(1, self.practice)
        self.practice.web.loadFinished.connect(self._focus_practice_if_active)

    def _focus_practice_if_active(self, loaded: bool) -> None:
        if loaded and self.pages.currentIndex() == 1 and self.practice is not None:
            self.practice.activate()

    def _update_navigation(self, width: int) -> None:
        compact = width < 980
        if getattr(self, "_compact", None) == compact:
            return
        self._compact = compact
        self.sidebar.setVisible(not compact)
        self.top_nav.setVisible(compact)
        self.subtitle.setVisible(not compact)
        size = 32 if compact else 42
        self.mark.setPixmap(QApplication.instance().windowIcon().pixmap(size, size))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "sidebar"):
            self._update_navigation(event.size().width())

    def closeEvent(self, event) -> None:  # noqa: N802
        self._pending_index = None
        self.training.close()
        super().closeEvent(event)
