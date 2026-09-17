from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from typing import Any, Mapping, Sequence

from .config import (
    DEFAULT_TEXT_GROUPING_CONFIG,
    TextGroupingConfig,
)
from .geometry import (
    BBox,
    calculate_pair_geometry,
    can_share_line,
    can_share_paragraph,
    left_to_right_key,
    reading_order_key,
    union_boxes,
)


@dataclass(frozen=True, slots=True)
class OCRTextBox:
    """
    Một OCR token đi kèm bbox và confidence.

    `bbox` luôn được chuẩn hóa về BBox(x1, y1, x2, y2),
    bất kể đầu vào ban đầu là rec_boxes hay polygon.
    """

    text: str
    bbox: BBox
    confidence: float = 1.0
    source_index: int | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.confidence):
            raise ValueError(
                "confidence must be a finite number."
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "confidence must be between 0 and 1."
            )

    @classmethod
    def from_raw(
        cls,
        *,
        text: str,
        box: BBox | Sequence[Any],
        confidence: float = 1.0,
        source_index: int | None = None,
    ) -> OCRTextBox:
        return cls(
            text=str(text).strip(),
            bbox=_coerce_bbox(box),
            confidence=float(confidence),
            source_index=source_index,
        )


@dataclass(frozen=True, slots=True)
class TextLine:
    """
    Một dòng văn bản sau bước word -> line.
    """

    words: tuple[OCRTextBox, ...]
    bbox: BBox
    text: str
    average_confidence: float

    def __post_init__(self) -> None:
        if not self.words:
            raise ValueError(
                "TextLine.words must not be empty."
            )

    @classmethod
    def from_words(
        cls,
        words: Sequence[OCRTextBox],
        *,
        separator: str,
    ) -> TextLine:
        ordered = tuple(
            sorted(
                words,
                key=lambda item: left_to_right_key(
                    item.bbox
                ),
            )
        )

        if not ordered:
            raise ValueError(
                "words must contain at least one OCRTextBox."
            )

        return cls(
            words=ordered,
            bbox=union_boxes(
                word.bbox
                for word in ordered
            ),
            text=separator.join(
                word.text
                for word in ordered
                if word.text
            ).strip(),
            average_confidence=(
                sum(
                    word.confidence
                    for word in ordered
                )
                / len(ordered)
            ),
        )


@dataclass(frozen=True, slots=True)
class TextGroup:
    """
    Một paragraph/text block sau bước line -> paragraph.
    """

    lines: tuple[TextLine, ...]
    bbox: BBox
    text: str
    average_confidence: float

    def __post_init__(self) -> None:
        if not self.lines:
            raise ValueError(
                "TextGroup.lines must not be empty."
            )

    @classmethod
    def from_lines(
        cls,
        lines: Sequence[TextLine],
        *,
        separator: str,
    ) -> TextGroup:
        ordered = tuple(
            sorted(
                lines,
                key=lambda line: reading_order_key(
                    line.bbox
                ),
            )
        )

        if not ordered:
            raise ValueError(
                "lines must contain at least one TextLine."
            )

        total_words = sum(
            len(line.words)
            for line in ordered
        )

        if total_words > 0:
            weighted_confidence = (
                sum(
                    line.average_confidence
                    * len(line.words)
                    for line in ordered
                )
                / total_words
            )
        else:
            weighted_confidence = 0.0

        return cls(
            lines=ordered,
            bbox=union_boxes(
                line.bbox
                for line in ordered
            ),
            text=separator.join(
                line.text
                for line in ordered
                if line.text
            ).strip(),
            average_confidence=weighted_confidence,
        )


class TextGrouper:
    """
    Gom OCR bbox theo pipeline:

        OCR token
        -> filter
        -> TextLine
        -> TextGroup

    Module này chỉ dùng geometry/rule.
    Không OCR, không dịch, không sửa nội dung text.
    """

    def __init__(
        self,
        config: TextGroupingConfig | None = None,
    ) -> None:
        self.config = (
            config
            or DEFAULT_TEXT_GROUPING_CONFIG
        )

    def group(
        self,
        *,
        texts: Sequence[str],
        boxes: Sequence[BBox | Sequence[Any]],
        scores: Sequence[float] | None = None,
    ) -> list[TextGroup]:
        """
        API thuận tiện cho output dạng:

            rec_texts
            rec_boxes / rec_polys
            rec_scores
        """

        items = self.make_items(
            texts=texts,
            boxes=boxes,
            scores=scores,
        )

        return self.group_items(items)

    def group_paddle_result(
        self,
        result: Mapping[str, Any],
    ) -> list[TextGroup]:
        """
        Nhận trực tiếp dictionary của PaddleOCR/PaddleX.

        Hỗ trợ cả:

            {
                "rec_texts": ...,
                "rec_scores": ...,
                "rec_boxes": ...
            }

        và:

            {
                "res": {
                    ...
                }
            }

        Nếu không có rec_boxes thì fallback sang rec_polys.
        """

        data: Mapping[str, Any] = result

        nested = result.get("res")

        if isinstance(nested, Mapping):
            data = nested

        texts = data.get("rec_texts")

        if texts is None:
            return []

        boxes = data.get("rec_boxes")

        if boxes is None or len(boxes) == 0:
            boxes = data.get("rec_polys")

        if boxes is None:
            return []

        scores = data.get("rec_scores")

        return self.group(
            texts=texts,
            boxes=boxes,
            scores=scores,
        )

    def make_items(
        self,
        *,
        texts: Sequence[str],
        boxes: Sequence[BBox | Sequence[Any]],
        scores: Sequence[float] | None = None,
    ) -> list[OCRTextBox]:
        if len(texts) != len(boxes):
            raise ValueError(
                "texts and boxes must have the same length."
            )

        if scores is not None and len(scores) != len(texts):
            raise ValueError(
                "scores and texts must have the same length."
            )

        items: list[OCRTextBox] = []

        for index, (text, box) in enumerate(
            zip(texts, boxes)
        ):
            confidence = (
                1.0
                if scores is None
                else float(scores[index])
            )

            items.append(
                OCRTextBox.from_raw(
                    text=text,
                    box=box,
                    confidence=confidence,
                    source_index=index,
                )
            )

        return items

    def filter_items(
        self,
        items: Sequence[OCRTextBox],
    ) -> list[OCRTextBox]:
        """
        Loại text rỗng, confidence thấp và bbox quá nhỏ.
        """

        config = self.config

        return [
            item
            for item in items
            if (
                item.text.strip()
                and item.confidence
                >= config.min_ocr_confidence
                and item.bbox.width
                >= config.min_bbox_width
                and item.bbox.height
                >= config.min_bbox_height
            )
        ]

    def group_items(
        self,
        items: Sequence[OCRTextBox],
    ) -> list[TextGroup]:
        filtered = self.filter_items(items)

        if not filtered:
            return []

        lines = self.group_words_to_lines(
            filtered
        )

        return self.group_lines_to_paragraphs(
            lines
        )

    def group_words_to_lines(
        self,
        items: Sequence[OCRTextBox],
    ) -> list[TextLine]:
        """
        Gom token thành dòng bằng greedy clustering.

        Với mỗi token:
        - tìm các dòng hiện có thỏa can_share_line()
        - chọn dòng có center-Y gần nhất
        - nếu không có candidate thì tạo dòng mới
        """

        filtered = self.filter_items(items)

        if not filtered:
            return []

        ordered_items = sorted(
            filtered,
            key=lambda item: reading_order_key(
                item.bbox
            ),
        )

        line_buckets: list[list[OCRTextBox]] = []

        for item in ordered_items:
            best_index: int | None = None
            best_score: tuple[float, float, float] | None = None

            for index, bucket in enumerate(
                line_buckets
            ):
                line_box = union_boxes(
                    word.bbox
                    for word in bucket
                )

                if not can_share_line(
                    item.bbox,
                    line_box,
                    self.config.word_to_line,
                ):
                    continue

                metrics = calculate_pair_geometry(
                    item.bbox,
                    line_box,
                )

                score = (
                    metrics.center_y_distance_ratio,
                    metrics.horizontal_gap_ratio,
                    abs(
                        item.bbox.center_y
                        - line_box.center_y
                    ),
                )

                if (
                    best_score is None
                    or score < best_score
                ):
                    best_score = score
                    best_index = index

            if best_index is None:
                line_buckets.append([item])
            else:
                line_buckets[best_index].append(
                    item
                )

        lines = [
            TextLine.from_words(
                bucket,
                separator=self.config.word_separator,
            )
            for bucket in line_buckets
        ]

        return sorted(
            lines,
            key=lambda line: reading_order_key(
                line.bbox
            ),
        )

    def group_lines_to_paragraphs(
        self,
        lines: Sequence[TextLine],
    ) -> list[TextGroup]:
        """
        Gom TextLine thành TextGroup.

        Một dòng mới được so với dòng cuối của từng group.
        Điều này cho phép xử lý nhiều block/cột tốt hơn so với
        chỉ so với dòng đứng ngay trước trong toàn trang.
        """

        if not lines:
            return []

        ordered_lines = sorted(
            lines,
            key=lambda line: reading_order_key(
                line.bbox
            ),
        )

        group_buckets: list[list[TextLine]] = []

        for line in ordered_lines:
            best_index: int | None = None
            best_score: tuple[float, float, float] | None = None

            for index, bucket in enumerate(
                group_buckets
            ):
                previous = bucket[-1]

                # Group chỉ phát triển theo chiều trên -> dưới.
                if line.bbox.center_y <= previous.bbox.center_y:
                    continue

                reference_gap_ratio = (
                    _median_line_gap_ratio(bucket)
                )

                if not can_share_paragraph(
                    previous.bbox,
                    line.bbox,
                    self.config.line_to_paragraph,
                    reference_gap_ratio=(
                        reference_gap_ratio
                    ),
                ):
                    continue

                metrics = calculate_pair_geometry(
                    previous.bbox,
                    line.bbox,
                )

                score = (
                    abs(metrics.vertical_gap_ratio),
                    metrics.center_x_distance_ratio,
                    metrics.left_edge_distance_ratio,
                )

                if (
                    best_score is None
                    or score < best_score
                ):
                    best_score = score
                    best_index = index

            if best_index is None:
                group_buckets.append([line])
            else:
                group_buckets[best_index].append(
                    line
                )

        groups = [
            TextGroup.from_lines(
                bucket,
                separator=self.config.line_separator,
            )
            for bucket in group_buckets
        ]

        return sorted(
            groups,
            key=lambda group: reading_order_key(
                group.bbox
            ),
        )


def group_ocr(
    *,
    texts: Sequence[str],
    boxes: Sequence[BBox | Sequence[Any]],
    scores: Sequence[float] | None = None,
    config: TextGroupingConfig | None = None,
) -> list[TextGroup]:
    """
    Functional API ngắn gọn.
    """

    return TextGrouper(
        config=config
    ).group(
        texts=texts,
        boxes=boxes,
        scores=scores,
    )


def group_paddle_result(
    result: Mapping[str, Any],
    *,
    config: TextGroupingConfig | None = None,
) -> list[TextGroup]:
    """
    Functional API cho raw PaddleOCR JSON/result dictionary.
    """

    return TextGrouper(
        config=config
    ).group_paddle_result(result)


def _coerce_bbox(
    box: BBox | Sequence[Any],
) -> BBox:
    if isinstance(box, BBox):
        return box

    values = list(box)

    if len(values) == 4 and all(
        _is_scalar(value)
        for value in values
    ):
        return BBox.from_sequence(values)

    return BBox.from_polygon(values)


def _is_scalar(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False

    # Một point/polygon như [10, 20] không được xem là scalar.
    try:
        len(value)
    except TypeError:
        return True

    return False


def _median_line_gap_ratio(
    lines: Sequence[TextLine],
) -> float | None:
    """
    Khoảng cách dòng trung vị của một paragraph đang xây.

    Với group chỉ có 1 dòng chưa đủ dữ liệu -> None.
    """

    if len(lines) < 2:
        return None

    gaps = [
        calculate_pair_geometry(
            upper.bbox,
            lower.bbox,
        ).vertical_gap_ratio
        for upper, lower in zip(
            lines,
            lines[1:],
        )
    ]

    if not gaps:
        return None

    return float(median(gaps))
