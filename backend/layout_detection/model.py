from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
from paddleocr import LayoutDetection

from .config import (
    DEFAULT_LAYOUT_DETECTION_CONFIG,
    LayoutDetectionConfig,
    SimplifiedLayoutLabel,
)


class LayoutDetectionError(RuntimeError):
    """
    Lỗi cơ sở của layout detection.
    """


class LayoutModelLoadError(LayoutDetectionError):
    """
    Không thể tải PP-DocLayout.
    """


class LayoutDetectionInputError(ValueError):
    """
    Ảnh đầu vào không hợp lệ.
    """


class LayoutDetectionInferenceError(
    LayoutDetectionError
):
    """
    Lỗi xảy ra trong quá trình model inference.
    """


class LayoutDetectionOutputError(
    LayoutDetectionError
):
    """
    Kết quả từ PaddleOCR không có cấu trúc mong đợi.
    """


BBox = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class LayoutRegion:
    """
    Một vùng bố cục được phát hiện.

    Attributes
    ----------
    bbox:
        Bounding box theo định dạng:

            (x1, y1, x2, y2)

        Khoảng bbox sử dụng dạng [x1, x2) và [y1, y2).

    label:
        Nhãn đã được chuẩn hóa cho ứng dụng.

        Ví dụ:
            title
            paragraph
            caption

    raw_label:
        Nhãn gốc trả về từ PP-DocLayout.

        Ví dụ:
            paragraph_title
            text
            figure_title

    class_id:
        ID lớp gốc của model.

    confidence:
        Độ tin cậy của bbox.
    """

    bbox: BBox
    label: SimplifiedLayoutLabel

    raw_label: str
    class_id: int
    confidence: float

    @property
    def x1(self) -> int:
        return self.bbox[0]

    @property
    def y1(self) -> int:
        return self.bbox[1]

    @property
    def x2(self) -> int:
        return self.bbox[2]

    @property
    def y2(self) -> int:
        return self.bbox[3]

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass(frozen=True, slots=True)
class LayoutDetectionResult:
    """
    Kết quả phát hiện bố cục của một ảnh.
    """

    image_width: int
    image_height: int

    model_name: str
    regions: tuple[LayoutRegion, ...]

    @property
    def region_count(self) -> int:
        return len(self.regions)

    def regions_by_label(
        self,
        label: SimplifiedLayoutLabel,
    ) -> tuple[LayoutRegion, ...]:
        """
        Lấy các vùng thuộc cùng một loại.

        Example
        -------
        paragraphs = result.regions_by_label(
            "paragraph"
        )
        """

        return tuple(
            region
            for region in self.regions
            if region.label == label
        )


class LayoutLabelNormalizer:
    """
    Chuẩn hóa 23 nhãn gốc của PP-DocLayout về tập nhãn
    nhỏ hơn của SubVision.

    Class này không xử lý bbox hoặc confidence.
    """

    def __init__(
        self,
        mapping: Mapping[
            str,
            SimplifiedLayoutLabel,
        ],
    ) -> None:
        self._mapping = dict(mapping)

    def normalize(
        self,
        raw_label: str,
    ) -> SimplifiedLayoutLabel:
        """
        Trả nhãn đã chuẩn hóa.

        Nhãn không có trong mapping được chuyển thành "other".
        """

        if not isinstance(raw_label, str):
            return "other"

        normalized_key = (
            raw_label
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

        return self._mapping.get(
            normalized_key,
            "other",
        )


class LayoutDetector:
    """
    Hộp đen phát hiện các vùng bố cục trong ảnh.

    Input:
        np.ndarray uint8, H x W x 3.

    Output:
        LayoutDetectionResult.

    Module chỉ phát hiện layout. Nó không:
        - chạy OCR;
        - đọc chữ;
        - ghép OCR bbox với layout bbox;
        - dịch nội dung.
    """

    def __init__(
        self,
        config: LayoutDetectionConfig | None = None,
    ) -> None:
        self.config = (
            config
            or DEFAULT_LAYOUT_DETECTION_CONFIG
        )

        self._label_normalizer = (
            LayoutLabelNormalizer(
                self.config.label_mapping
            )
        )

        self._model: LayoutDetection | None = None

        self._load_model()

    # ==========================================================
    # Public properties
    # ==========================================================

    @property
    def model_name(self) -> str:
        return self.config.model_name

    # ==========================================================
    # Main API
    # ==========================================================

    def predict(
        self,
        image: np.ndarray,
    ) -> LayoutDetectionResult:
        """
        Phát hiện các vùng bố cục trong ảnh.

        Parameters
        ----------
        image:
            Ảnh uint8 theo dạng H x W x 3.

        Returns
        -------
        LayoutDetectionResult
            Danh sách các bbox đã chuẩn hóa nhãn.
        """

        validated_image = self._validate_image(
            image
        )

        image_height, image_width = (
            validated_image.shape[:2]
        )

        try:
            output = self._model.predict(
                input=validated_image,
                batch_size=self.config.batch_size,
                threshold=(
                    self.config.confidence_threshold
                ),
                layout_nms=self.config.layout_nms,
            )

            result_objects = list(output)

        except Exception as exc:
            raise LayoutDetectionInferenceError(
                "PP-DocLayout could not process the "
                "supplied image."
            ) from exc

        if not result_objects:
            return LayoutDetectionResult(
                image_width=image_width,
                image_height=image_height,
                model_name=self.model_name,
                regions=(),
            )

        # predict() nhận một ảnh nên chỉ cần phần tử đầu.
        raw_result = self._extract_result_data(
            result_objects[0]
        )

        raw_boxes = raw_result.get("boxes", [])

        if not isinstance(raw_boxes, list):
            raise LayoutDetectionOutputError(
                "The model output field 'boxes' "
                "must be a list."
            )

        regions: list[LayoutRegion] = []

        for raw_box in raw_boxes:
            region = self._convert_raw_box(
                raw_box=raw_box,
                image_width=image_width,
                image_height=image_height,
            )

            if region is None:
                continue

            regions.append(region)

        if self.config.sort_regions_by_position:
            regions.sort(
                key=lambda region: (
                    region.y1,
                    region.x1,
                    -region.confidence,
                )
            )

        return LayoutDetectionResult(
            image_width=image_width,
            image_height=image_height,
            model_name=self.model_name,
            regions=tuple(regions),
        )

    def __call__(
        self,
        image: np.ndarray,
    ) -> LayoutDetectionResult:
        """
        Cho phép gọi detector như một function.
        """

        return self.predict(image)

    # ==========================================================
    # Model loading
    # ==========================================================

    def _load_model(self) -> None:
        """
        Tải PP-DocLayout đúng một lần.
        """

        try:
            self._model = LayoutDetection(
                model_name=self.config.model_name,
                device=self._resolve_device(),
                engine=self.config.engine,
                enable_mkldnn=(
                    self.config.enable_mkldnn
                ),
                cpu_threads=self.config.cpu_threads,
            )

        except Exception as exc:
            raise LayoutModelLoadError(
                "Could not load layout model "
                f"{self.config.model_name!r}."
            ) from exc

    def _resolve_device(self) -> str | None:
        """
        Chuyển cấu hình nội bộ thành device của PaddleOCR.

        None để PaddleOCR tự chọn GPU hoặc CPU.
        """

        if self.config.device == "auto":
            return None

        if self.config.device == "gpu":
            return "gpu"

        return "cpu"

    # ==========================================================
    # Output conversion
    # ==========================================================

    def _convert_raw_box(
        self,
        *,
        raw_box: Any,
        image_width: int,
        image_height: int,
    ) -> LayoutRegion | None:
        """
        Chuyển một bbox gốc của PaddleOCR thành LayoutRegion.
        """

        if not isinstance(raw_box, Mapping):
            return None

        raw_label = str(
            raw_box.get("label", "")
        ).strip()

        class_id = self._safe_int(
            raw_box.get("cls_id", -1)
        )

        confidence = self._safe_float(
            raw_box.get("score", 0.0)
        )

        if (
            confidence
            < self.config.confidence_threshold
        ):
            return None

        coordinate = raw_box.get("coordinate")

        bbox = self._normalize_bbox(
            coordinate=coordinate,
            image_width=image_width,
            image_height=image_height,
        )

        if bbox is None:
            return None

        normalized_label = (
            self._label_normalizer.normalize(
                raw_label
            )
        )

        if (
            normalized_label == "other"
            and not self.config.keep_other_regions
        ):
            return None

        return LayoutRegion(
            bbox=bbox,
            label=normalized_label,
            raw_label=raw_label,
            class_id=class_id,
            confidence=confidence,
        )

    def _normalize_bbox(
        self,
        *,
        coordinate: Any,
        image_width: int,
        image_height: int,
    ) -> BBox | None:
        """
        Chuẩn hóa bbox float của model thành bbox integer.

        Dùng floor cho góc trái trên và ceil cho góc phải dưới
        để không làm mất một phần vùng model phát hiện.
        """

        if not isinstance(
            coordinate,
            (list, tuple),
        ):
            return None

        if len(coordinate) != 4:
            return None

        try:
            x1_raw, y1_raw, x2_raw, y2_raw = (
                float(value)
                for value in coordinate
            )

        except (TypeError, ValueError):
            return None

        values = (
            x1_raw,
            y1_raw,
            x2_raw,
            y2_raw,
        )

        if not all(
            math.isfinite(value)
            for value in values
        ):
            return None

        x1 = math.floor(min(x1_raw, x2_raw))
        y1 = math.floor(min(y1_raw, y2_raw))

        x2 = math.ceil(max(x1_raw, x2_raw))
        y2 = math.ceil(max(y1_raw, y2_raw))

        if self.config.clip_boxes_to_image:
            x1 = max(0, min(x1, image_width))
            y1 = max(0, min(y1, image_height))

            x2 = max(0, min(x2, image_width))
            y2 = max(0, min(y2, image_height))

        if x2 <= x1 or y2 <= y1:
            return None

        return x1, y1, x2, y2

    @staticmethod
    def _extract_result_data(
        result_object: Any,
    ) -> dict[str, Any]:
        """
        Lấy dictionary kết quả từ Result object của PaddleOCR.

        PaddleOCR cung cấp kết quả qua thuộc tính `.json`.
        """

        raw_json = getattr(
            result_object,
            "json",
            None,
        )

        if callable(raw_json):
            raw_json = raw_json()

        if isinstance(raw_json, str):
            try:
                raw_json = json.loads(raw_json)

            except json.JSONDecodeError as exc:
                raise LayoutDetectionOutputError(
                    "The model returned invalid JSON."
                ) from exc

        if not isinstance(raw_json, Mapping):
            raise LayoutDetectionOutputError(
                "The model result does not provide a "
                "valid JSON mapping."
            )

        result_data: Any = raw_json

        # Kết quả PaddleOCR thường có dạng:
        #
        # {
        #     "res": {
        #         "boxes": [...]
        #     }
        # }
        if "res" in result_data:
            result_data = result_data["res"]

        if not isinstance(result_data, Mapping):
            raise LayoutDetectionOutputError(
                "The model result field 'res' is invalid."
            )

        return dict(result_data)

    # ==========================================================
    # Input validation
    # ==========================================================

    def _validate_image(
        self,
        image: np.ndarray,
    ) -> np.ndarray:
        """
        Kiểm tra ảnh đầu vào.

        Module không tự resize, normalize hoặc đổi kênh màu.
        Các bước inference nội bộ do PaddleOCR xử lý.
        """

        if not isinstance(image, np.ndarray):
            raise LayoutDetectionInputError(
                "image must be a numpy.ndarray, "
                f"received {type(image).__name__}."
            )

        if image.dtype != np.uint8:
            raise LayoutDetectionInputError(
                "image dtype must be uint8."
            )

        if image.ndim != 3:
            raise LayoutDetectionInputError(
                "image must have shape H x W x 3."
            )

        if image.shape[2] != 3:
            raise LayoutDetectionInputError(
                "image must contain exactly 3 channels."
            )

        image_height, image_width = image.shape[:2]

        if (
            image_width
            < self.config.min_image_width
        ):
            raise LayoutDetectionInputError(
                "image width is smaller than "
                f"{self.config.min_image_width}."
            )

        if (
            image_height
            < self.config.min_image_height
        ):
            raise LayoutDetectionInputError(
                "image height is smaller than "
                f"{self.config.min_image_height}."
            )

        pixel_count = image_width * image_height

        if (
            pixel_count
            > self.config.max_image_pixels
        ):
            raise LayoutDetectionInputError(
                "image contains more than "
                f"{self.config.max_image_pixels} pixels."
            )

        return np.ascontiguousarray(image)

    # ==========================================================
    # Conversion helpers
    # ==========================================================

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int:
        try:
            return int(value)

        except (TypeError, ValueError):
            return -1

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> float:
        try:
            result = float(value)

        except (TypeError, ValueError):
            return 0.0

        if not math.isfinite(result):
            return 0.0

        return result