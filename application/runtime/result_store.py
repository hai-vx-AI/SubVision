from __future__ import annotations

from backend.pipeline import PipelineResult


class LatestResultStore:
    """Single-slot latest-result buffer. New result replaces old result."""

    def __init__(self) -> None:
        self._result: PipelineResult | None = None

    def replace(self, result: PipelineResult) -> None:
        self._result = result

    def get(self) -> PipelineResult | None:
        return self._result

    def clear(self) -> None:
        self._result = None

    @property
    def has_result(self) -> bool:
        return self._result is not None
