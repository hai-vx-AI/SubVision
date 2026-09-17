from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from ..tokenizer import DictionaryToken


class LiteralPhraseTrieError(RuntimeError):
    """Base error của Literal PhraseTrie."""


class LiteralPhraseTrieInputError(ValueError):
    """Input PhraseTrie không hợp lệ."""


class LiteralPhraseTrieLoadError(LiteralPhraseTrieError):
    """Canonical phrase resource không đúng contract."""


@dataclass(frozen=True, slots=True)
class LiteralPhraseEntry:
    source_phrase: str
    normalized_tokens: tuple[str, ...]
    translation: str


@dataclass(frozen=True, slots=True)
class LiteralPhraseMatch:
    entry: LiteralPhraseEntry
    start_token_index: int
    end_token_index: int
    start_char: int
    end_char: int

    @property
    def token_count(self) -> int:
        return self.end_token_index - self.start_token_index

    @property
    def translation(self) -> str:
        return self.entry.translation


@dataclass(slots=True)
class _Node:
    children: dict[str, "_Node"] = field(default_factory=dict)
    entry: LiteralPhraseEntry | None = None


class LiteralPhraseTrie:
    """
    Trie chỉ index canonical phrase resource.

    Phrase key đã được create_json chuẩn hóa bằng DictionaryTokenizer.
    Runtime KHÔNG normalize resource lần nữa.
    """

    MIN_PHRASE_TOKENS = 2

    def __init__(
        self,
        phrases: Mapping[str, str],
    ) -> None:
        if not isinstance(phrases, Mapping):
            raise LiteralPhraseTrieLoadError(
                "phrases must be a mapping."
            )

        self._root = _Node()
        self._size = 0
        self._max_phrase_tokens = 0

        for source_phrase, translation in phrases.items():
            self._insert(source_phrase, translation)

    def __len__(self) -> int:
        return self._size

    @property
    def max_phrase_tokens(self) -> int:
        return self._max_phrase_tokens

    def longest_match(
        self,
        tokens: Sequence[DictionaryToken],
        start_index: int,
    ) -> LiteralPhraseMatch | None:
        self._validate_match_input(tokens, start_index)

        if start_index == len(tokens) or self._size == 0:
            return None

        node = self._root
        best_entry: LiteralPhraseEntry | None = None
        best_end: int | None = None
        end_limit = min(
            len(tokens),
            start_index + self._max_phrase_tokens,
        )

        for index in range(start_index, end_limit):
            node = node.children.get(tokens[index].normalized)
            if node is None:
                break

            if node.entry is not None:
                best_entry = node.entry
                best_end = index + 1

        if best_entry is None or best_end is None:
            return None

        return LiteralPhraseMatch(
            entry=best_entry,
            start_token_index=start_index,
            end_token_index=best_end,
            start_char=tokens[start_index].start,
            end_char=tokens[best_end - 1].end,
        )

    def _insert(
        self,
        source_phrase: object,
        translation: object,
    ) -> None:
        if not isinstance(source_phrase, str) or not source_phrase:
            raise LiteralPhraseTrieLoadError(
                "Every phrase key must be a non-empty string."
            )

        if not isinstance(translation, str) or not translation:
            raise LiteralPhraseTrieLoadError(
                f"Phrase {source_phrase!r} must map to one non-empty string."
            )

        normalized_tokens = tuple(source_phrase.split(" "))

        if (
            len(normalized_tokens) < self.MIN_PHRASE_TOKENS
            or any(not token for token in normalized_tokens)
            or source_phrase != " ".join(normalized_tokens)
        ):
            raise LiteralPhraseTrieLoadError(
                f"Phrase key is not canonical: {source_phrase!r}."
            )

        node = self._root
        for token in normalized_tokens:
            node = node.children.setdefault(token, _Node())

        if node.entry is not None:
            raise LiteralPhraseTrieLoadError(
                f"Duplicate canonical phrase: {source_phrase!r}."
            )

        node.entry = LiteralPhraseEntry(
            source_phrase=source_phrase,
            normalized_tokens=normalized_tokens,
            translation=translation,
        )
        self._size += 1
        self._max_phrase_tokens = max(
            self._max_phrase_tokens,
            len(normalized_tokens),
        )

    @staticmethod
    def _validate_match_input(
        tokens: Sequence[DictionaryToken],
        start_index: int,
    ) -> None:
        if not isinstance(tokens, Sequence):
            raise LiteralPhraseTrieInputError(
                "tokens must be a sequence of DictionaryToken."
            )

        if not isinstance(start_index, int):
            raise LiteralPhraseTrieInputError(
                "start_index must be an integer."
            )

        if not 0 <= start_index <= len(tokens):
            raise LiteralPhraseTrieInputError(
                "start_index is outside token range."
            )

        if any(not isinstance(token, DictionaryToken) for token in tokens):
            raise LiteralPhraseTrieInputError(
                "Every token must be a DictionaryToken."
            )
