from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RegionMode = Literal["fullscreen", "custom"]
OCRMode = Literal["fast", "quality"]
TranslationMode = Literal["dictionary", "language_model"] | None
ExecutionMode = Literal["manual", "auto"]


@dataclass(frozen=True, slots=True)
class ScreenRegion:
    """Immutable region in the application's global logical coordinates."""

    x1: int
    y1: int
    x2: int
    y2: int

    def __post_init__(self) -> None:
        if self.x2 <= self.x1:
            raise ValueError("x2 must be greater than x1.")
        if self.y2 <= self.y1:
            raise ValueError("y2 must be greater than y1.")

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def coordinates(self) -> tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass(slots=True)
class AppState:
    """
    Single source of truth for application state.

    State owns data and local mutations only. It does not know UI, capture,
    BackendPipeline, workers, realtime loops, or cross-domain policy.
    """

    # Region
    screen_region: ScreenRegion
    selected_region: ScreenRegion
    region_mode: RegionMode = "fullscreen"
    region_selection_active: bool = False

    # OCR
    ocr_mode: OCRMode = "fast"

    # Features: two independent state axes.
    translation_mode: TranslationMode = "dictionary"
    dashboard_enabled: bool = False

    # Execution/runtime-facing state.
    execution_mode: ExecutionMode = "manual"
    session_running: bool = False
    pipeline_running: bool = False

    # Translation Overlay visibility only; Dashboard is independent.
    translation_visible: bool = False

    @classmethod
    def create(cls, screen_region: ScreenRegion) -> "AppState":
        return cls(
            screen_region=screen_region,
            selected_region=screen_region,
        )

    # ------------------------------------------------------------------
    # Region
    # ------------------------------------------------------------------

    def begin_region_selection(self) -> None:
        self.region_selection_active = True

    def cancel_region_selection(self) -> None:
        self.region_selection_active = False

    def set_fullscreen_region(self) -> None:
        self.selected_region = self.screen_region
        self.region_mode = "fullscreen"
        self.region_selection_active = False

    def set_custom_region(self, region: ScreenRegion) -> None:
        self.selected_region = region
        self.region_mode = "custom"
        self.region_selection_active = False

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------

    def set_ocr_mode(self, mode: OCRMode) -> None:
        if mode not in {"fast", "quality"}:
            raise ValueError(f"Unsupported OCR mode: {mode!r}.")
        self.ocr_mode = mode

    # ------------------------------------------------------------------
    # Features
    # ------------------------------------------------------------------

    def set_translation_mode(self, mode: TranslationMode) -> None:
        if mode not in {None, "dictionary", "language_model"}:
            raise ValueError(f"Unsupported translation mode: {mode!r}.")
        self.translation_mode = mode

    def set_dashboard_enabled(self, enabled: bool) -> None:
        self.dashboard_enabled = bool(enabled)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def set_execution_mode(self, mode: ExecutionMode) -> None:
        if mode not in {"manual", "auto"}:
            raise ValueError(f"Unsupported execution mode: {mode!r}.")
        self.execution_mode = mode

    def start_session(self) -> None:
        self.session_running = True

    def stop_session(self) -> None:
        self.session_running = False
        self.pipeline_running = False
        self.translation_visible = False

    def begin_pipeline(self) -> None:
        self.pipeline_running = True

    def finish_pipeline(self) -> None:
        self.pipeline_running = False

    def show_translation(self) -> None:
        self.translation_visible = True

    def hide_translation(self) -> None:
        self.translation_visible = False

    def toggle_translation_visibility(self) -> None:
        self.translation_visible = not self.translation_visible

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, object]:
        return {
            "region": {
                "mode": self.region_mode,
                "screen_region": self.screen_region.coordinates,
                "selected_region": self.selected_region.coordinates,
                "selection_active": self.region_selection_active,
            },
            "ocr": {
                "mode": self.ocr_mode,
            },
            "features": {
                "translation_mode": self.translation_mode,
                "dashboard_enabled": self.dashboard_enabled,
            },
            "execution": {
                "mode": self.execution_mode,
                "session_running": self.session_running,
                "pipeline_running": self.pipeline_running,
                "translation_visible": self.translation_visible,
            },
        }
