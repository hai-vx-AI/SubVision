from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .model import (
    QualityOCR,
    QualityOCRInferenceError,
    QualityOCRInitializationError,
    QualityOCRInputError,
)


def load_image(image_path: Path) -> np.ndarray:
    """
    Đọc ảnh test dưới dạng:

        - numpy.ndarray
        - uint8
        - BGR
        - shape (height, width, 3)

    Đây là đúng hợp đồng đầu vào của QualityOCR.
    """

    if not image_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy ảnh: {image_path}"
        )

    if not image_path.is_file():
        raise ValueError(
            f"Đường dẫn không phải file: {image_path}"
        )

    image = cv2.imread(
        str(image_path),
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise ValueError(
            "OpenCV không thể đọc ảnh. "
            "Hãy kiểm tra đường dẫn và định dạng file."
        )

    return image


def extract_result_data(result: Any) -> dict[str, Any]:
    """
    Lấy dictionary dữ liệu từ PaddleOCR Result object.

    Dạng dữ liệu thông thường:

        {
            "res": {
                "rec_texts": [...],
                "rec_scores": [...],
                "rec_boxes": [...]
            }
        }
    """

    if not hasattr(result, "json"):
        raise TypeError(
            "PaddleOCR Result object không có thuộc tính json."
        )

    payload = result.json

    # Hỗ trợ cả trường hợp json là property hoặc method.
    if callable(payload):
        payload = payload()

    if not isinstance(payload, dict):
        raise TypeError(
            "result.json phải trả về dictionary."
        )

    result_data = payload.get("res", payload)

    if not isinstance(result_data, dict):
        raise TypeError(
            "Không tìm thấy dictionary kết quả OCR hợp lệ."
        )

    return result_data


def print_result(
    result: Any,
    result_index: int,
) -> int:
    """
    In nội dung của một Result object.

    Returns
    -------
    int
        Số dòng chữ nhận dạng được.
    """

    data = extract_result_data(result)

    texts = list(data.get("rec_texts", []))
    raw_scores = list(data.get("rec_scores", []))
    boxes = data.get("rec_boxes", [])

    scores = [
        float(score)
        for score in raw_scores
    ]

    print("-" * 70)
    print(f"RESULT OBJECT {result_index}")
    print("-" * 70)

    if not texts:
        print("Không nhận dạng được nội dung chữ.")
        return 0

    for index, text in enumerate(texts):
        score = (
            scores[index]
            if index < len(scores)
            else None
        )

        score_display = (
            f"{score:.4f}"
            if score is not None
            else "N/A"
        )

        print(
            f"[{index + 1:02d}] "
            f"confidence={score_display} | "
            f"{text}"
        )

        try:
            box = boxes[index]

            if isinstance(box, np.ndarray):
                box = box.tolist()
            elif hasattr(box, "tolist"):
                box = box.tolist()

            print(f"     bbox={box}")

        except (IndexError, TypeError):
            # Bbox có thể không tồn tại ở một số dạng kết quả.
            pass

    return len(texts)


def save_visualization(
    results: list[Any],
    output_dir: Path,
) -> None:
    """
    Lưu ảnh có kết quả OCR được PaddleOCR vẽ sẵn.
    """

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for result in results:
        if not hasattr(result, "save_to_img"):
            raise TypeError(
                "PaddleOCR Result object không hỗ trợ save_to_img()."
            )

        result.save_to_img(
            save_path=str(output_dir),
        )


def test_quality_ocr(
    image_path: Path,
    output_dir: Path | None = None,
) -> None:
    """
    Chạy kiểm thử QualityOCR trên một ảnh thực tế.
    """

    image = load_image(image_path)

    height, width, channels = image.shape

    print("=" * 70)
    print("QUALITY OCR TEST")
    print("=" * 70)
    print(f"Ảnh:       {image_path}")
    print(f"Kích thước: {width} × {height}")
    print(f"Số kênh:   {channels}")
    print(f"Dtype:     {image.dtype}")
    print()

    # ----------------------------------------------------------
    # Khởi tạo model
    # ----------------------------------------------------------

    print("Đang khởi tạo QualityOCR...")

    initialization_start = time.perf_counter()

    try:
        ocr = QualityOCR()
    except QualityOCRInitializationError as exc:
        raise RuntimeError(
            f"Không thể khởi tạo QualityOCR: {exc}"
        ) from exc

    initialization_time = (
        time.perf_counter() - initialization_start
    )

    print(
        "Thời gian khởi tạo: "
        f"{initialization_time:.3f} giây"
    )
    print()

    # ----------------------------------------------------------
    # Inference
    # ----------------------------------------------------------

    print("Đang chạy OCR...")

    inference_start = time.perf_counter()

    try:
        results = ocr.predict(image)

    except QualityOCRInputError as exc:
        raise RuntimeError(
            f"Ảnh đầu vào không hợp lệ: {exc}"
        ) from exc

    except QualityOCRInferenceError as exc:
        raise RuntimeError(
            f"QualityOCR inference thất bại: {exc}"
        ) from exc

    inference_time = (
        time.perf_counter() - inference_start
    )

    print(
        "Thời gian inference: "
        f"{inference_time:.3f} giây"
    )
    print(f"Số Result object: {len(results)}")
    print()

    if not results:
        raise AssertionError(
            "QualityOCR không trả về Result object nào."
        )

    # ----------------------------------------------------------
    # Đọc kết quả
    # ----------------------------------------------------------

    total_text_lines = 0

    for result_index, result in enumerate(
        results,
        start=1,
    ):
        total_text_lines += print_result(
            result=result,
            result_index=result_index,
        )

    # ----------------------------------------------------------
    # Lưu ảnh bbox nếu được yêu cầu
    # ----------------------------------------------------------

    if output_dir is not None:
        save_visualization(
            results=results,
            output_dir=output_dir,
        )

    # ----------------------------------------------------------
    # Tổng kết
    # ----------------------------------------------------------

    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Số dòng chữ:          {total_text_lines}")
    print(f"Thời gian khởi tạo:   {initialization_time:.3f}s")
    print(f"Thời gian inference:  {inference_time:.3f}s")

    if output_dir is not None:
        print(f"Thư mục kết quả:      {output_dir}")

    if total_text_lines == 0:
        raise AssertionError(
            "Model chạy thành công nhưng không nhận dạng được chữ. "
            "Hãy thử một ảnh có nội dung rõ hơn."
        )

    print("Trạng thái: PASS")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Kiểm thử QualityOCR với một ảnh đầu vào."
        )
    )

    parser.add_argument(
        "--image",
        type=Path,
        required=True,
        help="Đường dẫn tới ảnh cần kiểm thử.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Thư mục tùy chọn để lưu ảnh kết quả có bbox."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    test_quality_ocr(
        image_path=args.image,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()

'''
python -m backend.OCR.quality.test `
    --image "D:\.vscode\SubVision\images\image.png" `
    --output "outputs\quality_ocr"
'''