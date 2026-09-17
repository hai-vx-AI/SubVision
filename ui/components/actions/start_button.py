from __future__ import annotations

from PyQt6.QtWidgets import QPushButton


class StartButton(QPushButton):
    """
    Independent action button for starting a SubVision runtime session.

    Start is NOT an execution-mode choice.

    It represents the transition:

        setup/configuration
            ->
        runtime session

    This button only emits QPushButton.clicked.

    It does NOT:
        - validate configuration;
        - choose Manual/Auto;
        - call BackendPipeline;
        - create workers;
        - open runtime windows;
        - modify AppState.

    Those responsibilities belong to the external application/controller layer.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build only this button's static UI."""
        self.setText("Start")
        self.setObjectName("startButton")
        self.setMinimumHeight(42)
