"""Small, cached client for AoE4 World's documented aggregate statistics API."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://aoe4world.com/api/v0/stats/rm_solo"
SOURCE_ROOT = "https://aoe4world.com/stats/rm_solo"
USER_AGENT = "AOE4Toolbox/1.1 (civilization stats; https://aoe4world.com/api)"

# The existing guide flag codes also work for the statistics page. Keep the
# mapping explicit: the two sites do not use the same civilization identifiers.
WORLD_TO_CODE = {
    "abbasid_dynasty": "ABB", "ayyubids": "AYY", "byzantines": "BYZ",
    "chinese": "CHI", "delhi_sultanate": "DEL", "english": "ENG",
    "french": "FRE", "golden_horde": "GOH", "house_of_lancaster": "HOL",
    "holy_roman_empire": "HRE", "japanese": "JAP", "jeanne_darc": "JDA",
    "jin_dynasty": "JIN", "knights_templar": "KTE", "macedonian_dynasty": "MAC",
    "malians": "MAL", "mongols": "MON", "order_of_the_dragon": "DRA",
    "ottomans": "OTT", "rus": "RUS", "sengoku_daimyo": "SEN",
    "tughlaq_dynasty": "TUG", "zhu_xis_legacy": "ZXL",
}

RANK_LEVELS = (
    ("全部段位", ""), ("青铜", "bronze"), ("白银", "silver"),
    ("黄金", "gold"), ("白金", "platinum"), ("钻石", "diamond"),
    ("征服者", "conqueror"), ("黄金及以上", "≥gold"),
    ("白金及以上", "≥platinum"), ("钻石及以上", "≥diamond"),
    ("征服者及以上", "≥conqueror"), ("征服者 IV 及以上", "≥conqueror_4"),
)
RATINGS = (
    ("全部分数", ""), ("500–699", "500-699"), ("700–999", "700-999"),
    ("1000–1199", "1000-1199"), ("1200–1399", "1200-1399"),
    ("高于 1000", ">1000"), ("高于 1200", ">1200"),
    ("高于 1400", ">1400"), ("高于 1700", ">1700"),
)


class StatsError(Exception):
    """The remote or cached snapshot cannot be displayed safely."""


@dataclass(frozen=True)
class StatsFilter:
    patch: str = ""
    rank_level: str = ""
    rating: str = ""

    def __post_init__(self) -> None:
        if self.rank_level and self.rating:
            raise ValueError("段位和分数筛选不能同时启用")
        if self.rank_level not in {value for _, value in RANK_LEVELS}:
            raise ValueError("不支持的段位筛选")
        if self.rating not in {value for _, value in RATINGS}:
            raise ValueError("不支持的分数筛选")
        if self.patch and self.patch != "any" and not self.patch.isdecimal():
            raise ValueError("补丁编号必须是数字")

    def query(self) -> str:
        parameters = {key: value for key, value in asdict(self).items() if value}
        return urlencode(parameters)


def _get_json(url: str) -> dict:
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise StatsError(f"统计接口返回 HTTP {response.status}")
            payload = json.load(response)
    except HTTPError as exc:
        raise StatsError(f"统计接口返回 HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise StatsError(f"无法读取 AOE4 World 统计：{exc}") from exc
    if not isinstance(payload, dict):
        raise StatsError("统计接口返回格式不正确")
    return payload


def _valid_rows(payload: dict, kind: str) -> list[dict]:
    rows = payload.get("data")
    if not isinstance(rows, list) or not rows or len(rows) > 2000:
        raise StatsError(f"{kind}统计缺失或数量异常")
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("civilization"), str):
            raise StatsError(f"{kind}统计格式不正确")
        if kind == "对阵" and not isinstance(row.get("other_civilization"), str):
            raise StatsError("对阵统计缺少对手文明")
        rate, count = row.get("win_rate"), row.get("games_count")
        if (not isinstance(rate, (int, float)) or isinstance(rate, bool)
                or not 0 <= rate <= 100 or not isinstance(count, int)
                or isinstance(count, bool) or count < 0):
            raise StatsError(f"{kind}胜率或场次数值异常")
    return rows


def fetch_snapshot(filters: StatsFilter) -> dict:
    """Exactly two documented aggregate requests, never one per civilization."""
    query = filters.query()
    suffix = f"?{query}" if query else ""
    civilizations = _get_json(f"{API_ROOT}/civilizations{suffix}")
    matchups = _get_json(f"{API_ROOT}/matchups{suffix}")
    civ_rows = _valid_rows(civilizations, "文明")
    matchup_rows = _valid_rows(matchups, "对阵")
    if civilizations.get("patch") != matchups.get("patch"):
        raise StatsError("两份统计的补丁范围不一致，请稍后重试")
    return {
        "version": 1,
        "requested": asdict(filters),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "patch": str(matchups.get("patch") or ""),
        "civilizations": civ_rows,
        "matchups": matchup_rows,
    }


def overall_excluding_mirrors(rows: list[dict], civilization: str) -> tuple[float, int] | None:
    """Replicate the site's 'Total Excl. Mirrors' using API player counts."""
    relevant = [row for row in rows if row.get("civilization") == civilization
                and row.get("other_civilization") != civilization]
    if not relevant or any(not isinstance(row.get("win_count"), int)
                           or not isinstance(row.get("player_games_count"), int)
                           for row in relevant):
        return None
    wins = sum(row["win_count"] for row in relevant)
    player_games = sum(row["player_games_count"] for row in relevant)
    games = sum(row["games_count"] for row in relevant)
    return (100 * wins / player_games, games) if player_games else None


def source_url(filters: StatsFilter, civ: str = "", opponent: str = "") -> str:
    path = "/matchups"
    if civ and opponent:
        path += f"/{civ}/{opponent}"
    query = filters.query()
    return f"{SOURCE_ROOT}{path}{'?' + query if query else ''}"


class StatsStore:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def path_for(self, filters: StatsFilter) -> Path:
        key = json.dumps(asdict(filters), sort_keys=True, ensure_ascii=False).encode("utf-8")
        return self.folder / f"stats-{hashlib.sha256(key).hexdigest()[:16]}.json"

    def load(self, filters: StatsFilter) -> dict | None:
        path = self.path_for(filters)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("cache is not an object")
            if data.get("version") != 1 or data.get("requested") != asdict(filters):
                raise ValueError("cache version/filter mismatch")
            fetched = datetime.fromisoformat(data.get("fetched_at", ""))
            if fetched.tzinfo is None:
                raise ValueError("cache timestamp lacks timezone")
            _valid_rows({"data": data.get("civilizations")}, "文明")
            _valid_rows({"data": data.get("matchups")}, "对阵")
            return data
        except (OSError, ValueError, TypeError, StatsError) as exc:
            raise StatsError(f"本地胜率缓存无法读取：{exc}") from exc

    def save(self, filters: StatsFilter, snapshot: dict) -> None:
        if snapshot.get("requested") != asdict(filters):
            raise StatsError("筛选条件与统计结果不一致")
        self.folder.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(prefix=".stats-", suffix=".json", dir=self.folder)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(snapshot, stream, ensure_ascii=False, separators=(",", ":"))
            os.replace(temp_name, self.path_for(filters))
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def is_fresh(snapshot: dict, now: datetime | None = None) -> bool:
    try:
        fetched = datetime.fromisoformat(snapshot["fetched_at"])
        if fetched.tzinfo is None:
            return False
        age = (now or datetime.now(timezone.utc)) - fetched
        return timedelta(0) <= age < timedelta(hours=24)
    except (KeyError, TypeError, ValueError):
        return False
