from __future__ import annotations

from PyQt6.QtWidgets import QGraphicsOpacityEffect, QPushButton


class AutoModeButton(QPushButton):
    """
    Independent visual component for Auto execution mode.

    Auto mode may require GPU availability, but this button does not
    inspect hardware and does not decide whether Auto is allowed.

    An external layer is responsible for:
        - GPU capability detection;
        - Manual/Auto exclusivity;
        - enabling/disabling this button;
        - updating application state.

    Example:

        auto_button.setEnabled(gpu_available)
        auto_button.set_selected(True)
    """

    SELECTED_OPACITY = 1.0
    UNSELECTED_OPACITY = 0.50

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._selected = False

        self._build_ui()
        self._build_visual_effects()
        self._apply_visual_state()

    def _build_ui(self) -> None:
        """Build only this button's static UI."""
        self.setText("Auto")
        self.setObjectName("autoModeButton")
        self.setMinimumWidth(140)
        self.setMinimumHeight(38)

        self.setToolTip(
            "Continuous real-time mode. "
            "Availability is determined by the application."
        )

    def _build_visual_effects(self) -> None:
        """Create visual helpers owned only by this button."""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)

    def set_selected(self, selected: bool) -> None:
        """Update only this button's selected appearance."""
        self._selected = bool(selected)
        self._apply_visual_state()

    def _apply_visual_state(self) -> None:
        """Apply only this button's local visual state."""
        self._opacity_effect.setOpacity(
            self.SELECTED_OPACITY
            if self._selected
            else self.UNSELECTED_OPACITY
        )
