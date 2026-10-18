from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes


LOGGER = logging.getLogger(__name__)
HOOKPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


class LowLevelInputGuard:
    """Short-lived Windows hooks that reject all input except our tagged SendInput.

    Each hook owns a message-pumping thread. The guard activates only after
    both hooks have been installed; closing always clears the suppression flag
    before removing the hooks.
    """

    HOOKS = {"keyboard": 13, "mouse": 14}
    INJECTED_FLAGS = {"keyboard": 0x10, "mouse": 0x01}
    WM_QUIT = 0x0012

    def __init__(self, tag: int) -> None:
        self._tag = tag
        self._active = threading.Event()
        self._ready = {kind: threading.Event() for kind in self.HOOKS}
        self._errors: dict[str, Exception] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._thread_ids: dict[str, int] = {}
        self._handles: dict[str, int] = {}
        self._callbacks: dict[str, HOOKPROC] = {}

        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        self._user32.SetWindowsHookExW.restype = wintypes.HHOOK
        self._user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        self._user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        self._user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        self._user32.CallNextHookEx.restype = wintypes.LPARAM
        self._user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        self._user32.GetMessageW.restype = ctypes.c_int
        self._user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
        self._user32.PeekMessageW.restype = wintypes.BOOL
        self._user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
        self._user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
        self._user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self._user32.PostThreadMessageW.restype = wintypes.BOOL
        self._kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    def activate(self) -> None:
        try:
            for kind in self.HOOKS:
                thread = threading.Thread(target=self._hook_loop, args=(kind,), name=f"pulseclick-{kind}-guard", daemon=True)
                self._threads[kind] = thread
                thread.start()
            for kind in self.HOOKS:
                if not self._ready[kind].wait(2.0):
                    raise TimeoutError(f"{kind} 输入钩子启动超时")
                if kind in self._errors:
                    raise self._errors[kind]
                if not self._handles.get(kind) or not self._threads[kind].is_alive():
                    raise RuntimeError(f"{kind} 输入钩子未就绪")
            self._active.set()
        except Exception:
            self.close()
            raise

    def healthy(self) -> bool:
        return self._active.is_set() and all(
            self._handles.get(kind) and self._threads[kind].is_alive() for kind in self.HOOKS
        )

    def close(self) -> None:
        self._active.clear()
        for thread_id in tuple(self._thread_ids.values()):
            self._user32.PostThreadMessageW(thread_id, self.WM_QUIT, 0, 0)
        for thread in tuple(self._threads.values()):
            if thread is not threading.current_thread():
                thread.join(timeout=0.5)
        living = [thread for thread in self._threads.values() if thread.is_alive()]
        if living:
            for handle in tuple(self._handles.values()):
                self._user32.UnhookWindowsHookEx(handle)
            for thread_id in tuple(self._thread_ids.values()):
                self._user32.PostThreadMessageW(thread_id, self.WM_QUIT, 0, 0)
            for thread in living:
                thread.join(timeout=0.5)
        if any(thread.is_alive() for thread in self._threads.values()):
            LOGGER.error("Input guard message-loop thread did not exit")
            return
        self._thread_ids.clear()
        self._handles.clear()
        self._threads.clear()
        self._callbacks.clear()

    def _hook_loop(self, kind: str) -> None:
        handle = None
        try:
            self._thread_ids[kind] = int(self._kernel32.GetCurrentThreadId())
            callback = HOOKPROC(lambda code, wparam, lparam: self._on_event(kind, code, wparam, lparam))
            self._callbacks[kind] = callback
            handle = self._user32.SetWindowsHookExW(self.HOOKS[kind], callback, None, 0)
            if not handle:
                raise OSError(ctypes.get_last_error(), f"无法安装 {kind} 输入钩子")
            self._handles[kind] = int(handle)
            message = MSG()
            # PostThreadMessage requires a message queue to exist before the
            # owner signals readiness; PeekMessage creates it if needed.
            self._user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            self._ready[kind].set()
            while self._user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                self._user32.TranslateMessage(ctypes.byref(message))
                self._user32.DispatchMessageW(ctypes.byref(message))
        except Exception as exc:
            self._errors[kind] = exc
            LOGGER.exception("Input guard hook failed: %s", kind)
            self._ready[kind].set()
        finally:
            if handle:
                self._user32.UnhookWindowsHookEx(handle)

    def _on_event(self, kind: str, code: int, wparam: int, lparam: int) -> int:
        if code >= 0 and self._active.is_set():
            try:
                structure = KBDLLHOOKSTRUCT if kind == "keyboard" else MSLLHOOKSTRUCT
                data = ctypes.cast(lparam, ctypes.POINTER(structure)).contents
                ours = bool(data.flags & self.INJECTED_FLAGS[kind]) and data.dwExtraInfo == self._tag
                if not ours:
                    return 1
            except Exception:
                return 1
        return int(self._user32.CallNextHookEx(None, code, wparam, lparam))
