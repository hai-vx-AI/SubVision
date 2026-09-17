"""
Literal English -> Vietnamese Translation
==========================================

PURPOSE
-------
Dịch literal từ tiếng Anh sang tiếng Việt bằng:

    PhraseTrie + word dictionary

Đây là public boundary của toàn bộ module `literal`.
Code bên ngoài chỉ cần import từ package này, không cần biết
`translation.py`, `phrase_trie.py` hoặc cấu trúc dictionary bên trong.


INPUT
-----
text: str

Chỉ nhận đúng MỘT đoạn text trong mỗi lần gọi.

Không nhận:
    - list / tuple / batch;
    - bbox;
    - OCR result;
    - confidence;
    - object từ module khác.


OUTPUT
------
LiteralTranslationResult

Fields:

    source_text: str
        Chính xác text đầu vào.

    translated_text: str
        Bản dịch literal tiếng Việt.


PUBLIC API
----------
Khởi tạo một lần:

    translator = LiteralTranslator()

Dịch và lấy đầy đủ result:

    result = translator.translate(text)

    result.source_text
    result.translated_text

Nếu chỉ cần chuỗi tiếng Việt:

    translated_text = translator.translate_text(text)

Có thể gọi trực tiếp:

    result = translator(text)


MAIN USAGE
----------
from backend.translation.dictionary.literal import LiteralTranslator

translator = LiteralTranslator()

result = translator.translate(
    "Machine learning is important."
)

print(result.translated_text)


BEHAVIOR
--------
- DictionaryTokenizer là normalization contract dùng chung.
- Canonical dictionary đã được chuẩn hóa ở build-time.
- Runtime không normalize lại dictionary resource.
- Input text được tokenize/normalize bằng DictionaryTokenizer.
- Phrase được ưu tiên trước word.
- Tại mỗi vị trí, longest phrase match thắng.
- Phrase đã match sẽ consume toàn bộ span của nó.
- Không có phrase thì fallback sang word dictionary.
- Unknown / number / email giữ nguyên.
- Giữ source order, punctuation và spacing.
- Không semantic guessing.
- Không deduplicate từ lặp.
- Kết quả deterministic với cùng input và cùng dictionary.


STATE
-----
LiteralTranslator giữ các resource đã load:

    - word dictionary;
    - PhraseTrie;
    - DictionaryTokenizer.

Nên tạo translator một lần và tái sử dụng.

Mỗi lần translate độc lập:
    - không translation history;
    - không context từ lần gọi trước;
    - không cross-call deduplication.


ERRORS
------
LiteralTranslationInputError
    Input không đúng contract.

LiteralDictionaryLoadError
    Canonical dictionary thiếu, hỏng hoặc sai schema.

LiteralTranslationError
    Base runtime error của module.


BOUNDARY
--------
Public:
    LiteralTranslator
    LiteralTranslationResult
    các exception public

Internal:
    PhraseTrie
    dictionary JSON
    token/match objects
    normalization implementation

Code bên ngoài không nên import hoặc phụ thuộc trực tiếp
vào các thành phần internal.
"""

from __future__ import annotations

from .translation import (
    LiteralDictionaryLoadError,
    LiteralTranslationError,
    LiteralTranslationInputError,
    LiteralTranslationResult,
    LiteralTranslator,
)


__all__ = [
    "LiteralTranslator",
    "LiteralTranslationResult",
    "LiteralTranslationError",
    "LiteralTranslationInputError",
    "LiteralDictionaryLoadError",
]