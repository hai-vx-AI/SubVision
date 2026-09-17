from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from .phrase_trie import (
    PhraseMatch,
    PhraseTrie,
)
from .tokenizer import (
    DictionaryToken,
    DictionaryTokenizer,
)
from .vocabulary import (
    DictionaryVocabulary,
    WordEntry,
)


TranslationItemType = Literal[
    "phrase",
    "word",
    "number",
    "unknown",
]


class DictionaryTranslatorError(RuntimeError):
    """
    Lỗi cơ sở của dictionary translator.
    """


class DictionaryTranslatorInputError(ValueError):
    """
    Đầu vào của translator không hợp lệ.
    """


@dataclass(frozen=True, slots=True)
class DictionaryTranslationItem:
    """
    Kết quả dịch của một từ, cụm từ hoặc số.

    Attributes
    ----------
    source_text:
        Nội dung gốc trong câu.

    normalized_tokens:
        Các token chuẩn hóa.

    translations:
        Một hoặc nhiều nghĩa tìm được.

        Rỗng nếu không tìm thấy nghĩa.

    item_type:
        phrase:
            Cụm từ được tìm thấy trong PhraseTrie.

        word:
            Từ đơn được tìm thấy trong Vocabulary.

        number:
            Token dạng số, giữ nguyên.

        unknown:
            Từ không có trong từ điển.

    start_token_index, end_token_index:
        Khoảng token dạng [start, end).

    start_char, end_char:
        Khoảng ký tự trong chuỗi gốc dạng [start, end).
    """

    source_text: str
    normalized_tokens: tuple[str, ...]
    translations: tuple[str, ...]

    item_type: TranslationItemType

    start_token_index: int
    end_token_index: int

    start_char: int
    end_char: int

    @property
    def translated(self) -> bool:
        """
        Có tìm thấy bản dịch hay không.
        """

        return bool(self.translations)

    @property
    def primary_translation(self) -> str | None:
        """
        Nghĩa đầu tiên.

        Trả về None nếu không có bản dịch.
        """

        if not self.translations:
            return None

        return self.translations[0]

    @property
    def display_text(self) -> str:
        """
        Nội dung dùng để hiển thị.

        Nếu có bản dịch:
            trả nghĩa đầu tiên.

        Nếu không:
            giữ nguyên source_text.
        """

        return (
            self.primary_translation
            or self.source_text
        )


@dataclass(frozen=True, slots=True)
class DictionaryTranslationResult:
    """
    Kết quả xử lý toàn bộ chuỗi.
    """

    original_text: str
    items: tuple[DictionaryTranslationItem, ...]

    @property
    def literal_translation(self) -> str:
        """
        Ghép nghĩa đầu tiên của từng item bằng khoảng trắng.

        Đây là bản dịch từng từ/cụm, không phải bản dịch
        ngữ pháp hoàn chỉnh.
        """

        return " ".join(
            item.display_text
            for item in self.items
        )

    @property
    def translated_items(
        self,
    ) -> tuple[DictionaryTranslationItem, ...]:
        """
        Chỉ lấy các item có bản dịch.
        """

        return tuple(
            item
            for item in self.items
            if item.translated
        )

    @property
    def unknown_items(
        self,
    ) -> tuple[DictionaryTranslationItem, ...]:
        """
        Chỉ lấy các token không tìm thấy nghĩa.
        """

        return tuple(
            item
            for item in self.items
            if item.item_type == "unknown"
        )


class DictionaryTranslator:
    """
    Điều phối quá trình dịch bằng từ điển.

    Translator không tự chứa dữ liệu từ điển.
    Nó sử dụng:
        - DictionaryTokenizer;
        - DictionaryVocabulary;
        - PhraseTrie.
    """

    def __init__(
        self,
        tokenizer: DictionaryTokenizer | None = None,
        vocabulary: DictionaryVocabulary | None = None,
        phrase_trie: PhraseTrie | None = None,
    ) -> None:
        self.tokenizer = (
            tokenizer
            or DictionaryTokenizer()
        )

        self.vocabulary = (
            vocabulary
            or DictionaryVocabulary(self.tokenizer)
        )

        self.phrase_trie = (
            phrase_trie
            or PhraseTrie(
                config=self.tokenizer.config,
                tokenizer=self.tokenizer,
            )
        )

    def translate(
        self,
        text: str,
    ) -> DictionaryTranslationResult:
        """
        Dịch một chuỗi theo từ và cụm từ.

        Đây là API chính của translator.
        """

        validated_text = self._validate_text(text)

        tokens = self.tokenizer.tokenize(
            validated_text
        )

        if not tokens:
            return DictionaryTranslationResult(
                original_text=validated_text,
                items=(),
            )

        phrase_matches = (
            self.phrase_trie.find_matches(tokens)
        )

        matches_by_start = {
            match.start_token_index: match
            for match in phrase_matches
        }

        items: list[DictionaryTranslationItem] = []

        token_index = 0

        while token_index < len(tokens):
            phrase_match = matches_by_start.get(
                token_index
            )

            if phrase_match is not None:
                items.append(
                    self._create_phrase_item(
                        text=validated_text,
                        match=phrase_match,
                    )
                )

                token_index = (
                    phrase_match.end_token_index
                )

                continue

            token = tokens[token_index]

            items.append(
                self._create_token_item(token)
            )

            token_index += 1

        return DictionaryTranslationResult(
            original_text=validated_text,
            items=tuple(items),
        )

    def translate_text(
        self,
        text: str,
    ) -> str:
        """
        API rút gọn chỉ trả bản dịch ghép từng từ/cụm.
        """

        return self.translate(
            text
        ).literal_translation

    def translate_word(
        self,
        word: str,
    ) -> DictionaryTranslationItem:
        """
        Dịch riêng một từ đơn.

        Example
        -------
        result = translator.translate_word("machine")
        print(result.translations)
        """

        validated_text = self._validate_text(word)

        tokens = self.tokenizer.tokenize(
            validated_text
        )

        if len(tokens) != 1:
            raise DictionaryTranslatorInputError(
                "translate_word() requires exactly one token."
            )

        token = tokens[0]

        if token.start != 0 or token.end != len(
            validated_text
        ):
            raise DictionaryTranslatorInputError(
                "translate_word() input contains unsupported "
                "surrounding characters."
            )

        return self._create_token_item(token)

    def add_words(
        self,
        words: Mapping[
            str,
            str | Sequence[str],
        ],
        *,
        replace: bool = False,
    ) -> None:
        """
        API tiện lợi để thêm từ đơn.
        """

        self.vocabulary.add_many(
            words,
            replace=replace,
        )

    def add_phrases(
        self,
        phrases: Mapping[
            str,
            str | Sequence[str],
        ],
        *,
        replace: bool = False,
    ) -> None:
        """
        API tiện lợi để thêm cụm từ.
        """

        self.phrase_trie.add_many(
            phrases,
            replace=replace,
        )

    def __call__(
        self,
        text: str,
    ) -> DictionaryTranslationResult:
        """
        Cho phép gọi object như function.
        """

        return self.translate(text)

    def _create_phrase_item(
        self,
        *,
        text: str,
        match: PhraseMatch,
    ) -> DictionaryTranslationItem:
        """
        Chuyển PhraseMatch thành TranslationItem.
        """

        return DictionaryTranslationItem(
            source_text=text[
                match.start_char:match.end_char
            ],
            normalized_tokens=(
                match.entry.normalized_tokens
            ),
            translations=match.translations,
            item_type="phrase",
            start_token_index=(
                match.start_token_index
            ),
            end_token_index=(
                match.end_token_index
            ),
            start_char=match.start_char,
            end_char=match.end_char,
        )

    def _create_token_item(
        self,
        token: DictionaryToken,
    ) -> DictionaryTranslationItem:
        """
        Dịch một token riêng lẻ.
        """

        if token.is_number:
            return DictionaryTranslationItem(
                source_text=token.text,
                normalized_tokens=(
                    token.normalized,
                ),
                translations=(),
                item_type="number",
                start_token_index=token.index,
                end_token_index=token.index + 1,
                start_char=token.start,
                end_char=token.end,
            )

        word_entry = (
            self.vocabulary.get_normalized(
                token.normalized
            )
        )

        if word_entry is None:
            return DictionaryTranslationItem(
                source_text=token.text,
                normalized_tokens=(
                    token.normalized,
                ),
                translations=(),
                item_type="unknown",
                start_token_index=token.index,
                end_token_index=token.index + 1,
                start_char=token.start,
                end_char=token.end,
            )

        return self._create_word_item(
            token=token,
            entry=word_entry,
        )

    @staticmethod
    def _create_word_item(
        *,
        token: DictionaryToken,
        entry: WordEntry,
    ) -> DictionaryTranslationItem:
        """
        Tạo kết quả cho từ tìm thấy trong vocabulary.
        """

        return DictionaryTranslationItem(
            source_text=token.text,
            normalized_tokens=(
                token.normalized,
            ),
            translations=entry.translations,
            item_type="word",
            start_token_index=token.index,
            end_token_index=token.index + 1,
            start_char=token.start,
            end_char=token.end,
        )

    @staticmethod
    def _validate_text(
        text: str,
    ) -> str:
        if not isinstance(text, str):
            raise DictionaryTranslatorInputError(
                "text must be a string, "
                f"received {type(text).__name__}."
            )

        if "\x00" in text:
            raise DictionaryTranslatorInputError(
                "text must not contain null characters."
            )

        return text