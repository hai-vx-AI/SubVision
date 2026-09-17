from __future__ import annotations

import traceback

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from application.state import ScreenRegion
from backend.pipeline import BackendPipeline, PipelineConfig

from .screen_capture import ScreenCaptureAdapter


class TranslationWorkerSignals(QObject):
    capture_completed = pyqtSignal(int)
    succeeded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)


class TranslationWorker(QRunnable):
    """One screen capture + one BackendPipeline run."""

    def __init__(
        self,
        *,
        request_id: int,
        region: ScreenRegion,
        config: PipelineConfig,
        capture_adapter: ScreenCaptureAdapter,
        pipeline: BackendPipeline,
    ) -> None:
        super().__init__()
        self.request_id = request_id
        self.region = region
        self.config = config
        self.capture_adapter = capture_adapter
        self.pipeline = pipeline
        self.signals = TranslationWorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            image = self.capture_adapter.capture(self.region)

            # Screenshot is already complete, so old overlay may be restored.
            self.signals.capture_completed.emit(self.request_id)

            result = self.pipeline.run(
                image=image,
                config=self.config,
            )

            self.signals.succeeded.emit(
                self.request_id,
                result,
            )

        except Exception:
            self.signals.failed.emit(
                self.request_id,
                traceback.format_exc(),
            )
