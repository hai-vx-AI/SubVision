from .hotkeys import GlobalHotkeyService
from .renderer import TranslationRenderer
from .result_store import LatestResultStore
from .screen_capture import ScreenCaptureAdapter, ScreenCaptureError
from .session_runner import SessionRunner
from .translation_worker import (
    TranslationWorker,
    TranslationWorkerSignals,
)

__all__ = [
    "LatestResultStore",
    "ScreenCaptureAdapter",
    "ScreenCaptureError",
    "TranslationWorker",
    "TranslationWorkerSignals",
    "TranslationRenderer",
    "SessionRunner",
    "GlobalHotkeyService",
]

"""
SUBVISION APPLICATION RUNTIME
=============================

Manual
------
R
  -> capture
  -> BackendPipeline
  -> LatestResultStore
  -> show new translation

Auto
----
timer
  -> capture
  -> BackendPipeline
  -> LatestResultStore

Visibility
----------
Tab
  -> show/hide latest translation only

Tab never runs BackendPipeline.

Important rules
---------------
- One active pipeline job maximum.
- Auto tick while busy is skipped.
- Manual R shows the new result after success.
- Output is hidden before screenshot capture.
- Previous output may return immediately after capture while AI is still running.
- Stop invalidates in-flight results.
- A model call already running inside a worker cannot be safely preempted;
  its stale result is discarded when it eventually returns.
- PipelineResult is runtime data and does not live in AppState.
"""