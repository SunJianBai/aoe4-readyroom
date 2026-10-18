from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QLineEdit, QWidget

from .cycle import normalize_cycle_step


class KeyStepEdit(QLineEdit):
    """Typed key names plus optional recording of one simultaneous chord."""

    focus_changed = pyqtSignal(bool)
    recording_error = pyqtSignal(str)

    KEY_NAMES = {
        Qt.Key.Key_Control: "CTRL", Qt.Key.Key_Alt: "ALT",
        Qt.Key.Key_Shift: "SHIFT", Qt.Key.Key_Meta: "WIN",
        Qt.Key.Key_Backspace: "BACKSPACE", Qt.Key.Key_Tab: "TAB",
        Qt.Key.Key_Return: "ENTER", Qt.Key.Key_Enter: "ENTER",
        Qt.Key.Key_Escape: "ESC", Qt.Key.Key_Space: "SPACE",
        Qt.Key.Key_PageUp: "PAGEUP", Qt.Key.Key_PageDown: "PAGEDOWN",
        Qt.Key.Key_End: "END", Qt.Key.Key_Home: "HOME",
        Qt.Key.Key_Left: "LEFT", Qt.Key.Key_Up: "UP",
        Qt.Key.Key_Right: "RIGHT", Qt.Key.Key_Down: "DOWN",
        Qt.Key.Key_Insert: "INSERT", Qt.Key.Key_Delete: "DELETE",
    }
    MODIFIER_FLAGS = (
        (Qt.KeyboardModifier.ControlModifier, "CTRL"),
        (Qt.KeyboardModifier.AltModifier, "ALT"),
        (Qt.KeyboardModifier.ShiftModifier, "SHIFT"),
        (Qt.KeyboardModifier.MetaModifier, "WIN"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._recording = False
        self._original_text = ""
        self._held: set[str] = set()
        self._captured: list[str] = []
        self.setMaxLength(48)
        self.setPlaceholderText("H、Q 或 Ctrl+Q")
        self.setAccessibleDescription("直接输入键名，或用录制按钮同时按住 1 至 3 个键")

    def begin_recording(self) -> None:
        self._original_text = self.text()
        self._recording = True
        self._held.clear()
        self._captured.clear()
        self.setText("")
        self.setPlaceholderText("同时按住 1–3 个键，全部松开后保存")
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _cancel_recording(self) -> None:
        self._recording = False
        self._held.clear()
        self._captured.clear()
        self.setText(self._original_text)
        self.setPlaceholderText("H、Q 或 Ctrl+Q")

    @classmethod
    def _event_key(cls, event: QKeyEvent) -> str | None:
        key = event.key()
        if key in cls.KEY_NAMES:
            return cls.KEY_NAMES[key]
        native = event.nativeVirtualKey()
        if 0x41 <= native <= 0x5A:
            return chr(native)
        if 0x30 <= native <= 0x39:
            return None if event.modifiers() & Qt.KeyboardModifier.KeypadModifier else chr(native)
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key)
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            return None if event.modifiers() & Qt.KeyboardModifier.KeypadModifier else chr(key)
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            return f"F{key - Qt.Key.Key_F1 + 1}"
        return None

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if not self._recording:
            super().keyPressEvent(event)
            return
        if event.isAutoRepeat():
            event.accept()
            return
        key = self._event_key(event)
        if key is None:
            self._cancel_recording()
            self.recording_error.emit("无法录制此键；可手动输入支持的键名")
            event.accept()
            return
        current = [name for flag, name in self.MODIFIER_FLAGS if event.modifiers() & flag]
        current.append(key)
        for name in current:
            if name not in self._captured:
                if len(self._captured) == 3:
                    self._cancel_recording()
                    self.recording_error.emit("每一步最多录制 3 个键")
                    event.accept()
                    return
                self._captured.append(name)
            self._held.add(name)
        self.setText("+".join(self._captured))
        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if not self._recording:
            super().keyReleaseEvent(event)
            return
        if not event.isAutoRepeat():
            key = self._event_key(event)
            if key is not None:
                self._held.discard(key)
            if not self._held and self._captured:
                self._recording = False
                self.setPlaceholderText("H、Q 或 Ctrl+Q")
                self.setText(normalize_cycle_step("+".join(self._captured)))
                self.editingFinished.emit()
        event.accept()

    def focusInEvent(self, event: QEvent) -> None:  # noqa: N802
        self.focus_changed.emit(True)
        super().focusInEvent(event)

    def focusOutEvent(self, event: QEvent) -> None:  # noqa: N802
        if self._recording:
            self._cancel_recording()
        super().focusOutEvent(event)
        self.focus_changed.emit(False)
