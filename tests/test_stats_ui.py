from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from aoevillager.stats_ui import StatsPage
from tests.test_stats_data import sample_snapshot


class StatsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_matrix_overview_and_guide_link_use_one_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            page = StatsPage(Path(folder))
            page.resize(1050, 700)
            page.show()
            page._display(sample_snapshot())
            self.app.processEvents()
            self.assertEqual((page.matrix_model.rowCount(), page.matrix_model.columnCount()), (2, 3))
            self.assertEqual(page.overview.rowCount(), 2)
            row = page.matrix_model.slugs.index("english")
            column = page.matrix_model.slugs.index("french") + 1
            self.assertEqual(page.matrix_model.headerData(
                column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole), "")
            self.assertEqual(page.matrix_model.headerData(
                row, Qt.Orientation.Vertical, Qt.ItemDataRole.ToolTipRole), "英格兰")
            self.assertFalse(page.matrix_model.headerData(
                column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DecorationRole).isNull())
            self.assertEqual(page.overview.item(0, 0).text(), "")
            self.assertTrue(page.overview.item(0, 0).toolTip())
            self.assertEqual(page.focused_table.item(0, 0).text(), "")
            self.assertTrue(page.focused_table.item(0, 0).toolTip())
            page._matrix_clicked(page.matrix_model.index(row, column))
            self.assertIn("60.0%", page.detail_text.text())
            selected: list[str] = []
            page.guide_requested.connect(selected.append)
            page.guides_button.click()
            self.assertEqual(selected, ["ENG"])
            page.selected_civ = "unavailable_in_this_patch"
            page._display(sample_snapshot())
            self.assertIn(page.selected_civ, page.matrix_model.slugs)
            page._display(None)
            self.assertEqual(page.civ_combo.count(), 0)
            self.assertEqual(page.selected_civ, "")
            page.close()

    def test_rank_and_rating_filters_are_mutually_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            page = StatsPage(Path(folder))
            page.rank_combo.setCurrentIndex(page.rank_combo.findData("gold"))
            self.assertEqual(page._filters().rank_level, "gold")
            page.rating_combo.setCurrentIndex(page.rating_combo.findData(">1200"))
            self.assertEqual(page._filters().rating, ">1200")
            self.assertEqual(page._filters().rank_level, "")
            page.shutdown()
            page.close()


if __name__ == "__main__":
    unittest.main()
