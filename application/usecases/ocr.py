from __future__ import annotations

from application.state import AppState, OCRMode


class OCRUseCase:
    """
    OCR-domain state operations only.

    It does not know UI widgets, OCR engines, PipelineConfig, Region,
    Feature, or Execution domains.
    """

    def __init__(self, state: AppState) -> None:
        self.state = state

    def set_mode(self, mode: OCRMode) -> None:
        self.state.set_ocr_mode(mode)

    def set_fast(self) -> None:
        self.set_mode("fast")

    def set_quality(self) -> None:
        self.set_mode("quality")
