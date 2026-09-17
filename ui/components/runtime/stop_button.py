from __future__ import annotations

from PyQt6.QtWidgets import QPushButton


class StopButton(QPushButton):
    """
    Independent runtime action button for stopping the current SubVision run.

    Clicking only emits QPushButton.clicked.
    Actual worker/timer/backend/window shutdown belongs to another layer.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build only this button's static UI."""
        self.setText("Stop")
        self.setObjectName("stopButton")
        self.setMinimumWidth(150)
        self.setMinimumHeight(36)
