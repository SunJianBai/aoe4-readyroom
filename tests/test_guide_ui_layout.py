from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QObject, QUrl
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import QApplication

from aoevillager.guide_ui import CivCard, GuideAgeRow, GuidePage, GuideStepRow, ResourcePill


class _TopLevelCivCardWatcher(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.shown = 0

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if (event.type() == QEvent.Type.Show and isinstance(obj, CivCard)
                and obj.isWindow() and obj.parentWidget() is None):
            self.shown += 1
        return False


class GuideLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_civilization_cards_never_appear_as_separate_windows(self) -> None:
        watcher = _TopLevelCivCardWatcher()
        self.app.installEventFilter(watcher)
        try:
            with tempfile.TemporaryDirectory() as folder:
                page = GuidePage(Path(folder))
                page.show()
                self.app.processEvents()
                self.assertEqual(watcher.shown, 0)
                self.assertTrue(page.civ_cards)
                self.assertTrue(all(card.isVisible() for card in page.civ_cards))
                page.close()
        finally:
            self.app.removeEventFilter(watcher)

    def test_list_cards_scroll_without_overlapping(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            page = GuidePage(Path(folder))
            page.data["builds"] = [
                {"id": f"build{i:04d}", "civ": "ZXL", "title": f"Build {i}",
                 "author": "Author", "views": i,
                 "ageTimings": {"feudal": {"t": 240}}}
                for i in range(10)
            ]
            page.resize(850, 720)
            page.show()
            page._show_civ("ZXL")
            self.app.processEvents()
            first = page.cards_layout.itemAt(0).widget()
            second = page.cards_layout.itemAt(1).widget()
            self.assertGreaterEqual(second.y(), first.y() + first.height() + 8)
            self.assertGreater(page.cards_area.height(), page.cards_area.parent().height())
            page.close()

    def test_native_build_table_keeps_tints_icons_and_age_rows(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            page = GuidePage(Path(folder))
            page.data["builds"] = [{
                "id": "example01", "civ": "ENG", "title": "Example",
                "steps": [
                    {"age": 1, "type": "age", "steps": [
                        {"time": "0:00", "food": "5", "gold": "1",
                         "description": '<img src="/assets/pictures/resource/sheep.webp" class="icon-none">'},
                    ]},
                    {"age": 1, "type": "ageUp", "steps": [
                        {"time": "4:00", "food": "3", "gold": "3", "description": "Advance"},
                    ]},
                ],
            }]
            page.resize(760, 700)
            page.show()
            page._show_detail("example01")
            self.app.processEvents()
            steps = page.detail.widget().findChildren(GuideStepRow)
            ages = page.detail.widget().findChildren(GuideAgeRow)
            self.assertEqual((len(steps), len(ages)), (2, 2))
            pills = steps[1].findChildren(ResourcePill)
            self.assertEqual({pill.key: pill.change for pill in pills}["food"], "down")
            self.assertEqual({pill.key: pill.change for pill in pills}["gold"], "up")
            image = steps[0].description.document().resource(
                QTextDocument.ResourceType.ImageResource,
                QUrl("guideicon:/resource/sheep.webp"),
            )
            self.assertFalse(image.isNull())
            self.assertGreaterEqual(steps[0].description.height() + 4,
                                    steps[0].description.document().size().height())
            page.close()


if __name__ == "__main__":
    unittest.main()
