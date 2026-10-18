from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from aoevillager.hub import ToolboxWindow
from aoevillager.settings import SettingsStore


def configure_logging() -> None:
    if getattr(sys, "frozen", False):
        folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    else:
        folder = Path(__file__).resolve().parent
    folder.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=folder / "aoe4toolbox.log",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        encoding="utf-8",
    )


def configure_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AOE4Toolbox.Desktop")
    except (AttributeError, OSError):
        pass


def main() -> int:
    configure_windows_app_id()
    app = QApplication(sys.argv)
    app.setOrganizationName("AOEvillager")
    app.setApplicationName("AOE4Toolbox")
    app.setApplicationDisplayName("帝国时代 4 工具箱")
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    icon = QIcon(str(base / "assets" / "aoevillager.png"))
    app.setWindowIcon(icon)
    configure_logging()
    try:
        window = ToolboxWindow(SettingsStore(), base / "web" / "hotkeys.html")
        window.setWindowIcon(icon)
    except Exception as exc:
        logging.exception("Unable to initialize application")
        QMessageBox.critical(None, "帝国时代 4 工具箱启动失败", str(exc))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
