from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from aoevillager.practice import HotkeyPracticePage


ASSETS = Path(__file__).resolve().parents[1] / "assets" / "practice"


class PracticeNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.page = HotkeyPracticePage(ASSETS)
        self.page.resize(760, 700)
        self.page.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.page.close()
        self.page.deleteLater()
        self.app.processEvents()

    def test_initial_page_is_searchable_civilization_grid(self) -> None:
        self.assertEqual(self.page.page_stack.currentIndex(), 0)
        self.assertEqual(len(self.page.civ_cards), len(self.page.catalog.civilizations))
        self.page.civ_search.setText("阿尤布")
        self.app.processEvents()
        self.assertIn("1 /", self.page.civ_count.text())
        self.assertFalse(self.page.civ_empty.isVisible())
        self.page.civ_search.setText("不存在的文明")
        self.app.processEvents()
        self.assertTrue(self.page.civ_empty.isVisible())

    def test_civilization_opens_practice_and_can_be_changed(self) -> None:
        self.page._choose_civilization("french")
        self.assertEqual(self.page.page_stack.currentIndex(), 1)
        self.assertEqual(self.page.civ_combo.currentData(), "french")
        self.assertTrue(self.page._available)
        self.assertIn("法兰西", self.page.civ_button.text())
        self.page._show_civilization_picker()
        self.assertEqual(self.page.page_stack.currentIndex(), 0)
        self.page._choose_civilization("english")
        self.assertEqual(self.page.civ_combo.currentData(), "english")
        self.assertIn("英格兰", self.page.civ_button.text())

    def test_building_selection_gets_most_of_desktop_height(self) -> None:
        self.page.resize(1250, 970)
        self.page._choose_civilization("english")
        self.app.processEvents()
        self.assertGreater(self.page.building_scroll.height(), self.page.height() * 0.6)
        self.assertFalse(self.page.target_icon.isVisible())
        self.page._start()
        self.app.processEvents()
        self.assertTrue(self.page.target_icon.isVisible())
        self.page.pause()


if __name__ == "__main__":
    unittest.main()
