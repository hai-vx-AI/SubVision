from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .models import OCRPipelineItem, PipelineBBox


class OCRResultExtractionError(RuntimeError):
    pass


def extract_ocr_items(raw_results: Any) -> list[OCRPipelineItem]:
    if raw_results is None:
        return []

    if not isinstance(raw_results, (list, tuple)):
        raw_results = [raw_results]

    output: list[OCRPipelineItem] = []

    for result in raw_results:
        data = _extract_payload(result)

        texts = data.get("rec_texts", [])
        scores = data.get("rec_scores", [])
        boxes = data.get("rec_boxes")

        if boxes is None:
            boxes = data.get("rec_polys", [])

        count = min(len(texts), len(boxes))

        for index in range(count):
            text = str(texts[index])
            confidence = float(scores[index]) if index < len(scores) else 0.0
            bbox = _normalize_bbox(boxes[index])

            output.append(
                OCRPipelineItem(
                    text=text,
                    confidence=confidence,
                    bbox=bbox,
                )
            )

    return output


def _extract_payload(result: Any) -> Mapping[str, Any]:
    payload = getattr(result, "json", result)

    if callable(payload):
        payload = payload()

    if not isinstance(payload, Mapping):
        raise OCRResultExtractionError(
            "PaddleOCR result payload must be a mapping."
        )

    data = payload.get("res", payload)

    if not isinstance(data, Mapping):
        raise OCRResultExtractionError(
            "PaddleOCR 'res' payload must be a mapping."
        )

    return data


def _normalize_bbox(box: Any) -> PipelineBBox:
    if hasattr(box, "tolist"):
        box = box.tolist()

    if not isinstance(box, Sequence):
        raise OCRResultExtractionError("OCR bbox must be a sequence.")

    if (
        len(box) >= 4
        and _is_number(box[0])
        and _is_number(box[1])
        and _is_number(box[2])
        and _is_number(box[3])
    ):
        return PipelineBBox(
            x1=int(round(float(box[0]))),
            y1=int(round(float(box[1]))),
            x2=int(round(float(box[2]))),
            y2=int(round(float(box[3]))),
        )

    points: list[tuple[float, float]] = []

    for point in box:
        if hasattr(point, "tolist"):
            point = point.tolist()

        if (
            isinstance(point, Sequence)
            and len(point) >= 2
            and _is_number(point[0])
            and _is_number(point[1])
        ):
            points.append((float(point[0]), float(point[1])))

    if not points:
        raise OCRResultExtractionError(
            "OCR polygon contains no valid points."
        )

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    return PipelineBBox(
        x1=int(round(min(xs))),
        y1=int(round(min(ys))),
        x2=int(round(max(xs))),
        y2=int(round(max(ys))),
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))
