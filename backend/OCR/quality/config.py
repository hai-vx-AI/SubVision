from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


EngineName = Literal["paddle_static"]
LimitType = Literal["max", "min"]


def _default_cpu_threads() -> int:
    """
    Dùng tối đa 8 CPU threads.

    QualityOCR ưu tiên GPU, nhưng vẫn cho phép chạy CPU
    khi máy không có GPU tương thích.
    """
    return max(1, min(8, os.cpu_count() or 4))


def _validate_device(device: str) -> None:
    """
    Các giá trị hợp lệ:

        auto
        cpu
        gpu
        gpu:0
        gpu:1
        ...
    """

    if device in {"auto", "cpu", "gpu"}:
        return

    if device.startswith("gpu:"):
        gpu_index = device.removeprefix("gpu:")

        if gpu_index.isdigit():
            return

    raise ValueError(
        "device must be 'auto', 'cpu', 'gpu', "
        "or a specific GPU such as 'gpu:0'."
    )


@dataclass(frozen=True, slots=True)
class QualityOCRConfig:
    """
    Cấu hình nội bộ cho OCR quality.

    QualityOCR sử dụng model lớn hơn và ảnh đầu vào có độ phân giải
    xử lý cao hơn FastOCR nhằm ưu tiên độ chính xác.
    """

    # ==========================================================
    # Pretrained models
    # ==========================================================

    detection_model_name: str = "PP-OCRv6_medium_det"
    recognition_model_name: str = "PP-OCRv6_medium_rec"

    # ==========================================================
    # Runtime
    # ==========================================================

    # auto:
    # - dùng GPU nếu PaddlePaddle hỗ trợ GPU;
    # - nếu không thì dùng CPU.
    device: str = "auto"

    engine: EngineName = "paddle_static"

    # Tạm tắt oneDNN do môi trường Windows hiện tại từng gặp lỗi:
    # ConvertPirAttribute2RuntimeAttribute.
    enable_mkldnn: bool = False

    cpu_threads: int = field(default_factory=_default_cpu_threads)

    # ==========================================================
    # Các module phụ
    # ==========================================================

    # Ảnh đầu vào là screenshot nên không cần xoay toàn tài liệu.
    use_doc_orientation_classify: bool = False

    # Screenshot không bị cong như ảnh chụp giấy.
    use_doc_unwarping: bool = False

    # Module mặc định của PaddleOCR chỉ xử lý hướng 0° và 180°.
    # Chưa cần bật trong phiên bản hiện tại.
    use_textline_orientation: bool = False

    # ==========================================================
    # Text detection
    # ==========================================================

    # Quality xử lý ở độ phân giải cao gấp đôi FastOCR.
    #
    # Ảnh có cạnh dài > 1280 sẽ được thu nhỏ, giữ nguyên tỉ lệ.
    # Ảnh có cạnh dài <= 1280 không bị ép thành 1280×1280.
    text_det_limit_side_len: int = 1280
    text_det_limit_type: LimitType = "max"

    # Nhạy hơn FastOCR một chút để giữ các nét chữ khó,
    # nhỏ, mờ hoặc nằm trên nền phức tạp.
    text_det_thresh: float = 0.25

    # Giữ thêm các vùng chữ có confidence trung bình.
    text_det_box_thresh: float = 0.50

    # Mở rộng bbox để tránh cắt sát nét chữ.
    text_det_unclip_ratio: float = 1.50

    # ==========================================================
    # Text recognition
    # ==========================================================

    # Có lợi khi một ảnh chứa nhiều dòng hoặc nhiều vùng chữ.
    text_recognition_batch_size: int = 4

    # Giữ kết quả confidence thấp để NLP hậu xử lý sau OCR.
    text_rec_score_thresh: float = 0.05

    # ==========================================================
    # Hợp đồng đầu vào
    # ==========================================================

    min_image_height: int = 16
    min_image_width: int = 16

    # Hỗ trợ cả ảnh 8K khoảng 33 MP nhưng vẫn có giới hạn
    # để tránh đầu vào bất thường chiếm quá nhiều RAM/VRAM.
    max_image_pixels: int = 40_000_000

    def __post_init__(self) -> None:
        """Kiểm tra config trước khi khởi tạo model."""

        if not self.detection_model_name.strip():
            raise ValueError(
                "detection_model_name must not be empty."
            )

        if not self.recognition_model_name.strip():
            raise ValueError(
                "recognition_model_name must not be empty."
            )

        _validate_device(self.device)

        if self.engine != "paddle_static":
            raise ValueError(
                "QualityOCRConfig currently supports "
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


DEFAULT_QUALITY_OCR_CONFIG = QualityOCRConfig()