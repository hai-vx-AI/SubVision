from __future__ import annotations

import importlib.resources as resources
from dataclasses import dataclass
from pathlib import Path

from symspellpy import SymSpell, Verbosity

from .config import (
    DEFAULT_OCR_CORRECTION_CONFIG,
    OCRCorrectionConfig,
)


class VocabularyError(RuntimeError):
    """
    Lỗi cơ sở của vocabulary.
    """


class VocabularyLoadError(VocabularyError):
    """
    Không thể tải frequency dictionary.
    """


class VocabularyInputError(ValueError):
    """
    Token hoặc dữ liệu truyền vào vocabulary không hợp lệ.
    """


@dataclass(frozen=True, slots=True)
class VocabularyCandidate:
    """
    Một ứng viên sửa lỗi được trả về từ vocabulary.

    Attributes
    ----------
    term:
        Từ ứng viên.

    distance:
        Damerau-Levenshtein edit distance giữa token đầu vào
        và từ ứng viên.

    frequency:
        Tần suất của ứng viên trong frequency dictionary.
    """

    term: str
    distance: int
    frequency: int


class OCRVocabulary:
    """
    Quản lý từ điển tiếng Anh và chỉ mục SymSpell.

    Trách nhiệm:
        - tải frequency dictionary;
        - kiểm tra một token có tồn tại hay không;
        - lấy tần suất của token;
        - sinh ứng viên gần nhất bằng edit distance;
        - cho phép bổ sung thuật ngữ riêng.

    Không chịu trách nhiệm:
        - tách câu thành token;
        - quyết định token nào cần sửa;
        - tự thay token trong câu;
        - xử lý ngữ nghĩa;
        - dịch văn bản.
    """

    DEFAULT_DICTIONARY_RESOURCE = (
        "frequency_dictionary_en_82_765.txt"
    )

    def __init__(
        self,
        config: OCRCorrectionConfig | None = None,
    ) -> None:
        self.config = (
            config or DEFAULT_OCR_CORRECTION_CONFIG
        )

        self._sym_spell = SymSpell(
            max_dictionary_edit_distance=(
                self.config.max_dictionary_edit_distance
            ),
            prefix_length=self.config.prefix_length,
            count_threshold=self.config.count_threshold,
        )

        self._dictionary_source: str = ""
        self._load_dictionary()

    # ==========================================================
    # Public properties
    # ==========================================================

    @property
    def size(self) -> int:
        """
        Số từ hợp lệ hiện có trong vocabulary.
        """

        return self._sym_spell.entry_count

    @property
    def dictionary_source(self) -> str:
        """
        Nguồn từ điển đang được sử dụng.
        """

        return self._dictionary_source

    # ==========================================================
    # Public vocabulary API
    # ==========================================================

    def contains(self, token: str) -> bool:
        """
        Kiểm tra token có tồn tại trong từ điển hay không.

        Việc kiểm tra không phân biệt chữ hoa/chữ thường.

        Examples
        --------
        vocabulary.contains("problem")  -> True
        vocabulary.contains("Problem")  -> True
        vocabulary.contains("problcm")  -> False
        """

        normalized = self._normalize_token(token)

        return normalized in self._sym_spell.words

    def frequency(self, token: str) -> int:
        """
        Trả về tần suất của token trong từ điển.

        Trả về 0 nếu token không tồn tại.
        """

        normalized = self._normalize_token(token)

        return int(
            self._sym_spell.words.get(normalized, 0)
        )

    def suggest(
        self,
        token: str,
        *,
        max_edit_distance: int | None = None,
        limit: int | None = None,
    ) -> list[VocabularyCandidate]:
        """
        Sinh danh sách ứng viên gần token đầu vào.

        Parameters
        ----------
        token:
            Một token đơn đã được tách khỏi câu.

        max_edit_distance:
            Khoảng cách tối đa cho lần tìm kiếm này.
            Nếu None, sử dụng config.max_lookup_edit_distance.

        limit:
            Số ứng viên tối đa được trả về.
            Nếu None, sử dụng config.max_suggestions.

        Returns
        -------
        list[VocabularyCandidate]
            Ứng viên được sắp xếp theo:
                1. edit distance tăng dần;
                2. frequency giảm dần;
                3. tên từ theo alphabet.
        """

        original_token = self._validate_token(token)

        lookup_distance = (
            self.config.max_lookup_edit_distance
            if max_edit_distance is None
            else max_edit_distance
        )

        suggestion_limit = (
            self.config.max_suggestions
            if limit is None
            else limit
        )

        self._validate_lookup_arguments(
            max_edit_distance=lookup_distance,
            limit=suggestion_limit,
        )

        suggestions = self._sym_spell.lookup(
            phrase=original_token,
            verbosity=Verbosity.ALL,
            max_edit_distance=lookup_distance,
            include_unknown=self.config.include_unknown,
            transfer_casing=self.config.transfer_casing,
        )

        candidates = [
            VocabularyCandidate(
                term=suggestion.term,
                distance=int(suggestion.distance),
                frequency=int(suggestion.count),
            )
            for suggestion in suggestions
            if suggestion.count
            >= self.config.min_candidate_frequency
        ]

        candidates.sort(
            key=lambda candidate: (
                candidate.distance,
                -candidate.frequency,
                candidate.term.casefold(),
            )
        )

        return candidates[:suggestion_limit]

    def add_word(
        self,
        word: str,
        *,
        frequency: int = 1,
    ) -> None:
        """
        Thêm một từ hoặc thuật ngữ riêng vào vocabulary.

        Có thể dùng cho:
            - tên nhân vật;
            - tên sản phẩm;
            - thuật ngữ phim;
            - từ chuyên ngành.

        Example
        -------
        vocabulary.add_word(
            "SubVision",
            frequency=1_000_000,
        )
        """

        normalized = self._normalize_token(word)

        if frequency < 1:
            raise VocabularyInputError(
                "frequency must be at least 1."
            )

        effective_frequency = max(
            frequency,
            self.config.count_threshold,
        )

        self._sym_spell.create_dictionary_entry(
            key=normalized,
            count=effective_frequency,
        )

        if not self.contains(normalized):
            raise VocabularyError(
                f"Could not add word to vocabulary: {word!r}."
            )

    def add_words(
        self,
        words: dict[str, int],
    ) -> None:
        """
        Thêm nhiều từ cùng tần suất.

        Example
        -------
        vocabulary.add_words(
            {
                "SubVision": 1_000_000,
                "OpenAI": 1_000_000,
                "PaddleOCR": 1_000_000,
            }
        )
        """

        if not isinstance(words, dict):
            raise VocabularyInputError(
                "words must be a dictionary of "
                "{word: frequency}."
            )

        for word, frequency in words.items():
            self.add_word(
                word,
                frequency=frequency,
            )

    # ==========================================================
    # Dictionary loading
    # ==========================================================

    def _load_dictionary(self) -> None:
        """
        Tải từ điển tùy chỉnh hoặc từ điển mặc định
        được đóng gói trong symspellpy.
        """

        if self.config.dictionary_path is not None:
            self._load_custom_dictionary(
                self.config.dictionary_path
            )
        else:
            self._load_default_dictionary()

        if self._sym_spell.entry_count == 0:
            raise VocabularyLoadError(
                "The vocabulary was loaded but contains no words."
            )

    def _load_custom_dictionary(
        self,
        dictionary_path: Path,
    ) -> None:
        """
        Tải frequency dictionary do dự án cung cấp.
        """

        path = dictionary_path.expanduser().resolve()

        if not path.exists():
            raise VocabularyLoadError(
                f"Dictionary file does not exist: {path}"
            )

        if not path.is_file():
            raise VocabularyLoadError(
                f"Dictionary path is not a file: {path}"
            )

        loaded = self._sym_spell.load_dictionary(
            corpus=path,
            term_index=self.config.dictionary_term_index,
            count_index=self.config.dictionary_count_index,
            separator=self.config.dictionary_separator,
            encoding=self.config.dictionary_encoding,
        )

        if not loaded:
            raise VocabularyLoadError(
                f"Could not load dictionary: {path}"
            )

        self._dictionary_source = str(path)

    def _load_default_dictionary(self) -> None:
        """
        Tải frequency dictionary tiếng Anh mặc định
        đi kèm package symspellpy.
        """

        try:
            resource = resources.files(
                "symspellpy"
            ).joinpath(
                self.DEFAULT_DICTIONARY_RESOURCE
            )

            if not resource.is_file():
                raise VocabularyLoadError(
                    "Bundled SymSpell dictionary was not found: "
                    f"{self.DEFAULT_DICTIONARY_RESOURCE}"
                )

            # as_file() hoạt động cả khi package được cài dưới dạng
            # thư mục thông thường hoặc resource đóng gói.
            with resources.as_file(resource) as path:
                loaded = self._sym_spell.load_dictionary(
                    corpus=path,
                    term_index=(
                        self.config.dictionary_term_index
                    ),
                    count_index=(
                        self.config.dictionary_count_index
                    ),
                    separator=(
                        self.config.dictionary_separator
                    ),
                    encoding=(
                        self.config.dictionary_encoding
                    ),
                )

            if not loaded:
                raise VocabularyLoadError(
                    "Could not load the bundled SymSpell "
                    "frequency dictionary."
                )

            self._dictionary_source = (
                "symspellpy:"
                f"{self.DEFAULT_DICTIONARY_RESOURCE}"
            )

        except VocabularyLoadError:
            raise

        except Exception as exc:
            raise VocabularyLoadError(
                "Unexpected error while loading the bundled "
                "SymSpell frequency dictionary."
            ) from exc

    # ==========================================================
    # Validation
    # ==========================================================

    def _normalize_token(
        self,
        token: str,
    ) -> str:
        """
        Chuẩn hóa token để kiểm tra trực tiếp trong dictionary.

        Không xóa dấu câu và không tự sửa nội dung token.
        Corrector sau này phải tách token đúng trước khi gọi
        vocabulary.
        """

        validated = self._validate_token(token)
        return validated.casefold()

    def _validate_token(
        self,
        token: str,
    ) -> str:
        """
        Kiểm tra một token đơn trước khi đưa vào SymSpell.
        """

        if not isinstance(token, str):
            raise VocabularyInputError(
                "token must be a string, "
                f"received {type(token).__name__}."
            )

        stripped = token.strip()

        if not stripped:
            raise VocabularyInputError(
                "token must not be empty."
            )

        if any(character.isspace() for character in stripped):
            raise VocabularyInputError(
                "Vocabulary only accepts one token at a time."
            )

        if len(stripped) > self.config.max_token_length:
            raise VocabularyInputError(
                "token length exceeds the configured maximum of "
                f"{self.config.max_token_length} characters."
            )

        return stripped

    def _validate_lookup_arguments(
        self,
        *,
        max_edit_distance: int,
        limit: int,
    ) -> None:
        """
        Kiểm tra tham số của một lần tìm ứng viên.
        """

        if max_edit_distance < 0:
            raise VocabularyInputError(
                "max_edit_distance must not be negative."
            )

        if (
            max_edit_distance
            > self.config.max_dictionary_edit_distance
        ):
            raise VocabularyInputError(
                "max_edit_distance must not exceed "
                "config.max_dictionary_edit_distance."
            )

        if limit < 1:
            raise VocabularyInputError(
                "limit must be at least 1."
            )