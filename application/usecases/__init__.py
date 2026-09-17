"""
Application use cases.

This package contains the application-level operations that are allowed to
change :class:`application.state.AppState`.

The main idea is simple:

    UI intent
        -> Controller
        -> UseCase
        -> AppState

A use case represents one small group of state-changing operations for one
application concern.  It does not coordinate the whole application.

Available use cases
-------------------

RegionUseCase
    Owns operations related to the selected screen region:

        - begin custom-region selection;
        - cancel selection;
        - switch back to fullscreen;
        - validate and accept a custom ScreenRegion.

    Local region validation, such as minimum size and screen boundaries,
    belongs here because it is part of the region domain itself.


OCRUseCase
    Owns OCR-mode state changes:

        - Fast OCR;
        - Quality OCR.

    It only changes ``state.ocr_mode``.  It does not load or run an OCR
    model.


FeatureUseCase
    Provides primitive operations for feature state:

        - Dictionary translation;
        - Language Model translation;
        - no translation;
        - Dashboard enabled / disabled.

    Important:

    This use case intentionally does NOT decide relationships between
    Dictionary, Language Model, and Dashboard.

    Examples of cross-feature rules that belong to the Controller:

        - Dictionary and Language Model are mutually exclusive;
        - Dashboard is independent;
        - at least one feature must remain enabled;
        - what happens when the user clicks an already-selected feature.

    FeatureUseCase only provides the state-changing tools needed to apply
    those decisions.


ExecutionUseCase
    Owns execution/session state transitions:

        - Manual mode;
        - Auto mode;
        - start / stop session;
        - begin / finish one pipeline run;
        - show / hide / toggle translation overlay visibility.

    Auto mode here is only a state:

        state.execution_mode == "auto"

    It does NOT implement a timer, sleep interval, worker, capture loop, or
    backend loop.

    Realtime Auto execution belongs to ``application.runtime`` and should
    behave sequentially:

        capture
            -> backend run
            -> result
            -> finish
            -> next capture

    Only one pipeline run should be in flight at a time.


Package boundaries
------------------

Use cases may depend on:

    application.state

Use cases must NOT depend on:

    ui
    backend
    application.runtime
    other use cases

In particular:

    RegionUseCase       does not know OCRUseCase.
    OCRUseCase          does not know FeatureUseCase.
    FeatureUseCase      does not know ExecutionUseCase.
    ExecutionUseCase    does not know RegionUseCase.

Relationships between domains are coordinated elsewhere, normally by
``application.controller``.


Typical construction
--------------------

Create one AppState and give the same instance to every use case:

    from application.state import AppState, ScreenRegion
    from application.usecases import (
        ExecutionUseCase,
        FeatureUseCase,
        OCRUseCase,
        RegionUseCase,
    )

    screen = ScreenRegion(
        x1=0,
        y1=0,
        x2=1536,
        y2=864,
    )

    state = AppState.create(screen)

    region = RegionUseCase(state)
    ocr = OCRUseCase(state)
    features = FeatureUseCase(state)
    execution = ExecutionUseCase(state)

All use cases now operate on the same source of truth.


Typical usage through a Controller
----------------------------------

The Controller receives UI intent and decides which primitive operation to
apply.

Example — Fast OCR button:

    UI:
        ocr_mode_requested("fast")

    Controller:
        ocr.set_fast()

    State:
        state.ocr_mode == "fast"

    Controller:
        control_panel.set_ocr_mode(state.ocr_mode)


Example — Dashboard button:

    Controller first decides whether the requested transition is valid.

    If it is valid:

        features.enable_dashboard()

    Then the Controller renders the resulting state:

        control_panel.set_feature_state(
            translation_mode=state.translation_mode,
            dashboard_enabled=state.dashboard_enabled,
        )


Example — Manual pipeline run:

    if execution.begin_pipeline():
        # Controller asks Runtime to perform one real run.
        ...
        execution.finish_pipeline()


Design rule
-----------

Use cases provide domain-specific state-changing operations.

They are intentionally small.

They do not act as a second Controller and they do not execute backend work.
Their purpose is to keep state mutations explicit, testable, isolated, and
easy to replace when one application concern changes.
"""

from .execution import ExecutionUseCase
from .feature import FeatureUseCase
from .ocr import OCRUseCase
from .region import (
    RegionSelectionResult,
    RegionUseCase,
)

__all__ = [
    "ExecutionUseCase",
    "FeatureUseCase",
    "OCRUseCase",
    "RegionSelectionResult",
    "RegionUseCase",
]
