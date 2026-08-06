from __future__ import annotations

import re
from dataclasses import dataclass

from .config import (
    DEFAULT_OCR_CORRECTION_CONFIG,
    OCRCorrectionConfig,
)
from .vocabulary import (
    OCRVocabulary,
    VocabularyCandidate,
    VocabularyInputError,
)


class OCRCorrectionError(RuntimeError):
    """
    Lỗi cơ sở của module OCR correction.
    """


class OCRCorrectionInputError(ValueError):
    """
    Dữ liệu truyền vào OCRCorrector không hợp lệ.
    """


@dataclass(frozen=True, slots=True)
class TokenCorrection:
    """
    Kết quả xử lý một token.

    Attributes
    ----------
    original:
        Token ban đầu từ OCR.

    corrected:
        Token sau khi sửa. Nếu không sửa, giá trị này giống original.

    start:
        Vị trí bắt đầu của token trong chuỗi gốc.

    end:
        Vị trí kết thúc của token trong chuỗi gốc.

    changed:
        Token có được thay đổi hay không.

    distance:
        Edit distance giữa token gốc và ứng viên được chọn.
        None nếu token không được sửa.

    frequency:
        Tần suất của ứng viên được chọn trong từ điển.
        None nếu token không được sửa.

    reason:
        Lý do sửa hoặc giữ nguyên token.
    """

    original: str
    corrected: str

    start: int
    end: int

    changed: bool

    distance: int | None = None
    frequency: int | None = None

    reason: str = ""


@dataclass(frozen=True, slots=True)
class OCRCorrectionResult:
    """
    Kết quả sửa lỗi cho toàn bộ chuỗi OCR.
    """

    original_text: str
    corrected_text: str
    tokens: tuple[TokenCorrection, ...]

    @property
    def changed(self) -> bool:
        """
        Chuỗi có ít nhất một token được sửa hay không.
        """

        return any(token.changed for token in self.tokens)

    @property
    def corrections(self) -> tuple[TokenCorrection, ...]:
        """
        Chỉ trả về những token thực sự được sửa.
        """

        return tuple(
            token
            for token in self.tokens
            if token.changed
        )


class OCRCorrector:
    """
    Sửa lỗi vật lý/non-word trong kết quả OCR tiếng Anh.

    Pipeline
    --------
    Text OCR
        → tìm token
        → bỏ qua token đặc biệt
        → kiểm tra từ điển
        → tìm ứng viên bằng edit distance
        → chọn ứng viên gần nhất
        → dùng frequency để phân hạng khi cùng distance
        → ghép lại câu

    Module này không:
        - sửa lỗi ngữ nghĩa;
        - kiểm tra ngữ pháp;
        - dịch văn bản;
        - tự viết lại câu;
        - xử lý confidence của OCR.
    """

    # Token tiếng Anh, cho phép chứa apostrophe hoặc dấu gạch nối.
    #
    # Ví dụ được nhận thành một token:
    #   don't
    #   John's
    #   state-of-the-art
    TOKEN_PATTERN = re.compile(
        r"[A-Za-z]+(?:['’\-][A-Za-z]+)*"
    )

    # Các pattern đặc biệt được giữ nguyên.
    URL_PATTERN = re.compile(
        r"^(?:https?://|www\.)",
        re.IGNORECASE,
    )

    EMAIL_PATTERN = re.compile(
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )

    # Với token ngắn, edit distance 2 quá rộng.
    # Ví dụ "fo" có thể gần với "to", "of", "go", "do", "for".
    SHORT_TOKEN_MAX_LENGTH = 4
    SHORT_TOKEN_MAX_DISTANCE = 1

    def __init__(
        self,
        config: OCRCorrectionConfig | None = None,
        vocabulary: OCRVocabulary | None = None,
    ) -> None:
        self.config = (
            config or DEFAULT_OCR_CORRECTION_CONFIG
        )

        self.vocabulary = (
            vocabulary or OCRVocabulary(self.config)
        )

    def correct(
        self,
        text: str,
    ) -> OCRCorrectionResult:
        """
        Sửa các lỗi vật lý rõ ràng trong một chuỗi OCR.

        Parameters
        ----------
        text:
            Chuỗi tiếng Anh thu được từ OCR.

        Returns
        -------
        OCRCorrectionResult
            Chuỗi đã sửa và thông tin từng token.
        """

        validated_text = self._validate_text(text)

        matches = list(
            self.TOKEN_PATTERN.finditer(validated_text)
        )

        if not matches:
            return OCRCorrectionResult(
                original_text=validated_text,
                corrected_text=validated_text,
                tokens=(),
            )

        corrected_parts: list[str] = []
        token_results: list[TokenCorrection] = []

        cursor = 0

        for match in matches:
            start, end = match.span()
            token = match.group(0)

            # Giữ nguyên phần nằm giữa hai token:
            # khoảng trắng, dấu câu, xuống dòng...
            corrected_parts.append(
                validated_text[cursor:start]
            )

            correction = self.correct_token(
                token=token,
                text=validated_text,
                start=start,
                end=end,
            )

            corrected_parts.append(
                correction.corrected
            )

            token_results.append(correction)
            cursor = end

        # Giữ phần còn lại sau token cuối.
        corrected_parts.append(
            validated_text[cursor:]
        )

        return OCRCorrectionResult(
            original_text=validated_text,
            corrected_text="".join(corrected_parts),
            tokens=tuple(token_results),
        )

    def correct_text(
        self,
        text: str,
    ) -> str:
        """
        API rút gọn: chỉ trả về chuỗi đã sửa.
        """

        return self.correct(text).corrected_text

    def correct_token(
        self,
        token: str,
        *,
        text: str = "",
        start: int = 0,
        end: int | None = None,
    ) -> TokenCorrection:
        """
        Kiểm tra và sửa một token riêng lẻ.

        Hàm này có thể được dùng trực tiếp cho chế độ dịch từ điển.
        """

        validated_token = self._validate_token(token)

        token_end = (
            start + len(validated_token)
            if end is None
            else end
        )

        skip_reason = self._get_skip_reason(
            token=validated_token,
            text=text,
            start=start,
        )

        if skip_reason is not None:
            return self._unchanged(
                token=validated_token,
                start=start,
                end=token_end,
                reason=skip_reason,
            )

        # Token đã tồn tại trong từ điển:
        # không được sửa.
        if self.vocabulary.contains(validated_token):
            return self._unchanged(
                token=validated_token,
                start=start,
                end=token_end,
                reason="token_exists_in_dictionary",
            )

        lookup_distance = self._get_lookup_distance(
            validated_token
        )

        candidates = self.vocabulary.suggest(
            validated_token,
            max_edit_distance=lookup_distance,
            limit=self.config.max_suggestions,
        )

        if not candidates:
            return self._unchanged(
                token=validated_token,
                start=start,
                end=token_end,
                reason="no_candidate_found",
            )

        best_candidate = self._select_candidate(
            token=validated_token,
            candidates=candidates,
        )

        if best_candidate is None:
            return self._unchanged(
                token=validated_token,
                start=start,
                end=token_end,
                reason="candidate_is_ambiguous",
            )

        if (
            best_candidate.term.casefold()
            == validated_token.casefold()
        ):
            return self._unchanged(
                token=validated_token,
                start=start,
                end=token_end,
                reason="candidate_matches_original",
            )

        return TokenCorrection(
            original=validated_token,
            corrected=best_candidate.term,
            start=start,
            end=token_end,
            changed=True,
            distance=best_candidate.distance,
            frequency=best_candidate.frequency,
            reason="non_word_corrected",
        )

    def __call__(
        self,
        text: str,
    ) -> OCRCorrectionResult:
        """
        Cho phép gọi object như một function.

        Example
        -------
        corrector = OCRCorrector()
        result = corrector("I havc a problcm.")
        """

        return self.correct(text)

    # ==========================================================
    # Candidate selection
    # ==========================================================

    def _select_candidate(
        self,
        *,
        token: str,
        candidates: list[VocabularyCandidate],
    ) -> VocabularyCandidate | None:
        """
        Chọn ứng viên cuối cùng.

        Quy tắc:
            1. Edit distance nhỏ nhất.
            2. Trong nhóm cùng distance, frequency cao nhất.
            3. Với token rất ngắn, không sửa nếu hai ứng viên
               đứng đầu quá gần nhau về tần suất.
        """

        if not candidates:
            return None

        minimum_distance = min(
            candidate.distance
            for candidate in candidates
        )

        closest_candidates = [
            candidate
            for candidate in candidates
            if candidate.distance == minimum_distance
        ]

        closest_candidates.sort(
            key=lambda candidate: (
                -candidate.frequency,
                candidate.term.casefold(),
            )
        )

        best = closest_candidates[0]

        # Token dài thường cung cấp đủ thông tin vật lý.
        if len(token) > self.SHORT_TOKEN_MAX_LENGTH:
            return best

        # Nếu chỉ có một ứng viên gần nhất thì có thể chọn.
        if len(closest_candidates) == 1:
            return best

        second = closest_candidates[1]

        # Token ngắn rất dễ mơ hồ.
        # Chỉ sửa khi ứng viên đầu có tần suất rõ ràng hơn.
        if best.frequency >= second.frequency * 2:
            return best

        return None

    def _get_lookup_distance(
        self,
        token: str,
    ) -> int:
        """
        Chọn edit distance dựa trên độ dài token.

        Token ngắn:
            tối đa 1 phép sửa.

        Token dài:
            dùng max_lookup_edit_distance trong config.
        """

        if len(token) <= self.SHORT_TOKEN_MAX_LENGTH:
            return min(
                self.SHORT_TOKEN_MAX_DISTANCE,
                self.config.max_lookup_edit_distance,
            )

        return self.config.max_lookup_edit_distance

    # ==========================================================
    # Skip rules
    # ==========================================================

    def _get_skip_reason(
        self,
        *,
        token: str,
        text: str,
        start: int,
    ) -> str | None:
        """
        Xác định token có cần bỏ qua hay không.
        """

        if len(token) < self.config.min_token_length:
            return "token_too_short"

        if len(token) > self.config.max_token_length:
            return "token_too_long"

        # Contraction và possessive như:
        # don't, isn't, John's
        #
        # Từ điển SymSpell có thể không bao phủ đầy đủ,
        # nên giữ nguyên để tránh sửa sai.
        if "'" in token or "’" in token:
            return "token_contains_apostrophe"

        # Từ ghép như state-of-the-art được giữ nguyên.
        if "-" in token:
            return "token_contains_hyphen"

        if self.URL_PATTERN.match(token):
            return "token_is_url"

        if self.EMAIL_PATTERN.match(token):
            return "token_is_email"

        # Từ viết tắt như AI, CPU, OCR, USA.
        if len(token) >= 2 and token.isupper():
            return "token_is_acronym"

        # CamelCase hoặc mixed case:
        # OpenAI, PaddleOCR, YouTube.
        if self._is_mixed_case(token):
            return "token_has_mixed_case"

        # Từ viết hoa giữa câu có khả năng là tên riêng:
        # Netflix, Gandalf, London.
        if (
            token.istitle()
            and not self._is_sentence_start(
                text=text,
                token_start=start,
            )
        ):
            return "token_may_be_proper_name"

        return None

    @staticmethod
    def _is_mixed_case(token: str) -> bool:
        """
        Phát hiện CamelCase hoặc chữ hoa/thường trộn bất thường.

        Examples
        --------
        OpenAI    -> True
        PaddleOCR -> True
        Problem   -> False
        problem   -> False
        PROBLEM   -> False
        """

        if token.islower():
            return False

        if token.isupper():
            return False

        if token.istitle():
            return False

        return any(char.isupper() for char in token) and any(
            char.islower()
            for char in token
        )

    @staticmethod
    def _is_sentence_start(
        *,
        text: str,
        token_start: int,
    ) -> bool:
        """
        Kiểm tra token có nằm ở đầu câu hay không.
        """

        if not text:
            return token_start == 0

        prefix = text[:token_start].rstrip()

        if not prefix:
            return True

        return prefix[-1] in ".!?\n"

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_text(text: str) -> str:
        """
        Kiểm tra chuỗi OCR đầu vào.
        """

        if not isinstance(text, str):
            raise OCRCorrectionInputError(
                "text must be a string, "
                f"received {type(text).__name__}."
            )

        if not text:
            return ""

        if "\x00" in text:
            raise OCRCorrectionInputError(
                "text must not contain null characters."
            )

        return text

    def _validate_token(
        self,
        token: str,
    ) -> str:
        """
        Kiểm tra token đầu vào.
        """

        if not isinstance(token, str):
            raise OCRCorrectionInputError(
                "token must be a string, "
                f"received {type(token).__name__}."
            )

        stripped = token.strip()

        if not stripped:
            raise OCRCorrectionInputError(
                "token must not be empty."
            )

        if any(char.isspace() for char in stripped):
            raise OCRCorrectionInputError(
                "correct_token() only accepts one token."
            )

        if len(stripped) > self.config.max_token_length:
            raise OCRCorrectionInputError(
                "token exceeds the configured maximum length of "
                f"{self.config.max_token_length} characters."
            )

        return stripped

    # ==========================================================
    # Result helpers
    # ==========================================================

    @staticmethod
    def _unchanged(
        *,
        token: str,
        start: int,
        end: int,
        reason: str,
    ) -> TokenCorrection:
        """
        Tạo kết quả cho token được giữ nguyên.
        """

        return TokenCorrection(
            original=token,
            corrected=token,
            start=start,
            end=end,
            changed=False,
            distance=None,
            frequency=None,
            reason=reason,
        )