"""Offline building catalog migrated from the standalone AOE4 practice page."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


AGE_NAMES = {"Q": "时代 I", "W": "时代 II", "E": "时代 III", "R": "时代 IV"}

# The original page starts with common buildings, then replaces/hides them for
# civilization-specific build menus. Keep those rules separate from the UI.
HIDDEN_COMMON: dict[str, frozenset[str]] = {
    "byzantine": frozenset({"Q-A"}),
    "knights": frozenset({"Q-D", "Q-E", "E-Z"}),
    "macedonian": frozenset({"Q-S", "W-Q", "R-Q"}),
    "malians": frozenset({"Q-Z"}),
    "mongol": frozenset({
        "Q-Q", "Q-W", "Q-E", "Q-R", "Q-A", "Q-X", "Q-C",
        "W-Z", "W-X", "W-C", "W-W", "W-S", "E-Z", "R-Q",
    }),
    "russian": frozenset({"Q-W", "Q-Z", "Q-X", "Q-C"}),
    "japanese": frozenset({"Q-Q", "Q-W", "Q-R", "W-Q", "E-Z"}),
    "sengoku": frozenset({"Q-Q", "Q-W", "Q-R", "W-W", "E-Z", "E-Q"}),
    "tughlaq": frozenset({"Q-W", "Q-E", "Q-R", "E-Z"}),
    "goldenhorde": frozenset({
        "Q-Q", "Q-W", "Q-E", "Q-R", "Q-A", "Q-Z",
        "W-Z", "W-X", "W-C", "W-S", "E-Z", "R-Q",
    }),
    "delhi": frozenset({"E-Q"}),
}


@dataclass(frozen=True)
class Civilization:
    id: str
    name: str
    icon: Path


@dataclass(frozen=True)
class Building:
    id: str
    key: str
    name: str
    civ: str | None
    icon: Path

    @property
    def age_key(self) -> str:
        return self.key.split("-", 1)[0]

    @property
    def action_key(self) -> str:
        return self.key.split("-", 2)[1]


class PracticeCatalog:
    def __init__(self, asset_dir: Path) -> None:
        data = json.loads((asset_dir / "catalog.json").read_text(encoding="utf-8"))
        missing = sorted({
            item["icon"] for group in ("civilizations", "buildings")
            for item in data[group] if not (asset_dir / item["icon"]).is_file()
        })
        if missing:
            raise FileNotFoundError(f"快捷键练习缺少 {len(missing)} 张图标，例如：{missing[0]}")
        self.civilizations = tuple(
            Civilization(item["id"], item["name"], asset_dir / item["icon"])
            for item in data["civilizations"]
        )
        self.buildings = tuple(
            Building(item["id"], item["key"], item["name"], item["civ"], asset_dir / item["icon"])
            for item in data["buildings"]
        )

    def available(self, civilization: str) -> tuple[Building, ...]:
        hidden = HIDDEN_COMMON.get(civilization, frozenset())
        return tuple(
            building for building in self.buildings
            if (building.civ == civilization)
            or (building.civ is None and building.id not in hidden)
        )
