from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


LayoutModelSize = Literal["S", "M"]
DeviceName = Literal["auto", "cpu", "gpu"]
EngineName = Literal["paddle_static"]

SimplifiedLayoutLabel = Literal[
    "title",
    "paragraph",
    "caption",
    "table",
    "image",
    "chart",
    "formula",
    "header",
    "footer",
    "page_number",
    "other",
]


# ==============================================================
# 23 nhãn gốc của PP-DocLayout-S/M
# ==============================================================

RAW_LAYOUT_LABELS: tuple[str, ...] = (
    "paragraph_title",
    "image",
    "text",
    "number",
    "abstract",
    "content",
    "figure_title",
    "formula",
    "table",
    "table_title",
    "reference",
    "doc_title",
    "footnote",
    "header",
    "algorithm",
    "footer",
    "seal",
    "chart_title",
    "chart",
    "formula_number",
    "header_image",
    "footer_image",
    "aside_text",
)


# ==============================================================
# Ánh xạ 23 nhãn gốc về tập nhãn nội bộ đơn giản
# ==============================================================

DEFAULT_LAYOUT_LABEL_MAPPING: dict[
    str,
    SimplifiedLayoutLabel,
] = {
    # Tiêu đề tài liệu hoặc tiêu đề đoạn.
    "doc_title": "title",
    "paragraph_title": "title",

    # Các vùng chữ thông thường.
    "text": "paragraph",
    "abstract": "paragraph",
    "content": "paragraph",
    "reference": "paragraph",
    "footnote": "paragraph",
    "algorithm": "paragraph",
    "aside_text": "paragraph",

    # Tiêu đề của hình, bảng hoặc biểu đồ được xem như caption.
    "figure_title": "caption",
    "table_title": "caption",
    "chart_title": "caption",

    # Các vùng có cấu trúc riêng.
    "table": "table",
    "image": "image",
    "chart": "chart",

    # Công thức và số công thức.
    "formula": "formula",
    "formula_number": "formula",

    # Đầu trang.
    "header": "header",
    "header_image": "header",

    # Chân trang.
    "footer": "footer",
    "footer_image": "footer",

    # Số trang.
    "number": "page_number",

    # Nhãn không cần thiết đối với luồng dịch.
    "seal": "other",
}


def _default_cpu_threads() -> int:
    """
    Chọn số CPU thread hợp lý nhưng không vượt quá 8.
    """

    return max(
        1,
        min(8, os.cpu_count() or 4),
    )


@dataclass(frozen=True, slots=True)
class LayoutDetectionConfig:
    """
    Cấu hình cho module phát hiện bố cục tài liệu.

    Input:
        np.ndarray ảnh crop từ màn hình.

    Output:
        Danh sách bbox với nhãn bố cục đã được chuẩn hóa.

    Module này không:
        - chạy OCR;
        - đọc nội dung chữ;
        - liên kết bbox layout với bbox OCR;
        - dịch văn bản.
    """

    # ==========================================================
    # Model
    # ==========================================================

    # S:
    #     Model nhẹ nhất, ưu tiên tốc độ.
    #
    # M:
    #     Model cân bằng tốc độ và độ chính xác.
    model_size: LayoutModelSize = "M"

    # ==========================================================
    # Inference
    # ==========================================================

    # auto:
    #     Để PaddleOCR tự chọn GPU nếu có, nếu không dùng CPU.
    #
    # cpu:
    #     Luôn dùng CPU.
    #
    # gpu:
    #     Yêu cầu CUDA GPU.
    device: DeviceName = "auto"

    # Dùng inference engine mặc định và ổn định của Paddle.
    engine: EngineName = "paddle_static"

    # Tắt MKL-DNN mặc định để tránh lỗi oneDNN đã từng gặp
    # trong môi trường Windows của dự án.
    enable_mkldnn: bool = False

    cpu_threads: int = field(
        default_factory=_default_cpu_threads
    )

    # ==========================================================
    # Prediction
    # ==========================================================

    # Loại các bbox có confidence thấp hơn ngưỡng này.
    confidence_threshold: float = 0.35

    # Loại các bbox trùng lặp mạnh.
    layout_nms: bool = True

    # Dự án hiện xử lý từng ảnh crop nên batch size bằng 1.
    batch_size: int = 1

    # ==========================================================
    # Label normalization
    # ==========================================================

    # Ánh xạ nhãn gốc sang nhãn nội bộ.
    label_mapping: dict[
        str,
        SimplifiedLayoutLabel,
    ] = field(
        default_factory=lambda: dict(
            DEFAULT_LAYOUT_LABEL_MAPPING
        )
    )

    # False:
    #     Loại các vùng được chuẩn hóa thành "other".
    #
    # True:
    #     Giữ lại cả những vùng như seal.
    keep_other_regions: bool = False

    # ==========================================================
    # Output
    # ==========================================================

    # Ép bbox nằm trong kích thước ảnh đầu vào.
    clip_boxes_to_image: bool = True

    # Sắp xếp vùng từ trên xuống dưới, trái sang phải.
    sort_regions_by_position: bool = True

    # ==========================================================
    # Input validation
    # ==========================================================

    min_image_width: int = 16
    min_image_height: int = 16

    max_image_pixels: int = 20_000_000

    @property
    def model_name(self) -> str:
        """
        Tên model PaddleOCR tương ứng với lựa chọn S hoặc M.
        """

        return f"PP-DocLayout-{self.model_size}"

    def __post_init__(self) -> None:
        if self.model_size not in {"S", "M"}:
            raise ValueError(
                "model_size must be 'S' or 'M'."
            )

        if self.device not in {
            "auto",
            "cpu",
            "gpu",
        }:
            raise ValueError(
                "device must be 'auto', 'cpu', or 'gpu'."
            )

        if self.engine != "paddle_static":
            raise ValueError(
                "engine currently only supports "
                "'paddle_static'."
            )

        if self.cpu_threads < 1:
            raise ValueError(
                "cpu_threads must be at least 1."
            )

        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(
                "confidence_threshold must be between "
                "0 and 1."
            )

        if self.batch_size < 1:
            raise ValueError(
                "batch_size must be at least 1."
            )

        if self.min_image_width < 1:
            raise ValueError(
                "min_image_width must be at least 1."
            )

        if self.min_image_height < 1:
            raise ValueError(
                "min_image_height must be at least 1."
            )

        if self.max_image_pixels < 1:
            raise ValueError(
                "max_image_pixels must be at least 1."
            )

        allowed_labels = {
            "title",
            "paragraph",
            "caption",
            "table",
            "image",
            "chart",
            "formula",
            "header",
            "footer",
            "page_number",
            "other",
        }

        invalid_labels = {
            label
            for label in self.label_mapping.values()
            if label not in allowed_labels
        }

        if invalid_labels:
            raise ValueError(
                "label_mapping contains invalid normalized "
                f"labels: {sorted(invalid_labels)}"
            )


DEFAULT_LAYOUT_DETECTION_CONFIG = (
    LayoutDetectionConfig()
)