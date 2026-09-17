from __future__ import annotations

import sys
from pathlib import Path


# Hỗ trợ hai cách chạy:
#
# 1. Chạy từ thư mục gốc dự án:
#    python -m backend.translation.language_model.test
#
# 2. Bấm nút "Run Python File" trong VS Code.
try:
    from .config import LanguageTranslationConfig
    from .model import (
        LanguageModelLoadError,
        LanguageTranslationError,
        LanguageTranslator,
    )

except ImportError:
    project_root = Path(__file__).resolve().parents[3]

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from backend.translation.language_model.config import (
        LanguageTranslationConfig,
    )
    from backend.translation.language_model.model import (
        LanguageModelLoadError,
        LanguageTranslationError,
        LanguageTranslator,
    )


TEST_TEXTS = [
    "She decided to give up after several difficult days.",
    "The planes took off while the children were running.",
    (
        "Machine learning can help computers recognize text "
        "and translate subtitles automatically."
    ),
]


def create_translator() -> LanguageTranslator:
    """
    Khởi tạo model dịch đúng một lần.

    num_beams=2 cân bằng tốc độ và chất lượng.
    Có thể đổi thành 1 nếu CPU chạy chậm.
    """

    config = LanguageTranslationConfig(
        device="auto",
        num_beams=2,
        max_input_tokens=256,
        max_new_tokens=256,
        normalize_whitespace=True,
        local_files_only=False,
    )

    return LanguageTranslator(config)


def print_result(
    *,
    index: int,
    source_text: str,
    translator: LanguageTranslator,
) -> None:
    """
    Dịch và in kết quả của một đoạn text.
    """

    result = translator.translate(source_text)

    print()
    print(f"[TEST {index}]")
    print("-" * 100)

    print("Original:")
    print(result.source_text)

    print()
    print("Processed:")
    print(result.processed_text)

    print()
    print("Vietnamese:")
    print(result.translated_text)

    print()
    print(f"Device: {result.device}")

    print("-" * 100)


def main() -> None:
    print("=" * 100)
    print("ENGLISH TO VIETNAMESE TRANSLATION TEST")
    print("=" * 100)

    print()
    print("Loading translation model...")

    try:
        # Model chỉ được tải một lần tại đây.
        translator = create_translator()

    except LanguageModelLoadError as exc:
        print()
        print("Could not load the translation model.")
        print(f"Error: {exc}")
        print()
        print(
            "Check the internet connection on the first run, "
            "the installed dependencies, and the model cache."
        )
        return

    print("Model loaded successfully.")
    print(f"Model : {translator.model_name}")
    print(f"Device: {translator.device}")

    for index, text in enumerate(
        TEST_TEXTS,
        start=1,
    ):
        try:
            print_result(
                index=index,
                source_text=text,
                translator=translator,
            )

        except LanguageTranslationError as exc:
            print()
            print(f"[TEST {index}] Translation failed.")
            print(f"Input: {text}")
            print(f"Error: {exc}")
            print("-" * 100)


if __name__ == "__main__":
    main()