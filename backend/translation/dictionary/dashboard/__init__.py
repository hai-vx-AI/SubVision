"""
Dashboard Dictionary
====================

PURPOSE
-------
Nhận toàn bộ text tiếng Anh đã qua OCR Correction và trả về danh sách
từ/cụm từ để Dashboard hiển thị như một từ điển.

Runtime public flow:

    Sequence[str] corrected texts
              ↓
       DashboardExtractor
              ↓
    tuple[DashboardEntry, ...]

Module này KHÔNG nhận image, bbox, confidence, OCR Result hoặc TextGroup.
Module không dịch cả câu.


INPUT
-----
DashboardExtractor.extract(texts)

    texts: Sequence[str]

Mỗi phần tử là một corrected_text độc lập.

Ví dụ:

    [
        "Machine learning is useful.",
        "The machine learns from data.",
    ]

Quy tắc:
- Không truyền một str đơn lẻ.
- Phrase không match xuyên ranh giới giữa hai phần tử.
- Empty sequence hợp lệ và trả về ().


OUTPUT
------
tuple[DashboardEntry, ...]

DashboardEntry:

    term: str
        Headword/cụm từ tiếng Anh được tìm thấy.

    meanings: tuple[str, ...]
        Các nghĩa có trong Dashboard dictionary.
        Entry được trả về luôn có ít nhất một nghĩa.

    ipas: tuple[str, ...]
        Các IPA có trong dictionary.
        Có thể là tuple rỗng.

    entry_type: Literal["word", "phrase"]
        Phân biệt từ đơn và cụm từ.


BEHAVIOR
--------
Với từng corrected_text:

    DictionaryTokenizer
            ↓
    exact surface lookup
            ↓
    longest phrase first
            ↓
    word fallback
            ↓
    lemma fallback nếu exact word không tồn tại

Sau khi xử lý toàn bộ texts:

    unknown bị bỏ
        ↓
    deduplicate
        ↓
    sort A -> Z theo term hiển thị
        ↓
    tuple[DashboardEntry, ...]


USAGE
-----
from backend.translation.dictionary.dashboard import DashboardExtractor

dashboard = DashboardExtractor()

entries = dashboard.extract(
    [
        "Machine learning is useful.",
        "The machine learns from data.",
    ]
)

for entry in entries:
    print(entry.term)
    print(entry.entry_type)
    print(entry.ipas)
    print(entry.meanings)


DICTIONARY
----------
Mặc định DashboardExtractor đọc:

    dashboard/data/en_vi_dashboard.json

JSON này được tạo bởi create_json.py.

create_json.py là build-time tool, không phải runtime public API.
phrase_trie.py và DictionaryTokenizer là implementation detail.


STATE
-----
Dictionary, tokenizer và phrase trie được giữ để tái sử dụng trong cùng
DashboardExtractor.

Kết quả của extract() không được giữ giữa các lần gọi:
- không có history;
- không có cross-call dedupe;
- mỗi extract() là một snapshot độc lập.


PUBLIC API
----------
Chỉ cần dùng:

    DashboardExtractor
    DashboardEntry

Các error type được export để caller có thể xử lý lỗi input/resource nếu cần.
"""

from __future__ import annotations

from .processor import (
    DashboardDictionaryLoadError,
    DashboardEntry,
    DashboardError,
    DashboardExtractor,
    DashboardInputError,
)

__all__ = [
    "DashboardExtractor",
    "DashboardEntry",
    "DashboardError",
    "DashboardInputError",
    "DashboardDictionaryLoadError",
]
