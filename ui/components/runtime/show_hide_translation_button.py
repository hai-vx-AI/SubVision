from __future__ import annotations

from PyQt6.QtWidgets import QPushButton


class ShowHideTranslationButton(QPushButton):
    """
    Independent runtime button for the Vietnamese translation overlay only.

    This component does not show/hide any window by itself.

    An external layer owns actual overlay visibility and reflects that state
    back into this button via set_translation_visible(...).

    Dashboard visibility is intentionally unrelated.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._translation_visible = False

        self._build_ui()
        self._apply_visual_state()

    def _build_ui(self) -> None:
        """Build only this button's static UI."""
        self.setObjectName("showHideTranslationButton")
        self.setMinimumWidth(190)
        self.setMinimumHeight(36)

    def set_translation_visible(self, visible: bool) -> None:
        """
        Update only this button's visual label.

        True  -> Vietnamese translation overlay is currently visible.
        False -> Vietnamese translation overlay is currently hidden.
        """
        self._translation_visible = bool(visible)
        self._apply_visual_state()

    def _apply_visual_state(self) -> None:
        """Apply only this button's own label state."""
        self.setText(
            "Hide Translation (Tab)"
            if self._translation_visible
            else "Show Translation (Tab)"
        )
