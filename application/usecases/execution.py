from __future__ import annotations

from application.state import AppState, ExecutionMode


class ExecutionUseCase:
    """
    Execution/session-domain state operations only.

    Auto here is only an execution MODE. There is no interval, timer, sleep,
    FPS target, capture loop, worker, or BackendPipeline call in this class.

    The realtime Auto loop belongs to application.runtime and should execute
    sequentially with at most one pipeline run in flight:

        capture -> backend -> result -> finish -> next capture

    Cross-domain coordination belongs to the Controller.
    """

    def __init__(self, state: AppState) -> None:
        self.state = state

    # Execution mode ----------------------------------------------------

    def set_mode(self, mode: ExecutionMode) -> None:
        self.state.set_execution_mode(mode)

    def set_manual(self) -> None:
        self.set_mode("manual")

    def set_auto(self) -> None:
        self.set_mode("auto")

    # Session -----------------------------------------------------------

    def start_session(self) -> None:
        self.state.start_session()

    def stop_session(self) -> None:
        self.state.stop_session()

    # Pipeline run state ------------------------------------------------

    def can_start_pipeline(self) -> bool:
        return (
            self.state.session_running
            and not self.state.pipeline_running
        )

    def begin_pipeline(self) -> bool:
        if not self.can_start_pipeline():
            return False

        self.state.begin_pipeline()
        return True

    def finish_pipeline(self) -> None:
        self.state.finish_pipeline()

    # Translation Overlay visibility ----------------------------------

    def show_translation(self) -> None:
        self.state.show_translation()

    def hide_translation(self) -> None:
        self.state.hide_translation()

    def toggle_translation_visibility(self) -> None:
        self.state.toggle_translation_visibility()
