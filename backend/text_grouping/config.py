from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WordToLineConfig:
    """
    Quy tắc gom các OCR bbox thành cùng một dòng.

    Tất cả khoảng cách đều được chuẩn hóa theo chiều cao bbox,
    vì vậy không phụ thuộc vào độ phân giải hay kích thước chữ.
    """

    # Hai bbox có chiều cao lệch quá mức này sẽ không cùng dòng.
    #
    # Ví dụ:
    #     h1 = 20, h2 = 26
    #     ratio = 26 / 20 = 1.30
    #
    # 1.45 cho phép một mức sai lệch vừa phải từ OCR.
    max_height_ratio: float = 1.45

    # Tỷ lệ chồng nhau tối thiểu theo chiều dọc.
    #
    # overlap_height / min(h1, h2)
    #
    # Hai từ cùng dòng thường chồng nhau theo chiều dọc khá nhiều.
    min_vertical_overlap_ratio: float = 0.50

    # Trường hợp bbox OCR không khớp hoàn toàn, vẫn cho phép
    # gom nếu tâm Y đủ gần nhau.
    #
    # abs(center_y1 - center_y2) / average_height
    max_center_y_distance_ratio: float = 0.40

    # Khoảng cách ngang tối đa giữa hai bbox cùng dòng.
    #
    # horizontal_gap / average_height
    #
    # Ví dụ chữ cao 20 px:
    #     gap tối đa khoảng 45 px.
    max_horizontal_gap_ratio: float = 2.25

    def __post_init__(self) -> None:
        if self.max_height_ratio < 1.0:
            raise ValueError(
                "max_height_ratio must be at least 1.0."
            )

        if not 0.0 <= self.min_vertical_overlap_ratio <= 1.0:
            raise ValueError(
                "min_vertical_overlap_ratio must be between 0 and 1."
            )

        if self.max_center_y_distance_ratio < 0.0:
            raise ValueError(
                "max_center_y_distance_ratio must not be negative."
            )

        if self.max_horizontal_gap_ratio < 0.0:
            raise ValueError(
                "max_horizontal_gap_ratio must not be negative."
            )


@dataclass(frozen=True, slots=True)
class LineToParagraphConfig:
    """
    Quy tắc gom các dòng thành cùng một đoạn văn.

    Quy tắc được đặt tương đối chặt vì:

        Tách nhầm một đoạn thành hai nhóm
        ít nguy hiểm hơn
        gom nhầm hai đoạn khác nhau thành một nhóm.
    """

    # Hai dòng phải có kích thước chữ tương đối giống nhau.
    #
    # Ngưỡng này chặt hơn bước word → line để tránh gom
    # tiêu đề với phần nội dung bên dưới.
    max_height_ratio: float = 1.35

    # Khoảng cách dọc tối đa giữa hai dòng.
    #
    # vertical_gap / average_line_height
    max_vertical_gap_ratio: float = 1.20

    # OCR có thể tạo bbox dòng hơi chồng nhau.
    #
    # Giá trị 0.20 cho phép overlap tối đa khoảng 20%
    # chiều cao trung bình của hai dòng.
    max_vertical_overlap_ratio: float = 0.20

    # Hai dòng có thể thuộc cùng đoạn nếu vùng ngang của chúng
    # chồng nhau đủ nhiều.
    #
    # horizontal_overlap / min(width1, width2)
    min_horizontal_overlap_ratio: float = 0.20

    # Hoặc cạnh trái của hai dòng tương đối gần nhau.
    #
    # abs(left1 - left2) / average_line_height
    max_left_edge_distance_ratio: float = 1.25

    # Hỗ trợ văn bản căn phải.
    #
    # abs(right1 - right2) / average_line_height
    max_right_edge_distance_ratio: float = 1.25

    # Hỗ trợ phụ đề hoặc văn bản căn giữa.
    #
    # abs(center_x1 - center_x2) / max(width1, width2)
    max_center_x_distance_ratio: float = 0.28

    # Khi một đoạn đã có nhiều dòng, khoảng cách giữa dòng mới
    # phải tương đối giống khoảng cách trung vị của các dòng trước.
    #
    # 0.60 nghĩa là cho phép lệch khoảng 60%.
    max_spacing_deviation_ratio: float = 0.60

    def __post_init__(self) -> None:
        if self.max_height_ratio < 1.0:
            raise ValueError(
                "max_height_ratio must be at least 1.0."
            )

        if self.max_vertical_gap_ratio < 0.0:
            raise ValueError(
                "max_vertical_gap_ratio must not be negative."
            )

        if self.max_vertical_overlap_ratio < 0.0:
            raise ValueError(
                "max_vertical_overlap_ratio must not be negative."
            )

        if not 0.0 <= self.min_horizontal_overlap_ratio <= 1.0:
            raise ValueError(
                "min_horizontal_overlap_ratio must be between 0 and 1."
            )

        if self.max_left_edge_distance_ratio < 0.0:
            raise ValueError(
                "max_left_edge_distance_ratio must not be negative."
            )

        if self.max_right_edge_distance_ratio < 0.0:
            raise ValueError(
                "max_right_edge_distance_ratio must not be negative."
            )

        if self.max_center_x_distance_ratio < 0.0:
            raise ValueError(
                "max_center_x_distance_ratio must not be negative."
            )

        if self.max_spacing_deviation_ratio < 0.0:
            raise ValueError(
                "max_spacing_deviation_ratio must not be negative."
            )


@dataclass(frozen=True, slots=True)
class TextGroupingConfig:
    """
    Cấu hình tổng của module text grouping.

    Pipeline:

        OCR bbox
        → lọc bbox
        → gom bbox thành TextLine
        → gom TextLine thành TextGroup
    """

    # Loại OCR bbox có confidence quá thấp.
    min_ocr_confidence: float = 0.30

    # Loại bbox quá nhỏ hoặc không hợp lệ.
    min_bbox_width: float = 2.0
    min_bbox_height: float = 2.0

    word_to_line: WordToLineConfig = field(
        default_factory=WordToLineConfig
    )

    line_to_paragraph: LineToParagraphConfig = field(
        default_factory=LineToParagraphConfig
    )

    # Cách nối các OCR token trong cùng dòng.
    word_separator: str = " "

    # Cách nối các dòng trong cùng đoạn.
    #
    # Dùng khoảng trắng để model dịch nhận một câu liên tục.
    line_separator: str = " "

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_ocr_confidence <= 1.0:
            raise ValueError(
                "min_ocr_confidence must be between 0 and 1."
            )

        if self.min_bbox_width <= 0.0:
            raise ValueError(
                "min_bbox_width must be greater than 0."
            )

        if self.min_bbox_height <= 0.0:
            raise ValueError(
                "min_bbox_height must be greater than 0."
            )


DEFAULT_TEXT_GROUPING_CONFIG = TextGroupingConfig()