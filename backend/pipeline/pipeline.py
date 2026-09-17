from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING, Any

import numpy as np

from .config import PipelineConfig
from .models import (
    DashboardPipelineResult,
    OCRPipelineItem,
    PipelineBBox,
    PipelineResult,
    PipelineTextResult,
    TranslationPipelineResult,
)
from .ocr_result import OCRResultExtractionError, extract_ocr_items

if TYPE_CHECKING:
    from backend.OCR.fast import FastOCR
    from backend.OCR.quality import QualityOCR
    from backend.ocr_correction import OCRCorrector
    from backend.text_grouping import TextGrouper
    from backend.translation.dictionary.dashboard import DashboardExtractor
    from backend.translation.dictionary.literal import LiteralTranslator
    from backend.translation.language_model import LanguageTranslator


class BackendPipelineError(RuntimeError):
    pass


class BackendPipelineInputError(BackendPipelineError):
    pass


class BackendPipelineExecutionError(BackendPipelineError):
    pass


class BackendPipeline:
    """
    Atomic backend orchestrator.

    Common:
        image -> OCR -> OCR Correction -> corrected_texts

    Translation:
        dictionary:
            corrected OCR box -> LiteralTranslator

        language_model:
            corrected OCR boxes -> TextGrouping -> LanguageTranslator

    Independent:
        corrected_texts -> DashboardExtractor

    If one enabled branch fails, run() returns no partial result.
    """

    def __init__(
        self,
        *,
        fast_ocr: FastOCR | None = None,
        quality_ocr: QualityOCR | None = None,
        corrector: OCRCorrector | None = None,
        grouper: TextGrouper | None = None,
        literal_translator: LiteralTranslator | None = None,
        language_translator: LanguageTranslator | None = None,
        dashboard_extractor: DashboardExtractor | None = None,
    ) -> None:
        self._fast_ocr = fast_ocr
        self._quality_ocr = quality_ocr
        self._corrector = corrector
        self._grouper = grouper
        self._literal_translator = literal_translator
        self._language_translator = language_translator
        self._dashboard_extractor = dashboard_extractor

    def run(
        self,
        image: np.ndarray,
        config: PipelineConfig | None = None,
    ) -> PipelineResult:
        config = config or PipelineConfig()
        self._validate_image(image)
        started = perf_counter()

        try:
            ocr_items = extract_ocr_items(
                self._run_ocr(image, config)
            )

            if not ocr_items:
                return self._empty_result(
                    config=config,
                    elapsed_seconds=perf_counter() - started,
                )

            corrected_texts = self._correct(
                ocr_items,
                enabled=config.enable_ocr_correction,
            )

            translation_result = None
            if config.translation_mode is not None:
                translation_result = self._translate(
                    ocr_items,
                    corrected_texts,
                    config.translation_mode,
                    enable_text_grouping=config.enable_text_grouping,
                )

            dashboard_result = None
            if config.enable_dashboard:
                dashboard_result = DashboardPipelineResult(
                    entries=self._get_dashboard().extract(
                        corrected_texts
                    )
                )

            return PipelineResult(
                config=config,
                translation_result=translation_result,
                dashboard_result=dashboard_result,
                ocr_items=tuple(ocr_items),
                elapsed_seconds=perf_counter() - started,
            )

        except BackendPipelineError:
            raise
        except OCRResultExtractionError as exc:
            raise BackendPipelineExecutionError(
                "Failed to extract PaddleOCR result."
            ) from exc
        except Exception as exc:
            raise BackendPipelineExecutionError(
                "An enabled backend branch failed. "
                "No partial result was returned."
            ) from exc

    def __call__(
        self,
        image: np.ndarray,
        config: PipelineConfig | None = None,
    ) -> PipelineResult:
        return self.run(image, config)

    def _empty_result(
        self,
        *,
        config: PipelineConfig,
        elapsed_seconds: float,
    ) -> PipelineResult:
        translation_result = (
            TranslationPipelineResult(items=())
            if config.translation_mode is not None
            else None
        )
        dashboard_result = (
            DashboardPipelineResult(entries=())
            if config.enable_dashboard
            else None
        )

        return PipelineResult(
            config=config,
            translation_result=translation_result,
            dashboard_result=dashboard_result,
            ocr_items=(),
            elapsed_seconds=elapsed_seconds,
        )

    def _run_ocr(
        self,
        image: np.ndarray,
        config: PipelineConfig,
    ) -> Any:
        if config.ocr_mode == "fast":
            return self._get_fast_ocr().predict(image)

        if config.ocr_mode == "quality":
            return self._get_quality_ocr().predict(image)

        raise BackendPipelineInputError(
            f"Unsupported OCR mode: {config.ocr_mode!r}"
        )

    def _correct(
        self,
        ocr_items: list[OCRPipelineItem],
        *,
        enabled: bool,
    ) -> list[str]:
        if not enabled:
            return [item.text for item in ocr_items]

        corrector = self._get_corrector()
        return [
            corrector.correct_text(item.text)
            for item in ocr_items
        ]

    def _translate(
        self,
        ocr_items: list[OCRPipelineItem],
        corrected_texts: list[str],
        mode: str,
        *,
        enable_text_grouping: bool = False,
    ) -> TranslationPipelineResult:
        if mode == "dictionary":
            items = self._dictionary_items(
                ocr_items,
                corrected_texts,
            )

        elif mode == "language_model":
            items = self._language_items(
                ocr_items,
                corrected_texts,
                enable_text_grouping=enable_text_grouping,
            )

        else:
            raise BackendPipelineInputError(
                f"Unsupported translation mode: {mode!r}"
            )

        return TranslationPipelineResult(items=tuple(items))

    def _dictionary_items(
        self,
        ocr_items: list[OCRPipelineItem],
        corrected_texts: list[str],
    ) -> list[PipelineTextResult]:
        translator = self._get_literal()
        output: list[PipelineTextResult] = []

        for ocr_item, corrected_text in zip(
            ocr_items,
            corrected_texts,
            strict=True,
        ):
            translated = translator.translate(
                corrected_text
            ).translated_text

            output.append(
                PipelineTextResult(
                    unit_type="ocr_box",
                    bbox=ocr_item.bbox,
                    raw_text=ocr_item.text,
                    corrected_text=corrected_text,
                    translated_text=translated,
                    confidence=ocr_item.confidence,
                )
            )

        return output

    def _language_items(
        self,
        ocr_items: list[OCRPipelineItem],
        corrected_texts: list[str],
        *,
        enable_text_grouping: bool = False,
    ) -> list[PipelineTextResult]:

        # ==========================================================
        # GROUPING OFF
        # Translate each OCR box independently.
        # ==========================================================
        if not enable_text_grouping:
            translator = self._get_language()
            output: list[PipelineTextResult] = []

            for ocr_item, corrected_text in zip(
                ocr_items,
                corrected_texts,
                strict=True,
            ):
                translated = translator.translate(
                    corrected_text
                ).translated_text

                output.append(
                    PipelineTextResult(
                        unit_type="ocr_box",
                        bbox=ocr_item.bbox,
                        raw_text=ocr_item.text,
                        corrected_text=corrected_text,
                        translated_text=str(translated),
                        confidence=ocr_item.confidence,
                    )
                )

            return output

        # ==========================================================
        # GROUPING ON
        # Existing behavior.
        # ==========================================================
        grouper = self._get_grouper()

        boxes = [item.bbox.coordinates for item in ocr_items]
        scores = [item.confidence for item in ocr_items]

        raw_groups = grouper.group(
            texts=[item.text for item in ocr_items],
            boxes=boxes,
            scores=scores,
        )

        corrected_groups = grouper.group(
            texts=corrected_texts,
            boxes=boxes,
            scores=scores,
        )

        if len(raw_groups) != len(corrected_groups):
            raise BackendPipelineExecutionError(
                "Raw/corrected TextGrouping produced different group counts."
            )

        translator = self._get_language()
        output: list[PipelineTextResult] = []

        for raw_group, corrected_group in zip(
            raw_groups,
            corrected_groups,
            strict=True,
        ):
            raw_bbox = self._bbox_from_group(raw_group)
            corrected_bbox = self._bbox_from_group(corrected_group)

            if raw_bbox.coordinates != corrected_bbox.coordinates:
                raise BackendPipelineExecutionError(
                    "Raw/corrected TextGrouping produced different geometry."
                )

            confidence = getattr(
                corrected_group,
                "average_confidence",
                None,
            )

            output.append(
                PipelineTextResult(
                    unit_type="text_group",
                    bbox=corrected_bbox,
                    raw_text=str(raw_group.text),
                    corrected_text=str(corrected_group.text),
                    translated_text=str(
                        translator.translate(
                            corrected_group.text
                        ).translated_text
                    ),
                    confidence=(
                        float(confidence)
                        if confidence is not None
                        else None
                    ),
                )
            )

        return output

    @staticmethod
    def _bbox_from_group(group: Any) -> PipelineBBox:
        bbox = getattr(group, "bbox", None)
        if bbox is None:
            raise BackendPipelineExecutionError(
                "TextGroup has no bbox."
            )

        if all(
            hasattr(bbox, name)
            for name in ("x1", "y1", "x2", "y2")
        ):
            return PipelineBBox(
                int(bbox.x1),
                int(bbox.y1),
                int(bbox.x2),
                int(bbox.y2),
            )

        coordinates = getattr(bbox, "coordinates", None)
        if callable(coordinates):
            coordinates = coordinates()
        if coordinates is not None:
            bbox = coordinates

        try:
            x1, y1, x2, y2 = bbox
            return PipelineBBox(
                int(x1),
                int(y1),
                int(x2),
                int(y2),
            )
        except Exception as exc:
            raise BackendPipelineExecutionError(
                "Unsupported TextGroup bbox format."
            ) from exc

    @staticmethod
    def _validate_image(image: np.ndarray) -> None:
        if not isinstance(image, np.ndarray):
            raise BackendPipelineInputError(
                "image must be a numpy.ndarray."
            )
        if image.dtype != np.uint8:
            raise BackendPipelineInputError(
                "image dtype must be uint8."
            )
        if image.ndim != 3 or image.shape[2] != 3:
            raise BackendPipelineInputError(
                "image must have shape (H, W, 3)."
            )
        if image.shape[0] < 16 or image.shape[1] < 16:
            raise BackendPipelineInputError(
                "image must be at least 16x16."
            )

    def _get_fast_ocr(self) -> FastOCR:
        if self._fast_ocr is None:
            from backend.OCR.fast import FastOCR
            self._fast_ocr = FastOCR()
        return self._fast_ocr

    def _get_quality_ocr(self) -> QualityOCR:
        if self._quality_ocr is None:
            from backend.OCR.quality import QualityOCR
            self._quality_ocr = QualityOCR()
        return self._quality_ocr

    def _get_corrector(self) -> OCRCorrector:
        if self._corrector is None:
            from backend.ocr_correction import OCRCorrector
            self._corrector = OCRCorrector()
        return self._corrector

    def _get_grouper(self) -> TextGrouper:
        if self._grouper is None:
            from backend.text_grouping import TextGrouper
            self._grouper = TextGrouper()
        return self._grouper

    def _get_literal(self) -> LiteralTranslator:
        if self._literal_translator is None:
            from backend.translation.dictionary.literal import LiteralTranslator
            self._literal_translator = LiteralTranslator()
        return self._literal_translator

    def _get_language(self) -> LanguageTranslator:
        if self._language_translator is None:
            from backend.translation.language_model import LanguageTranslator
            self._language_translator = LanguageTranslator()
        return self._language_translator

    def _get_dashboard(self) -> DashboardExtractor:
        if self._dashboard_extractor is None:
            from backend.translation.dictionary.dashboard import DashboardExtractor
            self._dashboard_extractor = DashboardExtractor()
        return self._dashboard_extractor
