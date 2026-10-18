from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Sequence

from PyQt6.QtCore import QPoint, QSettings, QSize

from .cycle import normalize_cycle_step
from .hotkeys import parse_hotkey


DEFAULT_CUSTOM_KEYS = ("CTRL+0", "F11", "Q", "Q", "0", "CTRL+ALT+0")
NATION_PRESETS = {
    "regular": ("常规", 20.0),
    "golden_horde": ("金帐汗国", 37.0),
    "france": ("法兰西", 17.0),
}
CUSTOM_NATION = "custom"


@dataclass(slots=True)
class AppSettings:
    mode: str = "simple"
    toggle_hotkey: str = "F6"
    tc_key: str = "H"
    train_key: str = "Q"
    simple_nation: str = "regular"
    train_time_s: float = 20.0
    villagers_per_round: int = 2
    custom_keys: tuple[str, ...] = field(default_factory=lambda: DEFAULT_CUSTOM_KEYS)
    custom_gap_ms: int = 2
    custom_period_s: float = 40.0
    overlay_visible: bool = True
    overlay_x: int | None = None
    overlay_y: int | None = None
    overlay_width: int = 340
    overlay_height: int = 88
    overlay_opacity: int = 100

    @property
    def simple_period_s(self) -> float:
        return self.train_time_s * self.villagers_per_round

    @property
    def simple_steps(self) -> tuple[str, ...]:
        return ("CTRL+0", self.tc_key) + (self.train_key,) * self.villagers_per_round + ("0", "CTRL+ALT+0")


class SettingsStore:
    def __init__(self) -> None:
        self._settings = QSettings("AOEvillager", "AOEvillager")
        self.values = self._load()

    def _load(self) -> AppSettings:
        value = self._settings.value
        mode = str(value("mode", "simple"))
        if mode not in {"simple", "custom"}:
            mode = "simple"
        toggle_hotkey = str(value("toggle_hotkey", "F6"))
        try:
            parse_hotkey(toggle_hotkey)
        except ValueError:
            toggle_hotkey = "F6"
        custom_keys = DEFAULT_CUSTOM_KEYS
        try:
            stored = json.loads(str(value("custom/keys", "")))
            if isinstance(stored, list) and stored and all(isinstance(key, str) for key in stored):
                custom_keys = tuple(normalize_cycle_step(key) for key in stored)
        except (TypeError, ValueError):
            pass
        train_time_s = self._float(value("simple/train_time_s", 20.0), 20.0, 0.1, 3600.0)
        return AppSettings(
            mode=mode,
            toggle_hotkey=toggle_hotkey,
            tc_key=self._key(value("simple/tc_key", "H"), "H"),
            train_key=self._key(value("simple/train_key", "Q"), "Q"),
            simple_nation=self._nation(value("simple/nation"), train_time_s),
            train_time_s=train_time_s,
            villagers_per_round=self._int(value("simple/villagers_per_round", 2), 2, 1, 100),
            custom_keys=custom_keys,
            custom_gap_ms=self._int(value("custom/gap_ms", 2), 2, 0, 1000),
            custom_period_s=self._float(value("custom/period_s", 40.0), 40.0, 0.1, 3600.0),
            overlay_visible=self._bool(value("overlay/visible", True)),
            overlay_x=self._optional_int(value("overlay/x")),
            overlay_y=self._optional_int(value("overlay/y")),
            overlay_width=self._int(value("overlay/width", 340), 340, 280, 1200),
            overlay_height=self._int(value("overlay/height", 88), 88, 72, 500),
            overlay_opacity=self._int(value("overlay/opacity", 100), 100, 20, 100),
        )

    def set_mode(self, mode: str) -> None:
        if mode not in {"simple", "custom"}:
            raise ValueError("未知模式")
        self.values.mode = mode
        self._settings.setValue("mode", mode)

    def set_hotkey(self, hotkey: str) -> None:
        parse_hotkey(hotkey)
        self.values.toggle_hotkey = hotkey
        self._settings.setValue("toggle_hotkey", hotkey)

    def set_simple(self, tc_key: str, train_key: str, train_time_s: float, count: int, nation: str) -> None:
        tc_key = normalize_cycle_step(tc_key)
        train_key = normalize_cycle_step(train_key)
        if not 0.1 <= train_time_s <= 3600.0 or not 1 <= count <= 100:
            raise ValueError("训练时间或村民数量超出允许范围")
        if nation not in NATION_PRESETS and nation != CUSTOM_NATION:
            raise ValueError("未知国家预设")
        if nation in NATION_PRESETS and train_time_s != NATION_PRESETS[nation][1]:
            nation = CUSTOM_NATION
        self.values.tc_key = tc_key
        self.values.train_key = train_key
        self.values.simple_nation = nation
        self.values.train_time_s = float(train_time_s)
        self.values.villagers_per_round = int(count)
        self._settings.setValue("simple/tc_key", tc_key)
        self._settings.setValue("simple/train_key", train_key)
        self._settings.setValue("simple/nation", nation)
        self._settings.setValue("simple/train_time_s", train_time_s)
        self._settings.setValue("simple/villagers_per_round", count)

    def set_custom_keys(self, keys: Sequence[str]) -> None:
        normalized = tuple(normalize_cycle_step(key) for key in keys)
        if not normalized:
            raise ValueError("至少保留一个按键步骤")
        self.values.custom_keys = normalized
        self._settings.setValue("custom/keys", json.dumps(normalized, ensure_ascii=False))

    def set_custom_timing(self, gap_ms: int, period_s: float) -> None:
        if not 0 <= gap_ms <= 1000 or not 0.1 <= period_s <= 3600.0:
            raise ValueError("自定义时间超出允许范围")
        self.values.custom_gap_ms = int(gap_ms)
        self.values.custom_period_s = float(period_s)
        self._settings.setValue("custom/gap_ms", gap_ms)
        self._settings.setValue("custom/period_s", period_s)

    def set_overlay_visible(self, visible: bool) -> None:
        self.values.overlay_visible = bool(visible)
        self._settings.setValue("overlay/visible", bool(visible))

    def set_overlay_position(self, position: QPoint) -> None:
        self.values.overlay_x = position.x()
        self.values.overlay_y = position.y()
        self._settings.setValue("overlay/x", position.x())
        self._settings.setValue("overlay/y", position.y())

    def set_overlay_size(self, size: QSize) -> None:
        self.values.overlay_width = size.width()
        self.values.overlay_height = size.height()
        self._settings.setValue("overlay/width", size.width())
        self._settings.setValue("overlay/height", size.height())

    def set_overlay_opacity(self, percent: int) -> None:
        self.values.overlay_opacity = percent
        self._settings.setValue("overlay/opacity", percent)

    @staticmethod
    def _nation(raw: object, train_time_s: float) -> str:
        if raw == CUSTOM_NATION:
            return CUSTOM_NATION
        if raw in NATION_PRESETS and train_time_s == NATION_PRESETS[raw][1]:
            return str(raw)
        if raw is None:
            for nation, (_, seconds) in NATION_PRESETS.items():
                if train_time_s == seconds:
                    return nation
        return CUSTOM_NATION

    @staticmethod
    def _key(raw: object, fallback: str) -> str:
        try:
            return normalize_cycle_step(str(raw))
        except ValueError:
            return fallback

    @staticmethod
    def _int(raw: object, fallback: int, minimum: int, maximum: int) -> int:
        try:
            return min(max(int(raw), minimum), maximum)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _float(raw: object, fallback: float, minimum: float, maximum: float) -> float:
        try:
            value = float(raw)
            if not minimum <= value <= maximum:
                return fallback
            return value
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _optional_int(raw: object) -> int | None:
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _bool(raw: object) -> bool:
        return raw is True or str(raw).strip().lower() in {"1", "true", "yes", "on"}
