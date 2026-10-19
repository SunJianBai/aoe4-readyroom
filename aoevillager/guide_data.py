"""Manual, offline-first import of the public AOE4 Guides API.

The public list API intentionally has no pagination.  A sync reads at most the
ten published results exposed for each civilization; it never walks the site's
sitemap or enumerates build IDs.  Individual links can be added explicitly.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


API_ROOT = "https://aoe4-guides-api-7h2vti5ckq-ey.a.run.app"
SOURCE_ROOT = "https://aoe4guides.com"
BUILD_ID = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
ICON_PATH = re.compile(r"/assets/pictures/[A-Za-z0-9_./-]+\.webp\Z", re.I)

# The names shown here are interface labels, not translations of user guides.
CIVILIZATIONS = {
    "ENG": "英格兰", "FRE": "法兰西", "RUS": "罗斯", "MAL": "马里",
    "DEL": "德里苏丹", "HRE": "神圣罗马帝国", "ABB": "黑衣大食",
    "OTT": "奥斯曼", "CHI": "中国", "MON": "蒙古", "BYZ": "拜占庭",
    "JAP": "日本", "AYY": "阿尤布", "JDA": "圣女贞德", "ZXL": "朱子遗训",
    "DRA": "龙之骑士团", "HOL": "兰开斯特王朝", "KTE": "圣殿骑士团",
    "GOH": "金帐汗国", "SEN": "战国大名", "MAC": "马其顿王朝",
    "TUG": "图格鲁克王朝", "JIN": "金朝", "VIK": "维京人",
    "SCO": "苏格兰人",
}


class GuideSyncError(Exception):
    """A remote response could not be used as a complete snapshot."""


def source_url(build_id: str) -> str:
    return f"{SOURCE_ROOT}/builds/{quote(build_id)}"


def build_id_from_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.hostname not in {"aoe4guides.com", "www.aoe4guides.com"}:
        raise ValueError("请粘贴 aoe4guides.com 的 HTTPS 流程链接")
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2 or parts[0] != "builds" or not BUILD_ID.fullmatch(parts[1]):
        raise ValueError("链接不是有效的单篇流程地址")
    return parts[1]


def icon_path(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme and (parsed.scheme != "https" or parsed.hostname not in {
        "aoe4guides.com", "www.aoe4guides.com"
    }):
        return None
    path = parsed.path
    if not ICON_PATH.fullmatch(path) or ".." in path.split("/"):
        return None
    return path


class _ImageFinder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paths: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "img":
            return
        path = icon_path(dict(attrs).get("src") or "")
        if path:
            self.paths.add(path)


def image_paths(builds: list[dict]) -> set[str]:
    finder = _ImageFinder()
    for build in builds:
        for section in build.get("steps") or []:
            if not isinstance(section, dict):
                continue
            finder.feed(str(section.get("gameplan") or ""))
            for step in section.get("steps") or []:
                if isinstance(step, dict):
                    finder.feed(str(step.get("description") or ""))
    return finder.paths


def _get_json(url: str) -> object:
    request = Request(url, headers={"User-Agent": "AOE4Toolbox/1.0 (manual guide sync)"})
    try:
        with urlopen(request, timeout=25) as response:
            if response.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                raise GuideSyncError("网站返回的不是 JSON 数据")
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 429:
            raise GuideSyncError("网站接口已限流；本地数据未改动，请稍后再试") from exc
        raise GuideSyncError(f"网站接口返回 HTTP {exc.code}；本地数据未改动") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GuideSyncError(f"获取流程失败：{exc}；本地数据未改动") from exc


def _validate_build(value: object) -> dict:
    if not isinstance(value, dict):
        raise GuideSyncError("流程数据格式不正确")
    build_id = value.get("id")
    if not isinstance(build_id, str) or not BUILD_ID.fullmatch(build_id):
        raise GuideSyncError("流程缺少有效 ID")
    if not isinstance(value.get("title"), str) or not isinstance(value.get("steps"), list):
        raise GuideSyncError(f"流程 {build_id} 缺少标题或步骤")
    return value


class GuideStore:
    def __init__(self, folder: Path, *, prefer_bundled: bool = False) -> None:
        self.folder = folder
        self.index_file = folder / "guides.json"
        self.assets = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets" / "guides"
        self.bundle_file = self.assets / "guides.json"
        self.prefer_bundled = prefer_bundled
        self._icon_info: dict[str, dict] | None = None

    def load(self) -> dict:
        filename = self.bundle_file if self.prefer_bundled and self.bundle_file.is_file() else self.index_file
        if not filename.is_file():
            return {"version": 1, "synced_at": None, "builds": [], "manual_ids": []}
        try:
            data = json.loads(filename.read_text(encoding="utf-8"))
            if data.get("version") != 1 or not isinstance(data.get("builds"), list):
                raise ValueError("版本或格式不正确")
            return data
        except (OSError, ValueError) as exc:
            raise GuideSyncError(f"流程资料无法读取（{filename}）：{exc}") from exc

    def save(self, data: dict) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(prefix=".guides-", suffix=".json", dir=self.folder)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.index_file)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def cached_icon(self, path: str) -> Path | None:
        safe = icon_path(path)
        if not safe:
            return None
        return self.assets / safe.removeprefix("/assets/")

    def flag(self, civ: str, *, large: bool = False) -> Path:
        size = "large" if large else "small"
        return self.assets / "flags" / f"{civ.lower()}-{size}.webp"

    def icon_info(self, path: str) -> dict:
        if self._icon_info is None:
            self._icon_info = {}
            for filename in (self.assets / "metadata").glob("*.json"):
                try:
                    entries = json.loads(filename.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict):
                            safe = icon_path(str(entry.get("imgSrc") or ""))
                            if safe:
                                self._icon_info.setdefault(safe, entry)
        return self._icon_info.get(path, {})

    def sync_public(self, progress: Callable[[str], None],
                    cancelled: Callable[[], bool] = lambda: False) -> tuple[int, int]:
        """Sync each civ's exposed top ten, never the site's entire corpus."""
        previous = self.load()
        by_id: dict[str, dict] = {}
        for index, civ in enumerate(CIVILIZATIONS, 1):
            if cancelled():
                raise GuideSyncError("同步已取消；本地数据未改动")
            progress(f"获取 {CIVILIZATIONS[civ]}（{index}/{len(CIVILIZATIONS)}）")
            payload = _get_json(f"{API_ROOT}/builds?civ={civ}&orderBy=score")
            if not isinstance(payload, list) or len(payload) > 10:
                raise GuideSyncError(f"{CIVILIZATIONS[civ]}的列表格式不正确；本地数据未改动")
            for item in payload:
                build = _validate_build(item)
                by_id[build["id"]] = build
            # Stay below the public list endpoint's 30/minute IP limit.
            if index < len(CIVILIZATIONS):
                for _ in range(21):
                    if cancelled():
                        raise GuideSyncError("同步已取消；本地数据未改动")
                    time.sleep(0.1)
        manual_ids = previous.get("manual_ids") or []
        for build in previous["builds"]:
            if build.get("id") in manual_ids and build["id"] not in by_id:
                by_id[build["id"]] = build
        builds = list(by_id.values())
        self.save({
            "version": 1,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "builds": builds,
            "manual_ids": manual_ids,
        })
        return len(builds), 0

    def import_link(self, url: str, progress: Callable[[str], None],
                    cancelled: Callable[[], bool] = lambda: False) -> tuple[int, int]:
        build_id = build_id_from_url(url)
        progress("获取指定流程")
        build = _validate_build(_get_json(f"{API_ROOT}/builds/{quote(build_id)}"))
        if build["id"] != build_id:
            raise GuideSyncError("网站返回了不匹配的流程 ID")
        previous = self.load()
        by_id = {item["id"]: item for item in previous["builds"]}
        by_id[build_id] = build
        manual_ids = list(dict.fromkeys([*previous.get("manual_ids", []), build_id]))
        self.save({**previous, "builds": list(by_id.values()), "manual_ids": manual_ids})
        return len(by_id), 0
    def import_file(self, filename: Path, progress: Callable[[str], None],
                    cancelled: Callable[[], bool] = lambda: False) -> tuple[int, int]:
        """Accept a future authorized JSON export without a network crawl."""
        progress("读取本地批量数据")
        try:
            if filename.stat().st_size > 100_000_000:
                raise GuideSyncError("数据文件超过 100 MB")
            payload = json.loads(filename.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GuideSyncError(f"无法读取数据文件：{exc}") from exc
        builds = payload.get("builds") if isinstance(payload, dict) else payload
        if not isinstance(builds, list) or not builds:
            raise GuideSyncError("批量文件需要是非空流程数组，或包含 builds 数组的对象")
        by_id = {}
        for item in builds:
            build = _validate_build(item)
            by_id[build["id"]] = build
        if cancelled():
            raise GuideSyncError("导入已取消；本地数据未改动")
        self.save({
            "version": 1,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "builds": list(by_id.values()),
            "manual_ids": [],
        })
        return len(by_id), 0

