"""
FAST OCR
========

OCR nhanh dùng PaddleOCR pretrained để nhận diện text tiếng Anh
từ một ảnh BGR.

Đây là public boundary của package:

    BGR image
        ↓
    FastOCR
        ↓
    raw PaddleOCR Result objects


============================================================
PURPOSE
============================================================

FastOCR chịu trách nhiệm:

    - kiểm tra ảnh đầu vào;
    - khởi tạo PaddleOCR;
    - chạy text detection;
    - chạy text recognition;
    - trả nguyên kết quả PaddleOCR.

FastOCR KHÔNG chịu trách nhiệm:

    - chụp màn hình;
    - crop ảnh;
    - resize/padding thủ công;
    - grouping các dòng text;
    - OCR correction;
    - dịch;
    - chuyển bounding box sang screen coordinates;
    - tạo result model riêng của SubVision.


============================================================
PUBLIC INPUT
============================================================

Main API:

    FastOCR.predict(image)

hoặc:

    FastOCR()(image)


image
-----

Type:

    numpy.ndarray

Required contract:

    dtype:
        numpy.uint8

    ndim:
        3

    shape:
        (height, width, 3)

    color format:
        BGR

    height:
        int

    width:
        int

    channels:
        3


Default size limits:

    height >= 16

    width >= 16

    height * width <= 20_000_000


Ví dụ hợp lệ:

    import cv2

    image = cv2.imread(
        "image.png",
        cv2.IMREAD_COLOR,
    )

    # image:
    # numpy.ndarray
    # dtype = uint8
    # shape = (H, W, 3)
    # BGR


FastOCR không thay đổi:

    - pixel content;
    - color order;
    - image dimensions.

Module chỉ bảo đảm vùng nhớ của array là contiguous
trước khi đưa vào PaddleOCR.


============================================================
PUBLIC OUTPUT
============================================================

FastOCR.predict(image)

trả về:

    list[Any]

Cụ thể:

    list các raw PaddleOCR Result objects.


Ví dụ:

    results = ocr.predict(image)

    for result in results:
        ...


FastOCR hiện KHÔNG tạo một class output riêng như:

    OCRResult
    OCRItem

Do đó output boundary hiện tại chính là raw PaddleOCR API.


------------------------------------------------------------
CÁCH ĐỌC MỘT PADDLEOCR RESULT
------------------------------------------------------------

Result object có thể đọc qua:

    payload = result.json

Một số phiên bản có thể triển khai json như method:

    if callable(payload):
        payload = payload()

Sau đó:

    data = payload.get(
        "res",
        payload,
    )


Các field đang được module test sử dụng:

    data["rec_texts"]

        Nội dung text nhận diện được.

        Runtime usage hiện tại:

            list[str]-like


    data["rec_scores"]

        Confidence của từng text recognition.

        Mỗi score có thể chuyển thành:

            float


    data["rec_boxes"]

        Bounding boxes do PaddleOCR trả về.

        Kiểu/shape cụ thể KHÔNG được FastOCR
        chuẩn hóa thành contract riêng.

        Test hiện xử lý trường hợp:

            numpy.ndarray


Quan hệ thông thường:

    rec_texts[i]
    rec_scores[i]
    rec_boxes[i]

thuộc cùng một recognition item.


QUAN TRỌNG:

FastOCR không bảo đảm bằng class/type riêng rằng:

    len(rec_texts)
    ==
    len(rec_scores)
    ==
    len(rec_boxes)

và cũng chưa định nghĩa một bbox model riêng.


============================================================
OUTPUT CONTRACT CHƯA ĐƯỢC CHUẨN HÓA
============================================================

Các chi tiết sau hiện vẫn thuộc raw PaddleOCR
và KHÔNG phải contract riêng của SubVision:

    - concrete class của PaddleOCR Result;
    - exact dtype của rec_boxes;
    - exact shape của rec_boxes;
    - bbox representation;
    - coordinate-system contract của bbox;
    - schema đầy đủ của result.json.

Nếu module phía sau cần các thông tin này,
nó phải đọc raw PaddleOCR Result
hoặc một module adapter khác phải chuẩn hóa chúng.


============================================================
STATE / LIFETIME
============================================================

FastOCR là object giữ model runtime.

Khi tạo:

    ocr = FastOCR()

module khởi tạo:

    PaddleOCR(...)

và lưu pipeline tại:

    self._pipeline


Pipeline được giữ lại và tái sử dụng:

    ocr(image_1)
    ocr(image_2)
    ocr(image_3)


Không nên tạo lại FastOCR cho mỗi ảnh nếu không cần thiết,
vì model initialization là một bước riêng và tương đối nặng.

FastOCR không giữ result của lần inference trước.


============================================================
CONFIG
============================================================

Config type:

    FastOCRConfig


Cách dùng mặc định:

    ocr = FastOCR()


Tương đương:

    ocr = FastOCR(
        config=DEFAULT_FAST_OCR_CONFIG
    )


Có thể truyền config riêng:

    config = FastOCRConfig(
        device="cpu",
        cpu_threads=4,
    )

    ocr = FastOCR(
        config=config
    )


Các field public của FastOCRConfig:


Pretrained models
-----------------

    detection_model_name: str

        default:
            "PP-OCRv5_mobile_det"


    recognition_model_name: str

        default:
            "en_PP-OCRv5_mobile_rec"


Runtime
-------

    device:
        Literal["auto", "cpu", "gpu"]

        default:
            "auto"


    enable_mkldnn: bool

        default:
            False


    cpu_threads: int

        default:
            min(8, available CPU threads)
            nhưng tối thiểu 1


Document processing
-------------------

    use_doc_orientation_classify: bool
        default: False

    use_doc_unwarping: bool
        default: False

    use_textline_orientation: bool
        default: False


Text detection
--------------

    text_det_limit_side_len: int
        default: 640

    text_det_limit_type:
        Literal["max", "min"]

        default:
            "max"

    text_det_thresh: float
        default: 0.30
        range: 0.0 -> 1.0

    text_det_box_thresh: float
        default: 0.60
        range: 0.0 -> 1.0

    text_det_unclip_ratio: float
        default: 1.50
        must be > 0


Text recognition
----------------

    text_recognition_batch_size: int
        default: 1
        minimum: 1

    text_rec_score_thresh: float
        default: 0.05
        range: 0.0 -> 1.0


Input safety
------------

    min_image_height: int
        default: 16

    min_image_width: int
        default: 16

    max_image_pixels: int
        default: 20_000_000


============================================================
MAIN USAGE
============================================================

from backend.OCR.fast import FastOCR

ocr = FastOCR()

results = ocr.predict(image)


Hoặc gọi object trực tiếp:

    results = ocr(image)


============================================================
CUSTOM CONFIG
============================================================

from backend.OCR.fast import (
    FastOCR,
    FastOCRConfig,
)

config = FastOCRConfig(
    device="cpu",
    cpu_threads=4,
    text_det_limit_side_len=640,
    text_det_unclip_ratio=1.50,
)

ocr = FastOCR(config)

results = ocr(image)


============================================================
ERRORS
============================================================

FastOCRInputError
-----------------

Input image sai contract.

Ví dụ:

    - không phải numpy.ndarray;
    - dtype không phải uint8;
    - không phải 3 dimensions;
    - không có đúng 3 channels;
    - ảnh quá nhỏ;
    - ảnh vượt max_image_pixels.


FastOCRInitializationError
--------------------------

Không thể khởi tạo PaddleOCR hoặc pretrained model.


FastOCRInferenceError
---------------------

Model đã được khởi tạo nhưng inference thất bại.


============================================================
PIPELINE POSITION
============================================================

Upstream cần cung cấp:

    numpy.ndarray
    uint8
    BGR
    (H, W, 3)

        ↓

    FastOCR

        ↓

    list[PaddleOCR Result]

        ↓

Module phía sau có trách nhiệm đọc:

    rec_texts
    rec_scores
    rec_boxes

và chuyển chúng sang representation tiếp theo của SubVision.


============================================================
REAL TEST
============================================================

Test hiện tại chạy trực tiếp với ảnh thật.

Từ project root:

    python -m backend.OCR.fast.test \
        --image "images/image.png" \
        --output "outputs/fast_ocr_test"

Test thực hiện:

    real image
        ↓
    OpenCV imread
        ↓
    FastOCR initialization
        ↓
    real PaddleOCR inference
        ↓
    rec_texts / rec_scores / rec_boxes
        ↓
    optional visualization

Đồng thời đo:

    - model initialization time;
    - inference time;
    - số text lines nhận diện được.


============================================================
PUBLIC API
============================================================

Thông thường module bên ngoài chỉ cần:

    FastOCR
    FastOCRConfig

Các exception được export để application layer
có thể xử lý lỗi cụ thể.


============================================================
IMPORTANT RULES
============================================================

1. Input luôn là BGR uint8 ndarray.

2. FastOCR không capture hoặc crop ảnh.

3. FastOCR không grouping OCR results.

4. FastOCR không sửa text OCR.

5. FastOCR không dịch.

6. FastOCR trả raw PaddleOCR Result.

7. PaddleOCR pipeline nên được khởi tạo một lần
   rồi tái sử dụng cho nhiều ảnh.

8. Không giả định schema chi tiết hơn của bbox
   nếu chưa có adapter/module khác contract hóa nó.
"""


from __future__ import annotations

from .config import (
    DEFAULT_FAST_OCR_CONFIG,
    FastOCRConfig,
)

from .model import (
    FastOCR,
    FastOCRInferenceError,
    FastOCRInitializationError,
    FastOCRInputError,
)


__all__ = [
    "FastOCR",
    "FastOCRConfig",
    "DEFAULT_FAST_OCR_CONFIG",
    "FastOCRInputError",
    "FastOCRInitializationError",
    "FastOCRInferenceError",
]