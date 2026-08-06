from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


EngineName = Literal["paddle_static"]
LimitType = Literal["max", "min"]
DeviceName = Literal["auto", "cpu", "gpu"]


def _default_cpu_threads() -> int:
    """
    Dùng tối đa 8 CPU threads để OCR đủ nhanh nhưng không chiếm
    toàn bộ tài nguyên của ứng dụng desktop.
    """
    return max(1, min(8, os.cpu_count() or 4))


@dataclass(frozen=True, slots=True)
class FastOCRConfig:
    """
    Toàn bộ cấu hình thuộc riêng module OCR fast.

    Module bên ngoài có thể truyền một config khác vào FastOCR,
    nhưng config đó phải vượt qua kiểm tra trong __post_init__.
    """

    # ==========================================================
    # Pretrained models
    # ==========================================================

    detection_model_name: str = "PP-OCRv5_mobile_det"
    recognition_model_name: str = "en_PP-OCRv5_mobile_rec"

    # ==========================================================
    # Runtime
    # ==========================================================

    device: DeviceName = "auto"
    engine: EngineName = "paddle_static"

    enable_mkldnn: bool = False
    cpu_threads: int = field(default_factory=_default_cpu_threads)

    # ==========================================================
    # Các module không cần thiết cho phụ đề tiếng Anh nằm ngang
    # ==========================================================

    use_doc_orientation_classify: bool = False
    use_doc_unwarping: bool = False
    use_textline_orientation: bool = False

    # ==========================================================
    # Text detection
    # ==========================================================

    # Cạnh dài nhất của ảnh detector xử lý không vượt quá 640 px.
    # PaddleOCR tự giữ tỉ lệ ảnh và resize nội bộ.
    text_det_limit_side_len: int = 640
    text_det_limit_type: LimitType = "max"

    # Ngưỡng pixel được xem là vùng chữ.
    text_det_thresh: float = 0.30

    # Ngưỡng giữ lại bounding box chữ.
    text_det_box_thresh: float = 0.60

    # Mức mở rộng bounding box để tránh crop sát nét chữ.
    text_det_unclip_ratio: float = 1.50

    # ==========================================================
    # Text recognition
    # ==========================================================

    # Phụ đề thường chỉ có một vài dòng nên batch 1 là đủ ổn định.
    text_recognition_batch_size: int = 1

    # Không loại bỏ kết quả theo confidence tại OCR.
    # Module khác có thể quyết định lọc sau.
    text_rec_score_thresh: float = 0.05

    # ==========================================================
    # Hợp đồng đầu vào
    # ==========================================================

    min_image_height: int = 16
    min_image_width: int = 16

    # Khoảng 20 MP, đủ nhận ảnh 4K nhưng ngăn dữ liệu quá lớn
    # gây tiêu thụ RAM bất thường.
    max_image_pixels: int = 20_000_000

    def __post_init__(self) -> None:
        """Kiểm tra config trước khi cho phép khởi tạo model."""

        if not self.detection_model_name.strip():
            raise ValueError(
                "detection_model_name must not be empty."
            )

        if not self.recognition_model_name.strip():
            raise ValueError(
                "recognition_model_name must not be empty."
            )

        if self.device not in {"auto", "cpu", "gpu"}:
            raise ValueError(
                "device must be 'auto', 'cpu', or 'gpu'."
            )

        if self.engine != "paddle_static":
            raise ValueError(
                "FastOCRConfig currently supports "
                "engine='paddle_static' only."
            )

        if self.cpu_threads < 1:
            raise ValueError(
                "cpu_threads must be at least 1."
            )

        if self.text_det_limit_side_len < 32:
            raise ValueError(
                "text_det_limit_side_len must be at least 32."
            )

        if self.text_det_limit_type not in {"max", "min"}:
            raise ValueError(
                "text_det_limit_type must be 'max' or 'min'."
            )

        thresholds = {
            "text_det_thresh": self.text_det_thresh,
            "text_det_box_thresh": self.text_det_box_thresh,
            "text_rec_score_thresh": self.text_rec_score_thresh,
        }

        for name, value in thresholds.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} must be between 0 and 1."
                )

        if self.text_det_unclip_ratio <= 0:
            raise ValueError(
                "text_det_unclip_ratio must be greater than 0."
            )

        if self.text_recognition_batch_size < 1:
            raise ValueError(
                "text_recognition_batch_size must be at least 1."
            )

        if self.min_image_height < 1:
            raise ValueError(
                "min_image_height must be positive."
            )

        if self.min_image_width < 1:
            raise ValueError(
                "min_image_width must be positive."
            )

        minimum_pixels = (
            self.min_image_height * self.min_image_width
        )

        if self.max_image_pixels < minimum_pixels:
            raise ValueError(
                "max_image_pixels is smaller than the minimum "
                "allowed image size."
            )


DEFAULT_FAST_OCR_CONFIG = FastOCRConfig()