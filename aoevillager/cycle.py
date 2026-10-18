from __future__ import annotations

import ctypes
import logging
import secrets
import sys
import threading
import time
from ctypes import wintypes
from typing import Callable, Protocol, Sequence

from PyQt6.QtCore import QObject, pyqtSignal

from .input_guard import LowLevelInputGuard


LOGGER = logging.getLogger(__name__)
MIN_UNBLOCKED_PAUSE_S = 0.25


SPECIAL_KEYS: dict[str, int] = {
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "ESC": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
}
MODIFIER_KEYS = {"CTRL": 0x11, "ALT": 0x12, "SHIFT": 0x10, "WIN": 0x5B}
MODIFIER_ORDER = ("CTRL", "ALT", "SHIFT", "WIN")
EXTENDED_KEYS = {"PAGEUP", "PAGEDOWN", "END", "HOME", "LEFT", "UP", "RIGHT", "DOWN", "INSERT", "DELETE", "WIN"}
ALIASES = {
    "RETURN": "ENTER", "ESCAPE": "ESC", "PGUP": "PAGEUP", "PGDOWN": "PAGEDOWN", "DEL": "DELETE",
    "CONTROL": "CTRL", "META": "WIN", "CMD": "WIN", "COMMAND": "WIN",
}


def normalize_single_key(value: str) -> str:
    """Only one physical key, without Ctrl/Alt/Shift/Win combinations."""

    key = ALIASES.get(value.strip().upper(), value.strip().upper())
    if "+" in key or "," in key or not key:
        raise ValueError("单键名称无效；组合键请用 + 连接 2–3 个键")
    if len(key) == 1 and key.isascii() and key.isalnum():
        return key
    if key in SPECIAL_KEYS:
        return key
    if key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        return f"F{int(key[1:])}"
    raise ValueError("支持字母、数字、F1–F24 和常用功能键")


def normalize_cycle_step(value: str) -> str:
    """One cycle step is one key or a chord of two or three distinct keys."""

    parts = value.split("+")
    if not 1 <= len(parts) <= 3:
        raise ValueError("每一步只能设置 1–3 个键，用 + 连接")
    normalized = []
    for part in parts:
        token = ALIASES.get(part.strip().upper(), part.strip().upper())
        if not token:
            raise ValueError("组合键不能包含空键")
        normalized.append(token if token in MODIFIER_KEYS else normalize_single_key(token))
    if len(set(normalized)) != len(normalized):
        raise ValueError("同一组合键不能重复使用相同按键")
    if len(normalized) == 1 and normalized[0] in MODIFIER_KEYS:
        raise ValueError("单键不能只设置 Ctrl、Alt、Shift 或 Win")
    if set(normalized) == {"CTRL", "ALT", "DELETE"}:
        raise ValueError("Windows 安全组合键 Ctrl+Alt+Delete 无法由程序发送")
    # Modifiers must go down before ordinary keys even if entered as Q+Ctrl.
    ordered = [key for key in MODIFIER_ORDER if key in normalized]
    ordered.extend(key for key in normalized if key not in MODIFIER_KEYS)
    return "+".join(ordered)


def virtual_key(key: str) -> int:
    key = ALIASES.get(key.strip().upper(), key.strip().upper())
    if key in MODIFIER_KEYS:
        return MODIFIER_KEYS[key]
    key = normalize_single_key(key)
    if len(key) == 1:
        return ord(key)
    if key.startswith("F") and key[1:].isdigit():
        return 0x70 + int(key[1:]) - 1
    return SPECIAL_KEYS[key]


ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("data", INPUT_UNION)]


class InputBackend(Protocol):
    def block(self) -> None: ...
    def unblock(self) -> None: ...
    def any_input_down(self) -> bool: ...
    def press(self, key: str) -> float: ...
    def release(self, key: str) -> None: ...


class WindowsInput:
    """All BlockInput and SendInput calls must happen on the same worker thread."""

    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("循环点击的键鼠屏蔽功能仅支持 Windows")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._user32.BlockInput.argtypes = [wintypes.BOOL]
        self._user32.BlockInput.restype = wintypes.BOOL
        self._user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        self._user32.SendInput.restype = wintypes.UINT
        self._user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self._user32.GetAsyncKeyState.restype = wintypes.SHORT
        self._tag = secrets.randbits(ctypes.sizeof(ctypes.c_size_t) * 8) or 1
        self._block_input_available = True
        self._blocked_with_api = False
        self._hook_guard: LowLevelInputGuard | None = None

    def block(self) -> None:
        if self._block_input_available:
            if self._user32.BlockInput(True):
                self._blocked_with_api = True
                return
            self._block_input_available = False
            LOGGER.warning("BlockInput unavailable; using short-lived keyboard and mouse hooks")
        guard = LowLevelInputGuard(self._tag)
        guard.activate()
        self._hook_guard = guard

    def unblock(self) -> None:
        if self._blocked_with_api:
            self._blocked_with_api = False
            if not self._user32.BlockInput(False):
                raise OSError(ctypes.get_last_error(), "无法恢复物理键鼠输入")
        elif self._hook_guard is not None:
            guard = self._hook_guard
            self._hook_guard = None
            guard.close()

    def any_input_down(self) -> bool:
        # The high bit reports whether a key is currently held. This includes
        # physical mouse buttons (VK 1–6) and keyboard keys (VK 8–254).
        return any(self._user32.GetAsyncKeyState(vk) & 0x8000 for vk in range(1, 255))

    def press(self, key: str) -> float:
        self._send(key, up=False)
        return time.perf_counter()

    def release(self, key: str) -> None:
        self._send(key, up=True)

    def _send(self, key: str, up: bool) -> None:
        if not up and self._hook_guard is not None and not self._hook_guard.healthy():
            raise RuntimeError("输入保护钩子已退出；本轮停止发送按键")
        normalized = ALIASES.get(key.strip().upper(), key.strip().upper())
        if normalized not in MODIFIER_KEYS:
            normalized = normalize_single_key(normalized)
        flags = self.KEYEVENTF_KEYUP if up else 0
        if normalized in EXTENDED_KEYS:
            flags |= self.KEYEVENTF_EXTENDEDKEY
        event = INPUT(type=1, data=INPUT_UNION(ki=KEYBDINPUT(virtual_key(normalized), 0, flags, 0, self._tag)))
        sent = self._user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
        if sent != 1:
            action = "松开" if up else "按下"
            raise OSError(ctypes.get_last_error(), f"无法{action} {normalized}；目标程序可能以更高权限运行")


class CycleEngine(QObject):
    """Send protected rounds and anchor the next round to a configured step."""

    state_changed = pyqtSignal(bool)
    round_completed = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        backend: InputBackend | None = None,
        suspend_hotkey: Callable[[bool], None] | None = None,
    ) -> None:
        super().__init__()
        self._backend = backend or WindowsInput()
        self._suspend_hotkey = suspend_hotkey or (lambda _suspended: None)
        self._lock = threading.Lock()
        self._keys = ("F11", "Q", "3")
        self._gap_ms = 10
        self._period_s = 20.0
        self._anchor_step_index = 1
        self._running = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def configure(
        self,
        keys: Sequence[str],
        gap_ms: int,
        period_s: float,
        *,
        anchor_step_index: int | None = None,
    ) -> None:
        normalized = tuple(normalize_cycle_step(key) for key in keys)
        if not normalized:
            raise ValueError("循环点击至少需要一个按键")
        if not 0 <= gap_ms <= 1000:
            raise ValueError("相邻步骤间隔须在 0–1000 ms 之间")
        if not 0.1 <= period_s <= 360000.0:
            raise ValueError("循环时间须在 0.1–360000 s 之间")
        anchor = min(1, len(normalized) - 1) if anchor_step_index is None else anchor_step_index
        if not 0 <= anchor < len(normalized):
            raise ValueError("循环计时起点必须是有效步骤")
        with self._lock:
            self._keys = normalized
            self._gap_ms = int(gap_ms)
            self._period_s = float(period_s)
            self._anchor_step_index = anchor

    def toggle(self) -> None:
        if self.is_running:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        with self._lock:
            if self._running or (self._thread and self._thread.is_alive()):
                return
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="pulseclick-cycle", daemon=True)
            self._thread.start()
        LOGGER.info("Cycle engine started")
        self.state_changed.emit(True)

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.5)

    def _run(self) -> None:
        next_at: float | None = None
        try:
            while not self._stop_event.is_set():
                if next_at is not None and self._stop_event.wait(max(0.0, next_at - time.perf_counter())):
                    break
                with self._lock:
                    keys = self._keys
                    gap_ms, period_s = self._gap_ms, self._period_s
                    anchor_step_index = self._anchor_step_index
                anchor_pressed_at = self._run_round(keys, gap_ms, anchor_step_index)
                if anchor_pressed_at is None:
                    self._stop_event.wait(0.01)
                    continue
                self.round_completed.emit()
                # If a long sequence outlasts its period, leave a brief
                # unblocked window so a physical stop hotkey can be received.
                next_at = max(anchor_pressed_at + period_s, time.perf_counter() + MIN_UNBLOCKED_PAUSE_S)
        except Exception as exc:  # pragma: no cover - depends on Windows input backend
            LOGGER.exception("Cycle engine failed")
            self.error.emit(f"循环点击已停止：{exc}")
        finally:
            with self._lock:
                self._running = False
                self._thread = None
            LOGGER.info("Cycle engine stopped")
            self.state_changed.emit(False)

    def _run_round(
        self,
        keys: Sequence[str],
        gap_ms: int,
        anchor_step_index: int,
    ) -> float | None:
        if self._backend.any_input_down():
            return None
        self._suspend_hotkey(True)
        blocked = False
        pressed: list[str] = []
        try:
            self._backend.block()
            blocked = True
            if self._backend.any_input_down():
                return None
            if self._stop_event.is_set():
                return None

            anchor_pressed_at = None
            for index, step in enumerate(keys):
                if index and gap_ms:
                    self._wait_gap(gap_ms)
                chord = normalize_cycle_step(step).split("+")
                for key in chord:
                    pressed_at = self._backend.press(key)
                    pressed.append(key)
                if index == anchor_step_index:
                    anchor_pressed_at = pressed_at
                for key in reversed(chord):
                    self._backend.release(key)
                    pressed.pop()
            return anchor_pressed_at
        finally:
            try:
                for key in reversed(pressed):
                    try:
                        self._backend.release(key)
                    except Exception:
                        LOGGER.exception("Failed to release %s after cycle error", key)
                if blocked:
                    self._backend.unblock()
            finally:
                self._suspend_hotkey(False)

    @staticmethod
    def _wait_gap(gap_ms: int) -> None:
        deadline = time.perf_counter() + gap_ms / 1000.0
        # Windows sleep can overshoot a 10 ms interval. A short final spin
        # keeps the default gap close to the requested value.
        if gap_ms > 15:
            time.sleep(max(0.0, gap_ms / 1000.0 - 0.01))
        while time.perf_counter() < deadline:
            pass

    def shutdown(self) -> None:
        self.stop()
