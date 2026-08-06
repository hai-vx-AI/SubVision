from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .model import FastOCR


def extract_ocr_data(result: Any) -> dict[str, Any]:
    """
    Lấy phần dữ liệu OCR từ Result object của PaddleOCR.

    PaddleOCR thường trả:
        {
            "res": {
                "rec_texts": [...],
                "rec_scores": [...],
                "rec_boxes": [...]
            }
        }
    """

    payload = result.json

    # Phòng trường hợp phiên bản thư viện triển khai json như method.
    if callable(payload):
        payload = payload()

    if not isinstance(payload, dict):
        raise TypeError(
            "PaddleOCR result.json must return a dictionary."
        )

    data = payload.get("res", payload)

    if not isinstance(data, dict):
        raise TypeError(
            "OCR result does not contain a valid result dictionary."
        )

    return data


def load_test_image(image_path: Path) -> np.ndarray:
    """
    Đọc ảnh bằng OpenCV.

    cv2.imread trả ảnh:
        - numpy.ndarray
        - uint8
        - BGR
    đúng với hợp đồng đầu vào của FastOCR.
    """

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image does not exist: {image_path}"
        )

    if not image_path.is_file():
        raise ValueError(
            f"Image path is not a file: {image_path}"
        )

    image = cv2.imread(
        str(image_path),
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise ValueError(
            "OpenCV could not read the image. "
            "Check the file format and path."
        )

    return image


def test_image(
    image_path: Path,
    output_dir: Path | None = None,
) -> None:
    image = load_test_image(image_path)

    height, width, channels = image.shape

    print("=" * 60)
    print("FAST OCR IMAGE TEST")
    print("=" * 60)
    print(f"Image:    {image_path}")
    print(f"Shape:    {width} x {height} x {channels}")
    print(f"Dtype:    {image.dtype}")
    print()

    print("Initializing FastOCR...")

    initialization_start = time.perf_counter()
    ocr = FastOCR()
    initialization_time = (
        time.perf_counter() - initialization_start
    )

    print(
        f"Initialization time: "
        f"{initialization_time:.3f} seconds"
    )

    print("Running OCR...")

    inference_start = time.perf_counter()
    results = ocr.predict(image)
    inference_time = time.perf_counter() - inference_start

    print(
        f"Inference time: "
        f"{inference_time:.3f} seconds"
    )
    print(f"Result objects: {len(results)}")
    print()

    if not results:
        raise AssertionError(
            "PaddleOCR returned no result objects."
        )

    total_texts = 0

    for result_index, result in enumerate(results, start=1):
        data = extract_ocr_data(result)

        texts = list(data.get("rec_texts", []))
        scores = [
            float(score)
            for score in data.get("rec_scores", [])
        ]
        boxes = data.get("rec_boxes")

        print("-" * 60)
        print(f"RESULT {result_index}")
        print("-" * 60)

        if not texts:
            print("No text was recognized.")
            continue

        total_texts += len(texts)

        for text_index, text in enumerate(texts):
            score = (
                scores[text_index]
                if text_index < len(scores)
                else None
            )

            score_text = (
                f"{score:.4f}"
                if score is not None
                else "N/A"
            )

            print(
                f"[{text_index + 1:02d}] "
                f"score={score_text} | {text}"
            )

            if (
                isinstance(boxes, np.ndarray)
                and text_index < len(boxes)
            ):
                print(
                    f"     box={boxes[text_index].tolist()}"
                )

        if output_dir is not None:
            output_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            result.save_to_img(str(output_dir))

    print()
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Recognized text lines: {total_texts}")
    print(f"Inference time:       {inference_time:.3f}s")

    if output_dir is not None:
        print(f"Visualization:        {output_dir}")

    if total_texts == 0:
        raise AssertionError(
            "OCR ran successfully but recognized no text. "
            "Use an image containing clear English text."
        )

    print("Status: PASS")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Test the FastOCR module with one image."
        )
    )

    parser.add_argument(
        "--image",
        type=Path,
        required=True,
        help="Path to the test image.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional directory for the OCR visualization."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    test_image(
        image_path=args.image,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()

'''
python -m backend.OCR.fast.test `
    --image "D:\.vscode\SubVision\images\image.png" `
    --output "outputs\fast_ocr_test"
'''