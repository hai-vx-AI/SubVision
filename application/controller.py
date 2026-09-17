from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from backend.pipeline import (
    BackendPipeline,
    PipelineResult,
)

from .runtime.hotkeys import GlobalHotkeyService
from .runtime.renderer import TranslationRenderer
from .runtime.result_store import LatestResultStore
from .runtime.screen_capture import ScreenCaptureAdapter
from .runtime.session_runner import SessionRunner
from .state import (
    AppState,
    ScreenRegion,
)
from .usecases import (
    ExecutionUseCase,
    FeatureUseCase,
    OCRUseCase,
    RegionUseCase,
)

if TYPE_CHECKING:
    from PyQt6.QtCore import QThreadPool

    # Import only for static typing.
    #
    # Runtime import is deliberately avoided so application.controller
    # does not depend on one exact UI import path during module loading.
    from ui.control_panel import ControlPanel


class AppController:
    """
    Main application coordinator and composition root.

    The Controller is the only layer that knows how the main application
    pieces relate to each other.

    Architecture
    ------------

        ControlPanel
            |
            | user intent
            v
        AppController
            |
            +----> UseCases ----> AppState
            |
            +----> SessionRunner
            |          |
            |          +----> ScreenCaptureAdapter
            |          +----> TranslationWorker
            |          +----> BackendPipeline
            |
            +----> TranslationRenderer
            |          |
            |          +----> Translation Overlay
            |          +----> Dashboard
            |
            +----> GlobalHotkeyService

    Responsibilities
    ----------------
    1. Construct and own application UseCases.
    2. Construct and own runtime helpers.
    3. Connect ControlPanel intent signals.
    4. Apply cross-domain policy.
    5. Start / stop runtime sessions.
    6. Route SessionRunner events to Renderer and UI.
    7. Keep UI rendering synchronized with AppState.
    8. Own long-lived capture/hotkey lifecycle.

    The Controller does NOT:
        - implement OCR;
        - implement translation;
        - perform screen capture itself;
        - perform bbox coordinate conversion;
        - draw UI widgets;
        - execute BackendPipeline directly.

    Cross-feature policy
    --------------------
    Dictionary and Language Model share one state field:

        state.translation_mode

    so only one may be active.

    Dashboard is independent:

        state.dashboard_enabled

    The Controller prevents the invalid configuration:

        translation_mode is None
        AND
        dashboard_enabled is False

    Runtime processing
    ------------------
    SessionRunner owns Manual / Auto execution.

    Renderer owns physical output rendering.

    AppState remains the source of truth for application state.
    """

    def __init__(
        self,
        *,
        state: AppState,
        control_panel: ControlPanel,
        pipeline: BackendPipeline,
        capture_adapter: ScreenCaptureAdapter | None = None,
        hotkeys: GlobalHotkeyService | None = None,
        result_store: LatestResultStore | None = None,
        capture_settle_ms: int = 100,
        thread_pool: QThreadPool | None = None,
        auto_available: bool = True,
        auto_unavailable_reason: str | None = None,
        on_state_changed: Callable[[AppState], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self.state = state
        self.control_panel = control_panel
        self.pipeline = pipeline

        self.on_state_changed = on_state_changed
        self.on_error = on_error

        self.auto_available = bool(
            auto_available
        )

        self.auto_unavailable_reason = (
            auto_unavailable_reason
        )

        # ==============================================================
        # USE CASES
        # ==============================================================

        self.region = RegionUseCase(
            state
        )

        self.ocr = OCRUseCase(
            state
        )

        self.features = FeatureUseCase(
            state
        )

        self.execution = ExecutionUseCase(
            state
        )

        # ==============================================================
        # RUNTIME SERVICES
        # ==============================================================

        self.capture_adapter = (
            capture_adapter
            if capture_adapter is not None
            else ScreenCaptureAdapter()
        )

        self.hotkeys = (
            hotkeys
            if hotkeys is not None
            else GlobalHotkeyService()
        )

        self.result_store = (
            result_store
            if result_store is not None
            else LatestResultStore()
        )

        self.renderer = TranslationRenderer(
            state=self.state,
            overlay=self.control_panel.translation_overlay,
            dashboard=self.control_panel.dashboard,
        )

        self.session_runner = SessionRunner(
            state=self.state,
            execution=self.execution,
            result_store=self.result_store,
            pipeline=self.pipeline,
            capture_adapter=self.capture_adapter,
            capture_settle_ms=capture_settle_ms,
            thread_pool=thread_pool,
        )

        # Long-lived capture service is started lazily on the first
        # runtime session.
        self._capture_started = False

        self._closed = False

        self._connect_ui()
        self._connect_runtime()
        self._connect_hotkeys()

        self._normalize_initial_state()
        self.render_state()

    # ==================================================================
    # CONNECTIONS
    # ==================================================================

    def _connect_ui(
        self,
    ) -> None:
        panel = self.control_panel

        # --------------------------------------------------------------
        # Region
        # --------------------------------------------------------------

        panel.fullscreen_requested.connect(
            self._on_fullscreen_requested
        )

        panel.region_selected.connect(
            self._on_region_selected
        )

        panel.region_selection_cancelled.connect(
            self._on_region_selection_cancelled
        )

        # --------------------------------------------------------------
        # OCR
        # --------------------------------------------------------------

        panel.ocr_mode_requested.connect(
            self._on_ocr_mode_requested
        )

        # --------------------------------------------------------------
        # Features
        # --------------------------------------------------------------

        panel.feature_requested.connect(
            self._on_feature_requested
        )

        # --------------------------------------------------------------
        # Execution mode
        # --------------------------------------------------------------

        panel.execution_mode_requested.connect(
            self._on_execution_mode_requested
        )

        # --------------------------------------------------------------
        # Runtime lifecycle
        # --------------------------------------------------------------

        panel.start_requested.connect(
            self._on_start_requested
        )

        panel.translate_requested.connect(
            self._on_manual_translation_requested
        )

        panel.stop_requested.connect(
            self._on_stop_requested
        )

        # Current ControlPanel owns the click-level toggle and emits the
        # resulting physical visibility value.
        #
        # Controller mirrors that intent into AppState.
        #
        # When ControlPanel is simplified later this can become a pure
        # `toggle_translation_requested` signal without changing the
        # underlying application architecture.
        panel.translation_visibility_changed.connect(
            self._on_translation_visibility_changed
        )

    def _connect_runtime(
        self,
    ) -> None:
        runner = self.session_runner

        runner.state_changed.connect(
            self._on_runtime_state_changed
        )

        runner.status_changed.connect(
            self._on_runtime_status_changed
        )

        runner.error_occurred.connect(
            self._on_runtime_error
        )

        runner.result_updated.connect(
            self._on_result_updated
        )

        runner.capture_started.connect(
            self._on_capture_started
        )

        runner.capture_finished.connect(
            self._on_capture_finished
        )

    def _connect_hotkeys(
        self,
    ) -> None:
        self.hotkeys.manual_translate_requested.connect(
            self._on_manual_translation_requested
        )

        self.hotkeys.toggle_translation_requested.connect(
            self._on_hotkey_toggle_translation
        )

    # ==================================================================
    # INITIAL STATE
    # ==================================================================

    def _normalize_initial_state(
        self,
    ) -> None:
        """
        Ensure the initial state is renderable.

        This does not try to encode every business rule in AppState.
        It only repairs impossible Controller-level combinations.
        """

        if not self._features_valid():
            self.features.set_dictionary()

        if (
            self.state.execution_mode == "auto"
            and not self.auto_available
        ):
            self.execution.set_manual()

    # ==================================================================
    # REGION
    # ==================================================================

    def _on_fullscreen_requested(
        self,
    ) -> None:
        if self.state.session_running:
            return

        self.region.set_fullscreen()
        self._state_did_change()

    def _on_region_selected(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        if self.state.session_running:
            return

        try:
            region = ScreenRegion(
                x1=int(x1),
                y1=int(y1),
                x2=int(x2),
                y2=int(y2),
            )
        except Exception as exc:
            self.control_panel.retry_region_selection()
            self._report_error(
                f"Invalid screen region: {exc}"
            )
            return

        result = self.region.confirm_selection(
            region
        )

        if result.accepted:
            self.control_panel.accept_region_selection()
            self._state_did_change()
            return

        self.control_panel.retry_region_selection()

        if result.reason:
            self._report_error(
                result.reason
            )

    def _on_region_selection_cancelled(
        self,
    ) -> None:
        self.region.cancel_selection()
        self._state_did_change()

    # ==================================================================
    # OCR
    # ==================================================================

    def _on_ocr_mode_requested(
        self,
        mode: str,
    ) -> None:
        if self.state.session_running:
            return

        if mode == "fast":
            self.ocr.set_fast()

        elif mode == "quality":
            self.ocr.set_quality()

        else:
            self._report_error(
                f"Unsupported OCR mode: {mode!r}"
            )
            return

        self._state_did_change()

    # ==================================================================
    # FEATURES
    # ==================================================================

    def _on_feature_requested(
        self,
        feature: str,
    ) -> None:
        """
        Apply cross-feature interaction policy.

        UseCases remain independent; relationships are resolved here.
        """

        if self.state.session_running:
            return

        if feature == "dictionary":
            self._toggle_dictionary()

        elif feature == "language_model":
            self._toggle_language_model()

        elif feature == "dashboard":
            self._toggle_dashboard()

        else:
            self._report_error(
                f"Unsupported feature: {feature!r}"
            )
            return

        self._state_did_change()

    def _toggle_dictionary(
        self,
    ) -> None:
        if (
            self.state.translation_mode
            == "dictionary"
        ):
            # Dictionary may be turned off only if Dashboard remains.
            if self.state.dashboard_enabled:
                self.features.clear_translation()
            return

        # Replaces Language Model automatically because translation_mode
        # contains only one translation branch.
        self.features.set_dictionary()

    def _toggle_language_model(
        self,
    ) -> None:
        if (
            self.state.translation_mode
            == "language_model"
        ):
            # Language Model may be turned off only if Dashboard remains.
            if self.state.dashboard_enabled:
                self.features.clear_translation()
            return

        self.features.set_language_model()

    def _toggle_dashboard(
        self,
    ) -> None:
        if not self.state.dashboard_enabled:
            self.features.enable_dashboard()
            return

        # Dashboard is currently ON.
        #
        # It may be disabled only if one translation branch remains.
        if self.state.translation_mode is not None:
            self.features.disable_dashboard()

    def _features_valid(
        self,
    ) -> bool:
        return (
            self.state.translation_mode
            is not None
            or self.state.dashboard_enabled
        )

    # ==================================================================
    # EXECUTION MODE
    # ==================================================================

    def _on_execution_mode_requested(
        self,
        mode: str,
    ) -> None:
        if self.state.session_running:
            return

        if mode == "manual":
            self.execution.set_manual()

        elif mode == "auto":
            if not self.auto_available:
                self._report_error(
                    self.auto_unavailable_reason
                    or "Auto mode is unavailable."
                )
                self.render_state()
                return

            self.execution.set_auto()

        else:
            self._report_error(
                f"Unsupported execution mode: {mode!r}"
            )
            return

        self._state_did_change()

    # ==================================================================
    # START / STOP
    # ==================================================================

    def _on_start_requested(
        self,
    ) -> None:
        if self.state.session_running:
            return

        if not self._features_valid():
            self._report_error(
                "At least one feature must be enabled."
            )
            self.render_state()
            return

        if (
            self.state.execution_mode == "auto"
            and not self.auto_available
        ):
            self._report_error(
                self.auto_unavailable_reason
                or "Auto mode is unavailable."
            )
            return

        try:
            self._ensure_capture_service_started()
        except Exception as exc:
            self._report_error(
                f"Failed to start screen capture: {exc}"
            )
            return

        # Enter runtime UI first so setup controls disappear before any
        # screenshot begins.
        self.control_panel.enter_runtime(
            mode=self.state.execution_mode,
            translation_enabled=(
                self.state.translation_mode
                is not None
            ),
        )

        # A new session has no result yet.
        #
        # Current ControlPanel may set its local overlay visibility during
        # enter_runtime(); normalize it immediately to the AppState policy.
        self.control_panel.set_translation_visible(
            False
        )

        self.renderer.clear()

        self.hotkeys.start()

        self.session_runner.start_session()

        self.render_runtime_state()

    def _on_stop_requested(
        self,
    ) -> None:
        if not self.state.session_running:
            return

        self.session_runner.stop_session()

        self.hotkeys.stop()

        self.renderer.clear()

        self.control_panel.leave_runtime()

        self._state_did_change()

    # ==================================================================
    # MANUAL TRANSLATION
    # ==================================================================

    def _on_manual_translation_requested(
        self,
    ) -> None:
        if not self.state.session_running:
            return

        if self.state.execution_mode != "manual":
            return

        self.session_runner.request_manual_translation()

    # ==================================================================
    # TRANSLATION VISIBILITY
    # ==================================================================

    def _on_translation_visibility_changed(
        self,
        visible: bool,
    ) -> None:
        """
        Receive the current ControlPanel's UI-local visibility change.

        State remains authoritative. If the requested change is invalid
        (for example before the first result exists), render_state() puts
        the UI back to the real state.
        """

        visible = bool(
            visible
        )

        if not self.state.session_running:
            return

        # Avoid recursion when Controller itself renders the current state
        # through ControlPanel.set_translation_visible().
        if (
            visible
            == self.state.translation_visible
        ):
            return

        if visible:
            self.session_runner.show_translation()
        else:
            self.session_runner.hide_translation()

        self.renderer.sync_visibility()
        self.render_runtime_state()

    def _on_hotkey_toggle_translation(
        self,
    ) -> None:
        if not self.state.session_running:
            return

        self.session_runner.toggle_translation_visibility()

        # SessionRunner emits state_changed; this explicit sync is harmless
        # and keeps the visual path deterministic.
        self.renderer.sync_visibility()
        self.render_runtime_state()

    # ==================================================================
    # SESSION RUNNER EVENTS
    # ==================================================================

    def _on_runtime_state_changed(
        self,
    ) -> None:
        self.renderer.sync_visibility()
        self.render_runtime_state()
        self._notify_state_changed()

    def _on_runtime_status_changed(
        self,
        text: str,
    ) -> None:
        if self.state.session_running:
            self.control_panel.set_runtime_status(
                text
            )

    def _on_runtime_error(
        self,
        traceback_text: str,
    ) -> None:
        self._report_error(
            traceback_text
        )

    def _on_result_updated(
        self,
        result: PipelineResult,
    ) -> None:
        """
        One successful PipelineResult became the latest result.

        SessionRunner already stored the result.

        Renderer receives:
            - the complete result;
            - the ScreenRegion used by the current session.

        Renderer then maps local translation bboxes to global screen
        coordinates and updates Dashboard independently.
        """

        self.renderer.set_result(
            result=result,
            region=self.state.selected_region,
        )

        self.render_runtime_state()

    def _on_capture_started(
        self,
    ) -> None:
        """
        Temporarily hide render output before screenshot capture.

        No application visibility state changes here.
        """

        self.renderer.suspend_for_capture()

    def _on_capture_finished(
        self,
    ) -> None:
        """
        Restore output after screenshot according to current AppState.
        """

        self.renderer.resume_after_capture()

    # ==================================================================
    # RENDER
    # ==================================================================

    def render_state(
        self,
    ) -> None:
        """
        Render complete Controller-owned state into ControlPanel.

        Call this after setup-state transitions.
        """

        panel = self.control_panel

        panel.set_ocr_mode(
            self.state.ocr_mode
        )

        panel.set_feature_state(
            translation_mode=(
                self.state.translation_mode
            ),
            dashboard_enabled=(
                self.state.dashboard_enabled
            ),
        )

        panel.set_execution_mode(
            self.state.execution_mode
        )

        panel.set_auto_available(
            self.auto_available,
            reason=self.auto_unavailable_reason,
        )

        panel.set_start_enabled(
            not self.state.session_running
            and self._features_valid()
        )

        if self.state.session_running:
            self.render_runtime_state()

    def render_runtime_state(
        self,
    ) -> None:
        """
        Synchronize runtime controls and physical Renderer visibility.
        """

        if not self.state.session_running:
            return

        self.control_panel.set_pipeline_running(
            self.state.pipeline_running
        )

        # Keep current ControlPanel's UI-local visibility mirror aligned
        # with AppState.
        #
        # Its emitted signal is ignored by the equality guard in
        # _on_translation_visibility_changed().
        self.control_panel.set_translation_visible(
            self.state.translation_visible
        )

        self.renderer.sync_visibility()

    # ==================================================================
    # STATE NOTIFICATION
    # ==================================================================

    def _state_did_change(
        self,
    ) -> None:
        self.render_state()
        self._notify_state_changed()

    def _notify_state_changed(
        self,
    ) -> None:
        if self.on_state_changed is not None:
            self.on_state_changed(
                self.state
            )

    # ==================================================================
    # CAPTURE LIFECYCLE
    # ==================================================================

    def _ensure_capture_service_started(
        self,
    ) -> None:
        if self._capture_started:
            return

        self.capture_adapter.start()
        self._capture_started = True

    # ==================================================================
    # ERROR REPORTING
    # ==================================================================

    def _report_error(
        self,
        message: str,
    ) -> None:
        if self.on_error is not None:
            self.on_error(
                message
            )
            return

        # No UI error-dialog contract exists yet.
        # Keep the error visible during development.
        print(
            message
        )

    # ==================================================================
    # PUBLIC LIFECYCLE
    # ==================================================================

    def shutdown(
        self,
    ) -> None:
        """
        Release Controller-owned runtime resources.

        Call once when the application is closing.
        """

        if self._closed:
            return

        self._closed = True

        if self.state.session_running:
            self.session_runner.stop_session()

        self.hotkeys.stop()

        self.renderer.clear()

        if self._capture_started:
            try:
                self.capture_adapter.close()
            finally:
                self._capture_started = False

    close = shutdown
