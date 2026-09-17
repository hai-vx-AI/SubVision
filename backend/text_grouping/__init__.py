"""
TEXT GROUPING
=============

Gom các OCR text box thành dòng và paragraph/text block
dựa hoàn toàn trên geometry.

Public pipeline:

    OCR text + bbox + confidence
        ↓
    OCRTextBox
        ↓
    TextLine
        ↓
    TextGroup


============================================================
PURPOSE
============================================================

TextGrouping chịu trách nhiệm:

    - nhận text + bbox + confidence từ OCR;
    - chuẩn hóa bbox về BBox(x1, y1, x2, y2);
    - loại OCR item không hợp lệ / confidence thấp;
    - gom các word/token thành TextLine;
    - gom các TextLine thành TextGroup;
    - sắp xếp text theo spatial reading order;
    - tạo bbox bao phủ cho line/group;
    - tính average confidence.


Module KHÔNG:

    - chạy OCR;
    - sửa lỗi OCR;
    - dịch;
    - hiểu ngữ nghĩa;
    - thay đổi nội dung word;
    - chuyển coordinate sang screen/global coordinates;
    - giữ session/history giữa nhiều lần gọi.


============================================================
PUBLIC INPUT
============================================================

API chính:

    TextGrouper.group(
        texts=...,
        boxes=...,
        scores=...,
    )


------------------------------------------------------------
texts
------------------------------------------------------------

Type:

    Sequence[str]

Ví dụ:

    [
        "Hello",
        "world",
        "This",
        "is",
        "test",
    ]


Mỗi phần tử tương ứng với một OCR bbox.


------------------------------------------------------------
boxes
------------------------------------------------------------

Type:

    Sequence[
        BBox | Sequence[Any]
    ]


Mỗi box có thể ở một trong các dạng:


1. BBox object:

    BBox(
        x1=10,
        y1=20,
        x2=80,
        y2=40,
    )


2. Axis-aligned sequence:

    [x1, y1, x2, y2]

Ví dụ:

    [10, 20, 80, 40]


3. Polygon:

    [
        [x1, y1],
        [x2, y2],
        [x3, y3],
        [x4, y4],
    ]


Polygon sẽ được chuyển thành axis-aligned BBox:

    x1 = min(all x)
    y1 = min(all y)
    x2 = max(all x)
    y2 = max(all y)


Do đó sau khi normalize,
rotation/orientation chi tiết của polygon không còn được giữ.


------------------------------------------------------------
scores
------------------------------------------------------------

Type:

    Sequence[float] | None


Nếu có:

    len(scores)
    ==
    len(texts)
    ==
    len(boxes)


Mỗi score được chuyển thành:

    float


Confidence hợp lệ:

    0.0 <= confidence <= 1.0


Nếu scores=None:

    confidence = 1.0

cho mọi OCR item.


------------------------------------------------------------
LENGTH CONTRACT
------------------------------------------------------------

Bắt buộc:

    len(texts) == len(boxes)


Nếu scores tồn tại:

    len(scores) == len(texts)


Nếu không:

    ValueError


============================================================
COORDINATE CONTRACT
============================================================

TextGrouping KHÔNG đổi coordinate system.

Nếu input bbox thuộc:

    crop-local coordinates

thì tất cả output BBox cũng thuộc:

    crop-local coordinates.


Nếu input bbox thuộc:

    full-image coordinates

thì output cũng thuộc:

    full-image coordinates.


Module chỉ:

    - normalize representation;
    - union bbox;
    - tính geometry.


Nó KHÔNG biết:

    - vị trí crop trên màn hình;
    - global screen coordinates;
    - DPI scale;
    - monitor coordinates.


============================================================
BBOX MODEL
============================================================

BBox:

    x1: float
    y1: float
    x2: float
    y2: float


Ý nghĩa:

    (x1, y1)
        góc trên-trái

    (x2, y2)
        góc dưới-phải


Điều kiện:

    x2 > x1

    y2 > y1

    tất cả coordinate phải finite.


Properties:

    width: float

    height: float

    area: float

    center_x: float

    center_y: float

    coordinates:
        tuple[
            float,
            float,
            float,
            float,
        ]


Có thể convert sang integer bbox:

    bbox.to_integer_tuple()

Output:

    tuple[int, int, int, int]

Quy tắc:

    x1, y1 -> floor
    x2, y2 -> ceil

để không cắt mất nội dung.


============================================================
INTERMEDIATE MODEL — OCRTextBox
============================================================

Mỗi OCR item được chuẩn hóa thành:

    OCRTextBox


Fields:

    text: str

        OCR text.

        Khi tạo bằng from_raw(),
        text được str(...).strip().


    bbox: BBox

        Bounding box đã normalize.


    confidence: float

        default:
            1.0

        range:
            0.0 -> 1.0


    source_index: int | None

        Index của item trong OCR input ban đầu.

        Khi dùng TextGrouper.make_items():

            source_index = index


Ví dụ:

    OCRTextBox(
        text="Hello",
        bbox=BBox(
            10,
            10,
            60,
            30,
        ),
        confidence=0.98,
        source_index=0,
    )


============================================================
FILTERING
============================================================

Trước khi grouping, OCRTextBox bị loại nếu:

    text.strip() == ""

hoặc:

    confidence
    < config.min_ocr_confidence

hoặc:

    bbox.width
    < config.min_bbox_width

hoặc:

    bbox.height
    < config.min_bbox_height


Default:

    min_ocr_confidence = 0.30

    min_bbox_width = 2.0

    min_bbox_height = 2.0


============================================================
OUTPUT — TextLine
============================================================

Word/token cùng một dòng được gom thành:

    TextLine


Fields:

    words:
        tuple[OCRTextBox, ...]

    bbox:
        BBox

    text:
        str

    average_confidence:
        float


------------------------------------------------------------
words
------------------------------------------------------------

Các OCRTextBox trong line được sort:

    trái -> phải


LƯU Ý:

Field thực tế là:

    line.words

KHÔNG phải:

    line.items


------------------------------------------------------------
bbox
------------------------------------------------------------

BBox bao phủ toàn bộ:

    line.words


------------------------------------------------------------
text
------------------------------------------------------------

Được ghép từ:

    word.text

theo thứ tự trái -> phải.


Separator mặc định:

    " "


Ví dụ:

    ["Hello", "world"]

        ↓

    "Hello world"


------------------------------------------------------------
average_confidence
------------------------------------------------------------

Là trung bình confidence của các word:

    sum(word.confidence)
    /
    len(words)


============================================================
OUTPUT — TextGroup
============================================================

Một paragraph/text block được biểu diễn bằng:

    TextGroup


Fields:

    lines:
        tuple[TextLine, ...]

    bbox:
        BBox

    text:
        str

    average_confidence:
        float


------------------------------------------------------------
lines
------------------------------------------------------------

Các line được sort theo reading order:

    trên -> dưới
    sau đó trái -> phải


------------------------------------------------------------
bbox
------------------------------------------------------------

BBox bao phủ tất cả line trong group.


------------------------------------------------------------
text
------------------------------------------------------------

Ghép:

    line.text

theo reading order.


Separator mặc định:

    " "


Ví dụ:

    line 1:
        "Hello world"

    line 2:
        "This is test"

Output:

    "Hello world This is test"


------------------------------------------------------------
average_confidence
------------------------------------------------------------

Không đơn giản là average của line.

Nó được weighted theo số word trong mỗi line:

    Σ(
        line.average_confidence
        ×
        number_of_words_in_line
    )
    /
    total_words


============================================================
MAIN OUTPUT
============================================================

TextGrouper.group(...)

trả về:

    list[TextGroup]


Ví dụ:

    groups = grouper.group(
        texts=rec_texts,
        boxes=rec_boxes,
        scores=rec_scores,
    )


Sau đó:

    for group in groups:

        print(group.text)

        print(
            group.bbox.coordinates
        )

        print(
            group.average_confidence
        )

        for line in group.lines:

            print(line.text)


============================================================
MAIN USAGE
============================================================

from backend.text_grouping import (
    TextGrouper,
)

grouper = TextGrouper()

groups = grouper.group(
    texts=rec_texts,
    boxes=rec_boxes,
    scores=rec_scores,
)


============================================================
FUNCTIONAL API
============================================================

Nếu không cần giữ TextGrouper instance:

    from backend.text_grouping import (
        group_ocr,
    )

    groups = group_ocr(
        texts=rec_texts,
        boxes=rec_boxes,
        scores=rec_scores,
    )


Input:

    texts:
        Sequence[str]

    boxes:
        Sequence[BBox | Sequence[Any]]

    scores:
        Sequence[float] | None

    config:
        TextGroupingConfig | None


Output:

    list[TextGroup]


============================================================
PADDLEOCR-STYLE INPUT
============================================================

Có API:

    grouper.group_paddle_result(
        result
    )


Input type:

    Mapping[str, Any]


Hỗ trợ trực tiếp:

    {
        "rec_texts": ...,
        "rec_scores": ...,
        "rec_boxes": ...,
    }


hoặc:

    {
        "res": {
            "rec_texts": ...,
            "rec_scores": ...,
            "rec_boxes": ...,
        }
    }


Nếu không có:

    rec_boxes

thì fallback:

    rec_polys


Nếu không có:

    rec_texts

hoặc không có cả:

    rec_boxes / rec_polys

thì output:

    []


============================================================
QUAN TRỌNG — PADDLEOCR RESULT OBJECT
============================================================

group_paddle_result() hiện nhận:

    Mapping[str, Any]

Nó KHÔNG nhận trực tiếp raw PaddleOCR Result object.


Nếu upstream có:

    result: PaddleOCR Result

thì phải lấy dictionary trước, ví dụ:

    payload = result.json

    if callable(payload):
        payload = payload()

    groups = grouper.group_paddle_result(
        payload
    )


Đây là boundary thực tế hiện tại.


============================================================
WORD -> LINE
============================================================

Pipeline:

    OCRTextBox[]
        ↓
    filter
        ↓
    spatial sort
        ↓
    greedy line clustering
        ↓
    TextLine[]


Hai bbox có thể cùng line dựa trên:

    - height ratio;
    - vertical overlap;
    - center-Y distance;
    - horizontal gap.


Default WordToLineConfig:

    max_height_ratio:
        float = 1.45

    min_vertical_overlap_ratio:
        float = 0.50

    max_center_y_distance_ratio:
        float = 0.40

    max_horizontal_gap_ratio:
        float = 2.25


Các distance chủ yếu được normalize theo bbox height,
không dùng pixel threshold cố định.


============================================================
LINE -> PARAGRAPH
============================================================

TextLine được gom thành TextGroup dựa trên:

    - relative height;
    - vertical gap;
    - vertical overlap;
    - horizontal overlap;
    - left edge alignment;
    - right edge alignment;
    - center alignment;
    - consistency của line spacing.


Default LineToParagraphConfig:

    max_height_ratio:
        float = 1.35

    max_vertical_gap_ratio:
        float = 1.20

    max_vertical_overlap_ratio:
        float = 0.20

    min_horizontal_overlap_ratio:
        float = 0.20

    max_left_edge_distance_ratio:
        float = 1.25

    max_right_edge_distance_ratio:
        float = 1.25

    max_center_x_distance_ratio:
        float = 0.28

    max_spacing_deviation_ratio:
        float = 0.60


============================================================
GROUPING ALGORITHM
============================================================

Word -> line:

    greedy clustering


Mỗi OCRTextBox:

    - xét các line hiện tại;
    - kiểm tra can_share_line();
    - nếu nhiều line hợp lệ:
        chọn line có geometry score tốt nhất;
    - nếu không:
        tạo line mới.


Line -> paragraph:

    greedy clustering


Mỗi TextLine:

    - xét dòng cuối của từng group hiện tại;
    - chỉ cho group phát triển từ trên xuống dưới;
    - kiểm tra can_share_paragraph();
    - có thể sử dụng median line spacing của group;
    - chọn candidate group tốt nhất;
    - nếu không:
        tạo group mới.


============================================================
ORDERING
============================================================

Reading order key:

    (
        bbox.center_y,
        bbox.x1,
    )


Trong cùng một line:

    (
        bbox.x1,
        bbox.center_y,
    )


Do đó module có thể thay đổi thứ tự OCR ban đầu
để tạo spatial reading order.


source_index trong OCRTextBox vẫn giữ index gốc
để có thể truy ngược item OCR ban đầu.


============================================================
STATE / LIFETIME
============================================================

TextGrouper giữ:

    config: TextGroupingConfig


Ngoài config, module không giữ state runtime.


Ví dụ:

    grouper = TextGrouper()

    result_1 = grouper.group(...)
    result_2 = grouper.group(...)
    result_3 = grouper.group(...)


Mỗi lần group hoàn toàn độc lập.

Không có:

    - previous text;
    - previous groups;
    - session vocabulary;
    - cache;
    - accumulated OCR state.


Vì vậy có thể coi:

    TextGrouper = stateless processor
                  với immutable configuration.


============================================================
CONFIG
============================================================

TextGroupingConfig:

    min_ocr_confidence: float
        default = 0.30

    min_bbox_width: float
        default = 2.0

    min_bbox_height: float
        default = 2.0

    word_to_line:
        WordToLineConfig

    line_to_paragraph:
        LineToParagraphConfig

    word_separator: str
        default = " "

    line_separator: str
        default = " "


============================================================
CUSTOM CONFIG
============================================================

from backend.text_grouping import (
    TextGrouper,
    TextGroupingConfig,
)

config = TextGroupingConfig(
    min_ocr_confidence=0.40,
    word_separator=" ",
    line_separator="\n",
)

grouper = TextGrouper(
    config=config
)

groups = grouper.group(
    texts=rec_texts,
    boxes=rec_boxes,
    scores=rec_scores,
)


============================================================
GEOMETRY MODELS
============================================================

PairGeometry chứa các metric giữa hai bbox:

    average_height: float
    average_width: float

    height_ratio: float
    width_ratio: float

    horizontal_gap: float
    vertical_gap: float

    horizontal_gap_ratio: float
    vertical_gap_ratio: float

    horizontal_overlap_ratio: float
    vertical_overlap_ratio: float

    center_x_distance_ratio: float
    center_y_distance_ratio: float

    left_edge_distance_ratio: float
    right_edge_distance_ratio: float


Các metric này chủ yếu phục vụ grouping algorithm.


============================================================
PIPELINE POSITION
============================================================

Upstream:

    OCR

cần cung cấp:

    texts
    boxes
    optional scores

        ↓

    TextGrouping

        ↓

    list[TextGroup]

        ↓

Downstream có thể sử dụng:

    group.text
    group.bbox
    group.average_confidence
    group.lines


Ví dụ downstream correction:

    corrected = corrector.correct_text(
        group.text
    )


============================================================
IMPORTANT BOUNDARY
============================================================

TextGrouping input hiện KHÔNG phải:

    list[PaddleOCR Result]


Nó nhận một trong hai dạng:

1.

    texts
    boxes
    scores


2.

    PaddleOCR-style Mapping:

        {
            "rec_texts": ...,
            "rec_scores": ...,
            "rec_boxes": ...,
        }


Do FastOCR / QualityOCR hiện trả:

    list[raw PaddleOCR Result]

nên giữa OCR và TextGrouping hiện vẫn cần một bước:

    raw PaddleOCR Result
        ↓
    result.json
        ↓
    Mapping
        ↓
    TextGrouper.group_paddle_result()


============================================================
IMPORTANT RULES
============================================================

1. TextGrouping chỉ xử lý geometry/layout.

2. Output chính là:

       list[TextGroup]

3. BBox chuẩn:

       BBox(
           x1: float,
           y1: float,
           x2: float,
           y2: float,
       )

4. Coordinate system được giữ nguyên từ input.

5. Polygon được collapse thành axis-aligned bbox.

6. Confidence nằm trong:

       0.0 -> 1.0

7. scores=None nghĩa là confidence=1.0.

8. OCR item dưới confidence threshold bị loại.

9. TextLine.words là field đúng.

10. TextLine và TextGroup đều có bbox + text +
    average_confidence.

11. Grouping sử dụng greedy geometry rules,
    không dùng ML/model.

12. Module không OCR, correction hoặc translation.

13. TextGrouper không giữ history giữa nhiều lần gọi.

14. group_paddle_result() nhận Mapping,
    không nhận raw PaddleOCR Result object.

15. Spatial ordering có thể khác thứ tự OCR ban đầu.
"""


from __future__ import annotations

from .config import (
    DEFAULT_TEXT_GROUPING_CONFIG,
    LineToParagraphConfig,
    TextGroupingConfig,
    WordToLineConfig,
)

from .geometry import (
    BBox,
    BBoxCoordinates,
    PairGeometry,
    calculate_pair_geometry,
    can_share_line,
    can_share_paragraph,
    horizontal_gap,
    horizontal_overlap,
    horizontal_overlap_ratio,
    left_to_right_key,
    median_box_height,
    reading_order_key,
    safe_ratio,
    size_ratio,
    union_boxes,
    vertical_gap,
    vertical_overlap,
    vertical_overlap_ratio,
)

from .grouper import (
    OCRTextBox,
    TextGroup,
    TextGrouper,
    TextLine,
    group_ocr,
    group_paddle_result,
)


__all__ = [
    # Main API
    "TextGrouper",
    "group_ocr",
    "group_paddle_result",

    # Public data models
    "OCRTextBox",
    "TextLine",
    "TextGroup",
    "BBox",

    # Config
    "TextGroupingConfig",
    "WordToLineConfig",
    "LineToParagraphConfig",
    "DEFAULT_TEXT_GROUPING_CONFIG",

    # Geometry models
    "BBoxCoordinates",
    "PairGeometry",

    # Advanced geometry helpers
    "calculate_pair_geometry",
    "can_share_line",
    "can_share_paragraph",
    "safe_ratio",
    "size_ratio",
    "horizontal_gap",
    "vertical_gap",
    "horizontal_overlap",
    "vertical_overlap",
    "horizontal_overlap_ratio",
    "vertical_overlap_ratio",
    "union_boxes",
    "median_box_height",
    "reading_order_key",
    "left_to_right_key",
]