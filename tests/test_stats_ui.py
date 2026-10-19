from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication

from aoevillager.stats_data import WORLD_TO_CODE
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
            snapshot = sample_snapshot()
            # API's mirror-inclusive rates rank these in the opposite order.
            snapshot["civilizations"][0]["win_rate"] = 42.0
            snapshot["civilizations"][1]["win_rate"] = 58.0
            page._display(snapshot)
            self.app.processEvents()
            self.assertEqual((page.matrix_model.rowCount(), page.matrix_model.columnCount()), (2, 3))
            self.assertEqual(page.overview.rowCount(), 2)
            self.assertEqual(page.matrix_model.slugs, ["english", "french"])
            self.assertEqual(page.overview.item(0, 0).data(Qt.ItemDataRole.UserRole), "english")
            self.assertEqual(page.overview.item(0, 1).text(), "60.0%")
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

    def test_entire_matrix_fits_small_and_large_windows_without_scrollbars(self) -> None:
        slugs = list(WORLD_TO_CODE)
        snapshot = sample_snapshot()
        snapshot["civilizations"] = [
            {"civilization": slug, "win_rate": 50.0 + index / 10,
             "pick_rate": 4.0, "games_count": 10000, "duration_median": 1200}
            for index, slug in enumerate(slugs)
        ]
        snapshot["matchups"] = [
            {"civilization": slug, "other_civilization": other,
             "win_rate": 50.0, "win_count": 500,
             "player_games_count": 1000, "games_count": 500}
            for slug in slugs for other in slugs
        ]
        with tempfile.TemporaryDirectory() as folder:
            page = StatsPage(Path(folder))
            page.show()
            page._display(snapshot)
            for width, height in ((620, 450), (1200, 760)):
                page.resize(width, height)
                self.app.processEvents()
                self.app.processEvents()
                matrix = page.matrix
                self.assertEqual(matrix.model().columnCount(), 24)
                self.assertEqual(matrix.model().rowCount(), 23)
                self.assertEqual(matrix.horizontalScrollBarPolicy(),
                                 Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                self.assertEqual(matrix.verticalScrollBarPolicy(),
                                 Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                self.assertLessEqual(sum(matrix.columnWidth(i) for i in range(24)),
                                     matrix.viewport().width())
                self.assertLessEqual(sum(matrix.rowHeight(i) for i in range(23)),
                                     matrix.viewport().height())
            wheel = QWheelEvent(
                QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, 120),
                Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier,
                Qt.ScrollPhase.ScrollUpdate, False,
            )
            matrix.wheelEvent(wheel)
            self.app.processEvents()
            self.assertGreater(matrix.zoom_factor, 1.0)
            self.assertEqual(matrix.horizontalScrollBarPolicy(),
                             Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.assertGreater(sum(matrix.columnWidth(i) for i in range(24)),
                               matrix.viewport().width())
            matrix.set_zoom(1.0)
            self.app.processEvents()
            self.assertEqual(matrix.horizontalScrollBarPolicy(),
                             Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            page.shutdown()
            page.close()


if __name__ == "__main__":
    unittest.main()
