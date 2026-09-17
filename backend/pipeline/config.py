from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


OCRMode = Literal["fast", "quality"]
TranslationMode = Literal["dictionary", "language_model"] | None


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """
    User-selectable backend features for one run.

    Valid combinations:
        dictionary
        language_model
        dashboard only
        dictionary + dashboard
        language_model + dashboard

    Invalid:
        no feature enabled

    Dictionary and language_model are mutually exclusive because
    translation_mode can contain only one value.
    """

    ocr_mode: OCRMode = "fast"
    translation_mode: TranslationMode = "dictionary"
    enable_dashboard: bool = False
    enable_ocr_correction: bool = True
    enable_text_grouping: bool = False

    def __post_init__(self) -> None:
        if self.ocr_mode not in ("fast", "quality"):
            raise ValueError(
                "ocr_mode must be 'fast' or 'quality'."
            )

        if self.translation_mode not in (
            None,
            "dictionary",
            "language_model",
        ):
            raise ValueError(
                "translation_mode must be None, "
                "'dictionary', or 'language_model'."
            )

        if (
            self.translation_mode is None
            and not self.enable_dashboard
        ):
            raise ValueError(
                "At least one feature must be enabled: "
                "dictionary, language_model, or dashboard."
            )

    @property
    def enable_translation(self) -> bool:
        return self.translation_mode is not None
