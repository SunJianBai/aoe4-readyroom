from __future__ import annotations

import logging
import threading

from PyQt6.QtCore import QObject, pyqtSignal
from pynput import keyboard


LOGGER = logging.getLogger(__name__)
MODIFIERS = {"CTRL", "ALT", "SHIFT", "WIN"}
SPECIAL_KEYS = {
    "SPACE",
    "TAB",
    "ENTER",
    "ESC",
    "BACKSPACE",
    "DELETE",
    "HOME",
    "END",
    "PAGEUP",
    "PAGEDOWN",
    "UP",
    "DOWN",
    "LEFT",
    "RIGHT",
}


def parse_hotkey(text: str) -> frozenset[str]:
    """将 Qt 的 Ctrl+Alt+F6 形式转换为可匹配的键集合。"""

    aliases = {
        "CONTROL": "CTRL",
        "META": "WIN",
        "CMD": "WIN",
        "COMMAND": "WIN",
        "ESCAPE": "ESC",
        "RETURN": "ENTER",
        "PGUP": "PAGEUP",
        "PGDOWN": "PAGEDOWN",
        "DEL": "DELETE",
    }
    parts = [part.strip().upper() for part in text.split("+") if part.strip()]
    tokens = frozenset(aliases.get(part, part) for part in parts)
    if not tokens:
        raise ValueError("快捷键不能为空")
    non_modifiers = tokens - MODIFIERS
    if len(non_modifiers) != 1:
        raise ValueError("快捷键需要包含一个非修饰键")
    key = next(iter(non_modifiers))
    valid = (
        len(key) == 1
        or key in SPECIAL_KEYS
        or (key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24)
    )
    if not valid:
        raise ValueError(f"暂不支持键 {key}")
    return tokens


class GlobalHotkeyManager(QObject):
    """使用 pynput 监听 Windows 全局键盘事件。"""

    triggered = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, shortcut: str) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._required = parse_hotkey(shortcut)
        self._pressed: set[str] = set()
        self._latched = False
        self._suspensions: set[str] = set()
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._listener.start()
            LOGGER.info("Global hotkey listener started")
        except Exception as exc:  # pragma: no cover - depends on OS input backend
            LOGGER.exception("Global hotkey listener failed")
            self.error.emit(f"无法注册全局快捷键：{exc}")

    def set_shortcut(self, shortcut: str) -> None:
        required = parse_hotkey(shortcut)
        with self._lock:
            self._required = required
            self._latched = False

    def set_suspended(self, suspended: bool, reason: str = "editor") -> None:
        with self._lock:
            if suspended:
                self._suspensions.add(reason)
            else:
                self._suspensions.discard(reason)
            if suspended:
                self._latched = False

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode, injected: bool = False) -> None:
        if injected:
            return
        token = self._key_token(key)
        if token is None:
            return
        should_trigger = False
        with self._lock:
            self._pressed.add(token)
            matched = self._required.issubset(self._pressed)
            if matched and not self._latched and not self._suspensions:
                self._latched = True
                should_trigger = True
        if should_trigger:
            self.triggered.emit()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode, injected: bool = False) -> None:
        if injected:
            return
        token = self._key_token(key)
        if token is None:
            return
        with self._lock:
            self._pressed.discard(token)
            if not self._required.issubset(self._pressed):
                self._latched = False

    @staticmethod
    def _key_token(key: keyboard.Key | keyboard.KeyCode) -> str | None:
        modifier_map = {
            keyboard.Key.ctrl: "CTRL",
            keyboard.Key.ctrl_l: "CTRL",
            keyboard.Key.ctrl_r: "CTRL",
            keyboard.Key.alt: "ALT",
            keyboard.Key.alt_l: "ALT",
            keyboard.Key.alt_r: "ALT",
            keyboard.Key.alt_gr: "ALT",
            keyboard.Key.shift: "SHIFT",
            keyboard.Key.shift_l: "SHIFT",
            keyboard.Key.shift_r: "SHIFT",
            keyboard.Key.cmd: "WIN",
            keyboard.Key.cmd_l: "WIN",
            keyboard.Key.cmd_r: "WIN",
        }
        if key in modifier_map:
            return modifier_map[key]
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                return key.char.upper()
            return None
        name = getattr(key, "name", "")
        name_map = {
            "space": "SPACE",
            "tab": "TAB",
            "enter": "ENTER",
            "esc": "ESC",
            "backspace": "BACKSPACE",
            "delete": "DELETE",
            "home": "HOME",
            "end": "END",
            "page_up": "PAGEUP",
            "page_down": "PAGEDOWN",
            "up": "UP",
            "down": "DOWN",
            "left": "LEFT",
            "right": "RIGHT",
        }
        if name in name_map:
            return name_map[name]
        if name.startswith("f") and name[1:].isdigit():
            return name.upper()
        return None

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            listener.stop()
            listener.join(timeout=0.5)
        LOGGER.info("Global hotkey listener stopped")
