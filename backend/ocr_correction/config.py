from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OCRCorrectionConfig:
    """
    Cấu hình cho module sửa lỗi vật lý sau OCR.

    Module này chỉ xử lý lỗi non-word ở cấp ký tự, ví dụ:

        problcm  -> problem
        machinc  -> machine
        wlth     -> with

    Module không:
        - kiểm tra ngữ nghĩa của câu;
        - sửa từ hợp lệ nhưng sai ngữ cảnh;
        - dịch văn bản;
        - tự viết lại câu.
    """

    # ==========================================================
    # Frequency dictionary
    # ==========================================================

    # None:
    #     Dùng frequency_dictionary_en_82_765.txt được đóng gói
    #     sẵn trong symspellpy.
    #
    # Path:
    #     Dùng từ điển riêng theo định dạng:
    #
    #         word frequency
    #         the 23135851162
    #         problem 12345678
    #
    dictionary_path: Path | str | None = None

    # Vị trí cột chứa từ trong mỗi dòng từ điển.
    dictionary_term_index: int = 0

    # Vị trí cột chứa tần suất.
    dictionary_count_index: int = 1

    # Ký tự phân cách giữa từ và tần suất.
    dictionary_separator: str = " "

    dictionary_encoding: str = "utf-8"

    # Từ phải có tần suất ít nhất bằng giá trị này mới được xem
    # là một từ chính thức trong từ điển.
    count_threshold: int = 1

    # ==========================================================
    # SymSpell index
    # ==========================================================

    # Khoảng cách lớn nhất được dùng khi xây dựng chỉ mục.
    #
    # Giá trị 2 cho phép xử lý phần lớn lỗi OCR nhỏ:
    # - thiếu một hoặc hai ký tự;
    # - thừa ký tự;
    # - thay ký tự;
    # - đảo hai ký tự gần nhau.
    max_dictionary_edit_distance: int = 2

    # Độ dài prefix được SymSpell dùng để tạo chỉ mục.
    #
    # Phải lớn hơn max_dictionary_edit_distance.
    # Giá trị mặc định phổ biến của SymSpell là 7.
    prefix_length: int = 7

    # ==========================================================
    # Candidate lookup
    # ==========================================================

    # Khoảng cách tối đa khi tìm ứng viên cho một token.
    #
    # Không được lớn hơn max_dictionary_edit_distance.
    max_lookup_edit_distance: int = 2

    # Số ứng viên tối đa vocabulary trả về.
    max_suggestions: int = 5

    # Không trả token gốc như một ứng viên giả khi không tìm thấy
    # từ nào trong khoảng edit distance cho phép.
    include_unknown: bool = False

    # Chuyển kiểu viết hoa từ token OCR sang ứng viên.
    #
    # Ví dụ:
    #     Problcm -> Problem
    #     PROBLCM -> PROBLEM
    transfer_casing: bool = True

    # Loại ứng viên có tần suất thấp hơn giá trị này.
    min_candidate_frequency: int = 1

    # ==========================================================
    # Token constraints
    # ==========================================================

    # Corrector sau này có thể bỏ qua token quá ngắn vì sửa các từ
    # như "I", "a", "an" thường dễ gây false correction.
    min_token_length: int = 2

    # Giới hạn để từ chối dữ liệu bất thường.
    max_token_length: int = 64

    def __post_init__(self) -> None:
        """Kiểm tra cấu hình ngay khi khởi tạo."""

        if self.dictionary_path is not None:
            object.__setattr__(
                self,
                "dictionary_path",
                Path(self.dictionary_path),
            )

        if self.dictionary_term_index < 0:
            raise ValueError(
                "dictionary_term_index must not be negative."
            )

        if self.dictionary_count_index < 0:
            raise ValueError(
                "dictionary_count_index must not be negative."
            )

        if (
            self.dictionary_term_index
            == self.dictionary_count_index
        ):
            raise ValueError(
                "dictionary_term_index and "
                "dictionary_count_index must be different."
            )

        if not self.dictionary_separator:
            raise ValueError(
                "dictionary_separator must not be empty."
            )

        if not self.dictionary_encoding.strip():
            raise ValueError(
                "dictionary_encoding must not be empty."
            )

        if self.count_threshold < 0:
            raise ValueError(
                "count_threshold must not be negative."
            )

        if self.max_dictionary_edit_distance < 0:
            raise ValueError(
                "max_dictionary_edit_distance must not be negative."
            )

        if self.prefix_length < 1:
            raise ValueError(
                "prefix_length must be at least 1."
            )

        if (
            self.prefix_length
            <= self.max_dictionary_edit_distance
        ):
            raise ValueError(
                "prefix_length must be greater than "
                "max_dictionary_edit_distance."
            )

        if self.max_lookup_edit_distance < 0:
            raise ValueError(
                "max_lookup_edit_distance must not be negative."
            )

        if (
            self.max_lookup_edit_distance
            > self.max_dictionary_edit_distance
        ):
            raise ValueError(
                "max_lookup_edit_distance must not exceed "
                "max_dictionary_edit_distance."
            )

        if self.max_suggestions < 1:
            raise ValueError(
                "max_suggestions must be at least 1."
            )

        if self.min_candidate_frequency < 1:
            raise ValueError(
                "min_candidate_frequency must be at least 1."
            )

        if self.min_token_length < 1:
            raise ValueError(
                "min_token_length must be at least 1."
            )

        if self.max_token_length < self.min_token_length:
            raise ValueError(
                "max_token_length must be greater than or equal "
                "to min_token_length."
            )


DEFAULT_OCR_CORRECTION_CONFIG = OCRCorrectionConfig()