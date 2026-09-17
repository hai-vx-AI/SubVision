"""
REAL integration test for backend.pipeline.

Run from SubVision root:
    python -m backend.pipeline.test

Uses:
    SubVision/images/image.png

Tests:
    dictionary
    language_model
    dashboard
    dictionary + dashboard
    language_model + dashboard
    invalid: all OFF

Also saves annotated translation images to:
    SubVision/images/pipeline_test_results/
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import BackendPipeline, PipelineConfig


PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGE_PATH = PROJECT_ROOT / "images" / "image.png"
OUTPUT_DIR = PROJECT_ROOT / "images" / "pipeline_test_results"

# True = test cả FastOCR và QualityOCR.
# Đổi False nếu chỉ muốn chạy FastOCR trước.
TEST_QUALITY_OCR = True

OCR_MODES = ("fast", "quality") if TEST_QUALITY_OCR else ("fast",)

CASES = (
    ("dictionary_only", "dictionary", False),
    ("language_only", "language_model", False),
    ("dashboard_only", None, True),
    ("dictionary_dashboard", "dictionary", True),
    ("language_dashboard", "language_model", True),
)


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def load_image() -> np.ndarray:
    if not IMAGE_PATH.is_file():
        raise FileNotFoundError(
            f"Image not found: {IMAGE_PATH}"
        )

    rgb = np.asarray(
        Image.open(IMAGE_PATH).convert("RGB"),
        dtype=np.uint8,
    )

    # Backend OCR convention: BGR ndarray.
    return rgb[:, :, ::-1].copy()


def get_font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    line = words[0]

    for word in words[1:]:
        candidate = f"{line} {word}"
        box = draw.textbbox((0, 0), candidate, font=font)

        if box[2] - box[0] <= max_width:
            line = candidate
        else:
            lines.append(line)
            line = word

    lines.append(line)
    return lines


def save_translation_image(
    result,
    *,
    name: str,
) -> Path:
    """
    Draw bbox + translated_text on the real source image.
    """
    image = Image.open(IMAGE_PATH).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = get_font(18)

    width, height = image.size

    for index, item in enumerate(result.items, 1):
        x1, y1, x2, y2 = item.bbox.coordinates

        x1 = max(0, min(width - 1, x1))
        x2 = max(0, min(width - 1, x2))
        y1 = max(0, min(height - 1, y1))
        y2 = max(0, min(height - 1, y2))

        if x2 <= x1 or y2 <= y1:
            continue

        draw.rectangle(
            (x1, y1, x2, y2),
            outline=(255, 255, 255, 255),
            width=2,
        )

        lines = wrap_text(
            draw,
            f"{index}. {item.translated_text}",
            font,
            max_width=max(200, min(width - 20, 420)),
        )

        line_h = 22
        label_h = len(lines) * line_h + 8
        label_w = max(
            draw.textbbox((0, 0), line, font=font)[2]
            for line in lines
        ) + 12

        label_w = min(label_w, width - 4)
        lx = min(x1, max(0, width - label_w - 2))
        ly = y2 + 4

        if ly + label_h > height:
            ly = max(0, y1 - label_h - 4)

        draw.rectangle(
            (lx, ly, lx + label_w, ly + label_h),
            fill=(0, 0, 0, 215),
        )

        for offset, line in enumerate(lines):
            draw.text(
                (lx + 6, ly + 4 + offset * line_h),
                line,
                font=font,
                fill=(255, 255, 255, 255),
            )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{name}.png"

    Image.alpha_composite(
        image,
        overlay,
    ).convert("RGB").save(output)

    return output


def print_translation(result) -> None:
    print(f"translation_items={len(result.items)}")

    for index, item in enumerate(result.items, 1):
        print()
        print(f"[{index}] {item.unit_type}")
        print(f"  bbox       : {item.bbox.coordinates}")
        print(f"  confidence : {item.confidence}")
        print(f"  raw        : {item.raw_text}")
        print(f"  corrected  : {item.corrected_text}")
        print(f"  translated : {item.translated_text}")


def print_dashboard(result) -> None:
    print(f"dashboard_entries={len(result.entries)}")

    for index, entry in enumerate(result.entries, 1):
        print()
        print(f"[{index}] {entry.term}")
        print(f"  type : {entry.entry_type}")
        print(f"  IPA  : {', '.join(entry.ipas) or '<none>'}")

        for meaning in entry.meanings:
            print(f"  - {meaning}")


def validate_case(
    result,
    *,
    translation_mode: str | None,
    dashboard: bool,
) -> None:
    check(
        (result.translation_result is not None)
        == (translation_mode is not None),
        "translation_result presence is wrong.",
    )

    check(
        (result.dashboard_result is not None)
        == dashboard,
        "dashboard_result presence is wrong.",
    )

    if translation_mode == "dictionary":
        check(
            all(
                item.unit_type == "ocr_box"
                for item in result.translation_result.items
            ),
            "Dictionary must output ocr_box items.",
        )

    if translation_mode == "language_model":
        check(
            all(
                item.unit_type == "text_group"
                for item in result.translation_result.items
            ),
            "Language model must output text_group items.",
        )


def test_invalid_config() -> None:
    try:
        PipelineConfig(
            translation_mode=None,
            enable_dashboard=False,
        )
    except ValueError as exc:
        print("all_off: PASS")
        print(f"  {exc}")
        return

    raise AssertionError(
        "All-off config must be rejected."
    )


def run_tests() -> None:
    print("=" * 72)
    print("BACKEND PIPELINE — REAL IMAGE TEST")
    print("=" * 72)
    print(f"image={IMAGE_PATH}")

    image = load_image()

    print(f"shape={image.shape}")
    print(f"dtype={image.dtype}")

    # Reuse expensive OCR/model/dictionary resources.
    pipeline = BackendPipeline()

    print()
    print("INVALID CONFIG")
    test_invalid_config()

    case_count = 0

    for ocr_mode in OCR_MODES:
        print()
        print("#" * 72)
        print(f"OCR MODE: {ocr_mode}")
        print("#" * 72)

        for name, mode, dashboard in CASES:
            case_count += 1

            print()
            print("=" * 72)
            print(f"CASE: {name}")
            print("=" * 72)

            config = PipelineConfig(
                ocr_mode=ocr_mode,
                translation_mode=mode,
                enable_dashboard=dashboard,
                enable_ocr_correction=True,
            )

            print(asdict(config))

            result = pipeline.run(
                image=image,
                config=config,
            )

            validate_case(
                result,
                translation_mode=mode,
                dashboard=dashboard,
            )

            print(f"ocr_items={len(result.ocr_items)}")
            print(f"elapsed={result.elapsed_seconds:.3f}s")

            if result.translation_result is not None:
                print()
                print("TRANSLATION")
                print_translation(result.translation_result)

                # Save one visual output for each translation branch.
                if name in ("dictionary_only", "language_only"):
                    output = save_translation_image(
                        result.translation_result,
                        name=f"{ocr_mode}_{name}",
                    )
                    print()
                    print(f"result_image={output}")

            if result.dashboard_result is not None:
                print()
                print("DASHBOARD")

                # Full vocabulary print in Dashboard-only mode.
                if name == "dashboard_only":
                    print_dashboard(result.dashboard_result)
                else:
                    print(
                        "dashboard_entries="
                        f"{len(result.dashboard_result.entries)}"
                    )

            print()
            print(f"{name}: PASS")

    print()
    print("=" * 72)
    print("FINAL")
    print("=" * 72)
    print(f"valid_cases={case_count}")
    print("invalid_all_off=PASS")
    print(f"result_images={OUTPUT_DIR}")
    print("Backend pipeline production test: PASS")


if __name__ == "__main__":
    run_tests()
