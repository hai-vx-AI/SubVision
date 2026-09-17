"""
LANGUAGE MODEL TRANSLATION
==========================

Machine translation Anh -> Việt bằng MarianMT.

Public pipeline:

    English text: str
        ↓
    LanguageTranslator
        ↓
    LanguageTranslationResult
        └── translated_text: str


============================================================
PURPOSE
============================================================

Module chịu trách nhiệm:

    - nhận text tiếng Anh;
    - validate input;
    - preprocessing nhẹ;
    - tokenize bằng tokenizer của model;
    - chạy MarianMT;
    - decode output;
    - trả bản dịch tiếng Việt.


Module KHÔNG:

    - OCR;
    - grouping bbox;
    - OCR correction;
    - dictionary lookup;
    - lemmatization;
    - PhraseTrie;
    - dịch từng word/phrase;
    - sử dụng chatbot prompt;
    - quản lý UI.


============================================================
PUBLIC INPUT
============================================================

API chính:

    LanguageTranslator.translate(text)


text
----

Type:

    str


Ý nghĩa:

    Một câu hoặc đoạn text tiếng Anh cần dịch.


Ví dụ:

    "She decided to give up."

    "Machine learning can translate subtitles."


Input có thể là:

    - một câu;
    - nhiều câu;
    - paragraph ngắn;
    - chuỗi rỗng.


Không cho phép:

    null character:

        "\\x00"


Giới hạn mặc định theo character:

    len(text) <= 5_000


Config:

    max_input_characters: int
        default = 5_000


============================================================
INPUT PREPROCESSING
============================================================

Nếu:

    normalize_whitespace = True

thì whitespace liên tiếp được collapse thành một space.


Ví dụ input:

    "She   decided\\nto leave."

processed_text:

    "She decided to leave."


Module KHÔNG:

    - lowercase;
    - lemmatize;
    - bỏ punctuation;
    - thay tense;
    - chia text thành từng word để dịch.


============================================================
MODEL INPUT
============================================================

Sau preprocessing, module thêm:

    target_language_token


Default:

    ">>vie<<"


Ví dụ:

    processed_text:

        "She decided to give up."

    model input:

        ">>vie<< She decided to give up."


Sau đó model input được đưa vào Hugging Face tokenizer.


============================================================
TOKEN LIMIT
============================================================

Tokenizer được gọi với:

    truncation=True

    max_length=config.max_input_tokens


Default:

    max_input_tokens = 256


Maximum config cho model hiện tại:

    512


QUAN TRỌNG:

Nếu input sau tokenization dài hơn max_input_tokens,
tokenizer sẽ TRUNCATE phần vượt giới hạn.

Module hiện:

    - không raise error vì token overflow;
    - không trả flag cho biết truncation đã xảy ra.


Do đó:

    result.processed_text

có thể chứa toàn bộ processed input,

trong khi model thực tế chỉ dịch phần token sequence
sau khi đã bị truncate.


Downstream không được giả định rằng:

    translated_text

luôn bao phủ 100% processed_text

nếu input có thể dài.


============================================================
PUBLIC OUTPUT
============================================================

translator.translate(text)

trả về:

    LanguageTranslationResult


LanguageTranslationResult
-------------------------

Dataclass immutable với các field:


    source_text: str

        Chính text ban đầu truyền vào translator.


    translated_text: str

        Bản dịch tiếng Việt do model sinh.


    processed_text: str

        Text sau preprocessing nhẹ.

        Không chứa target language token.


    device: str

        Device thực tế chạy inference.

        Ví dụ:

            "cpu"
            "cuda"


Ví dụ:

    result = translator.translate(
        "She decided to give up."
    )

    print(result.source_text)
    print(result.processed_text)
    print(result.translated_text)
    print(result.device)


============================================================
EMPTY INPUT
============================================================

Nếu input chỉ rỗng hoặc whitespace:

    result = translator.translate("")


Output vẫn là:

    LanguageTranslationResult


Với:

    source_text == input

    processed_text == ""

    translated_text == ""

    device == current device


Model inference không được chạy cho empty input.


============================================================
SIMPLE OUTPUT API
============================================================

Nếu downstream chỉ cần Vietnamese string:

    translated = translator.translate_text(
        text
    )


Input:

    str


Output:

    str


Output chính là:

    result.translated_text


============================================================
CALLABLE API
============================================================

Có thể gọi object trực tiếp:

    result = translator(
        "The plane took off."
    )


Tương đương:

    result = translator.translate(
        "The plane took off."
    )


============================================================
MAIN USAGE
============================================================

from backend.translation.language_model import (
    LanguageTranslator,
)

translator = LanguageTranslator()

result = translator.translate(
    "Machine learning can translate subtitles."
)

print(
    result.translated_text
)


Nếu chỉ cần text:

    translated_text = translator.translate_text(
        "Machine learning can translate subtitles."
    )


============================================================
STATE / LIFETIME
============================================================

LanguageTranslator là object STATEFUL về model runtime.

Khi:

    translator = LanguageTranslator()

module thực hiện:

    resolve device
        ↓
    load Hugging Face tokenizer
        ↓
    load Seq2Seq model
        ↓
    move model to CPU/CUDA
        ↓
    optional float16
        ↓
    model.eval()


Object giữ:

    self._tokenizer
    self._model
    self._device
    self.config


Model được tái sử dụng:

    translator(text_1)
    translator(text_2)
    translator(text_3)


Không nên tạo lại LanguageTranslator
cho mỗi câu vì model sẽ bị load lại.


Module KHÔNG giữ:

    - previous source text;
    - previous translation;
    - conversation context;
    - translation history;
    - accumulated session state.


Mỗi lần translate() độc lập về semantic context.


============================================================
DEVICE
============================================================

Config:

    device:
        Literal[
            "auto",
            "cpu",
            "gpu",
        ]


------------------------------------------------------------
auto
------------------------------------------------------------

Nếu:

    torch.cuda.is_available() == True

thì:

    CUDA

ngược lại:

    CPU


------------------------------------------------------------
cpu
------------------------------------------------------------

Luôn dùng:

    torch.device("cpu")


------------------------------------------------------------
gpu
------------------------------------------------------------

Yêu cầu CUDA.

Nếu CUDA không khả dụng:

    LanguageModelLoadError


Không hỗ trợ public config kiểu:

    "gpu:0"
    "gpu:1"

ở implementation hiện tại.


============================================================
FLOAT16
============================================================

Config:

    use_float16_on_gpu: bool

Default:

    True


Chỉ áp dụng khi:

    actual device == CUDA


Khi đó:

    model.half()


CPU không bị chuyển sang float16.


============================================================
MODEL
============================================================

Default model:

    Helsinki-NLP/opus-mt-en-vi


Config field:

    model_name: str


Tokenizer:

    AutoTokenizer


Model:

    AutoModelForSeq2SeqLM


Model được load bằng:

    from_pretrained(model_name)


============================================================
MODEL CACHE / DOWNLOAD
============================================================

Config:

    local_files_only: bool


Default:

    False


False:

    Hugging Face có thể tải model/tokenizer
    nếu chưa tồn tại local cache.


True:

    chỉ dùng model/tokenizer đã có trong local cache.


Do đó việc:

    LanguageTranslator()

có thể gây:

    - disk access;
    - model download;
    - network dependency;

nếu model chưa tồn tại và local_files_only=False.


============================================================
GENERATION
============================================================

Model sử dụng deterministic generation:

    do_sample = False


Default config:

    max_new_tokens:
        int = 256

    num_beams:
        int = 2

    length_penalty:
        float = 1.0

    early_stopping:
        bool = True


------------------------------------------------------------
num_beams
------------------------------------------------------------

1:

    greedy decoding
    nhanh hơn


2:

    default


Giá trị lớn hơn:

    search rộng hơn nhưng inference nặng hơn.


============================================================
CONFIG
============================================================

LanguageTranslationConfig


Fields:


Model
-----

    model_name: str

        default:
            "Helsinki-NLP/opus-mt-en-vi"


    target_language_token: str

        default:
            ">>vie<<"


Device
------

    device:
        Literal["auto", "cpu", "gpu"]

        default:
            "auto"


    use_float16_on_gpu: bool

        default:
            True


Input
-----

    max_input_tokens: int

        default:
            256

        allowed:
            1 -> 512


    max_input_characters: int

        default:
            5_000

        minimum:
            1


    normalize_whitespace: bool

        default:
            True


Generation
----------

    max_new_tokens: int

        default:
            256

        minimum:
            1


    num_beams: int

        default:
            2

        minimum:
            1


    length_penalty: float

        default:
            1.0

        constraint:
            > 0


    early_stopping: bool

        default:
            True


Loading
-------

    local_files_only: bool

        default:
            False


============================================================
CUSTOM CONFIG
============================================================

from backend.translation.language_model import (
    LanguageTranslationConfig,
    LanguageTranslator,
)


Ưu tiên CPU / latency:

    config = LanguageTranslationConfig(
        device="cpu",
        num_beams=1,
    )

    translator = LanguageTranslator(
        config=config
    )


GPU:

    config = LanguageTranslationConfig(
        device="gpu",
        use_float16_on_gpu=True,
        num_beams=2,
    )

    translator = LanguageTranslator(
        config=config
    )


============================================================
ERRORS
============================================================

LanguageTranslationError
------------------------

Base runtime error của module.


LanguageModelLoadError
----------------------

Không thể:

    - resolve requested device;
    - load tokenizer;
    - load model;
    - move/setup model.


Ví dụ:

    device="gpu"

nhưng CUDA không khả dụng.


LanguageTranslationInputError
-----------------------------

Input text không đúng contract.

Ví dụ:

    - không phải str;
    - chứa "\\x00";
    - vượt max_input_characters.


LanguageTranslationInferenceError
---------------------------------

Model đã load nhưng lỗi xảy ra trong:

    tokenization
    tensor transfer
    generation
    decoding
    output cleanup


============================================================
PIPELINE POSITION
============================================================

Upstream cần cung cấp:

    str


Ví dụ:

    TextGroup.text
        ↓
    OCRCorrector.correct_text()
        ↓
    corrected str
        ↓
    LanguageTranslator


Output:

    LanguageTranslationResult

hoặc:

    translated Vietnamese str


Module không cần:

    bbox
    confidence
    OCR Result object
    TextGroup object


============================================================
IMPORTANT BOUNDARY
============================================================

LanguageTranslator chỉ nhận:

    str


Nó KHÔNG nhận trực tiếp:

    TextGroup

    OCRCorrectionResult

    PaddleOCR Result


Ví dụ nếu upstream có:

    group: TextGroup

thì:

    translated = translator.translate_text(
        group.text
    )


Nếu upstream có:

    correction: OCRCorrectionResult

thì:

    translated = translator.translate_text(
        correction.corrected_text
    )


============================================================
IMPORTANT RULES
============================================================

1. Public input chính:

       str

2. Public detailed output:

       LanguageTranslationResult

3. Public simple output:

       str

4. Model dịch toàn câu/đoạn, không dịch word-by-word.

5. Module không phụ thuộc DictionaryTokenizer,
   PhraseTrie hay dictionary translation.

6. Whitespace có thể được normalize trước inference.

7. Model/tokenizer được load một lần và nên tái sử dụng.

8. Translation call không giữ context từ lần gọi trước.

9. Input vượt max_input_characters bị reject.

10. Input vượt max_input_tokens có thể bị tokenizer truncate
    mà hiện không có truncation flag trong result.

11. processed_text không nhất thiết chính xác là toàn bộ text
    mà model đã thực sự nhìn thấy nếu token truncation xảy ra.

12. device trong result là device thực tế,
    không nhất thiết bằng config.device="auto".

13. local_files_only=False có thể gây download model
    khi khởi tạo.

14. Module không biết bbox, OCR confidence hoặc layout.
"""


from __future__ import annotations

from .config import (
    DEFAULT_LANGUAGE_TRANSLATION_CONFIG,
    LanguageTranslationConfig,
)

from .model import (
    LanguageModelLoadError,
    LanguageTranslationError,
    LanguageTranslationInferenceError,
    LanguageTranslationInputError,
    LanguageTranslationResult,
    LanguageTranslator,
)


__all__ = [
    # Main API
    "LanguageTranslator",

    # Result
    "LanguageTranslationResult",

    # Config
    "LanguageTranslationConfig",
    "DEFAULT_LANGUAGE_TRANSLATION_CONFIG",

    # Errors
    "LanguageTranslationError",
    "LanguageModelLoadError",
    "LanguageTranslationInputError",
    "LanguageTranslationInferenceError",
]