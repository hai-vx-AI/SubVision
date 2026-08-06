from __future__ import annotations

import re
import unicodedata
from simplemma import lemmatize
from dataclasses import dataclass
from typing import Literal

from .config import (
    DEFAULT_DICTIONARY_TRANSLATION_CONFIG,
    DictionaryTranslationConfig,
)


TokenType = Literal["word", "number"]


class DictionaryTokenizerError(RuntimeError):
    """
    Lỗi cơ sở của dictionary tokenizer.
    """


class DictionaryTokenizerInputError(ValueError):
    """
    Chuỗi đầu vào của tokenizer không hợp lệ.
    """


@dataclass(frozen=True, slots=True)
class DictionaryToken:
    """
    Một token được tách từ chuỗi đầu vào.

    Attributes
    ----------
    index:
        Thứ tự của token trong danh sách.

    text:
        Nội dung gốc của token.

    normalized:
        Nội dung đã chuẩn hóa để dùng khi tra từ điển
        hoặc tìm cụm trong Trie.

    start:
        Vị trí bắt đầu trong chuỗi gốc.

    end:
        Vị trí kết thúc trong chuỗi gốc.
        Python sử dụng khoảng [start, end).

    token_type:
        "word" hoặc "number".
    """

    index: int
    text: str
    normalized: str
    start: int
    end: int
    token_type: TokenType

    @property
    def length(self) -> int:
        """
        Độ dài token gốc.
        """

        return len(self.text)

    @property
    def is_word(self) -> bool:
        return self.token_type == "word"

    @property
    def is_number(self) -> bool:
        return self.token_type == "number"


class DictionaryTokenizer:
    """
    Tách chuỗi thành các token phục vụ dịch bằng từ điển.

    Tokenizer này:
        - nhận một chuỗi;
        - tách từ và số;
        - giữ vị trí start/end;
        - chuẩn hóa token để tra cứu;
        - không xóa hoặc thay đổi chuỗi gốc.

    Tokenizer này không:
        - tìm cụm từ;
        - tra nghĩa;
        - dịch văn bản;
        - sửa lỗi OCR;
        - kiểm tra ngữ nghĩa.
    """

    # [^\W\d_] nghĩa là một ký tự chữ Unicode:
    #     A-Z, a-z, é, ü...
    #
    # Phần sau cho phép token chứa apostrophe hoặc hyphen:
    #     don't
    #     John's
    #     state-of-the-art
    WORD_PATTERN = (
        r"[^\W\d_]+"
        r"(?:['’\-‐-‒–—−][^\W\d_]+)*"
    )

    # Nhận các dạng số phổ biến:
    #     10
    #     10.5
    #     10:30
    #     2026-08-01
    #     1,000
    NUMBER_PATTERN = (
        r"\d+"
        r"(?:[.,:/\-]\d+)*"
    )

    TOKEN_PATTERN = re.compile(
        rf"(?P<word>{WORD_PATTERN})"
        rf"|(?P<number>{NUMBER_PATTERN})",
        flags=re.UNICODE,
    )

    APOSTROPHE_TRANSLATION = str.maketrans(
        {
            "’": "'",
            "‘": "'",
            "‛": "'",
            "ʼ": "'",
        }
    )

    HYPHEN_TRANSLATION = str.maketrans(
        {
            "‐": "-",
            "-": "-",
            "‒": "-",
            "–": "-",
            "—": "-",
            "−": "-",
        }
    )

    def __init__(
        self,
        config: DictionaryTranslationConfig | None = None,
    ) -> None:
        self.config = (
            config
            or DEFAULT_DICTIONARY_TRANSLATION_CONFIG
        )

    def tokenize(
        self,
        text: str,
    ) -> tuple[DictionaryToken, ...]:
        """
        Tách chuỗi thành danh sách token.

        Parameters
        ----------
        text:
            Chuỗi đầu vào sau bước OCR correction.

        Returns
        -------
        tuple[DictionaryToken, ...]
            Danh sách token theo đúng thứ tự xuất hiện.
        """

        validated_text = self._validate_text(text)

        if not validated_text:
            return ()

        tokens: list[DictionaryToken] = []

        for match in self.TOKEN_PATTERN.finditer(
            validated_text
        ):
            token_type = self._get_token_type(match)

            if (
                token_type == "number"
                and not self.config.include_numbers
            ):
                continue

            original = match.group(0)

            if (
                len(original)
                > self.config.max_token_characters
            ):
                continue

            if (
                token_type == "word"
                and len(original) == 1
                and not self.config.include_single_character_words
            ):
                continue

            normalized = self.normalize_token(
                original,
                apply_lemma=(token_type == "word"),
            )

            tokens.append(
                DictionaryToken(
                    index=len(tokens),
                    text=original,
                    normalized=normalized,
                    start=match.start(),
                    end=match.end(),
                    token_type=token_type,
                )
            )

        return tuple(tokens)

    def normalize_token(
        self,
        token: str,
        *,
        apply_lemma: bool = True,
    ) -> str:
        """
        Chuẩn hóa một token để tra từ điển và PhraseTrie.

        Ví dụ:

            "Decided"  → "decide"
            "STUDIES"  → "study"
            "Machines" → "machine"

        apply_lemma=False được dùng cho số và những token
        không cần lemmatization.
        """

        validated_token = self._validate_token(token)

        normalized = unicodedata.normalize(
            self.config.unicode_normalization,
            validated_token,
        )

        if self.config.normalize_apostrophes:
            normalized = normalized.translate(
                self.APOSTROPHE_TRANSLATION
            )

        if self.config.normalize_hyphens:
            normalized = normalized.translate(
                self.HYPHEN_TRANSLATION
            )

        if not self.config.case_sensitive:
            normalized = normalized.casefold()

        if (
            apply_lemma
            and self.config.lemmatize_words
        ):
            normalized = lemmatize(
                normalized,
                lang=self.config.lemmatizer_language,
            )

        return normalized

    def normalize_phrase(
        self,
        phrase: str,
    ) -> tuple[str, ...]:
        """
        Chuyển một cụm từ thành tuple token chuẩn hóa.

        Hàm này sẽ được dùng khi thêm cụm vào PhraseTrie.

        Ví dụ:

            "Look Up"
                → ("look", "up")

            "In Front Of"
                → ("in", "front", "of")
        """

        tokens = self.tokenize(phrase)

        return tuple(
            token.normalized
            for token in tokens
        )

    def extract_normalized_tokens(
        self,
        text: str,
    ) -> tuple[str, ...]:
        """
        API rút gọn: chỉ lấy danh sách nội dung chuẩn hóa.

        Ví dụ:

            "I Want To Look Up This Word"

        Kết quả:

            (
                "i",
                "want",
                "to",
                "look",
                "up",
                "this",
                "word",
            )
        """

        return tuple(
            token.normalized
            for token in self.tokenize(text)
        )

    def __call__(
        self,
        text: str,
    ) -> tuple[DictionaryToken, ...]:
        """
        Cho phép gọi tokenizer như một function.

        Ví dụ:

            tokenizer = DictionaryTokenizer()
            tokens = tokenizer("Look up this word.")
        """

        return self.tokenize(text)

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_text(
        self,
        text: str,
    ) -> str:
        if not isinstance(text, str):
            raise DictionaryTokenizerInputError(
                "text must be a string, "
                f"received {type(text).__name__}."
            )

        if "\x00" in text:
            raise DictionaryTokenizerInputError(
                "text must not contain null characters."
            )

        if (
            len(text)
            > self.config.max_input_characters
        ):
            raise DictionaryTokenizerInputError(
                "text exceeds the configured maximum length of "
                f"{self.config.max_input_characters} characters."
            )

        return text

    def _validate_token(
        self,
        token: str,
    ) -> str:
        if not isinstance(token, str):
            raise DictionaryTokenizerInputError(
                "token must be a string, "
                f"received {type(token).__name__}."
            )

        if not token:
            raise DictionaryTokenizerInputError(
                "token must not be empty."
            )

        if any(character.isspace() for character in token):
            raise DictionaryTokenizerInputError(
                "normalize_token() only accepts one token."
            )

        if (
            len(token)
            > self.config.max_token_characters
        ):
            raise DictionaryTokenizerInputError(
                "token exceeds the configured maximum length of "
                f"{self.config.max_token_characters} characters."
            )

        return token

    @staticmethod
    def _get_token_type(
        match: re.Match[str],
    ) -> TokenType:
        if match.lastgroup == "number":
            return "number"

        return "word"