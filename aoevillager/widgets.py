"""Reusable input controls for the desktop settings UI."""

from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox


class NoWheelComboBox(QComboBox):
    """Prevent changing a preset while scrolling the settings page."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    """Keep incidental wheel scrolling from changing a numeric setting."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """The decimal counterpart; keyboard and arrow-button edits still work."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        event.ignore()
