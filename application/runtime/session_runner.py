from __future__ import annotations

from PyQt6.QtCore import (
    QObject,
    QThreadPool,
    QTimer,
    pyqtSignal,
)

from application.state import AppState
from application.usecases import ExecutionUseCase
from backend.pipeline import BackendPipeline, PipelineConfig

from .result_store import LatestResultStore
from .screen_capture import ScreenCaptureAdapter
from .translation_worker import TranslationWorker


class SessionRunner(QObject):
    """
    Runtime execution engine.

    Responsibilities
    ----------------
    1. Start / stop one runtime session.
    2. Run one Manual translation request.
    3. Run Auto continuously and sequentially:

           capture
               -> BackendPipeline
               -> result
               -> next capture

       There is NO recurring Auto timer and NO Auto interval.

    4. Guarantee at most one pipeline job is active at a time.
    5. Store the newest PipelineResult in LatestResultStore.
    6. Maintain translation-overlay visibility state through
       ExecutionUseCase.
    7. Emit runtime events for Controller/UI.

    Important separation
    --------------------
    Processing and rendering are intentionally independent.

    SessionRunner NEVER:
        - imports UI widgets;
        - calls TranslationOverlay;
        - calls Dashboard;
        - calls a Renderer;
        - shows or hides text directly.

    Instead:

        SessionRunner
            -> result_updated(result)
            -> Controller / Renderer
            -> UI

    Translation visibility is only application state:

        state.translation_visible

    Visibility policy
    -----------------
    - At session start, translation_visible is False.
    - The FIRST successful result of the session enables translation
      visibility automatically, but only when a translation branch
      exists (Dictionary or Language Model).
    - Later results NEVER force visibility to True.
    - If the user hides translation, new Manual/Auto results continue
      to be computed and stored, but remain hidden.
    - If Auto is running while translation is hidden, Auto continues
      normally in the background.
    - Dashboard visibility is NOT controlled by translation_visible.
      Dashboard is an independent feature handled by Controller/UI.

    Capture suspension
    ------------------
    Before capture:

        capture_started

    is emitted so Controller/UI can temporarily hide SubVision output.

    After the screenshot has been obtained:

        capture_finished

    is emitted. Controller/UI may then restore the latest output
    according to the current AppState.

    `capture_settle_ms` exists only to give hidden UI windows time to
    disappear before the screenshot. It is NOT an Auto interval.
    """

    # General runtime state changed.
    state_changed = pyqtSignal()

    # Human-readable runtime status for RuntimeControls.
    status_changed = pyqtSignal(str)

    # Full traceback string.
    error_occurred = pyqtSignal(str)

    # A new successful PipelineResult became the latest result.
    result_updated = pyqtSignal(object)

    # UI should temporarily hide capture-sensitive output.
    capture_started = pyqtSignal()

    # Screenshot is complete; UI may restore output according to state.
    capture_finished = pyqtSignal()

    def __init__(
        self,
        *,
        state: AppState,
        execution: ExecutionUseCase,
        result_store: LatestResultStore,
        pipeline: BackendPipeline,
        capture_adapter: ScreenCaptureAdapter,
        capture_settle_ms: int = 100,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__()

        self.state = state
        self.execution = execution

        self.result_store = result_store
        self.pipeline = pipeline
        self.capture_adapter = capture_adapter

        # This delay is only for:
        #
        #     hide UI
        #         -> wait briefly
        #         -> capture clean screen
        #
        # It is unrelated to Auto cadence.
        self.capture_settle_ms = max(
            0,
            int(capture_settle_ms),
        )

        self.thread_pool = (
            thread_pool
            if thread_pool is not None
            else QThreadPool.globalInstance()
        )

        # Monotonic request generation.
        #
        # Incrementing this invalidates callbacks belonging to an older
        # request/session after Stop.
        self._request_id = 0

        self._active_request_id: int | None = None
        self._active_worker: TranslationWorker | None = None

        # True only from capture_started until the worker reports that
        # the screenshot itself is complete.
        self._capture_pending = False

        # Visibility is initialized only by the first successful result
        # of each session.
        self._first_successful_result_pending = True

    # ==================================================================
    # PUBLIC STATUS
    # ==================================================================

    @property
    def capture_pending(
        self,
    ) -> bool:
        """
        True while SubVision output must remain hidden for capture.

        Controller may use this when synchronizing visibility so a user
        toggle cannot accidentally show the overlay during the capture
        window.
        """

        return self._capture_pending

    @property
    def has_active_request(
        self,
    ) -> bool:
        return self._active_request_id is not None

    # ==================================================================
    # SESSION
    # ==================================================================

    def start_session(
        self,
    ) -> None:
        """
        Start one runtime session.

        Manual:
            waits for request_manual_translation().

        Auto:
            starts the first run immediately.
            Every successful run schedules the next run.
        """

        if self.state.session_running:
            return

        # Invalidate any stale callback left by an older session.
        self._request_id += 1
        self._active_request_id = None
        self._active_worker = None
        self._capture_pending = False

        # A new session starts without an old visible result.
        self.result_store.clear()

        self._first_successful_result_pending = True

        self.execution.start_session()

        # No result exists yet, therefore the translation overlay starts
        # hidden. The first successful result may enable it.
        self.execution.hide_translation()

        if self.state.execution_mode == "auto":
            self.status_changed.emit(
                "Auto — starting"
            )

            self.state_changed.emit()

            # No cadence timer:
            # start the first run immediately.
            self._request_translation()
            return

        self.status_changed.emit(
            "Ready — press R to translate"
        )
        self.state_changed.emit()

    def stop_session(
        self,
    ) -> None:
        """
        Stop runtime orchestration.

        A QRunnable already executing cannot be forcibly killed safely.
        Instead, its request ID is invalidated. Any later callback from
        that worker is ignored.
        """

        if not self.state.session_running:
            return

        # Invalidate all callbacks from an in-flight worker.
        self._request_id += 1
        self._active_request_id = None
        self._active_worker = None

        self._capture_pending = False
        self._first_successful_result_pending = True

        self.execution.stop_session()

        # Ensure Controller/UI can leave capture-suspended state even if
        # Stop happened in the middle of a capture.
        self.capture_finished.emit()

        self.status_changed.emit(
            "Stopped"
        )
        self.state_changed.emit()

    # ==================================================================
    # MANUAL
    # ==================================================================

    def request_manual_translation(
        self,
    ) -> None:
        """
        Request exactly one run in Manual mode.

        Unlike the old implementation, a Manual request does NOT force
        translation visibility on success.

        Only the first successful result of the session is shown by
        default. Later Manual results respect the user's current
        translation_visible state.
        """

        if not self.state.session_running:
            return

        if self.state.execution_mode != "manual":
            return

        self._request_translation()

    # ==================================================================
    # TRANSLATION VISIBILITY STATE
    # ==================================================================

    def toggle_translation_visibility(
        self,
    ) -> None:
        """
        Toggle only the translation-overlay visibility state.

        This does not:
            - stop Manual/Auto processing;
            - modify Dashboard state;
            - render anything directly.

        Before the first successful result there is nothing to show, so
        the request is ignored.
        """

        if not self.state.session_running:
            return

        if self.state.translation_mode is None:
            return

        if not self.result_store.has_result:
            return

        self.execution.toggle_translation_visibility()
        self.state_changed.emit()

    def show_translation(
        self,
    ) -> None:
        """
        Explicitly set translation visibility ON.

        Normally Controller only needs toggle_translation_visibility(),
        but these explicit methods are useful for deterministic commands.
        """

        if not self.state.session_running:
            return

        if self.state.translation_mode is None:
            return

        if not self.result_store.has_result:
            return

        self.execution.show_translation()
        self.state_changed.emit()

    def hide_translation(
        self,
    ) -> None:
        """
        Explicitly set translation visibility OFF.

        Processing continues normally, including Auto.
        """

        if not self.state.session_running:
            return

        self.execution.hide_translation()
        self.state_changed.emit()

    # ==================================================================
    # REQUEST
    # ==================================================================

    def _request_translation(
        self,
    ) -> None:
        """
        Begin one capture + BackendPipeline run.

        ExecutionUseCase.begin_pipeline() is the single-flight guard.
        """

        if not self.execution.begin_pipeline():
            return

        self._request_id += 1
        request_id = self._request_id

        self._active_request_id = request_id
        self._capture_pending = True

        # Controller/UI must hide:
        #     translation overlay
        #     dashboard
        #     runtime controls if needed
        #
        # before the screenshot.
        self.capture_started.emit()

        self.status_changed.emit(
            "Capturing..."
        )
        self.state_changed.emit()

        # Keep QTimer only as a one-shot event-loop delay.
        #
        # This is NOT the old recurring Auto timer.
        QTimer.singleShot(
            self.capture_settle_ms,
            lambda rid=request_id: (
                self._launch_worker(rid)
            ),
        )

    # ==================================================================
    # WORKER
    # ==================================================================

    def _launch_worker(
        self,
        request_id: int,
    ) -> None:
        """
        Launch exactly one TranslationWorker.
        """

        if (
            not self.state.session_running
            or request_id != self._active_request_id
        ):
            # The request was cancelled before the worker started.
            self.execution.finish_pipeline()

            self._capture_pending = False
            self.capture_finished.emit()
            self.state_changed.emit()
            return

        config = PipelineConfig(
            ocr_mode=self.state.ocr_mode,
            translation_mode=self.state.translation_mode,
            enable_dashboard=self.state.dashboard_enabled,
            enable_ocr_correction=True,
        )

        worker = TranslationWorker(
            request_id=request_id,
            region=self.state.selected_region,
            config=config,
            capture_adapter=self.capture_adapter,
            pipeline=self.pipeline,
        )

        worker.signals.capture_completed.connect(
            self._on_worker_capture_completed
        )

        worker.signals.succeeded.connect(
            self._on_worker_succeeded
        )

        worker.signals.failed.connect(
            self._on_worker_failed
        )

        self._active_worker = worker
        self.thread_pool.start(worker)

    def _on_worker_capture_completed(
        self,
        request_id: int,
    ) -> None:
        """
        Screenshot is complete, but BackendPipeline may still be running.

        From this point Controller/UI may restore the PREVIOUS latest
        result if current state says it should be visible.
        """

        if request_id != self._active_request_id:
            return

        self._capture_pending = False

        self.capture_finished.emit()

        self.status_changed.emit(
            "Translating..."
        )

        self.state_changed.emit()

    def _on_worker_succeeded(
        self,
        request_id: int,
        result: object,
    ) -> None:
        """
        Commit one successful result.

        Critical visibility rule:

            first successful result
                -> translation visible by default

            every later result
                -> NEVER changes translation_visible

        Therefore hidden Auto keeps processing invisibly and replacing the
        latest result without popping the overlay back onto the screen.
        """

        if request_id != self._active_request_id:
            return

        self._active_request_id = None
        self._active_worker = None

        self._capture_pending = False

        self.execution.finish_pipeline()

        # Latest-result replacement is independent from visibility.
        self.result_store.replace(
            result
        )

        # Only the first successful result initializes default visibility.
        #
        # Dashboard-only sessions have no translation overlay, therefore
        # translation_visible remains False.
        if self._first_successful_result_pending:
            self._first_successful_result_pending = False

            if self.state.translation_mode is not None:
                self.execution.show_translation()

        # Controller / Renderer receives the result regardless of whether
        # translation is currently visible.
        self.result_updated.emit(
            result
        )

        if self.state.execution_mode == "auto":
            self.status_changed.emit(
                "Auto — running"
            )
        else:
            self.status_changed.emit(
                "Ready"
            )

        self.state_changed.emit()

        # AUTO:
        #
        # Do not use an interval.
        # Do not overlap requests.
        #
        # Give Qt one event-loop turn to process:
        #     result_updated
        #     UI rendering
        #     Stop / visibility input
        #
        # then start the next capture.
        self._schedule_next_auto_run()

    def _on_worker_failed(
        self,
        request_id: int,
        traceback_text: str,
    ) -> None:
        """
        Finish a failed request.

        Failure does not change translation visibility and does not destroy
        the previous latest result.

        Auto is deliberately NOT restarted automatically after an exception.
        This avoids an infinite high-speed error loop when the failure is
        permanent (invalid backend configuration, dead capture stream, etc.).

        The session remains alive so Controller may decide how to report,
        retry, or stop it.
        """

        if request_id != self._active_request_id:
            return

        self._active_request_id = None
        self._active_worker = None

        self._capture_pending = False

        self.capture_finished.emit()

        self.execution.finish_pipeline()

        self.status_changed.emit(
            "Translation failed"
        )

        self.error_occurred.emit(
            traceback_text
        )

        self.state_changed.emit()

    # ==================================================================
    # AUTO
    # ==================================================================

    def _schedule_next_auto_run(
        self,
    ) -> None:
        """
        Schedule the next Auto iteration with NO cadence interval.

        QTimer.singleShot(0, ...) is used only to return control to Qt's
        event loop before the next request begins. It is not a time-based
        Auto scheduler.
        """

        if not self.state.session_running:
            return

        if self.state.execution_mode != "auto":
            return

        QTimer.singleShot(
            0,
            self._continue_auto_run,
        )

    def _continue_auto_run(
        self,
    ) -> None:
        """
        Re-check state after the event-loop turn, then start the next run.
        """

        if not self.state.session_running:
            return

        if self.state.execution_mode != "auto":
            return

        if self.state.pipeline_running:
            return

        self._request_translation()
