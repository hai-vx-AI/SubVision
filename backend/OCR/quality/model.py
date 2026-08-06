from __future__ import annotations

from typing import Any

import numpy as np
from paddleocr import PaddleOCR

from .config import (
    DEFAULT_QUALITY_OCR_CONFIG,
    QualityOCRConfig,
)


class QualityOCRInputError(ValueError):
    """
    Dữ liệu đầu vào không tuân thủ hợp đồng của QualityOCR.
    """


class QualityOCRInitializationError(RuntimeError):
    """
    Không thể tải PaddleOCR hoặc pretrained models.
    """


class QualityOCRInferenceError(RuntimeError):
    """
    Model đã khởi tạo nhưng inference xảy ra lỗi.
    """


class QualityOCR:
    """
    Hộp đen OCR chất lượng cao.

    Input
    -----
    numpy.ndarray:
        - shape: (height, width, 3)
        - dtype: uint8
        - color format: BGR

    Output
    ------
    list:
        Danh sách raw Result objects của PaddleOCR.

    Module này không:
        - chụp màn hình;
        - chọn hoặc crop vùng ảnh;
        - padding thủ công;
        - resize thủ công;
        - chuẩn hóa kết quả OCR;
        - sửa nội dung bằng NLP;
        - dịch văn bản.
    """

    def __init__(
        self,
        config: QualityOCRConfig | None = None,
    ) -> None:
        self.config = config or DEFAULT_QUALITY_OCR_CONFIG
        self._pipeline = self._build_pipeline()

    def _build_pipeline(self) -> PaddleOCR:
        """
        Khởi tạo pipeline PP-OCRv6 Medium theo config nội bộ.
        """

        device = (
            None
            if self.config.device == "auto"
            else self.config.device
        )

        try:
            return PaddleOCR(
                # Pretrained models
                text_detection_model_name=(
                    self.config.detection_model_name
                ),
                text_recognition_model_name=(
                    self.config.recognition_model_name
                ),

                # Runtime
                device=device,
                engine=self.config.engine,
                enable_mkldnn=self.config.enable_mkldnn,
                cpu_threads=self.config.cpu_threads,

                # Optional modules
                use_doc_orientation_classify=(
                    self.config.use_doc_orientation_classify
                ),
                use_doc_unwarping=(
                    self.config.use_doc_unwarping
                ),
                use_textline_orientation=(
                    self.config.use_textline_orientation
                ),

                # Detection
                text_det_limit_side_len=(
                    self.config.text_det_limit_side_len
                ),
                text_det_limit_type=(
                    self.config.text_det_limit_type
                ),
                text_det_thresh=(
                    self.config.text_det_thresh
                ),
                text_det_box_thresh=(
                    self.config.text_det_box_thresh
                ),
                text_det_unclip_ratio=(
                    self.config.text_det_unclip_ratio
                ),

                # Recognition
                text_recognition_batch_size=(
                    self.config.text_recognition_batch_size
                ),
                text_rec_score_thresh=(
                    self.config.text_rec_score_thresh
                ),
            )

        except Exception as exc:
            raise QualityOCRInitializationError(
                "Could not initialize the QualityOCR pipeline. "
                "Make sure PaddleOCR 3.7 or newer is installed "
                "and the PP-OCRv6 models can be downloaded."
            ) from exc

    def predict(
        self,
        image: np.ndarray,
    ) -> list[Any]:
        """
        Kiểm tra ảnh rồi chạy QualityOCR.

        PaddleOCR tự thực hiện preprocessing cần thiết như resize,
        padding nội bộ, normalize và chuyển tensor.
        """

        validated_image = self._validate_image(image)

        try:
            results = self._pipeline.predict(validated_image)
            return list(results)

        except Exception as exc:
            raise QualityOCRInferenceError(
                "QualityOCR inference failed."
            ) from exc

    def __call__(
        self,
        image: np.ndarray,
    ) -> list[Any]:
        """
        Cho phép gọi object như một function.

        Example
        -------
        ocr = QualityOCR()
        results = ocr(image)
        """

        return self.predict(image)

    def _validate_image(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        """
        Kiểm tra dữ liệu ngoại lai trước khi đưa vào model.

        Hàm này chỉ xác thực dữ liệu, không chỉnh sửa nội dung ảnh.
        """

        if not isinstance(image, np.ndarray):
            raise QualityOCRInputError(
                "image must be numpy.ndarray, "
                f"received {type(image).__name__}."
            )

        if image.dtype != np.uint8:
            raise QualityOCRInputError(
                "image dtype must be uint8, "
                f"received {image.dtype}."
            )

        if image.ndim != 3:
            raise QualityOCRInputError(
                "image must have exactly 3 dimensions: "
                "(height, width, channels)."
            )

        if image.shape[2] != 3:
            raise QualityOCRInputError(
                "image must have exactly 3 BGR channels. "
                f"Received shape: {image.shape}."
            )

        height, width, _ = image.shape

        if height < self.config.min_image_height:
            raise QualityOCRInputError(
                "image height must be at least "
                f"{self.config.min_image_height}px."
            )

        if width < self.config.min_image_width:
            raise QualityOCRInputError(
                "image width must be at least "
                f"{self.config.min_image_width}px."
            )

        pixel_count = height * width

        if pixel_count > self.config.max_image_pixels:
            raise QualityOCRInputError(
                f"image contains {pixel_count:,} pixels, "
                "exceeding the configured safety limit of "
                f"{self.config.max_image_pixels:,} pixels."
            )

        # Chỉ đảm bảo vùng nhớ liên tục.
        # Không resize, padding, crop hoặc chỉnh sửa pixel.
        return np.ascontiguousarray(image)