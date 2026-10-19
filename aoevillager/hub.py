"""Extensible desktop shell for the AOE4 tools."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QStandardPaths, QTimer
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from .settings import SettingsStore
from .theme import TOOLBOX_STYLE
from .ui import TrainingPage


class ToolboxWindow(QMainWindow):
    TOOL_NAMES = ("自动训练村民工具", "快捷键练习", "开局流程", "文明胜率")

    def __init__(self, store: SettingsStore, practice_assets: Path) -> None:
        super().__init__()
        self._practice_assets = practice_assets
        self.setWindowTitle("帝国备战室")
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
        self.shell_header = header
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(15, 9, 15, 9)
        header_row.setSpacing(11)
        self.mark = QLabel()
        self.mark.setPixmap(QApplication.instance().windowIcon().pixmap(42, 42))
        self.mark.setAccessibleName("IV 应用图标")
        header_row.addWidget(self.mark)
        header_copy = QVBoxLayout()
        header_copy.setSpacing(1)
        title = QLabel("帝国备战室")
        title.setObjectName("shellTitle")
        header_copy.addWidget(title)
        self.subtitle = QLabel("自动训练村民 · 快捷键练习 · 开局流程 · 文明胜率")
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
        self.guides = None
        self.stats = None
        self._practice_slot = QWidget()
        self._guides_slot = QWidget()
        self._stats_slot = QWidget()
        self.pages.addWidget(self.training)
        self.pages.addWidget(self._practice_slot)
        self.pages.addWidget(self._guides_slot)
        self.pages.addWidget(self._stats_slot)
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
                if position != index and button.hasFocus():
                    button.clearFocus()

    def select_tool(self, index: int) -> None:
        if index == self.pages.currentIndex():
            self._pending_index = None
            self._mark_selected(index)
            return
        if index != 0 and self.training.engine.is_running:
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
                self._mark_selected(self.pages.currentIndex())
                return
            self.training.set_tool_active(False)
            self.pages.setCurrentIndex(1)
            QTimer.singleShot(0, self.practice.activate)
        elif index == 2:
            try:
                self._ensure_guides()
            except Exception as exc:
                QMessageBox.warning(self, "开局流程无法打开", str(exc))
                self._mark_selected(self.pages.currentIndex())
                return
            if self.practice is not None:
                self.practice.pause()
            self.training.set_tool_active(False)
            self.pages.setCurrentIndex(2)
        elif index == 3:
            try:
                self._ensure_stats()
            except Exception as exc:
                QMessageBox.warning(self, "文明胜率无法打开", str(exc))
                self._mark_selected(self.pages.currentIndex())
                return
            if self.practice is not None:
                self.practice.pause()
            self.training.set_tool_active(False)
            self.pages.setCurrentIndex(3)
            QTimer.singleShot(0, self.stats.activate)
        else:
            if self.practice is not None:
                self.practice.pause()
            self.pages.setCurrentIndex(0)
            self.training.set_tool_active(True)
        self._mark_selected(index)
        self._update_navigation(self.width())

    def _ensure_practice(self) -> None:
        if self.practice is not None:
            return
        from .practice import HotkeyPracticePage

        self.practice = HotkeyPracticePage(self._practice_assets)
        self.pages.removeWidget(self._practice_slot)
        self._practice_slot.deleteLater()
        self.pages.insertWidget(1, self.practice)

    def _ensure_guides(self) -> None:
        if self.guides is not None:
            return
        from .guide_ui import GuidePage

        folder = Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )) / "guides"
        self.guides = GuidePage(folder)
        self.pages.removeWidget(self._guides_slot)
        self._guides_slot.deleteLater()
        self.pages.insertWidget(2, self.guides)

    def _ensure_stats(self) -> None:
        if self.stats is not None:
            return
        from .stats_ui import StatsPage

        folder = Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )) / "stats"
        self.stats = StatsPage(folder)
        self.stats.guide_requested.connect(self._open_civ_guides)
        self.pages.removeWidget(self._stats_slot)
        self._stats_slot.deleteLater()
        self.pages.insertWidget(3, self.stats)

    def _open_civ_guides(self, code: str) -> None:
        self.select_tool(2)
        if self.pages.currentIndex() == 2 and self.guides is not None:
            self.guides._show_civ(code)

    def _update_navigation(self, width: int) -> None:
        compact = width < 820
        if getattr(self, "_compact", None) == compact:
            return
        self._compact = compact
        self.shell_header.setVisible(True)
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
        if self.guides is not None:
            self.guides.shutdown()
        if self.stats is not None:
            self.stats.shutdown()
        self.training.close()
        super().closeEvent(event)
