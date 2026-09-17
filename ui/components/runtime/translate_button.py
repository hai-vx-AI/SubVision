from __future__ import annotations

from PyQt6.QtWidgets import QPushButton


class TranslateButton(QPushButton):
    """
    Independent runtime action button for requesting a new processing cycle.

    The button only emits QPushButton.clicked.

    It does NOT:
        - call BackendPipeline;
        - update the result stream;
        - know Manual/Auto mode;
        - know Dictionary/Language Model/Dashboard;
        - implement the global R hotkey.

    The global R shortcut belongs to the runtime/controller/hotkey layer.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build only this button's static UI."""
        self.setText("Translate (R)")
        self.setObjectName("translateButton")
        self.setMinimumWidth(150)
        self.setMinimumHeight(36)
