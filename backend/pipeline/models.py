from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.translation.dictionary.dashboard import DashboardEntry

from .config import PipelineConfig


PipelineUnitType = Literal["ocr_box", "text_group"]


@dataclass(frozen=True, slots=True)
class PipelineBBox:
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


@dataclass(frozen=True, slots=True)
class OCRPipelineItem:
    text: str
    confidence: float
    bbox: PipelineBBox


@dataclass(frozen=True, slots=True)
class PipelineTextResult:
    """
    Spatial translation result.

    Dictionary:
        one result per OCR box.

    Language model:
        one result per TextGroup.
    """

    unit_type: PipelineUnitType
    bbox: PipelineBBox
    raw_text: str
    corrected_text: str
    translated_text: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class TranslationPipelineResult:
    """
    Result of exactly one translation branch.

    This object never contains Dashboard data.
    """

    items: tuple[PipelineTextResult, ...]

    @property
    def empty(self) -> bool:
        return not self.items

    @property
    def translated_texts(self) -> tuple[str, ...]:
        return tuple(
            item.translated_text
            for item in self.items
        )


@dataclass(frozen=True, slots=True)
class DashboardPipelineResult:
    """
    Independent Dashboard vocabulary result.

    No bbox, overlay or TextGrouping data belongs here.
    """

    entries: tuple[DashboardEntry, ...]

    @property
    def empty(self) -> bool:
        return not self.entries


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """
    Complete atomic backend result.

    Disabled feature:
        corresponding result is None.

    Enabled feature with no OCR/content:
        corresponding result object exists but contains an empty tuple.
    """

    config: PipelineConfig
    translation_result: TranslationPipelineResult | None
    dashboard_result: DashboardPipelineResult | None
    ocr_items: tuple[OCRPipelineItem, ...]
    elapsed_seconds: float

    @property
    def empty(self) -> bool:
        translation_empty = (
            self.translation_result is None
            or self.translation_result.empty
        )
        dashboard_empty = (
            self.dashboard_result is None
            or self.dashboard_result.empty
        )
        return translation_empty and dashboard_empty
