from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..tokenizer import (
    DictionaryToken,
    DictionaryTokenizer,
    DictionaryTokenizerInputError,
)
from .phrase_trie import (
    LiteralPhraseTrie,
    LiteralPhraseTrieLoadError,
)


class LiteralTranslationError(RuntimeError):
    """Base runtime error của Literal Translator."""


class LiteralTranslationInputError(ValueError):
    """Literal chỉ nhận đúng một đoạn text dạng str."""


class LiteralDictionaryLoadError(LiteralTranslationError):
    """Canonical Literal dictionary bị thiếu hoặc sai contract."""


DEFAULT_DICTIONARY_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "en_vi_literal.json"
)


@dataclass(frozen=True, slots=True)
class LiteralTranslationResult:
    source_text: str
    translated_text: str


class LiteralTranslator:
    """
    Dịch một đoạn text Anh -> Việt bằng longest phrase rồi word fallback.

    DictionaryTokenizer là source of truth cho normalization.
    Canonical JSON đã được create_json chuẩn hóa và KHÔNG được normalize lại.
    """

    def __init__(
        self,
        dictionary_path: Path | str | None = None,
    ) -> None:
        self._tokenizer = DictionaryTokenizer()
        self.dictionary_path = (
            DEFAULT_DICTIONARY_PATH
            if dictionary_path is None
            else Path(dictionary_path).expanduser().resolve()
        )

        words, phrases = self._load_resource()
        self._words = words

        try:
            self._phrase_trie = LiteralPhraseTrie(phrases)
        except LiteralPhraseTrieLoadError as exc:
            raise LiteralDictionaryLoadError(
                "Invalid canonical phrase resource."
            ) from exc

    @property
    def word_count(self) -> int:
        return len(self._words)

    @property
    def phrase_count(self) -> int:
        return len(self._phrase_trie)

    def translate(
        self,
        text: str,
    ) -> LiteralTranslationResult:
        source_text = self._validate_text(text)
        tokens = self._tokenize(source_text)

        if not tokens:
            return LiteralTranslationResult(
                source_text=source_text,
                translated_text=source_text,
            )

        output: list[str] = []
        cursor = 0
        token_index = 0

        while token_index < len(tokens):
            phrase_tokens = self._contiguous_tokens(
                source_text,
                tokens,
                token_index,
            )
            match = self._phrase_trie.longest_match(
                phrase_tokens,
                0,
            )

            if match is not None:
                output.append(source_text[cursor:match.start_char])
                output.append(match.translation)
                cursor = match.end_char
                token_index += match.token_count
                continue

            token = tokens[token_index]
            translation = (
                self._words.get(token.normalized)
                if token.is_word
                else None
            )

            if translation is not None:
                output.append(source_text[cursor:token.start])
                output.append(translation)
                cursor = token.end

            token_index += 1

        output.append(source_text[cursor:])

        return LiteralTranslationResult(
            source_text=source_text,
            translated_text="".join(output),
        )

    def translate_text(self, text: str) -> str:
        return self.translate(text).translated_text

    def __call__(self, text: str) -> LiteralTranslationResult:
        return self.translate(text)

    def _load_resource(
        self,
    ) -> tuple[dict[str, str], dict[str, str]]:
        path = self.dictionary_path

        if not path.is_file():
            raise LiteralDictionaryLoadError(
                f"Literal dictionary does not exist: {path}"
            )

        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise LiteralDictionaryLoadError(
                f"Could not load Literal dictionary: {path}"
            ) from exc

        if not isinstance(data, dict) or set(data) != {"words", "phrases"}:
            raise LiteralDictionaryLoadError(
                "Literal dictionary must contain exactly 'words' and 'phrases'."
            )

        words = data["words"]
        phrases = data["phrases"]

        if not isinstance(words, dict) or not isinstance(phrases, dict):
            raise LiteralDictionaryLoadError(
                "'words' and 'phrases' must be objects."
            )

        word_index: dict[str, str] = {}

        for source_word, translation in words.items():
            if (
                not isinstance(source_word, str)
                or not source_word
                or source_word != source_word.strip()
                or any(char.isspace() for char in source_word)
            ):
                raise LiteralDictionaryLoadError(
                    f"Invalid canonical word key: {source_word!r}."
                )

            if not isinstance(translation, str) or not translation:
                raise LiteralDictionaryLoadError(
                    f"Word {source_word!r} must map to one non-empty string."
                )

            # Quan trọng: key đã canonical từ create_json.
            # Không normalize / lemma lại ở runtime.
            word_index[source_word] = translation

        return word_index, phrases

    def _tokenize(
        self,
        text: str,
    ) -> tuple[DictionaryToken, ...]:
        try:
            return self._tokenizer.tokenize(text)
        except DictionaryTokenizerInputError as exc:
            raise LiteralTranslationInputError(str(exc)) from exc

    @staticmethod
    def _validate_text(text: str) -> str:
        if not isinstance(text, str):
            raise LiteralTranslationInputError(
                "text must be a string, "
                f"received {type(text).__name__}."
            )

        if "\x00" in text:
            raise LiteralTranslationInputError(
                "text must not contain null characters."
            )

        return text

    @staticmethod
    def _contiguous_tokens(
        text: str,
        tokens: tuple[DictionaryToken, ...],
        start_index: int,
    ) -> tuple[DictionaryToken, ...]:
        """Không cho phrase match xuyên qua punctuation/symbol."""

        end_index = start_index + 1

        while end_index < len(tokens):
            gap = text[
                tokens[end_index - 1].end:
                tokens[end_index].start
            ]
            if not gap or not gap.isspace():
                break
            end_index += 1

        return tokens[start_index:end_index]
