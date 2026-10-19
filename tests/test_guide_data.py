from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aoevillager.guide_data import (
    GuideStore, GuideSyncError, build_id_from_url, icon_path, image_paths,
)


def build(build_id: str, civ: str) -> dict:
    return {
        "id": build_id,
        "title": f"Guide {build_id}",
        "civ": civ,
        "steps": [{"age": 1, "type": "age", "steps": [{"time": "0:00", "description": "Start"}]}],
    }


class GuideDataTests(unittest.TestCase):
    def test_only_original_site_links_and_icons_are_accepted(self) -> None:
        self.assertEqual(
            build_id_from_url("https://aoe4guides.com/builds/abcDEF123?ref=example"),
            "abcDEF123",
        )
        with self.assertRaises(ValueError):
            build_id_from_url("https://evil.example/builds/abcDEF123")
        self.assertEqual(icon_path("https://aoe4guides.com/assets/pictures/resource/sheep.webp"),
                         "/assets/pictures/resource/sheep.webp")
        self.assertIsNone(icon_path("https://evil.example/assets/pictures/resource/sheep.webp"))
        self.assertIsNone(icon_path("/assets/pictures/../secret.webp"))

    def test_image_parser_only_collects_safe_icons(self) -> None:
        data = [build("abcDEF123", "ENG")]
        data[0]["steps"][0]["steps"][0]["description"] = (
            '<img src="/assets/pictures/resource/sheep.webp">'
            '<img src="https://evil.example/stolen.webp">'
        )
        self.assertEqual(image_paths(data), {"/assets/pictures/resource/sheep.webp"})

    def test_sync_replaces_snapshot_only_after_all_civs_succeed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = GuideStore(Path(temp))
            store.save({"version": 1, "synced_at": "old", "builds": [build("existing01", "ENG")],
                        "manual_ids": []})
            original = store.index_file.read_bytes()
            with patch("aoevillager.guide_data.CIVILIZATIONS", {"ENG": "英格兰", "FRE": "法兰西"}), \
                 patch("aoevillager.guide_data._get_json", side_effect=[
                     [build("newbuild01", "ENG")], GuideSyncError("remote failed")
                 ]), patch("aoevillager.guide_data.time.sleep"):
                with self.assertRaises(GuideSyncError):
                    store.sync_public(lambda _: None)
            self.assertEqual(store.index_file.read_bytes(), original)

    def test_import_file_persists_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            store = GuideStore(folder / "cache")
            imported = folder / "provided.json"
            imported.write_text(json.dumps({"builds": [build("abcDEF123", "ENG")]}), encoding="utf-8")
            count, failures = store.import_file(imported, lambda _: None)
            self.assertEqual((count, failures), (1, 0))
            self.assertEqual(store.load()["builds"][0]["id"], "abcDEF123")

    def test_packaged_snapshot_takes_precedence_over_legacy_local_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            store = GuideStore(folder / "cache", prefer_bundled=True)
            store.save({"version": 1, "synced_at": "old", "builds": [build("legacy123", "ENG")]})
            bundled = folder / "bundled.json"
            bundled.write_text(json.dumps({
                "version": 1, "synced_at": "new", "builds": [build("packaged1", "FRE")],
            }), encoding="utf-8")
            store.bundle_file = bundled
            self.assertEqual([item["id"] for item in store.load()["builds"]], ["packaged1"])
            self.assertEqual(json.loads(store.index_file.read_text(encoding="utf-8"))["builds"][0]["id"],
                             "legacy123")

    def test_icons_are_bundled_not_downloaded_on_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = GuideStore(Path(temp))
            icon = store.cached_icon("/assets/pictures/resource/sheep.webp")
            self.assertIsNotNone(icon)
            self.assertTrue(icon.is_file())
            self.assertTrue(store.flag("ENG", large=True).is_file())


if __name__ == "__main__":
    unittest.main()
