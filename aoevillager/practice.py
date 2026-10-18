"""Embedded shortcut-practice page copied from the user's standalone HTML."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class HotkeyPracticePage(QWidget):
    def __init__(self, html_path: Path) -> None:
        super().__init__()
        if not html_path.is_file():
            raise FileNotFoundError(f"找不到内置快捷键练习页面：{html_path}")
        self.setAccessibleName("帝国时代 4 快捷键练习")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)

        header = QFrame()
        header.setObjectName("practiceHeader")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(16, 10, 16, 10)
        title = QLabel("快捷键练习")
        title.setObjectName("practiceTitle")
        header_row.addWidget(title)
        header_row.addStretch()
        hint = QLabel("选择文明 → 选择模式 → 按提示输入快捷键")
        hint.setObjectName("shellMuted")
        hint.setWordWrap(True)
        header_row.addWidget(hint)
        layout.addWidget(header)

        frame = QFrame()
        frame.setObjectName("webFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(1, 1, 1, 1)
        self.web = QWebEngineView()
        self.web.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.web.setAccessibleName("快捷键练习内容")
        # The original self-contained HTML still refers to remote civilization
        # and building artwork. Its JavaScript and CSS are bundled locally.
        self.web.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self.web.setUrl(QUrl.fromLocalFile(str(html_path)))
        frame_layout.addWidget(self.web)
        layout.addWidget(frame, 1)

    def activate(self) -> None:
        self.web.setFocus()

    def pause(self) -> None:
        self.web.page().runJavaScript(
            "if (typeof gameState !== 'undefined' && gameState.isPlaying "
            "&& typeof pauseGame === 'function') pauseGame();"
        )
