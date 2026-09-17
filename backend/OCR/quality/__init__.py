"""
QUALITY OCR
===========

OCR chất lượng cao của SubVision.

Public boundary:

    BGR image
        ↓
    QualityOCR
        ↓
    raw PaddleOCR Result objects


============================================================
PURPOSE
============================================================

QualityOCR chịu trách nhiệm:

    - validate ảnh đầu vào;
    - khởi tạo PaddleOCR quality models;
    - chạy text detection;
    - chạy text recognition;
    - trả raw PaddleOCR Result.

QualityOCR KHÔNG:

    - capture màn hình;
    - crop vùng ảnh;
    - resize/padding thủ công;
    - grouping text;
    - OCR correction;
    - NLP hậu xử lý;
    - dịch;
    - chuẩn hóa PaddleOCR result thành model riêng.


============================================================
PUBLIC INPUT
============================================================

Main API:

    QualityOCR.predict(image)

hoặc:

    QualityOCR()(image)


image
-----

Type:

    numpy.ndarray

Contract:

    dtype:
        numpy.uint8

    ndim:
        3

    shape:
        (height, width, 3)

    color:
        BGR

    height:
        int
        >= 16 mặc định

    width:
        int
        >= 16 mặc định

    pixel count:
        height * width
        <= 40_000_000 mặc định


Ví dụ:

    import cv2

    image = cv2.imread(
        "image.png",
        cv2.IMREAD_COLOR,
    )

    # numpy.ndarray
    # dtype = uint8
    # shape = (H, W, 3)
    # BGR


QualityOCR không sửa:

    - kích thước ảnh;
    - màu;
    - pixel content.

Module chỉ đảm bảo array có contiguous memory
trước khi đưa vào PaddleOCR.


============================================================
PUBLIC OUTPUT
============================================================

QualityOCR.predict(image)

trả về:

    list[Any]

Trong thực tế:

    list các raw PaddleOCR Result objects.


Ví dụ:

    results = ocr.predict(image)

    for result in results:
        ...


Module hiện KHÔNG định nghĩa:

    QualityOCRResult
    OCRItem
    OCRBox

Output boundary hiện tại vẫn là PaddleOCR Result.


============================================================
ĐỌC PADDLEOCR RESULT
============================================================

Test hiện tại đọc:

    payload = result.json

Nếu json là method:

    if callable(payload):
        payload = payload()

Sau đó:

    data = payload.get(
        "res",
        payload,
    )


Các field đang được sử dụng:

    data["rec_texts"]

        Nội dung OCR.

        Runtime usage:
            list[str]-like


    data["rec_scores"]

        Confidence tương ứng với text.

        Mỗi phần tử được chuyển thành:
            float


    data["rec_boxes"]

        Bounding boxes từ PaddleOCR.

        Test hiện có thể xử lý:
            numpy.ndarray
            hoặc object hỗ trợ .tolist()


Thông thường:

    rec_texts[i]
    rec_scores[i]
    rec_boxes[i]

được xem là cùng một recognition item.


============================================================
OUTPUT CHƯA ĐƯỢC CONTRACT HÓA HOÀN TOÀN
============================================================

QualityOCR hiện KHÔNG bảo đảm bằng type riêng về:

    - concrete class của PaddleOCR Result;
    - dtype chính xác của rec_boxes;
    - shape chính xác của rec_boxes;
    - representation chính xác của bbox;
    - schema đầy đủ của result.json;
    - độ dài rec_texts / rec_scores / rec_boxes luôn bằng nhau.

Những chi tiết này hiện vẫn thuộc PaddleOCR.

Nếu downstream cần một contract ổn định hơn,
cần có adapter/module riêng để chuẩn hóa output.


============================================================
STATE / LIFETIME
============================================================

QualityOCR là stateful theo nghĩa nó giữ model runtime.

Khi:

    ocr = QualityOCR()

module tạo:

    PaddleOCR(...)

và lưu tại:

    self._pipeline


Pipeline được tái sử dụng:

    result_1 = ocr(image_1)
    result_2 = ocr(image_2)
    result_3 = ocr(image_3)


Không nên khởi tạo lại QualityOCR cho mỗi ảnh nếu không cần.

QualityOCR không giữ OCR result của lần inference trước.


============================================================
CONFIG
============================================================

Config type:

    QualityOCRConfig


Mặc định:

    ocr = QualityOCR()


Tương đương:

    ocr = QualityOCR(
        DEFAULT_QUALITY_OCR_CONFIG
    )


------------------------------------------------------------
MODEL
------------------------------------------------------------

detection_model_name: str

    default:
        "PP-OCRv6_medium_det"


recognition_model_name: str

    default:
        "PP-OCRv6_medium_rec"


------------------------------------------------------------
RUNTIME
------------------------------------------------------------

device: str

Hợp lệ:

    "auto"
    "cpu"
    "gpu"
    "gpu:0"
    "gpu:1"
    ...


engine:

    Literal["paddle_static"]

default:

    "paddle_static"


enable_mkldnn: bool

    default:
        False


cpu_threads: int

    default:
        tối đa 8 CPU threads

    minimum:
        1


------------------------------------------------------------
OPTIONAL PADDLEOCR MODULES
------------------------------------------------------------

use_doc_orientation_classify: bool
    default: False

use_doc_unwarping: bool
    default: False

use_textline_orientation: bool
    default: False


------------------------------------------------------------
TEXT DETECTION
------------------------------------------------------------

text_det_limit_side_len: int

    default:
        1280


text_det_limit_type:

    Literal["max", "min"]

    default:
        "max"


text_det_thresh: float

    default:
        0.25

    range:
        0.0 -> 1.0


text_det_box_thresh: float

    default:
        0.50

    range:
        0.0 -> 1.0


text_det_unclip_ratio: float

    default:
        1.50

    constraint:
        > 0


------------------------------------------------------------
TEXT RECOGNITION
------------------------------------------------------------

text_recognition_batch_size: int

    default:
        4

    minimum:
        1


text_rec_score_thresh: float

    default:
        0.05

    range:
        0.0 -> 1.0


------------------------------------------------------------
INPUT SAFETY
------------------------------------------------------------

min_image_height: int

    default:
        16


min_image_width: int

    default:
        16


max_image_pixels: int

    default:
        40_000_000


============================================================
USAGE
============================================================

Cách thông thường:

    from backend.OCR.quality import QualityOCR

    ocr = QualityOCR()

    results = ocr(image)


Hoặc:

    results = ocr.predict(image)


============================================================
CUSTOM CONFIG
============================================================

from backend.OCR.quality import (
    QualityOCR,
    QualityOCRConfig,
)

config = QualityOCRConfig(
    device="gpu:0",
    text_det_limit_side_len=1280,
    text_recognition_batch_size=4,
)

ocr = QualityOCR(
    config=config
)

results = ocr(image)


============================================================
ERRORS
============================================================

QualityOCRInputError
--------------------

Ảnh đầu vào không đúng contract.

Ví dụ:

    - không phải numpy.ndarray;
    - dtype != uint8;
    - ndim != 3;
    - channels != 3;
    - ảnh nhỏ hơn giới hạn;
    - ảnh vượt max_image_pixels.


QualityOCRInitializationError
-----------------------------

Không thể khởi tạo PaddleOCR hoặc pretrained models.


QualityOCRInferenceError
------------------------

Model đã khởi tạo nhưng inference thất bại.


============================================================
PIPELINE POSITION
============================================================

Upstream phải cung cấp:

    numpy.ndarray
    uint8
    BGR
    (H, W, 3)

        ↓

    QualityOCR

        ↓

    list[PaddleOCR Result]

        ↓

Downstream có thể đọc:

    rec_texts
    rec_scores
    rec_boxes


QualityOCR không quy định downstream phải là module nào.


============================================================
REAL TEST
============================================================

Test hiện tại chạy model thật với ảnh thật.

Từ project root:

    python -m backend.OCR.quality.test \
        --image "images/image.png" \
        --output "outputs/quality_ocr"


Test thực hiện:

    image file
        ↓
    cv2.imread()
        ↓
    BGR uint8 ndarray
        ↓
    QualityOCR()
        ↓
    real PaddleOCR inference
        ↓
    rec_texts
    rec_scores
    rec_boxes
        ↓
    optional visualization


Test đo:

    initialization time
    inference time
    số Result objects
    số dòng text nhận diện


============================================================
IMPORTANT RULES
============================================================

1. Input là BGR uint8 ndarray `(H, W, 3)`.

2. QualityOCR không capture/crop ảnh.

3. QualityOCR không grouping.

4. QualityOCR không correction.

5. QualityOCR không translation.

6. Output là raw PaddleOCR Result.

7. Model nên được khởi tạo một lần và tái sử dụng.

8. Không giả định chi tiết bbox ngoài những gì
   raw PaddleOCR thực sự cung cấp.

9. QualityOCR ưu tiên chất lượng OCR;
   policy lựa chọn khi nào sử dụng QualityOCR
   không thuộc trách nhiệm của module này.
"""


from __future__ import annotations

from .config import (
    DEFAULT_QUALITY_OCR_CONFIG,
    QualityOCRConfig,
)

from .model import (
    QualityOCR,
    QualityOCRInferenceError,
    QualityOCRInitializationError,
    QualityOCRInputError,
)


__all__ = [
    "QualityOCR",
    "QualityOCRConfig",
    "DEFAULT_QUALITY_OCR_CONFIG",
    "QualityOCRInputError",
    "QualityOCRInitializationError",
    "QualityOCRInferenceError",
]