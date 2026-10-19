from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aoevillager.guide_data import GuideSyncError
from scripts.prepare_guide_bundle import prepare


def guide(guide_id: str, title: str) -> dict:
    return {"id": guide_id, "title": title, "civ": "ENG", "steps": [], "author": "Example"}


class PrepareGuideBundleTests(unittest.TestCase):
    def test_merge_deduplicates_ids_and_replaces_existing_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / "old.json"
            new = root / "new.json"
            output = root / "bundle.json"
            old.write_text(json.dumps({"builds": [guide("build0001", "Old")]}), encoding="utf-8")
            new.write_text(json.dumps([guide("build0001", "New"), guide("build0002", "Second")]),
                           encoding="utf-8")
            self.assertEqual(prepare([old, new], output, merge=False), 2)
            self.assertEqual([item["title"] for item in json.loads(output.read_text(encoding="utf-8"))["builds"]],
                             ["New", "Second"])

    def test_rejects_invalid_export_without_changing_previous_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "bundle.json"
            output.write_text("previous", encoding="utf-8")
            incoming = root / "invalid.json"
            incoming.write_text(json.dumps([{"id": "build0001", "title": "Missing steps", "civ": "ENG"}]),
                                encoding="utf-8")
            with self.assertRaises(GuideSyncError):
                prepare([incoming], output, merge=False)
            self.assertEqual(output.read_text(encoding="utf-8"), "previous")


if __name__ == "__main__":
    unittest.main()
