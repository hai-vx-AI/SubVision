from __future__ import annotations

import sys
from pathlib import Path


# Hỗ trợ cả hai cách chạy:
#
# 1. Từ thư mục gốc:
#    python -m backend.translation.dictionary.test
#
# 2. Bấm nút tam giác "Run Python File" trong VS Code.
try:
    from .translator import DictionaryTranslator

except ImportError:
    project_root = Path(__file__).resolve().parents[3]

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from backend.translation.dictionary.translator import (
        DictionaryTranslator,
    )


TEST_TEXTS = [
    "She decided to give up after several difficult days.",
    "He studies machine learning and looks up new words every day.",
    "The planes took off while the children were running.",
]


def create_translator() -> DictionaryTranslator:
    """
    Khởi tạo translator và nạp dữ liệu từ/cụm mẫu.

    Các key đều sử dụng dạng lemma:
        decided  -> decide
        studies  -> study
        looks    -> look
        took     -> take
        children -> child
        running  -> run
    """

    translator = DictionaryTranslator()

    # ==========================================================
    # Từ đơn
    # ==========================================================

    translator.add_words(
        {
            "she": "cô ấy",
            "he": "anh ấy",
            "the": "cái",

            "decide": "quyết định",
            "give": "đưa",
            "after": "sau",
            "several": "một vài",
            "difficult": "khó khăn",
            "day": "ngày",

            "study": "học",
            "machine": "máy",
            "learning": "việc học",
            "and": "và",
            "look": "nhìn",
            "new": "mới",
            "word": "từ",
            "every": "mỗi",

            "plane": "máy bay",
            "take": "lấy",
            "off": "tắt",
            "while": "trong khi",
            "child": "đứa trẻ",
            "be": "là",
            "run": "chạy",

            "to": "để",
            "up": "lên",
        }
    )

    # ==========================================================
    # Cụm từ
    # ==========================================================

    translator.add_phrases(
        {
            "decide to": "quyết định",
            "give up": "từ bỏ",
            "machine learning": "học máy",
            "look up": "tra cứu",
            "every day": "mỗi ngày",
            "take off": "cất cánh",
        }
    )

    return translator


def print_tokens(
    translator: DictionaryTranslator,
    text: str,
) -> None:
    """
    In token gốc và token sau chuẩn hóa + lemma.
    """

    tokens = translator.tokenizer.tokenize(text)

    print("Tokens:")

    for token in tokens:
        print(
            f"  {token.index:02d}. "
            f"{token.text!r:<14}"
            f" -> {token.normalized!r:<14}"
            f" | type={token.token_type}"
            f" | char=[{token.start}, {token.end})"
        )


def print_translation_items(result) -> None:
    """
    In chi tiết kết quả dịch từng từ hoặc cụm.
    """

    print("Translation items:")

    for item in result.items:
        translation = (
            item.primary_translation
            if item.primary_translation is not None
            else "[giữ nguyên]"
        )

        normalized = " ".join(
            item.normalized_tokens
        )

        print(
            f"  - source={item.source_text!r:<22}"
            f" normalized={normalized!r:<20}"
            f" translation={translation!r:<18}"
            f" type={item.item_type}"
        )


def main() -> None:
    translator = create_translator()

    print("=" * 100)
    print("DICTIONARY TRANSLATION WITH LEMMATIZATION")
    print("=" * 100)

    for index, text in enumerate(
        TEST_TEXTS,
        start=1,
    ):
        result = translator.translate(text)

        print()
        print(f"[TEST {index}]")
        print("-" * 100)

        print(f"Original   : {result.original_text}")

        print()
        print_tokens(
            translator=translator,
            text=text,
        )

        print()
        print_translation_items(result)

        print()
        print(
            f"Translation: {result.literal_translation}"
        )

        print("-" * 100)


if __name__ == "__main__":
    main()