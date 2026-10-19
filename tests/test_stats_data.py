from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from aoevillager.stats_data import (
    StatsError, StatsFilter, StatsStore, WORLD_TO_CODE, fetch_snapshot, is_fresh,
    overall_excluding_mirrors, source_url,
)


def sample_snapshot(filters: StatsFilter = StatsFilter()) -> dict:
    def matchup(civ: str, opponent: str, wins: int, players: int, games: int) -> dict:
        return {
            "civilization": civ, "other_civilization": opponent,
            "win_rate": 100 * wins / players, "win_count": wins,
            "player_games_count": players, "games_count": games,
        }

    return {
        "version": 1,
        "requested": {"patch": filters.patch, "rank_level": filters.rank_level,
                      "rating": filters.rating},
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "patch": "10604,10884",
        "civilizations": [
            {"civilization": "english", "win_rate": 52.0, "pick_rate": 10.0,
             "games_count": 1000, "duration_median": 1200},
            {"civilization": "french", "win_rate": 48.0, "pick_rate": 8.0,
             "games_count": 800, "duration_median": 1300},
        ],
        "matchups": [
            matchup("english", "english", 50, 100, 50),
            matchup("english", "french", 63, 105, 100),
            matchup("french", "english", 42, 105, 100),
            matchup("french", "french", 50, 100, 50),
        ],
    }


class StatsDataTests(unittest.TestCase):
    def test_two_documented_requests_share_filters(self) -> None:
        filters = StatsFilter(patch="10604", rank_level="≥gold")
        sample = sample_snapshot(filters)
        payloads = [
            {"patch": sample["patch"], "data": sample["civilizations"]},
            {"patch": sample["patch"], "data": sample["matchups"]},
        ]
        with patch("aoevillager.stats_data._get_json", side_effect=payloads) as get:
            result = fetch_snapshot(filters)
        self.assertEqual(get.call_count, 2)
        for call in get.call_args_list:
            self.assertIn("patch=10604", call.args[0])
            self.assertIn("rank_level=%E2%89%A5gold", call.args[0])
        self.assertEqual(len(result["matchups"]), 4)

    def test_total_excludes_mirrors_using_player_games(self) -> None:
        sample = sample_snapshot()
        rate, games = overall_excluding_mirrors(sample["matchups"], "english")
        self.assertAlmostEqual(rate, 60.0)
        self.assertEqual(games, 100)

    def test_cache_is_keyed_by_filter_and_keeps_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = StatsStore(Path(folder))
            filters = StatsFilter()
            snapshot = sample_snapshot(filters)
            store.save(filters, snapshot)
            self.assertEqual(store.load(filters), snapshot)
            self.assertIsNone(store.load(StatsFilter(rank_level="gold")))
            self.assertTrue(is_fresh(snapshot))
            snapshot["fetched_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            self.assertFalse(is_fresh(snapshot))
            snapshot["fetched_at"] = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
            self.assertFalse(is_fresh(snapshot))
            snapshot["fetched_at"] = "invalid"
            store.save(filters, snapshot)
            with self.assertRaises(StatsError):
                store.load(filters)

    def test_mapping_and_source_link(self) -> None:
        self.assertEqual(len(WORLD_TO_CODE), 23)
        self.assertEqual(WORLD_TO_CODE["ayyubids"], "AYY")
        self.assertIn("/matchups/english/french?patch=10604",
                      source_url(StatsFilter(patch="10604"), "english", "french"))
        with self.assertRaises(ValueError):
            StatsFilter(rank_level="gold", rating=">1200")


if __name__ == "__main__":
    unittest.main()
