<<<<<<< HEAD
"""
DICTIONARY CORE
===============

Phần lõi dùng chung của hệ thống Dictionary.

Hiện tại package root chỉ cung cấp:

    DictionaryTokenizer

Hai subsystem:

    literal/
    dashboard/

có thể sử dụng tokenizer này nhưng được giữ độc lập với nhau.


Public pipeline:

    text: str
        ↓
    DictionaryTokenizer
        ↓
    tuple[DictionaryToken, ...]


============================================================
PURPOSE
============================================================

Dictionary core chịu trách nhiệm:

    - nhận một chuỗi text;
    - phát hiện word;
    - phát hiện number;
    - phát hiện email;
    - giữ nguyên text gốc của mỗi token;
    - giữ character span trong text gốc;
    - normalize token;
    - có thể lemmatize word;
    - cung cấp normalized token cho lookup / PhraseTrie.


Dictionary core KHÔNG:

    - đọc dictionary JSON;
    - tra nghĩa;
    - tìm phrase;
    - dịch;
    - chọn nghĩa;
    - sửa OCR;
    - hiểu semantic;
    - phụ thuộc Literal;
    - phụ thuộc Dashboard.


============================================================
PUBLIC INPUT
============================================================

Main API:

    DictionaryTokenizer.tokenize(text)


text
----

Type:

    str


Ví dụ:

    "I study machine learning."

    "100 dogs"

    "Contact user@example.com"

    "Meet me at 10:30."


Cho phép:

    - whitespace;
    - punctuation;
    - newline;
    - Unicode letters;
    - email;
    - number;
    - empty string.


Không cho phép:

    null character:

        "\\x00"


Giới hạn mặc định:

    len(text) <= 10_000 characters


Nếu vượt giới hạn:

    DictionaryTokenizerInputError


============================================================
PUBLIC OUTPUT
============================================================

tokenizer.tokenize(text)

trả về:

    tuple[DictionaryToken, ...]


Nếu không tìm thấy token:

    ()


Ví dụ:

    tokens = tokenizer.tokenize(
        "100 dogs"
    )


Có thể tạo output tương đương:

    (
        DictionaryToken(...),
        DictionaryToken(...),
    )


============================================================
DICTIONARY TOKEN
============================================================

DictionaryToken là immutable dataclass.


Fields:

    index: int

        Index của token trong output tuple.

        Token đầu tiên:

            index = 0


    text: str

        Nội dung gốc lấy trực tiếp từ input.

        Ví dụ:

            input:
                "Machines"

            text:
                "Machines"


    normalized: str

        Giá trị đã normalize để downstream lookup.

        Ví dụ mặc định:

            "Machines"
                ↓
            "machine"


    start: int

        Character index bắt đầu trong original input.


    end: int

        Character index kết thúc.

        Span dùng convention:

            [start, end)


        Vì vậy token gốc có thể lấy lại bằng:

            original_text[
                token.start:
                token.end
            ]


    token_type:

        Literal[
            "word",
            "number",
            "email",
        ]


============================================================
DICTIONARY TOKEN PROPERTIES
============================================================

token.length

Output:

    int

Ý nghĩa:

    len(token.text)


token.is_word

Output:

    bool


token.is_number

Output:

    bool


token.is_email

Output:

    bool


============================================================
TOKEN TYPES
============================================================

WORD
----

token_type:

    "word"


Ví dụ:

    hello
    machine
    don't
    John's
    state-of-the-art


Word có thể được:

    - Unicode-normalize;
    - normalize apostrophe;
    - normalize hyphen;
    - casefold;
    - lemmatize.


------------------------------------------------------------
NUMBER
------------------------------------------------------------

token_type:

    "number"


Các dạng được regex hiện tại hỗ trợ bao gồm:

    10

    10.5

    1,000

    10:30

    2026-08-01

    10/20


Number không được lemmatize.


------------------------------------------------------------
EMAIL
------------------------------------------------------------

token_type:

    "email"


Ví dụ:

    user@example.com

    hello.world@gmail.com

    user+test@company.co.uk


Email được match trước word và number để tránh bị
tách thành nhiều token.


Email không được lemmatize.


============================================================
PUNCTUATION
============================================================

Punctuation thông thường KHÔNG trở thành DictionaryToken.


Ví dụ:

    "Hello, world!"


Output token:

    "Hello"
    "world"


Các ký tự:

    ","
    "!"

không nằm trong output tuple.


Tuy nhiên character span của token vẫn trỏ về đúng vị trí
trong chuỗi gốc.


DictionaryTokenizer KHÔNG tạo punctuation token.


============================================================
NORMALIZATION
============================================================

Word mặc định trải qua pipeline:

    original token
        ↓
    Unicode normalization
        ↓
    apostrophe normalization
        ↓
    hyphen normalization
        ↓
    casefold
        ↓
    lemmatization
        ↓
    normalized


Default Unicode normalization:

    NFKC


Ví dụ dự kiến:

    "Machines"
        ↓
    "machine"

    "STUDIES"
        ↓
    "study"

    "Decided"
        ↓
    "decide"


============================================================
APOSTROPHE NORMALIZATION
============================================================

Nếu:

    normalize_apostrophes=True


Các apostrophe sau được normalize về:

    '


Bao gồm:

    ’
    ‘
    ‛
    ʼ


Ví dụ normalized representation:

    John’s
        ↓
    john's


============================================================
HYPHEN NORMALIZATION
============================================================

Nếu:

    normalize_hyphens=True


Các dạng hyphen/dash được normalize về:

    "-"


Bao gồm các dạng:

    ‐
    -
    ‒
    –
    —
    −


============================================================
LEMMATIZATION
============================================================

Config mặc định:

    lemmatize_words=True

    lemmatizer_language="en"


Dependency:

    simplemma


Lemmatization chỉ áp dụng cho:

    token_type == "word"


Không áp dụng cho:

    number
    email


Có thể gọi normalize_token trực tiếp:

    normalized = tokenizer.normalize_token(
        "Machines"
    )


Input:

    token: str


Output:

    str


============================================================
normalize_token()
============================================================

API:

    tokenizer.normalize_token(
        token,
        apply_lemma=True,
    )


Input:

    token: str

    apply_lemma: bool
        default = True


Token phải:

    - không rỗng;
    - không chứa whitespace;
    - không dài quá max_token_characters.


Output:

    str


Nếu:

    apply_lemma=False

thì token vẫn có thể được:

    Unicode normalize
    apostrophe normalize
    hyphen normalize
    casefold

nhưng không lemmatize.


============================================================
normalize_phrase()
============================================================

API:

    tokenizer.normalize_phrase(
        phrase
    )


Input:

    phrase: str


Output:

    tuple[str, ...]


Pipeline:

    phrase
        ↓
    tokenize()
        ↓
    lấy token.normalized
        ↓
    tuple[str, ...]


Ví dụ:

    "Look Up"

        ↓

    (
        "look",
        "up",
    )


Đây là API hữu ích cho PhraseTrie.


QUAN TRỌNG:

normalize_phrase() dùng chính tokenize().

Do đó:

    - punctuation không trở thành token;
    - word có thể bị lemmatize;
    - number phụ thuộc include_numbers;
    - single-character word phụ thuộc config.


============================================================
extract_normalized_tokens()
============================================================

API rút gọn:

    tokenizer.extract_normalized_tokens(
        text
    )


Input:

    str


Output:

    tuple[str, ...]


Ví dụ:

    "I Want To Look Up This Word"

        ↓

    (
        "i",
        "want",
        "to",
        "look",
        "up",
        "this",
        "word",
    )


Nó tương đương:

    tuple(
        token.normalized
        for token
        in tokenizer.tokenize(text)
    )


============================================================
CALLABLE API
============================================================

Có thể gọi tokenizer như function:

    tokenizer = DictionaryTokenizer()

    tokens = tokenizer(
        "Look up this word."
    )


Tương đương:

    tokens = tokenizer.tokenize(
        "Look up this word."
    )


============================================================
MAIN USAGE
============================================================

from backend.translation.dictionary import (
    DictionaryTokenizer,
)

tokenizer = DictionaryTokenizer()

tokens = tokenizer.tokenize(
    "I study machine learning at 10:30."
)

for token in tokens:

    print(
        token.index,
        token.text,
        token.normalized,
        token.token_type,
        token.start,
        token.end,
    )


============================================================
CONFIG
============================================================

Config type:

    TokenizerConfig


Fields:


case_sensitive: bool

    default:
        False


unicode_normalization:

    Literal[
        "NFC",
        "NFKC",
    ]

    default:
        "NFKC"


normalize_apostrophes: bool

    default:
        True


normalize_hyphens: bool

    default:
        True


include_numbers: bool

    default:
        True


include_single_character_words: bool

    default:
        True


max_input_characters: int

    default:
        10_000

    minimum:
        1


max_token_characters: int

    default:
        128

    minimum:
        1


lemmatize_words: bool

    default:
        True


lemmatizer_language: str

    default:
        "en"


============================================================
CUSTOM CONFIG
============================================================

from backend.translation.dictionary import (
    DictionaryTokenizer,
    TokenizerConfig,
)


config = TokenizerConfig(
    case_sensitive=False,
    include_numbers=True,
    lemmatize_words=True,
)

tokenizer = DictionaryTokenizer(
    config=config
)

tokens = tokenizer(
    "Machines 100 dogs"
)


============================================================
FILTERING BEHAVIOR
============================================================

NUMBER
------

Nếu:

    include_numbers=False

thì number được bỏ khỏi output hoàn toàn.


Ví dụ:

    "I have 100 dogs"

có thể chỉ trả:

    I
    have
    dogs


------------------------------------------------------------
SINGLE CHARACTER WORD
------------------------------------------------------------

Nếu:

    include_single_character_words=False

thì word có độ dài 1 ký tự bị bỏ.


Ví dụ:

    "I have a dog"

có thể bỏ:

    I
    a


Default hiện tại:

    include_single_character_words=True


============================================================
LONG TOKEN BEHAVIOR
============================================================

Trong tokenize():

Nếu một matched token dài hơn:

    max_token_characters

thì token đó bị:

    skip


Không raise error cho toàn bộ text.


Ngược lại, nếu gọi trực tiếp:

    normalize_token(...)

với token quá dài thì:

    DictionaryTokenizerInputError


Đây là hai behavior khác nhau cần phân biệt.


============================================================
STATE / LIFETIME
============================================================

DictionaryTokenizer giữ:

    config: TokenizerConfig


Ngoài config, tokenizer không giữ runtime state.


Ví dụ:

    tokenizer = DictionaryTokenizer()

    result_1 = tokenizer(text_1)
    result_2 = tokenizer(text_2)
    result_3 = tokenizer(text_3)


Các lần gọi độc lập.


Không có:

    - previous tokens;
    - dictionary cache;
    - phrase state;
    - vocabulary;
    - session history.


Có thể coi:

    DictionaryTokenizer

là stateless processor với immutable config.


============================================================
DEPENDENCIES
============================================================

DictionaryTokenizer phụ thuộc:

    Python stdlib:
        re
        unicodedata
        dataclasses
        typing

    external:
        simplemma


DictionaryTokenizer KHÔNG phụ thuộc:

    literal
    dashboard
    PhraseTrie
    dictionary JSON
    OCR
    OCR correction
    language model translator


============================================================
POSITION INSIDE DICTIONARY
============================================================

Architecture dự kiến:

    dictionary/
        │
        ├── tokenizer.py
        │
        ├── literal/
        │
        └── dashboard/


Shared dependency:

                  DictionaryTokenizer
                         ▲
                         │
                ┌────────┴────────┐
                │                 │
             Literal          Dashboard


Literal và Dashboard có thể dùng tokenizer.

Tokenizer không được import ngược:

    Literal
    Dashboard


============================================================
BOUNDARY WITH UPSTREAM
============================================================

Upstream chỉ cần cung cấp:

    str


Ví dụ:

    OCRCorrectionResult.corrected_text

        ↓

    DictionaryTokenizer


Tokenizer không nhận trực tiếp:

    OCRCorrectionResult
    TextGroup
    PaddleOCR Result
    BBox


Ví dụ đúng:

    tokens = tokenizer(
        correction.corrected_text
    )


Hoặc:

    tokens = tokenizer(
        group.text
    )


============================================================
BOUNDARY WITH LITERAL / DASHBOARD
============================================================

Downstream có thể sử dụng:

    token.text

để biết surface text gốc.


    token.normalized

để lookup.


    token.start
    token.end

để map kết quả trở lại original string.


    token.token_type

để quyết định xử lý:

        word
        number
        email


Literal và Dashboard không cần tự biết cách:

    casefold
    lemmatize
    normalize apostrophe
    normalize hyphen

nếu chúng quyết định dùng chung contract của tokenizer.


============================================================
ERRORS
============================================================

DictionaryTokenizerError
------------------------

Base runtime error của tokenizer.


DictionaryTokenizerInputError
-----------------------------

Input không đúng contract.

Ví dụ:

    tokenize():
        input không phải str;
        chứa null character;
        text quá dài.

    normalize_token():
        token không phải str;
        token rỗng;
        có whitespace;
        token quá dài.


============================================================
IMPORTANT RULES
============================================================

1. Public input chính:

       str


2. Public output chính:

       tuple[DictionaryToken, ...]


3. DictionaryToken:

       index: int
       text: str
       normalized: str
       start: int
       end: int
       token_type: Literal[
           "word",
           "number",
           "email",
       ]


4. start/end luôn tham chiếu original input text.


5. Tokenizer không sửa original string.


6. Punctuation không trở thành token.


7. Word có thể được lemmatize.


8. Number và email không được lemmatize.


9. Email được nhận diện trước word/number.


10. Tokenizer không tìm phrase.


11. Tokenizer không tra dictionary.


12. Tokenizer không dịch.


13. Tokenizer không đọc JSON.


14. Tokenizer không phụ thuộc Literal hoặc Dashboard.


15. Literal và Dashboard có thể phụ thuộc tokenizer.


16. Tokenizer không giữ history giữa các lần gọi.


17. normalize_phrase() sử dụng tokenize(),
    vì vậy nó tuân theo cùng filtering/config.


18. max_token_characters có hai behavior:

       tokenize():
           token quá dài -> skip

       normalize_token():
           token quá dài -> raise


19. Đây là shared normalization contract.
    Nếu Literal/Dashboard sử dụng token.normalized để lookup,
    dữ liệu/index của chúng phải tương thích với
    normalization này.
"""


from __future__ import annotations

from .tokenizer import (
    DEFAULT_TOKENIZER_CONFIG,
=======
from .config import (
    DEFAULT_DICTIONARY_TRANSLATION_CONFIG,
    DictionaryTranslationConfig,
)
from .phrase_trie import (
    PhraseEntry,
    PhraseMatch,
    PhraseTrie,
    PhraseTrieError,
    PhraseTrieInputError,
)
from .tokenizer import (
>>>>>>> 04baa413f449b21a5e77119f3024f4efeb2f3942
    DictionaryToken,
    DictionaryTokenizer,
    DictionaryTokenizerError,
    DictionaryTokenizerInputError,
<<<<<<< HEAD
    TokenizerConfig,
    TokenType,
    UnicodeNormalization,
=======
)
from .translator import (
    DictionaryTranslationItem,
    DictionaryTranslationResult,
    DictionaryTranslator,
    DictionaryTranslatorError,
    DictionaryTranslatorInputError,
)
from .vocabulary import (
    DictionaryVocabulary,
    DictionaryVocabularyError,
    DictionaryVocabularyInputError,
    DictionaryVocabularyLoadError,
    WordEntry,
>>>>>>> 04baa413f449b21a5e77119f3024f4efeb2f3942
)


__all__ = [
    # Main API
<<<<<<< HEAD
    "DictionaryTokenizer",

    # Result model
    "DictionaryToken",

    # Config
    "TokenizerConfig",
    "DEFAULT_TOKENIZER_CONFIG",

    # Public types
    "TokenType",
    "UnicodeNormalization",

    # Errors
    "DictionaryTokenizerError",
    "DictionaryTokenizerInputError",
=======
    "DictionaryTranslator",
    "DictionaryTranslationConfig",
    "DEFAULT_DICTIONARY_TRANSLATION_CONFIG",

    # Translation results
    "DictionaryTranslationResult",
    "DictionaryTranslationItem",

    # Tokenizer
    "DictionaryTokenizer",
    "DictionaryToken",

    # Word vocabulary
    "DictionaryVocabulary",
    "WordEntry",

    # Phrase Trie
    "PhraseTrie",
    "PhraseEntry",
    "PhraseMatch",

    # Translator errors
    "DictionaryTranslatorError",
    "DictionaryTranslatorInputError",

    # Tokenizer errors
    "DictionaryTokenizerError",
    "DictionaryTokenizerInputError",

    # Vocabulary errors
    "DictionaryVocabularyError",
    "DictionaryVocabularyInputError",
    "DictionaryVocabularyLoadError",

    # Phrase Trie errors
    "PhraseTrieError",
    "PhraseTrieInputError",
>>>>>>> 04baa413f449b21a5e77119f3024f4efeb2f3942
]