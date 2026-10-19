from __future__ import annotations

import unittest

from aoevillager.guide_table import build_table_rows, resource_change, villager_count


class GuideTableTests(unittest.TestCase):
    def test_resource_counts_and_direction(self) -> None:
        self.assertEqual(villager_count("~4+3"), 7)
        self.assertEqual(villager_count("5+"), 5)
        self.assertEqual(villager_count("<br>"), 0)
        self.assertEqual(resource_change("2", "5"), "down")
        self.assertEqual(resource_change("6", "5"), "up")
        self.assertEqual(resource_change("5+", "5"), "same")
        self.assertEqual(resource_change("5", None), "initial")

    def test_age_transition_carries_changes_across_sections(self) -> None:
        build = {"steps": [
            {"age": 1, "type": "age", "steps": [
                {"time": "0:00", "food": "5", "gold": "1", "description": "Start"},
            ]},
            {"age": 1, "type": "ageUp", "steps": [
                {"time": "4:00", "food": "3", "gold": "3", "description": "Advance"},
            ], "gameplan": "Keep scouting"},
        ]}
        rows = build_table_rows(build)
        self.assertEqual([row["kind"] for row in rows],
                         ["step", "advance", "step", "note", "arrival"])
        self.assertEqual(rows[0]["villagers"], 6)
        self.assertEqual(rows[2]["villagers"], 6)
        self.assertEqual(rows[2]["changes"]["food"], "down")
        self.assertEqual(rows[2]["changes"]["gold"], "up")
        self.assertTrue(rows[2]["in_age"])
        self.assertEqual(rows[1]["label"], "升级至封建时代")
        self.assertEqual(rows[-1]["label"], "已进入封建时代")


if __name__ == "__main__":
    unittest.main()
