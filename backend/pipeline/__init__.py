"""
SubVision Backend
=================

Public runtime API for the SubVision UI.

The UI should import pipeline functionality ONLY from this package:

    from backend.pipeline import BackendPipeline, PipelineConfig

Do not import OCR, OCR correction, TextGrouping, translators, Dashboard
extractors, or pipeline internals directly from the UI.

========================================================================
QUICK START
========================================================================

Create one backend pipeline and reuse it for normal sequential UI runs:

    from backend.pipeline import BackendPipeline, PipelineConfig

    pipeline = BackendPipeline()

    config = PipelineConfig(
        ocr_mode="fast",
        translation_mode="dictionary",
        enable_dashboard=False,
        enable_ocr_correction=True,
    )

    result = pipeline.run(image, config)

`BackendPipeline` is also callable:

    result = pipeline(image, config)

If config is omitted, `PipelineConfig()` is used.

========================================================================
IMAGE CONTRACT
========================================================================

BackendPipeline.run(image, config)

    image:
        numpy.ndarray
        dtype = numpy.uint8
        shape = (height, width, 3)
        color order = BGR
        minimum size = 16 x 16

The UI is responsible for screen capture / region capture and conversion to
this format.

Example when starting from a PIL RGB image:

    rgb = numpy.asarray(pil_image.convert("RGB"), dtype=numpy.uint8)
    image = rgb[:, :, ::-1].copy()   # RGB -> BGR

The backend does not capture the screen.

========================================================================
CONFIG
========================================================================

PipelineConfig fields:

    ocr_mode:
        "fast" | "quality"
        default: "fast"

    translation_mode:
        "dictionary" | "language_model" | None
        default: "dictionary"

        "dictionary"
            Translation is produced per OCR box.

        "language_model"
            OCR boxes are grouped by TextGrouping before translation.

        None
            Translation is disabled.

    enable_dashboard:
        bool
        default: False

    enable_ocr_correction:
        bool
        default: True

Valid feature combinations:

    translation_mode="dictionary"
    translation_mode="language_model"
    translation_mode=None + enable_dashboard=True
    dictionary + dashboard
    language_model + dashboard

Invalid:

    translation_mode=None + enable_dashboard=False

Dictionary and language-model translation are mutually exclusive because
`translation_mode` selects exactly one translation branch.

Constructing an invalid PipelineConfig raises ValueError.

========================================================================
PIPELINE FLOW
========================================================================

Common:

    BGR image
        -> OCR
        -> OCR Correction (optional)
        -> corrected texts

Dictionary translation:

    corrected OCR box
        -> LiteralTranslator
        -> PipelineTextResult(unit_type="ocr_box")

Language-model translation:

    corrected OCR boxes
        -> TextGrouping
        -> LanguageTranslator
        -> PipelineTextResult(unit_type="text_group")

Dashboard:

    corrected texts
        -> DashboardExtractor
        -> DashboardEntry[]

Dashboard is independent from translation and NEVER uses TextGrouping.

========================================================================
RESULT CONTRACT
========================================================================

BackendPipeline.run(...) returns PipelineResult:

    result.config
        PipelineConfig used for this run.

    result.translation_result
        TranslationPipelineResult | None

        None:
            translation was disabled.

        TranslationPipelineResult(items=()):
            translation was enabled but no translatable OCR content existed.

        result.translation_result.items:
            tuple[PipelineTextResult, ...]

    result.dashboard_result
        DashboardPipelineResult | None

        None:
            dashboard was disabled.

        DashboardPipelineResult(entries=()):
            dashboard was enabled but no vocabulary entries existed.

        result.dashboard_result.entries:
            tuple[DashboardEntry, ...]

    result.ocr_items
        tuple[OCRPipelineItem, ...]
        Normalized original OCR boxes before OCR correction.

    result.elapsed_seconds
        float
        Total backend execution time.

    result.empty
        True when both translation and dashboard contain no output.

========================================================================
TRANSLATION ITEM
========================================================================

PipelineTextResult:

    unit_type:
        "ocr_box" | "text_group"

    bbox:
        PipelineBBox

    raw_text:
        original OCR text

    corrected_text:
        text after OCR correction
        (same as raw_text when correction is disabled)

    translated_text:
        translated text for overlay

    confidence:
        float | None

Dictionary mode returns one translation item per OCR box:

    item.unit_type == "ocr_box"

Language-model mode returns one translation item per TextGroup:

    item.unit_type == "text_group"

Overlay coordinates:

    item.bbox.x1
    item.bbox.y1
    item.bbox.x2
    item.bbox.y2

or:

    x1, y1, x2, y2 = item.bbox.coordinates

PipelineBBox also provides:

    item.bbox.width
    item.bbox.height

========================================================================
DASHBOARD ENTRY
========================================================================

DashboardPipelineResult.entries contains DashboardEntry objects:

    entry.term:
        str
        English word or phrase.

    entry.meanings:
        tuple[str, ...]
        Dictionary meanings. At least one meaning is present for a returned
        entry.

    entry.ipas:
        tuple[str, ...]
        Available IPA pronunciations. May be empty.

    entry.entry_type:
        "word" | "phrase"

Dashboard entries have no bbox and no overlay semantics.

Typical UI use:

    if result.dashboard_result is not None:
        for entry in result.dashboard_result.entries:
            print(entry.term)
            print(entry.entry_type)
            print(entry.ipas)
            print(entry.meanings)

========================================================================
OCR ITEM
========================================================================

OCRPipelineItem:

    text:
        str

    confidence:
        float

    bbox:
        PipelineBBox

These are the normalized original OCR results and are mainly useful for
debugging, inspection, or optional UI diagnostics.

========================================================================
ERROR CONTRACT
========================================================================

BackendPipelineError
    Base backend runtime error.

BackendPipelineInputError
    Invalid runtime input, especially an invalid image.

BackendPipelineExecutionError
    An enabled backend branch failed during execution.

PipelineConfig validation errors are ValueError.

Recommended UI boundary:

    try:
        config = PipelineConfig(...)
        result = pipeline.run(image, config)

    except ValueError as exc:
        # Invalid UI configuration.
        ...

    except BackendPipelineInputError as exc:
        # Invalid captured image.
        ...

    except BackendPipelineExecutionError as exc:
        # OCR / correction / grouping / translation / dashboard failure.
        ...

Execution is atomic:

    If any enabled branch fails, BackendPipeline.run() raises.
    No partial PipelineResult is returned.

========================================================================
UI BOUNDARY
========================================================================

The UI should know only:

    input image
    PipelineConfig
    BackendPipeline
    PipelineResult and its public result models
    public backend errors

The UI should NOT depend on:

    backend.OCR.*
    backend.ocr_correction.*
    backend.text_grouping.*
    backend.translation.*
    backend.pipeline.config
    backend.pipeline.models
    backend.pipeline.ocr_result
    backend.pipeline.pipeline

This package (`backend.pipeline`) is the stable boundary between UI and backend implementation.
"""

from __future__ import annotations

from .config import (
    OCRMode,
    PipelineConfig,
    TranslationMode,
)
from .models import (
    DashboardPipelineResult,
    OCRPipelineItem,
    PipelineBBox,
    PipelineResult,
    PipelineTextResult,
    PipelineUnitType,
    TranslationPipelineResult,
)
from .pipeline import (
    BackendPipeline,
    BackendPipelineError,
    BackendPipelineExecutionError,
    BackendPipelineInputError,
)

# DashboardEntry appears inside the public PipelineResult contract, so it must
# also be reachable from the backend public boundary. The UI should not need to
# import backend.translation.dictionary.dashboard directly.
from backend.translation.dictionary.dashboard import DashboardEntry


__all__ = [
    # Main API
    "BackendPipeline",
    "PipelineConfig",

    # Configuration types
    "OCRMode",
    "TranslationMode",

    # Top-level result models
    "PipelineResult",
    "TranslationPipelineResult",
    "DashboardPipelineResult",

    # Result item models
    "PipelineTextResult",
    "OCRPipelineItem",
    "PipelineBBox",
    "PipelineUnitType",
    "DashboardEntry",

    # Public errors
    "BackendPipelineError",
    "BackendPipelineInputError",
    "BackendPipelineExecutionError",
]
