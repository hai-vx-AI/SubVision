from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .config import (
    DEFAULT_DICTIONARY_TRANSLATION_CONFIG,
    DictionaryTranslationConfig,
)
from .tokenizer import (
    DictionaryToken,
    DictionaryTokenizer,
)


class PhraseTrieError(RuntimeError):
    """
    Lỗi cơ sở của PhraseTrie.
    """


class PhraseTrieInputError(ValueError):
    """
    Dữ liệu được truyền vào PhraseTrie không hợp lệ.
    """


@dataclass(frozen=True, slots=True)
class PhraseEntry:
    """
    Một cụm từ được lưu trong Trie.

    Attributes
    ----------
    source_phrase:
        Cụm từ gốc khi được thêm vào Trie.

        Ví dụ:
            "look up"

    normalized_tokens:
        Các token đã được chuẩn hóa.

        Ví dụ:
            ("look", "up")

    translations:
        Một hoặc nhiều nghĩa tiếng Việt của cụm.
    """

    source_phrase: str
    normalized_tokens: tuple[str, ...]
    translations: tuple[str, ...]

    @property
    def token_count(self) -> int:
        """
        Số token của cụm từ.
        """

        return len(self.normalized_tokens)

    @property
    def primary_translation(self) -> str:
        """
        Nghĩa đầu tiên của cụm từ.
        """

        return self.translations[0]


@dataclass(frozen=True, slots=True)
class PhraseMatch:
    """
    Kết quả tìm thấy một cụm trong danh sách token.

    end_token_index sử dụng dạng exclusive.

    Ví dụ cụm chiếm token 3 và 4:

        start_token_index = 3
        end_token_index = 5
    """

    entry: PhraseEntry

    start_token_index: int
    end_token_index: int

    start_char: int
    end_char: int

    @property
    def token_count(self) -> int:
        """
        Số token được match.
        """

        return (
            self.end_token_index
            - self.start_token_index
        )

    @property
    def source_phrase(self) -> str:
        return self.entry.source_phrase

    @property
    def translations(self) -> tuple[str, ...]:
        return self.entry.translations

    @property
    def primary_translation(self) -> str:
        return self.entry.primary_translation


@dataclass(slots=True)
class _PhraseTrieNode:
    """
    Một node nội bộ trong Trie.

    children:
        Key là token chuẩn hóa tiếp theo.

    entry:
        Khác None nếu đường đi đến node này tạo thành
        một cụm hoàn chỉnh.
    """

    children: dict[str, _PhraseTrieNode] = field(
        default_factory=dict
    )

    entry: PhraseEntry | None = None


class PhraseTrie:
    """
    Trie cấp token dùng để lưu và tìm cụm từ.

    Ví dụ Trie chứa:

        look up
        look after
        look forward to

    Cấu trúc tương đương:

        root
        └── look
            ├── up
            ├── after
            └── forward
                └── to

    PhraseTrie:
        - lưu cụm bằng token chuẩn hóa;
        - tìm cụm từ một vị trí bất kỳ;
        - ưu tiên cụm dài nhất;
        - trả về vị trí token và ký tự;
        - không dịch từ đơn;
        - không sửa lỗi OCR;
        - không tự token hóa trong quá trình match.
    """

    MIN_PHRASE_TOKENS = 2

    def __init__(
        self,
        config: DictionaryTranslationConfig | None = None,
        tokenizer: DictionaryTokenizer | None = None,
    ) -> None:
        if config is not None:
            self.config = config

        elif tokenizer is not None:
            self.config = tokenizer.config

        else:
            self.config = (
                DEFAULT_DICTIONARY_TRANSLATION_CONFIG
            )

        self.tokenizer = (
            tokenizer
            or DictionaryTokenizer(self.config)
        )

        self._root = _PhraseTrieNode()
        self._size = 0

    # ==========================================================
    # Public properties
    # ==========================================================

    @property
    def size(self) -> int:
        """
        Số cụm hoàn chỉnh đang được lưu.
        """

        return self._size

    def __len__(self) -> int:
        return self._size

    # ==========================================================
    # Add phrases
    # ==========================================================

    def add(
        self,
        phrase: str,
        translations: str | Sequence[str],
        *,
        replace: bool = False,
    ) -> PhraseEntry:
        """
        Thêm một cụm từ vào Trie.

        Parameters
        ----------
        phrase:
            Cụm từ tiếng Anh.

        translations:
            Một nghĩa hoặc danh sách nhiều nghĩa tiếng Việt.

        replace:
            False:
                Nếu cụm đã tồn tại, bổ sung các nghĩa mới.

            True:
                Thay toàn bộ nghĩa cũ bằng nghĩa mới.

        Examples
        --------
        trie.add(
            "look up",
            "tra cứu",
        )

        trie.add(
            "take off",
            (
                "cất cánh",
                "cởi ra",
            ),
        )
        """

        validated_phrase = self._validate_phrase(
            phrase
        )

        normalized_tokens = (
            self.tokenizer.normalize_phrase(
                validated_phrase
            )
        )

        self._validate_phrase_tokens(
            normalized_tokens
        )

        validated_translations = (
            self._normalize_translations(
                translations
            )
        )

        node = self._root

        for token in normalized_tokens:
            node = node.children.setdefault(
                token,
                _PhraseTrieNode(),
            )

        existing_entry = node.entry

        if existing_entry is None:
            entry = PhraseEntry(
                source_phrase=validated_phrase,
                normalized_tokens=normalized_tokens,
                translations=validated_translations,
            )

            node.entry = entry
            self._size += 1

            return entry

        if replace:
            entry = PhraseEntry(
                source_phrase=validated_phrase,
                normalized_tokens=normalized_tokens,
                translations=validated_translations,
            )

            node.entry = entry
            return entry

        merged_translations = self._merge_translations(
            existing_entry.translations,
            validated_translations,
        )

        entry = PhraseEntry(
            source_phrase=existing_entry.source_phrase,
            normalized_tokens=normalized_tokens,
            translations=merged_translations,
        )

        node.entry = entry

        return entry

    def add_many(
        self,
        phrases: Mapping[
            str,
            str | Sequence[str],
        ],
        *,
        replace: bool = False,
    ) -> None:
        """
        Thêm nhiều cụm từ.

        Example
        -------
        trie.add_many(
            {
                "look up": "tra cứu",
                "give up": "từ bỏ",
                "machine learning": "học máy",
                "take off": (
                    "cất cánh",
                    "cởi ra",
                ),
            }
        )
        """

        if not isinstance(phrases, Mapping):
            raise PhraseTrieInputError(
                "phrases must be a mapping of "
                "{phrase: translations}."
            )

        for phrase, translations in phrases.items():
            self.add(
                phrase=phrase,
                translations=translations,
                replace=replace,
            )

    # ==========================================================
    # Direct lookup
    # ==========================================================

    def contains(
        self,
        phrase: str,
    ) -> bool:
        """
        Kiểm tra một cụm có tồn tại hay không.
        """

        return self.get(phrase) is not None

    def get(
        self,
        phrase: str,
    ) -> PhraseEntry | None:
        """
        Lấy thông tin cụm từ.

        Trả về None nếu không tồn tại.
        """

        validated_phrase = self._validate_phrase(
            phrase
        )

        normalized_tokens = (
            self.tokenizer.normalize_phrase(
                validated_phrase
            )
        )

        node = self._find_node(normalized_tokens)

        if node is None:
            return None

        return node.entry

    # ==========================================================
    # Phrase matching
    # ==========================================================

    def longest_match(
        self,
        tokens: Sequence[DictionaryToken],
        start_index: int,
    ) -> PhraseMatch | None:
        """
        Tìm cụm phù hợp bắt đầu từ một vị trí token.

        Khi nhiều cụm cùng bắt đầu tại vị trí đó, mặc định
        chọn cụm dài nhất.

        Ví dụ Trie chứa:

            New York
            New York City

        Input:

            I live in New York City

        Tại token "New", kết quả là:

            New York City

        Parameters
        ----------
        tokens:
            Danh sách token từ DictionaryTokenizer.

        start_index:
            Vị trí token bắt đầu dò.

        Returns
        -------
        PhraseMatch | None
            Cụm tìm được hoặc None.
        """

        self._validate_match_input(
            tokens=tokens,
            start_index=start_index,
        )

        if start_index == len(tokens):
            return None

        node = self._root

        best_entry: PhraseEntry | None = None
        best_end_index: int | None = None

        max_end_index = min(
            len(tokens),
            start_index
            + self.config.max_phrase_tokens,
        )

        for token_index in range(
            start_index,
            max_end_index,
        ):
            normalized_token = (
                tokens[token_index].normalized
            )

            next_node = node.children.get(
                normalized_token
            )

            if next_node is None:
                break

            node = next_node

            if node.entry is not None:
                best_entry = node.entry
                best_end_index = token_index + 1

                if not self.config.longest_match_first:
                    break

        if (
            best_entry is None
            or best_end_index is None
        ):
            return None

        return PhraseMatch(
            entry=best_entry,
            start_token_index=start_index,
            end_token_index=best_end_index,
            start_char=tokens[start_index].start,
            end_char=tokens[best_end_index - 1].end,
        )

    def find_matches(
        self,
        tokens: Sequence[DictionaryToken],
    ) -> tuple[PhraseMatch, ...]:
        """
        Tìm tất cả cụm không chồng lấn trong danh sách token.

        Thuật toán:
            - duyệt từ trái sang phải;
            - tại mỗi vị trí, tìm cụm dài nhất;
            - nếu tìm thấy, nhảy qua toàn bộ cụm;
            - nếu không, chuyển sang token tiếp theo.

        Ví dụ:

            I want to look up machine learning terms

        Kết quả có thể là:

            look up
            machine learning
        """

        if not isinstance(tokens, Sequence):
            raise PhraseTrieInputError(
                "tokens must be a sequence of "
                "DictionaryToken objects."
            )

        if not tokens:
            return ()

        matches: list[PhraseMatch] = []

        token_index = 0

        while token_index < len(tokens):
            match = self.longest_match(
                tokens=tokens,
                start_index=token_index,
            )

            if match is None:
                token_index += 1
                continue

            matches.append(match)

            token_index = match.end_token_index

        return tuple(matches)

    def find_in_text(
        self,
        text: str,
    ) -> tuple[PhraseMatch, ...]:
        """
        API tiện lợi để tìm cụm trực tiếp từ chuỗi.

        Hàm này:
            text
            → tokenizer
            → find_matches()

        Translator sau này thường sẽ tự tokenize một lần rồi
        truyền token vào find_matches() để tránh token hóa lặp.
        """

        tokens = self.tokenizer.tokenize(text)

        return self.find_matches(tokens)

    # ==========================================================
    # Management
    # ==========================================================

    def clear(self) -> None:
        """
        Xóa toàn bộ cụm khỏi Trie.
        """

        self._root = _PhraseTrieNode()
        self._size = 0

    # ==========================================================
    # Internal lookup
    # ==========================================================

    def _find_node(
        self,
        normalized_tokens: Sequence[str],
    ) -> _PhraseTrieNode | None:
        """
        Tìm node tương ứng với một chuỗi token.
        """

        node = self._root

        for token in normalized_tokens:
            next_node = node.children.get(token)

            if next_node is None:
                return None

            node = next_node

        return node

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_phrase(
        phrase: str,
    ) -> str:
        if not isinstance(phrase, str):
            raise PhraseTrieInputError(
                "phrase must be a string, "
                f"received {type(phrase).__name__}."
            )

        stripped = phrase.strip()

        if not stripped:
            raise PhraseTrieInputError(
                "phrase must not be empty."
            )

        return stripped

    def _validate_phrase_tokens(
        self,
        tokens: tuple[str, ...],
    ) -> None:
        if (
            len(tokens)
            < self.MIN_PHRASE_TOKENS
        ):
            raise PhraseTrieInputError(
                "A phrase must contain at least "
                f"{self.MIN_PHRASE_TOKENS} tokens. "
                "Single words belong in the word dictionary."
            )

        if (
            len(tokens)
            > self.config.max_phrase_tokens
        ):
            raise PhraseTrieInputError(
                "Phrase contains more than "
                f"{self.config.max_phrase_tokens} tokens."
            )

    @staticmethod
    def _normalize_translations(
        translations: str | Sequence[str],
    ) -> tuple[str, ...]:
        """
        Chuẩn hóa một nghĩa hoặc danh sách nghĩa thành tuple.
        """

        if isinstance(translations, str):
            stripped = translations.strip()

            if not stripped:
                raise PhraseTrieInputError(
                    "translation must not be empty."
                )

            return (stripped,)

        if not isinstance(translations, Sequence):
            raise PhraseTrieInputError(
                "translations must be a string "
                "or a sequence of strings."
            )

        normalized: list[str] = []

        for translation in translations:
            if not isinstance(translation, str):
                raise PhraseTrieInputError(
                    "Every translation must be a string."
                )

            stripped = translation.strip()

            if not stripped:
                continue

            if stripped not in normalized:
                normalized.append(stripped)

        if not normalized:
            raise PhraseTrieInputError(
                "At least one non-empty translation "
                "is required."
            )

        return tuple(normalized)

    @staticmethod
    def _merge_translations(
        current: tuple[str, ...],
        new: tuple[str, ...],
    ) -> tuple[str, ...]:
        """
        Ghép các nghĩa và loại bỏ giá trị trùng lặp.
        """

        merged = list(current)

        for translation in new:
            if translation not in merged:
                merged.append(translation)

        return tuple(merged)

    @staticmethod
    def _validate_match_input(
        *,
        tokens: Sequence[DictionaryToken],
        start_index: int,
    ) -> None:
        if not isinstance(tokens, Sequence):
            raise PhraseTrieInputError(
                "tokens must be a sequence."
            )

        if not isinstance(start_index, int):
            raise PhraseTrieInputError(
                "start_index must be an integer."
            )

        if start_index < 0:
            raise PhraseTrieInputError(
                "start_index must not be negative."
            )

        if start_index > len(tokens):
            raise PhraseTrieInputError(
                "start_index exceeds the token count."
            )

        for token in tokens:
            if not isinstance(
                token,
                DictionaryToken,
            ):
                raise PhraseTrieInputError(
                    "Every item in tokens must be "
                    "a DictionaryToken."
                )