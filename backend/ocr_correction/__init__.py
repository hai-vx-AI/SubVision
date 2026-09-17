"""
OCR CORRECTION
==============

Sửa lỗi vật lý / non-word trong text tiếng Anh sau OCR.

Ví dụ:

    problcm  -> problem
    machinc  -> machine
    wlth     -> with


Public pipeline:

    OCR text: str
        ↓
    OCRCorrector
        ↓
    OCRCorrectionResult
        ├── corrected_text
        └── TokenCorrection[]


============================================================
PURPOSE
============================================================

Module chịu trách nhiệm:

    - nhận text OCR tiếng Anh;
    - tìm các token tiếng Anh;
    - kiểm tra token trong frequency dictionary;
    - tìm candidate bằng edit distance;
    - xếp hạng candidate bằng distance + frequency;
    - sửa các lỗi non-word rõ ràng;
    - giữ nguyên formatting ngoài token;
    - trả thông tin chi tiết về từng token.


Module KHÔNG:

    - sửa grammar;
    - sửa semantic;
    - sửa một từ hợp lệ chỉ vì sai ngữ cảnh;
    - viết lại câu;
    - dịch;
    - xử lý OCR confidence;
    - xử lý bbox/layout.


============================================================
PUBLIC INPUT
============================================================

API chính:

    OCRCorrector.correct(text)


text
----

Type:

    str

Ý nghĩa:

    Text tiếng Anh đã được OCR tạo ra.

Ví dụ:

    "I havc a problcm with this machinc."


Cho phép:

    - khoảng trắng;
    - punctuation;
    - nhiều câu;
    - xuống dòng;
    - chuỗi rỗng.


Không cho phép:

    null character:

        "\\x00"


============================================================
PUBLIC OUTPUT
============================================================

corrector.correct(text)

trả về:

    OCRCorrectionResult


OCRCorrectionResult
-------------------

Fields:

    original_text: str

        Chính text input đã nhận.


    corrected_text: str

        Text sau correction.


    tokens: tuple[TokenCorrection, ...]

        Kết quả xử lý từng token được tokenizer nội bộ tìm thấy.


Properties:

    changed: bool

        True nếu có ít nhất một token thực sự bị sửa.


    corrections: tuple[TokenCorrection, ...]

        Chỉ chứa các token có:

            changed == True


============================================================
TOKEN CORRECTION
============================================================

TokenCorrection có cấu trúc:

    original: str

        Token OCR ban đầu.


    corrected: str

        Token sau correction.

        Nếu không sửa:

            corrected == original


    start: int

        Character index bắt đầu trong original text.


    end: int

        Character index kết thúc.

        Span sử dụng:

            [start, end)


    changed: bool

        Token có thực sự thay đổi hay không.


    distance: int | None

        Damerau-Levenshtein edit distance
        của candidate được chọn.

        None nếu không sửa.


    frequency: int | None

        Frequency của candidate trong dictionary.

        None nếu không sửa.


    reason: str

        Lý do sửa hoặc giữ nguyên.

Ví dụ reason hiện có:

    "non_word_corrected"

    "token_exists_in_dictionary"

    "no_candidate_found"

    "candidate_is_ambiguous"

    "candidate_matches_original"

    "token_too_short"

    "token_too_long"

    "token_contains_apostrophe"

    "token_contains_hyphen"

    "token_is_url"

    "token_is_email"

    "token_is_acronym"

    "token_has_mixed_case"

    "token_may_be_proper_name"


============================================================
SIMPLE OUTPUT
============================================================

Nếu downstream chỉ cần corrected string:

    corrected_text = corrector.correct_text(
        text
    )

Input:

    str

Output:

    str


============================================================
SINGLE TOKEN API
============================================================

Có thể xử lý một token riêng:

    correction = corrector.correct_token(
        "problcm"
    )


Input chính:

    token: str


Optional metadata:

    text: str = ""

    start: int = 0

    end: int | None = None


Output:

    TokenCorrection


Token phải:

    - là str;
    - không rỗng;
    - không chứa whitespace;
    - không dài quá max_token_length.


============================================================
USAGE
============================================================

Cách đơn giản nhất:

    from backend.ocr_correction import (
        OCRCorrector,
    )

    corrector = OCRCorrector()

    corrected_text = corrector.correct_text(
        "I havc a problcm."
    )


Nếu cần metadata:

    result = corrector.correct(
        "I havc a problcm."
    )

    print(result.original_text)
    print(result.corrected_text)
    print(result.changed)

    for correction in result.corrections:

        print(
            correction.original,
            correction.corrected,
            correction.distance,
            correction.frequency,
            correction.reason,
        )


Có thể gọi object trực tiếp:

    result = corrector(
        "I havc a problcm."
    )


============================================================
TOKENIZATION / FORMATTING
============================================================

Corrector tìm English word token bằng regex nội bộ.

Token có thể chứa:

    apostrophe:

        don't
        John's

    hyphen:

        state-of-the-art


Corrector chỉ thay phần token.

Các phần nằm giữa token được giữ nguyên:

    - whitespace;
    - punctuation;
    - newline;
    - ký tự khác.


Ví dụ về nguyên tắc:

    original:

        "Hello,  problcm!\nTest"

    correction chỉ thay:

        problcm

    còn:

        ",  "
        "!"
        "\\n"

    được giữ nguyên.


============================================================
CORRECTION POLICY
============================================================

Một token trước tiên được kiểm tra xem có nên bỏ qua không.

Sau đó:

    token
      ↓
    vocabulary.contains()
      ↓
    nếu đã tồn tại:
        giữ nguyên

    nếu chưa tồn tại:
      ↓
    vocabulary.suggest()
      ↓
    VocabularyCandidate[]
      ↓
    distance nhỏ nhất
      ↓
    frequency cao nhất


Token dài:

    length > 4

có thể sử dụng:

    config.max_lookup_edit_distance


Token ngắn:

    length <= 4

bị giới hạn:

    max edit distance = 1


Nếu nhiều candidate của token ngắn có cùng edit distance,
candidate tốt nhất chỉ được chọn khi frequency của nó ít nhất:

    2 × frequency của candidate thứ hai

Nếu không:

    giữ nguyên token.


============================================================
SKIP POLICY
============================================================

Corrector cố tình tránh sửa một số token để giảm false correction:

    token quá ngắn

    token quá dài

    apostrophe:
        don't

    hyphen:
        state-of-the-art

    acronym:
        AI
        CPU
        OCR

    mixed case:
        OpenAI
        PaddleOCR
        YouTube

    title-case nằm giữa câu:
        London
        Netflix

Token đã tồn tại trong dictionary cũng luôn được giữ nguyên.


============================================================
VOCABULARY
============================================================

OCRCorrector giữ một:

    OCRVocabulary

Vocabulary sử dụng:

    SymSpell
        +
    frequency dictionary


Mặc định:

    frequency_dictionary_en_82_765.txt

được lấy từ package:

    symspellpy


OCRVocabulary được khởi tạo một lần khi tạo:

    corrector = OCRCorrector()


OCRCorrector giữ vocabulary tại:

    corrector.vocabulary


============================================================
VOCABULARY PUBLIC API
============================================================

Kiểm tra token:

    vocabulary.contains(
        "problem"
    )

Input:

    str

Output:

    bool


Lấy frequency:

    vocabulary.frequency(
        "problem"
    )

Input:

    str

Output:

    int

Không tồn tại:

    0


Tìm candidates:

    candidates = vocabulary.suggest(
        "problcm"
    )

Output:

    list[VocabularyCandidate]


============================================================
VOCABULARY CANDIDATE
============================================================

VocabularyCandidate:

    term: str

        Candidate word.


    distance: int

        Damerau-Levenshtein edit distance.


    frequency: int

        Frequency trong dictionary.


Candidate list được sort theo:

    1. distance tăng dần
    2. frequency giảm dần
    3. term theo alphabet


============================================================
CUSTOM VOCABULARY
============================================================

Có thể bổ sung từ runtime:

    corrector.vocabulary.add_word(
        "SubVision",
        frequency=1_000_000,
    )


Hoặc nhiều từ:

    corrector.vocabulary.add_words(
        {
            "SubVision": 1_000_000,
            "OpenAI": 1_000_000,
            "PaddleOCR": 1_000_000,
        }
    )


Input add_word:

    word: str

    frequency: int
        default = 1
        minimum = 1


Input add_words:

    dict[str, int]


QUAN TRỌNG:

Vocabulary là STATEFUL.

Các custom words được thêm vào object hiện tại
sẽ ảnh hưởng các lần correction tiếp theo sử dụng
cùng OCRVocabulary / OCRCorrector instance.


============================================================
STATE / LIFETIME
============================================================

OCRCorrector giữ:

    config: OCRCorrectionConfig

    vocabulary: OCRVocabulary


OCRVocabulary giữ:

    SymSpell index
    frequency dictionary
    custom words được thêm runtime


Nên:

    corrector = OCRCorrector()

được tạo một lần và tái sử dụng:

    corrector(text_1)
    corrector(text_2)
    corrector(text_3)


Không nên load lại vocabulary cho mỗi text nếu không cần.


Corrector KHÔNG giữ:

    - text trước;
    - correction result trước;
    - session history.


Vì vậy:

    correction result = stateless

nhưng:

    vocabulary/model object = stateful


============================================================
CONFIG
============================================================

Config type:

    OCRCorrectionConfig


------------------------------------------------------------
DICTIONARY
------------------------------------------------------------

dictionary_path:

    Path | str | None

Default:

    None

None nghĩa là dùng frequency dictionary của symspellpy.


dictionary_term_index: int
    default = 0


dictionary_count_index: int
    default = 1


dictionary_separator: str
    default = " "


dictionary_encoding: str
    default = "utf-8"


count_threshold: int
    default = 1


============================================================
SYMSPELL INDEX
============================================================

max_dictionary_edit_distance: int

    default = 2


prefix_length: int

    default = 7

    phải lớn hơn:
        max_dictionary_edit_distance


============================================================
CANDIDATE LOOKUP
============================================================

max_lookup_edit_distance: int

    default = 2

    không được lớn hơn:
        max_dictionary_edit_distance


max_suggestions: int

    default = 5


include_unknown: bool

    default = False


transfer_casing: bool

    default = True


min_candidate_frequency: int

    default = 1


============================================================
TOKEN LIMITS
============================================================

min_token_length: int

    default = 2


max_token_length: int

    default = 64


============================================================
CUSTOM CONFIG
============================================================

from backend.ocr_correction import (
    OCRCorrectionConfig,
    OCRCorrector,
)

config = OCRCorrectionConfig(
    max_lookup_edit_distance=1,
    max_suggestions=3,
    min_token_length=2,
)

corrector = OCRCorrector(
    config=config
)


============================================================
CUSTOM VOCABULARY INSTANCE
============================================================

Có thể inject vocabulary:

    vocabulary = OCRVocabulary()

    vocabulary.add_word(
        "SubVision",
        frequency=1_000_000,
    )

    corrector = OCRCorrector(
        vocabulary=vocabulary
    )


Input constructor:

    OCRCorrector(
        config: OCRCorrectionConfig | None = None,
        vocabulary: OCRVocabulary | None = None,
    )


============================================================
ERRORS
============================================================

OCRCorrectionError
------------------

Base runtime error của corrector.


OCRCorrectionInputError
-----------------------

Input text/token của corrector sai contract.


VocabularyError
---------------

Base runtime error của vocabulary.


VocabularyInputError
--------------------

Input token / custom word / lookup argument sai.


VocabularyLoadError
-------------------

Không thể load frequency dictionary.


============================================================
PIPELINE POSITION
============================================================

Public input:

    str
    OCR text

        ↓

    OCRCorrector

        ↓

Public output:

    OCRCorrectionResult

hoặc:

    str
    qua correct_text()


Module không phụ thuộc bbox.

Do đó upstream cần chuyển OCR result/layout thành text
trước khi đưa vào module này.


============================================================
CURRENT IMPORTANT LIMITATION
============================================================

Code hiện có URL_PATTERN và EMAIL_PATTERN để tránh sửa
URL/email.

Tuy nhiên correct(text) trước tiên tokenize bằng regex chỉ nhận
word/apostrophe/hyphen token.

Vì vậy một chuỗi như:

    user@example.com

có thể bị chia thành nhiều token trước khi
_get_skip_reason() nhìn thấy nó.

Tương tự:

    https://example.com

không nhất thiết đến correct_token() như một URL hoàn chỉnh.

Do đó tại thời điểm hiện tại:

    KHÔNG được coi việc bảo toàn URL/email
    là một contract đã được đảm bảo hoàn toàn.

Nếu downstream phụ thuộc mạnh vào URL/email,
behavior này cần được kiểm tra hoặc sửa riêng sau.


============================================================
REAL TEST
============================================================

Test hiện tại tạo OCRCorrector thật:

    corrector = OCRCorrector()

sau đó chạy correction thật trên nhiều câu mẫu.

Ví dụ:

    "I havc a problcm with this machinc."

    "This applicatlon can translate English subtitles."

    "OpenAI uses PaddleOCR in this example."

    "CPU and GPU are both supported."


Test hiển thị:

    original_text
    corrected_text

và với mỗi correction:

    original
    corrected
    distance
    frequency


Chạy:

    python -m backend.ocr_correction.test


============================================================
PUBLIC API
============================================================

Thông thường downstream chỉ cần:

    OCRCorrector

    OCRCorrectionResult

    TokenCorrection


Nếu cần cấu hình:

    OCRCorrectionConfig


Nếu cần quản lý dictionary:

    OCRVocabulary

    VocabularyCandidate


============================================================
IMPORTANT RULES
============================================================

1. Public input chính là str, không phải OCR Result object.

2. Corrector không biết bbox hoặc OCR confidence.

3. Corrector chỉ sửa non-word physical errors.

4. Từ hợp lệ trong dictionary luôn được giữ nguyên.

5. Không thực hiện semantic correction.

6. Formatting ngoài token được giữ nguyên.

7. OCRVocabulary load frequency dictionary khi khởi tạo.

8. Nên tái sử dụng OCRCorrector thay vì tạo mới cho mỗi text.

9. Custom vocabulary có state và tồn tại trong lifetime
   của OCRVocabulary instance.

10. correct_text() dùng khi chỉ cần str.

11. correct() dùng khi cần metadata/debug.

12. URL/email preservation hiện chưa nên coi là contract
    đảm bảo hoàn toàn.
"""


from __future__ import annotations

from .config import (
    DEFAULT_OCR_CORRECTION_CONFIG,
    OCRCorrectionConfig,
)

from .corrector import (
    OCRCorrectionError,
    OCRCorrectionInputError,
    OCRCorrectionResult,
    OCRCorrector,
    TokenCorrection,
)

from .vocabulary import (
    OCRVocabulary,
    VocabularyCandidate,
    VocabularyError,
    VocabularyInputError,
    VocabularyLoadError,
)


__all__ = [
    # Main API
    "OCRCorrector",

    # Config
    "OCRCorrectionConfig",
    "DEFAULT_OCR_CORRECTION_CONFIG",

    # Results
    "OCRCorrectionResult",
    "TokenCorrection",

    # Vocabulary
    "OCRVocabulary",
    "VocabularyCandidate",

    # Correction errors
    "OCRCorrectionError",
    "OCRCorrectionInputError",

    # Vocabulary errors
    "VocabularyError",
    "VocabularyInputError",
    "VocabularyLoadError",
]