from __future__ import annotations

from PyQt6.QtWidgets import QPushButton


class SelectRegionButton(QPushButton):
    """
    Independent action button for starting region selection.

    This button does not create or control RegionSelector itself.
    It emits the normal QPushButton clicked signal only.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build only this button's static UI."""
        self.setText("Select Region")
        self.setObjectName("selectRegionButton")
        self.setMinimumWidth(140)
        self.setMinimumHeight(38)
