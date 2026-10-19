from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

from aoevillager.hub import ToolboxWindow


class _Engine(QObject):
    state_changed = pyqtSignal(bool)
    is_running = False

    def stop(self) -> None:
        self.state_changed.emit(False)


class _Training(QWidget):
    def __init__(self, _store) -> None:
        super().__init__()
        self.engine = _Engine()

    def set_tool_active(self, _active: bool) -> None:
        pass


class _Stats(QWidget):
    guide_requested = pyqtSignal(str)

    def __init__(self, _folder) -> None:
        super().__init__()
        self.activated = False

    def activate(self) -> None:
        self.activated = True

    def shutdown(self) -> None:
        pass


class NavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_wide_shell_keeps_sidebar_when_opening_guides(self) -> None:
        with patch("aoevillager.hub.TrainingPage", _Training):
            window = ToolboxWindow(object(), Path("."))
        self.assertEqual(window.windowTitle(), "帝国备战室")
        window._ensure_guides = lambda: None
        window.resize(1200, 800)
        window.show()
        self.app.processEvents()
        self.assertTrue(window.sidebar.isVisible())
        self.assertFalse(window.top_nav.isVisible())
        window.select_tool(2)
        self.app.processEvents()
        self.assertTrue(window.sidebar.isVisible(), "开局流程不应将工具导航移到顶部")
        self.assertFalse(window.top_nav.isVisible())
        window.resize(760, 800)
        self.app.processEvents()
        self.assertFalse(window.sidebar.isVisible())
        self.assertTrue(window.top_nav.isVisible(), "窄窗口仍需保留响应式导航")
        window.resize(1200, 800)
        self.app.processEvents()
        self.assertTrue(window.sidebar.isVisible())
        self.assertFalse(window.top_nav.isVisible())
        window.close()

    def test_statistics_is_fourth_tool_without_moving_navigation(self) -> None:
        with patch("aoevillager.hub.TrainingPage", _Training), patch(
            "aoevillager.stats_ui.StatsPage", _Stats
        ):
            window = ToolboxWindow(object(), Path("."))
            window.resize(1200, 800)
            window.show()
            window.select_tool(3)
            self.app.processEvents()
            self.assertEqual(window.pages.currentIndex(), 3)
            self.assertTrue(window.sidebar.isVisible())
            self.assertTrue(window.stats.activated)
            window.close()


if __name__ == "__main__":
    unittest.main()
