from __future__ import annotations

from .corrector import OCRCorrector


TEST_TEXTS = [
    "I havc a problcm with this machinc.",
    "We wlth need to check the systcm again.",
    "This applicatlon can translate English subtitles.",
    "The recognitlon result contains several erors.",
    "OpenAI uses PaddleOCR in this example.",
    "I am form Vietnam.",
    "CPU and GPU are both supported.",
    "This is already a completely correct sentence.",
]


def main() -> None:
    print("=" * 80)
    print("OCR CORRECTION TEST")
    print("=" * 80)

    corrector = OCRCorrector()

    for index, original_text in enumerate(
        TEST_TEXTS,
        start=1,
    ):
        result = corrector.correct(original_text)

        print()
        print(f"[TEST {index}]")
        print(f"Original : {result.original_text}")
        print(f"Corrected: {result.corrected_text}")

        if result.corrections:
            print("Changes:")

            for correction in result.corrections:
                print(
                    f"  - {correction.original}"
                    f" -> {correction.corrected}"
                    f" | distance={correction.distance}"
                    f" | frequency={correction.frequency}"
                )
        else:
            print("Changes  : None")

        print("-" * 80)


if __name__ == "__main__":
    main()