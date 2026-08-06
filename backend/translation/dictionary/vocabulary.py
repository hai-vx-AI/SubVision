from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .tokenizer import DictionaryTokenizer


class DictionaryVocabularyError(RuntimeError):
    """
    Lỗi cơ sở của word vocabulary.
    """


class DictionaryVocabularyInputError(ValueError):
    """
    Dữ liệu từ hoặc nghĩa không hợp lệ.
    """


class DictionaryVocabularyLoadError(DictionaryVocabularyError):
    """
    Không thể tải file từ điển.
    """


@dataclass(frozen=True, slots=True)
class WordEntry:
    """
    Một từ đơn trong từ điển.

    Attributes
    ----------
    source_word:
        Từ gốc khi được thêm vào vocabulary.

    normalized_word:
        Từ đã chuẩn hóa để dùng làm key tra cứu.

    translations:
        Một hoặc nhiều nghĩa tiếng Việt.
    """

    source_word: str
    normalized_word: str
    translations: tuple[str, ...]

    @property
    def primary_translation(self) -> str:
        """
        Nghĩa đầu tiên của từ.
        """

        return self.translations[0]


class DictionaryVocabulary:
    """
    Quản lý từ điển dịch từ đơn Anh → Việt.

    Vocabulary chịu trách nhiệm:
        - thêm từ;
        - lưu nhiều nghĩa;
        - chuẩn hóa từ trước khi lưu;
        - tra từ;
        - tải dữ liệu từ JSON.

    Vocabulary không:
        - tách câu;
        - tìm cụm từ;
        - điều phối quá trình dịch;
        - sửa lỗi OCR.
    """

    def __init__(
        self,
        tokenizer: DictionaryTokenizer | None = None,
    ) -> None:
        self.tokenizer = tokenizer or DictionaryTokenizer()

        self._entries: dict[str, WordEntry] = {}

    @property
    def size(self) -> int:
        """
        Số từ hiện có trong vocabulary.
        """

        return len(self._entries)

    def __len__(self) -> int:
        return self.size

    def add(
        self,
        word: str,
        translations: str | Sequence[str],
        *,
        replace: bool = False,
    ) -> WordEntry:
        """
        Thêm một từ vào vocabulary.

        Parameters
        ----------
        word:
            Từ tiếng Anh.

        translations:
            Một nghĩa hoặc nhiều nghĩa tiếng Việt.

        replace:
            False:
                Bổ sung nghĩa mới vào nghĩa hiện có.

            True:
                Thay toàn bộ nghĩa cũ.

        Examples
        --------
        vocabulary.add(
            "problem",
            "vấn đề",
        )

        vocabulary.add(
            "run",
            (
                "chạy",
                "vận hành",
            ),
        )
        """

        source_word = self._validate_word(word)

        normalized_word = self.tokenizer.normalize_token(
            source_word
        )

        normalized_translations = (
            self._normalize_translations(translations)
        )

        existing_entry = self._entries.get(
            normalized_word
        )

        if existing_entry is None or replace:
            entry = WordEntry(
                source_word=source_word,
                normalized_word=normalized_word,
                translations=normalized_translations,
            )

            self._entries[normalized_word] = entry

            return entry

        merged_translations = self._merge_translations(
            existing_entry.translations,
            normalized_translations,
        )

        entry = WordEntry(
            source_word=existing_entry.source_word,
            normalized_word=normalized_word,
            translations=merged_translations,
        )

        self._entries[normalized_word] = entry

        return entry

    def add_many(
        self,
        words: Mapping[
            str,
            str | Sequence[str],
        ],
        *,
        replace: bool = False,
    ) -> None:
        """
        Thêm nhiều từ cùng lúc.

        Example
        -------
        vocabulary.add_many(
            {
                "problem": "vấn đề",
                "machine": "máy móc",
                "run": (
                    "chạy",
                    "vận hành",
                ),
            }
        )
        """

        if not isinstance(words, Mapping):
            raise DictionaryVocabularyInputError(
                "words must be a mapping of "
                "{word: translations}."
            )

        for word, translations in words.items():
            self.add(
                word=word,
                translations=translations,
                replace=replace,
            )

    def get(
        self,
        word: str,
    ) -> WordEntry | None:
        """
        Tra một từ chưa chuẩn hóa.

        Ví dụ:
            get("Problem")
            get("PROBLEM")
            get("problem")

        Nếu case_sensitive=False, cả ba trường hợp đều
        tra cùng một entry.
        """

        validated_word = self._validate_word(word)

        normalized_word = self.tokenizer.normalize_token(
            validated_word
        )

        return self._entries.get(normalized_word)

    def get_normalized(
        self,
        normalized_word: str,
    ) -> WordEntry | None:
        """
        Tra từ đã được chuẩn hóa.

        Translator sử dụng hàm này vì token.normalized
        đã được tokenizer xử lý từ trước.
        """

        if not isinstance(normalized_word, str):
            raise DictionaryVocabularyInputError(
                "normalized_word must be a string."
            )

        if not normalized_word:
            return None

        return self._entries.get(normalized_word)

    def contains(
        self,
        word: str,
    ) -> bool:
        """
        Kiểm tra từ có trong vocabulary hay không.
        """

        return self.get(word) is not None

    def load_json(
        self,
        path: str | Path,
        *,
        replace: bool = False,
    ) -> None:
        """
        Tải từ điển từ file JSON.

        Định dạng được hỗ trợ:

        {
            "problem": "vấn đề",
            "machine": ["máy", "máy móc"],
            "run": ["chạy", "vận hành"]
        }
        """

        dictionary_path = Path(path).expanduser().resolve()

        if not dictionary_path.exists():
            raise DictionaryVocabularyLoadError(
                f"Dictionary file does not exist: "
                f"{dictionary_path}"
            )

        if not dictionary_path.is_file():
            raise DictionaryVocabularyLoadError(
                f"Dictionary path is not a file: "
                f"{dictionary_path}"
            )

        try:
            with dictionary_path.open(
                mode="r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

        except json.JSONDecodeError as exc:
            raise DictionaryVocabularyLoadError(
                f"Invalid JSON dictionary: "
                f"{dictionary_path}"
            ) from exc

        except OSError as exc:
            raise DictionaryVocabularyLoadError(
                f"Could not read dictionary: "
                f"{dictionary_path}"
            ) from exc

        if not isinstance(data, dict):
            raise DictionaryVocabularyLoadError(
                "Dictionary JSON root must be an object."
            )

        try:
            self.add_many(
                data,
                replace=replace,
            )

        except DictionaryVocabularyInputError as exc:
            raise DictionaryVocabularyLoadError(
                "Dictionary JSON contains invalid data."
            ) from exc

    def clear(self) -> None:
        """
        Xóa toàn bộ từ khỏi vocabulary.
        """

        self._entries.clear()

    def _validate_word(
        self,
        word: str,
    ) -> str:
        """
        Kiểm tra đầu vào phải chứa đúng một từ.
        """

        if not isinstance(word, str):
            raise DictionaryVocabularyInputError(
                "word must be a string, "
                f"received {type(word).__name__}."
            )

        stripped = word.strip()

        if not stripped:
            raise DictionaryVocabularyInputError(
                "word must not be empty."
            )

        tokens = self.tokenizer.tokenize(stripped)

        if len(tokens) != 1:
            raise DictionaryVocabularyInputError(
                "Word vocabulary only accepts one token. "
                "Multi-token expressions belong in PhraseTrie."
            )

        token = tokens[0]

        if not token.is_word:
            raise DictionaryVocabularyInputError(
                "Word vocabulary only accepts word tokens."
            )

        # Ngăn trường hợp input chứa thêm ký tự ngoài token,
        # ví dụ "word!" hoặc "hello world".
        if token.start != 0 or token.end != len(stripped):
            raise DictionaryVocabularyInputError(
                "word contains unsupported surrounding "
                "characters."
            )

        return stripped

    @staticmethod
    def _normalize_translations(
        translations: str | Sequence[str],
    ) -> tuple[str, ...]:
        """
        Chuyển một nghĩa hoặc danh sách nghĩa thành tuple.
        """

        if isinstance(translations, str):
            stripped = translations.strip()

            if not stripped:
                raise DictionaryVocabularyInputError(
                    "translation must not be empty."
                )

            return (stripped,)

        if not isinstance(translations, Sequence):
            raise DictionaryVocabularyInputError(
                "translations must be a string "
                "or a sequence of strings."
            )

        normalized: list[str] = []

        for translation in translations:
            if not isinstance(translation, str):
                raise DictionaryVocabularyInputError(
                    "Every translation must be a string."
                )

            stripped = translation.strip()

            if (
                stripped
                and stripped not in normalized
            ):
                normalized.append(stripped)

        if not normalized:
            raise DictionaryVocabularyInputError(
                "At least one translation is required."
            )

        return tuple(normalized)

    @staticmethod
    def _merge_translations(
        current: tuple[str, ...],
        new: tuple[str, ...],
    ) -> tuple[str, ...]:
        """
        Ghép các nghĩa và loại bỏ nghĩa trùng lặp.
        """

        merged = list(current)

        for translation in new:
            if translation not in merged:
                merged.append(translation)

        return tuple(merged)