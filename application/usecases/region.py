from __future__ import annotations

from dataclasses import dataclass

from application.state import AppState, ScreenRegion


@dataclass(frozen=True, slots=True)
class RegionSelectionResult:
    """Result of validating and accepting a custom region."""

    accepted: bool
    reason: str = ""


class RegionUseCase:
    """
    Region-domain state operations only.

    It does not know PyQt6, mouse input, selection drawing, capture, OCR,
    feature configuration, execution mode, or ControlPanel.
    """

    def __init__(
        self,
        state: AppState,
        *,
        min_width: int = 10,
        min_height: int = 10,
    ) -> None:
        if min_width <= 0:
            raise ValueError("min_width must be greater than 0.")
        if min_height <= 0:
            raise ValueError("min_height must be greater than 0.")

        self.state = state
        self.min_width = int(min_width)
        self.min_height = int(min_height)

    def begin_selection(self) -> None:
        self.state.begin_region_selection()

    def cancel_selection(self) -> None:
        self.state.cancel_region_selection()

    def set_fullscreen(self) -> None:
        self.state.set_fullscreen_region()

    def confirm_selection(
        self,
        region: ScreenRegion,
    ) -> RegionSelectionResult:
        error = self._validate_region(region)

        if error is not None:
            return RegionSelectionResult(
                accepted=False,
                reason=error,
            )

        self.state.set_custom_region(region)
        return RegionSelectionResult(accepted=True)

    def _validate_region(self, region: ScreenRegion) -> str | None:
        if region.width < self.min_width:
            return (
                "Selected region is too narrow. "
                f"Minimum width is {self.min_width}px."
            )

        if region.height < self.min_height:
            return (
                "Selected region is too short. "
                f"Minimum height is {self.min_height}px."
            )

        screen = self.state.screen_region

        if region.x1 < screen.x1:
            return "Selected region exceeds the left screen boundary."
        if region.y1 < screen.y1:
            return "Selected region exceeds the top screen boundary."
        if region.x2 > screen.x2:
            return "Selected region exceeds the right screen boundary."
        if region.y2 > screen.y2:
            return "Selected region exceeds the bottom screen boundary."

        return None
