from __future__ import annotations

from PyQt6.QtWidgets import QGraphicsOpacityEffect, QPushButton


class DictionaryButton(QPushButton):
    """
    Independent visual component for the Dictionary feature.

    This button owns only its local visual selected state.
    It does not know AppState, Controller, LanguageModelButton,
    DashboardButton, or backend translation code.
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
        self.setText("Dictionary")
        self.setObjectName("dictionaryButton")
        self.setMinimumWidth(140)
        self.setMinimumHeight(38)

    def _build_visual_effects(self) -> None:
        """Create visual helpers used by this button only."""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)

    def set_selected(self, selected: bool) -> None:
        """Render this button as selected/unselected."""
        self._selected = bool(selected)
        self._apply_visual_state()

    def _apply_visual_state(self) -> None:
        """Apply only this button's local visual state."""
        self._opacity_effect.setOpacity(
            self.SELECTED_OPACITY
            if self._selected
            else self.UNSELECTED_OPACITY
        )
