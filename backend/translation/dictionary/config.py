from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


UnicodeNormalization = Literal["NFC", "NFKC"]


@dataclass(frozen=True, slots=True)
class DictionaryTranslationConfig:
    """
    Cấu hình cho nhánh dịch bằng từ điển.

    Module dictionary sẽ hoạt động theo pipeline:

        text
        → tokenizer
        → phrase trie
        → word/phrase lookup
        → translation result
    """

    # ==========================================================
    # Token normalization
    # ==========================================================

    # Phân biệt chữ hoa và chữ thường khi tra cứu.
    #
    # False:
    #     "Look", "LOOK", "look" đều được chuẩn hóa thành "look".
    #
    # True:
    #     Giữ nguyên cách viết hoa/thường.
    case_sensitive: bool = False

    # Chuẩn hóa Unicode cho từng token.
    #
    # NFKC giúp đưa một số ký tự Unicode có hình thức khác nhau
    # về dạng thống nhất để tra từ điển.
    unicode_normalization: UnicodeNormalization = "NFKC"

    # Chuẩn hóa các dấu nháy cong thành dấu nháy thẳng.
    #
    # Ví dụ:
    #     don’t → don't
    normalize_apostrophes: bool = True

    # Chuẩn hóa các loại dấu gạch ngang Unicode thành "-".
    #
    # Ví dụ:
    #     state-of-the-art → state-of-the-art
    normalize_hyphens: bool = True

    # ==========================================================
    # Token selection
    # ==========================================================

    # Có lấy số thành token hay không.
    #
    # Số thường không cần dịch nhưng vẫn nên được giữ lại để:
    #     - bảo toàn thứ tự token;
    #     - giữ vị trí trong câu;
    #     - trả nguyên giá trị khi render.
    include_numbers: bool = True

    # Giữ từ có một ký tự như:
    #     I
    #     a
    #
    # Đây đều là các từ tiếng Anh hợp lệ.
    include_single_character_words: bool = True

    # ==========================================================
    # Phrase matching
    # ==========================================================

    # Số token tối đa trong một cụm từ.
    #
    # Ví dụ:
    #     look up               → 2 token
    #     in front of           → 3 token
    #     as a matter of fact   → 5 token
    #
    # Tham số này sẽ được phrase_trie.py sử dụng sau.
    max_phrase_tokens: int = 5

    # Ưu tiên cụm dài nhất khi có nhiều cụm bắt đầu tại cùng
    # một vị trí.
    #
    # Ví dụ từ điển chứa:
    #     New York
    #     New York City
    #
    # Với đầu vào "New York City", kết quả được chọn là
    # "New York City".
    longest_match_first: bool = True

    # ==========================================================
    # Input limits
    # ==========================================================

    # Giới hạn độ dài chuỗi đầu vào để tránh dữ liệu bất thường.
    max_input_characters: int = 10_000

    # Giới hạn độ dài của một token.
    max_token_characters: int = 128

    # Đưa các biến thể của từ về dạng từ điển.
    #
    # decided  → decide
    # studies  → study
    # machines → machine
    lemmatize_words: bool = True

    # Ngôn ngữ dùng cho lemmatizer.
    lemmatizer_language: str = "en"

    def __post_init__(self) -> None:
        if self.unicode_normalization not in {
            "NFC",
            "NFKC",
        }:
            raise ValueError(
                "unicode_normalization must be 'NFC' or 'NFKC'."
            )

        if self.max_phrase_tokens < 1:
            raise ValueError(
                "max_phrase_tokens must be at least 1."
            )

        if self.max_input_characters < 1:
            raise ValueError(
                "max_input_characters must be at least 1."
            )

        if self.max_token_characters < 1:
            raise ValueError(
                "max_token_characters must be at least 1."
            )


DEFAULT_DICTIONARY_TRANSLATION_CONFIG = (
    DictionaryTranslationConfig()
)