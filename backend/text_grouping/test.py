from __future__ import annotations

from .config import TextGroupingConfig
from .grouper import (
    OCRTextBox,
    TextGrouper,
    group_ocr,
)
from .geometry import BBox


def test_two_lines_one_paragraph() -> None:
    grouper = TextGrouper()

    groups = grouper.group(
        texts=[
            "Hello",
            "world",
            "This",
            "is",
            "test",
        ],
        boxes=[
            [10, 10, 55, 30],
            [65, 10, 115, 30],
            [10, 45, 45, 65],
            [55, 45, 70, 65],
            [80, 45, 120, 65],
        ],
        scores=[
            0.99,
            0.98,
            0.97,
            0.96,
            0.95,
        ],
    )

    assert len(groups) == 1

    group = groups[0]

    assert len(group.lines) == 2
    assert group.lines[0].text == "Hello world"
    assert group.lines[1].text == "This is test"
    assert group.text == "Hello world This is test"


def test_large_vertical_gap_creates_new_group() -> None:
    groups = group_ocr(
        texts=[
            "First",
            "paragraph",
            "Second",
            "paragraph",
        ],
        boxes=[
            [10, 10, 50, 30],
            [60, 10, 130, 30],
            [10, 120, 60, 140],
            [70, 120, 145, 140],
        ],
        scores=[
            0.99,
            0.99,
            0.99,
            0.99,
        ],
    )

    assert len(groups) == 2
    assert groups[0].text == "First paragraph"
    assert groups[1].text == "Second paragraph"


def test_low_confidence_is_filtered() -> None:
    grouper = TextGrouper()

    groups = grouper.group(
        texts=[
            "keep",
            "remove",
        ],
        boxes=[
            [10, 10, 50, 30],
            [60, 10, 120, 30],
        ],
        scores=[
            0.95,
            0.10,
        ],
    )

    assert len(groups) == 1
    assert groups[0].text == "keep"


def test_far_words_do_not_share_line() -> None:
    grouper = TextGrouper()

    lines = grouper.group_words_to_lines(
        [
            OCRTextBox(
                text="left",
                bbox=BBox(
                    10,
                    10,
                    50,
                    30,
                ),
                confidence=0.99,
            ),
            OCRTextBox(
                text="right",
                bbox=BBox(
                    300,
                    10,
                    350,
                    30,
                ),
                confidence=0.99,
            ),
        ]
    )

    assert len(lines) == 2


def test_polygon_input() -> None:
    groups = group_ocr(
        texts=[
            "polygon",
            "works",
        ],
        boxes=[
            [
                [10, 10],
                [70, 10],
                [70, 30],
                [10, 30],
            ],
            [
                [80, 10],
                [125, 10],
                [125, 30],
                [80, 30],
            ],
        ],
        scores=[
            0.99,
            0.98,
        ],
    )

    assert len(groups) == 1
    assert groups[0].text == "polygon works"


def test_paddle_result_wrapper() -> None:
    grouper = TextGrouper()

    result = {
        "res": {
            "rec_texts": [
                "hello",
                "world",
            ],
            "rec_scores": [
                0.98,
                0.97,
            ],
            "rec_boxes": [
                [10, 10, 50, 30],
                [60, 10, 110, 30],
            ],
        }
    }

    groups = grouper.group_paddle_result(
        result
    )

    assert len(groups) == 1
    assert groups[0].text == "hello world"


def test_custom_separator() -> None:
    config = TextGroupingConfig(
        word_separator="_",
        line_separator=" | ",
    )

    groups = TextGrouper(
        config=config
    ).group(
        texts=[
            "A",
            "B",
            "C",
            "D",
        ],
        boxes=[
            [10, 10, 30, 30],
            [40, 10, 60, 30],
            [10, 45, 30, 65],
            [40, 45, 60, 65],
        ],
        scores=[
            1.0,
            1.0,
            1.0,
            1.0,
        ],
    )

    assert len(groups) == 1
    assert groups[0].text == "A_B | C_D"


def run_tests() -> None:
    tests = [
        test_two_lines_one_paragraph,
        test_large_vertical_gap_creates_new_group,
        test_low_confidence_is_filtered,
        test_far_words_do_not_share_line,
        test_polygon_input,
        test_paddle_result_wrapper,
        test_custom_separator,
    ]

    passed = 0

    for test_function in tests:
        test_function()
        passed += 1

        print(
            f"[PASS] {test_function.__name__}"
        )

    print(
        f"\nAll tests passed: "
        f"{passed}/{len(tests)}"
    )


if __name__ == "__main__":
    run_tests()
