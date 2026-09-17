from __future__ import annotations

from PyQt6.QtWidgets import QPushButton


class FullscreenButton(QPushButton):
    """
    Independent action button for choosing the full-screen capture area.

    This button emits the normal QPushButton clicked signal only.
    It does not modify region state by itself.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build only this button's static UI."""
        self.setText("Full Screen")
        self.setObjectName("fullscreenButton")
        self.setMinimumWidth(140)
        self.setMinimumHeight(38)
