from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median
from typing import Iterable, Sequence

from .config import (
    LineToParagraphConfig,
    WordToLineConfig,
)


EPSILON = 1e-8

Number = int | float
BBoxCoordinates = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class BBox:
    """
    Bounding box dạng:

        (x1, y1, x2, y2)

    Trong đó:
        x1, y1: góc trên bên trái
        x2, y2: góc dưới bên phải
    """

    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        coordinates = (
            self.x1,
            self.y1,
            self.x2,
            self.y2,
        )

        if not all(
            math.isfinite(value)
            for value in coordinates
        ):
            raise ValueError(
                "BBox coordinates must be finite numbers."
            )

        if self.x2 <= self.x1:
            raise ValueError(
                "BBox x2 must be greater than x1."
            )

        if self.y2 <= self.y1:
            raise ValueError(
                "BBox y2 must be greater than y1."
            )

    @classmethod
    def from_sequence(
        cls,
        coordinates: Sequence[Number],
    ) -> BBox:
        """
        Tạo BBox từ:

            [x1, y1, x2, y2]
        """

        if len(coordinates) != 4:
            raise ValueError(
                "BBox coordinates must contain exactly 4 values."
            )

        x1, y1, x2, y2 = (
            float(value)
            for value in coordinates
        )

        return cls(
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
        )

    @classmethod
    def from_polygon(
        cls,
        points: Sequence[Sequence[Number]],
    ) -> BBox:
        """
        Chuyển polygon OCR thành axis-aligned bbox.

        Ví dụ PaddleOCR có thể trả:

            [
                [x1, y1],
                [x2, y2],
                [x3, y3],
                [x4, y4],
            ]
        """

        if len(points) < 2:
            raise ValueError(
                "Polygon must contain at least 2 points."
            )

        x_values: list[float] = []
        y_values: list[float] = []

        for point in points:
            if len(point) != 2:
                raise ValueError(
                    "Each polygon point must contain x and y."
                )

            x = float(point[0])
            y = float(point[1])

            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError(
                    "Polygon coordinates must be finite."
                )

            x_values.append(x)
            y_values.append(y)

        return cls(
            x1=min(x_values),
            y1=min(y_values),
            x2=max(x_values),
            y2=max(y_values),
        )

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def coordinates(self) -> BBoxCoordinates:
        return (
            self.x1,
            self.y1,
            self.x2,
            self.y2,
        )

    def union(
        self,
        other: BBox,
    ) -> BBox:
        """
        Tạo bbox bao phủ cả hai bbox.
        """

        return BBox(
            x1=min(self.x1, other.x1),
            y1=min(self.y1, other.y1),
            x2=max(self.x2, other.x2),
            y2=max(self.y2, other.y2),
        )

    def to_integer_tuple(
        self,
    ) -> tuple[int, int, int, int]:
        """
        Chuyển thành bbox integer nhưng không cắt mất nội dung.
        """

        return (
            math.floor(self.x1),
            math.floor(self.y1),
            math.ceil(self.x2),
            math.ceil(self.y2),
        )


@dataclass(frozen=True, slots=True)
class PairGeometry:
    """
    Các đại lượng hình học giữa hai bbox.

    Các giá trị ratio giúp thuật toán không phụ thuộc
    kích thước ảnh hoặc kích thước font.
    """

    average_height: float
    average_width: float

    height_ratio: float
    width_ratio: float

    horizontal_gap: float
    vertical_gap: float

    horizontal_gap_ratio: float
    vertical_gap_ratio: float

    horizontal_overlap_ratio: float
    vertical_overlap_ratio: float

    center_x_distance_ratio: float
    center_y_distance_ratio: float

    left_edge_distance_ratio: float
    right_edge_distance_ratio: float


def safe_ratio(
    numerator: float,
    denominator: float,
) -> float:
    """
    Phép chia an toàn.
    """

    return numerator / max(
        abs(denominator),
        EPSILON,
    )


def size_ratio(
    first: float,
    second: float,
) -> float:
    """
    Trả về tỷ lệ kích thước lớn / nhỏ.

    Kết quả luôn >= 1.
    """

    larger = max(first, second)
    smaller = min(first, second)

    return safe_ratio(
        larger,
        smaller,
    )


def horizontal_overlap(
    first: BBox,
    second: BBox,
) -> float:
    """
    Số pixel chồng nhau theo chiều ngang.
    """

    return max(
        0.0,
        min(first.x2, second.x2)
        - max(first.x1, second.x1),
    )


def vertical_overlap(
    first: BBox,
    second: BBox,
) -> float:
    """
    Số pixel chồng nhau theo chiều dọc.
    """

    return max(
        0.0,
        min(first.y2, second.y2)
        - max(first.y1, second.y1),
    )


def horizontal_overlap_ratio(
    first: BBox,
    second: BBox,
) -> float:
    """
    Mức độ chồng nhau theo chiều ngang.

        overlap / chiều rộng bbox nhỏ hơn
    """

    return safe_ratio(
        horizontal_overlap(first, second),
        min(first.width, second.width),
    )


def vertical_overlap_ratio(
    first: BBox,
    second: BBox,
) -> float:
    """
    Mức độ chồng nhau theo chiều dọc.

        overlap / chiều cao bbox nhỏ hơn
    """

    return safe_ratio(
        vertical_overlap(first, second),
        min(first.height, second.height),
    )


def horizontal_gap(
    first: BBox,
    second: BBox,
) -> float:
    """
    Khoảng cách ngang giữa hai bbox.

    Trả về 0 nếu chúng đang chồng nhau theo chiều ngang.
    """

    left, right = sorted(
        (first, second),
        key=lambda box: box.x1,
    )

    return max(
        0.0,
        right.x1 - left.x2,
    )


def vertical_gap(
    first: BBox,
    second: BBox,
) -> float:
    """
    Khoảng cách dọc có dấu giữa bbox trên và bbox dưới.

    Giá trị:
        > 0: hai bbox có khoảng trống.
        = 0: hai bbox vừa chạm nhau.
        < 0: hai bbox đang chồng nhau.
    """

    upper, lower = order_top_to_bottom(
        first,
        second,
    )

    return lower.y1 - upper.y2


def order_left_to_right(
    first: BBox,
    second: BBox,
) -> tuple[BBox, BBox]:
    """
    Trả bbox bên trái trước.
    """

    if (
        first.x1,
        first.center_x,
    ) <= (
        second.x1,
        second.center_x,
    ):
        return first, second

    return second, first


def order_top_to_bottom(
    first: BBox,
    second: BBox,
) -> tuple[BBox, BBox]:
    """
    Trả bbox phía trên trước.
    """

    if (
        first.center_y,
        first.y1,
    ) <= (
        second.center_y,
        second.y1,
    ):
        return first, second

    return second, first


def calculate_pair_geometry(
    first: BBox,
    second: BBox,
) -> PairGeometry:
    """
    Tính toàn bộ thông số hình học giữa hai bbox.
    """

    average_height = (
        first.height + second.height
    ) / 2.0

    average_width = (
        first.width + second.width
    ) / 2.0

    h_gap = horizontal_gap(
        first,
        second,
    )

    v_gap = vertical_gap(
        first,
        second,
    )

    return PairGeometry(
        average_height=average_height,
        average_width=average_width,

        height_ratio=size_ratio(
            first.height,
            second.height,
        ),

        width_ratio=size_ratio(
            first.width,
            second.width,
        ),

        horizontal_gap=h_gap,
        vertical_gap=v_gap,

        horizontal_gap_ratio=safe_ratio(
            h_gap,
            average_height,
        ),

        vertical_gap_ratio=safe_ratio(
            v_gap,
            average_height,
        ),

        horizontal_overlap_ratio=(
            horizontal_overlap_ratio(
                first,
                second,
            )
        ),

        vertical_overlap_ratio=(
            vertical_overlap_ratio(
                first,
                second,
            )
        ),

        center_x_distance_ratio=safe_ratio(
            abs(
                first.center_x
                - second.center_x
            ),
            max(first.width, second.width),
        ),

        center_y_distance_ratio=safe_ratio(
            abs(
                first.center_y
                - second.center_y
            ),
            average_height,
        ),

        left_edge_distance_ratio=safe_ratio(
            abs(first.x1 - second.x1),
            average_height,
        ),

        right_edge_distance_ratio=safe_ratio(
            abs(first.x2 - second.x2),
            average_height,
        ),
    )


def can_share_line(
    first: BBox,
    second: BBox,
    config: WordToLineConfig,
) -> bool:
    """
    Kiểm tra hai OCR bbox có thể thuộc cùng một dòng hay không.

    Điều kiện:

        1. Chiều cao tương đối giống nhau.
        2. Cùng mức Y.
        3. Khoảng cách ngang không quá lớn.
    """

    metrics = calculate_pair_geometry(
        first,
        second,
    )

    similar_height = (
        metrics.height_ratio
        <= config.max_height_ratio
    )

    aligned_vertically = (
        metrics.vertical_overlap_ratio
        >= config.min_vertical_overlap_ratio
        or
        metrics.center_y_distance_ratio
        <= config.max_center_y_distance_ratio
    )

    close_horizontally = (
        metrics.horizontal_gap_ratio
        <= config.max_horizontal_gap_ratio
    )

    return (
        similar_height
        and aligned_vertically
        and close_horizontally
    )


def can_share_paragraph(
    upper_line: BBox,
    lower_line: BBox,
    config: LineToParagraphConfig,
    reference_gap_ratio: float | None = None,
) -> bool:
    """
    Kiểm tra hai dòng có thể thuộc cùng một đoạn hay không.

    reference_gap_ratio:
        Khoảng cách dòng trung vị của đoạn hiện tại.

        Khi đoạn mới chỉ có một dòng, truyền None.
    """

    upper, lower = order_top_to_bottom(
        upper_line,
        lower_line,
    )

    # Không cho nối một dòng nằm gần như ngang hàng
    # thành quan hệ trên → dưới.
    if lower.center_y <= upper.center_y:
        return False

    metrics = calculate_pair_geometry(
        upper,
        lower,
    )

    similar_height = (
        metrics.height_ratio
        <= config.max_height_ratio
    )

    valid_vertical_gap = (
        -config.max_vertical_overlap_ratio
        <= metrics.vertical_gap_ratio
        <= config.max_vertical_gap_ratio
    )

    aligned_horizontally = (
        metrics.horizontal_overlap_ratio
        >= config.min_horizontal_overlap_ratio
        or
        metrics.left_edge_distance_ratio
        <= config.max_left_edge_distance_ratio
        or
        metrics.right_edge_distance_ratio
        <= config.max_right_edge_distance_ratio
        or
        metrics.center_x_distance_ratio
        <= config.max_center_x_distance_ratio
    )

    spacing_is_consistent = True

    if reference_gap_ratio is not None:
        spacing_is_consistent = is_spacing_consistent(
            current_gap_ratio=(
                metrics.vertical_gap_ratio
            ),
            reference_gap_ratio=(
                reference_gap_ratio
            ),
            max_deviation_ratio=(
                config.max_spacing_deviation_ratio
            ),
        )

    return (
        similar_height
        and valid_vertical_gap
        and aligned_horizontally
        and spacing_is_consistent
    )


def is_spacing_consistent(
    *,
    current_gap_ratio: float,
    reference_gap_ratio: float,
    max_deviation_ratio: float,
) -> bool:
    """
    So sánh khoảng cách dòng hiện tại với khoảng cách điển hình
    của đoạn đang xét.

    Ví dụ:

        Các gap trước:
            0.50, 0.55, 0.52

        Gap mới:
            0.54
        → có khả năng cùng đoạn.

        Gap mới:
            1.80
        → có khả năng bắt đầu đoạn mới.
    """

    difference = abs(
        current_gap_ratio
        - reference_gap_ratio
    )

    scale = max(
        abs(current_gap_ratio),
        abs(reference_gap_ratio),
        0.50,
    )

    deviation_ratio = difference / scale

    return (
        deviation_ratio
        <= max_deviation_ratio
    )


def union_boxes(
    boxes: Iterable[BBox],
) -> BBox:
    """
    Tạo một bbox bao phủ toàn bộ danh sách bbox.
    """

    box_list = list(boxes)

    if not box_list:
        raise ValueError(
            "boxes must contain at least one BBox."
        )

    result = box_list[0]

    for box in box_list[1:]:
        result = result.union(box)

    return result


def median_box_height(
    boxes: Iterable[BBox],
) -> float:
    """
    Tính chiều cao trung vị của một nhóm bbox.
    """

    heights = [
        box.height
        for box in boxes
    ]

    if not heights:
        raise ValueError(
            "boxes must contain at least one BBox."
        )

    return float(
        median(heights)
    )


def reading_order_key(
    box: BBox,
) -> tuple[float, float]:
    """
    Key sắp xếp đơn giản:

        trên xuống dưới
        trái sang phải
    """

    return (
        box.center_y,
        box.x1,
    )


def left_to_right_key(
    box: BBox,
) -> tuple[float, float]:
    """
    Key sắp xếp các bbox trong cùng dòng.
    """

    return (
        box.x1,
        box.center_y,
    )