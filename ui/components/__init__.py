"""
SubVision UI Components
=======================

PURPOSE
-------
Package `ui.components` chỉ chứa các UI component dạng button.

Mỗi button là một component độc lập.

Components KHÔNG điều phối ứng dụng, KHÔNG quản lý quan hệ giữa các button,
KHÔNG biết business state và KHÔNG gọi backend.

Ví dụ:

    DictionaryButton
    LanguageModelButton
    DashboardButton
    FastOCRButton
    QualityOCRButton
    FullscreenButton
    SelectRegionButton
    ManualModeButton
    AutoModeButton
    StartButton

Package này chỉ trả lời hai câu hỏi:

1. Button được dựng như thế nào?
2. Button phải trông như thế nào khi state của CHÍNH NÓ thay đổi?


======================================================================
1. BUTTON PHẢI ĐỘC LẬP
======================================================================

Một button chỉ được biết chính nó.

Ví dụ `DictionaryButton` được phép biết:

    self._selected
    self.set_selected(...)
    self._build_ui()
    self._apply_visual_state()

Nhưng KHÔNG được biết:

    LanguageModelButton
    DashboardButton
    AppState
    Controller
    BackendPipeline
    PipelineConfig

Không được viết logic kiểu:

    if dictionary selected:
        language_model_button.set_selected(False)

Không được truyền button khác vào constructor.

Không được giữ reference tới button khác.

Không được import button khác chỉ để điều khiển trạng thái của nó.

Quan hệ giữa nhiều button phải do module bên ngoài chịu trách nhiệm.


======================================================================
2. LOCAL STATE CHỈ LÀ VISUAL STATE
======================================================================

Button có thể giữ local UI state để biết nó phải hiển thị như thế nào.

Ví dụ:

    self._selected: bool = False

Public API tối thiểu có thể là:

    button.set_selected(True)
    button.set_selected(False)

Ý nghĩa:

    True
        button hiển thị trạng thái được chọn / active.

    False
        button hiển thị trạng thái không được chọn / inactive.

Local state này KHÔNG phải application state.

Nó không quyết định feature nào thực sự đang bật trong backend.

Ví dụ:

    dictionary_button.set_selected(True)

chỉ có nghĩa:

    "hãy vẽ Dictionary như đang được chọn"

Nó KHÔNG có nghĩa:

    "hãy bật dictionary translation trong backend"


======================================================================
3. BUTTON KHÔNG TỰ GIẢI QUYẾT QUAN HỆ VỚI BUTTON KHÁC
======================================================================

Ví dụ business rule:

    Dictionary và Language Model không được bật cùng lúc.

Rule này KHÔNG thuộc `components`.

Khi user click Dictionary, một module bên ngoài có thể quyết định:

    Dictionary     -> selected
    Language Model -> unselected

Components chỉ thực hiện:

    dictionary_button.set_selected(True)
    language_model_button.set_selected(False)

Tương tự, rule:

    ít nhất một trong
        Dictionary
        Language Model
        Dashboard
    phải được bật

cũng KHÔNG thuộc `components`.

Components không validate tổ hợp button.


======================================================================
4. CLICK CHỈ PHÁT RA UI EVENT
======================================================================

Button không nên tự thay đổi application state khi được click.

QPushButton có thể phát signal `clicked` bình thường.

Module bên ngoài sẽ:

    nhận clicked
        ->
    cập nhật state
        ->
    áp rule giữa các feature
        ->
    yêu cầu từng button cập nhật visual state

Luồng mong muốn:

    User click Dictionary
            |
            v
        clicked signal
            |
            v
    Controller / Binder / Coordinator
            |
            +---- update application state
            |
            +---- dictionary_button.set_selected(True)
            |
            +---- language_model_button.set_selected(False)

Không đặt đoạn điều phối này bên trong `DictionaryButton`.


======================================================================
5. BUILD_UI PHẢI TÁCH RIÊNG
======================================================================

Mọi button phải tách phần dựng giao diện cơ bản vào:

    _build_ui()

Ví dụ:

    class DictionaryButton(QPushButton):

        def __init__(self, parent=None):
            super().__init__(parent)

            self._selected = False

            self._build_ui()
            self._apply_visual_state()

        def _build_ui(self) -> None:
            self.setText("Dictionary")
            self.setObjectName("dictionaryButton")
            self.setMinimumWidth(150)

Mục tiêu:

    muốn đổi text
    muốn đổi kích thước
    muốn thêm icon
    muốn đổi tooltip
    muốn chỉnh objectName
    muốn thay cấu trúc visual

thì tập trung sửa ở `_build_ui()`.

Không rải code dựng UI khắp constructor hoặc các method xử lý state.


======================================================================
6. VISUAL STATE PHẢI TÁCH RIÊNG
======================================================================

Phần thay đổi ngoại hình theo state phải được đặt riêng, ví dụ:

    _apply_visual_state()

Public method:

    set_selected(...)

chỉ cập nhật local visual state rồi gọi:

    _apply_visual_state()

Ví dụ:

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._apply_visual_state()

    def _apply_visual_state(self) -> None:
        ...

Không đặt business rule vào `_apply_visual_state()`.

Method này chỉ được thay đổi ngoại hình của chính widget:

    opacity
    stylesheet property
    icon
    border
    background
    text style
    checked appearance

Tuyệt đối không sửa widget khác.


======================================================================
7. BUILD VÀ STATE LÀ HAI VIỆC KHÁC NHAU
======================================================================

Quy ước:

    _build_ui()
        tạo ngoại hình/cấu hình cơ bản của button.

    _apply_visual_state()
        áp ngoại hình theo local state hiện tại.

    set_selected(...)
        public API để module bên ngoài yêu cầu đổi visual state.

Không trộn ba trách nhiệm này.


======================================================================
8. COMPONENTS KHÔNG IMPORT BACKEND
======================================================================

Trong `ui.components` không được import:

    BackendPipeline
    PipelineConfig
    PipelineResult

hoặc bất kỳ module runtime/backend nào.

Button không được biết:

    OCR chạy thế nào
    translation chạy thế nào
    dashboard extract thế nào
    pipeline config được tạo thế nào

Ví dụ `FastOCRButton` chỉ hiển thị lựa chọn "Fast OCR".

Nó không được khởi tạo `FastOCR`.

Ví dụ `DashboardButton` chỉ hiển thị lựa chọn Dashboard.

Nó không được khởi tạo Dashboard window hoặc DashboardExtractor.


======================================================================
9. COMPONENTS KHÔNG IMPORT APP STATE / CONTROLLER
======================================================================

Không được có:

    from ...state import AppState
    from ...controller import Controller

trong các button.

Dependency direction phải là:

    Controller / Binder
            |
            v
        Components

không phải:

        Components
            |
            v
        Controller


======================================================================
10. MỘT BUTTON KHÔNG ĐƯỢC SHOW/HIDE BUTTON KHÁC
======================================================================

Ví dụ cấm:

    class DictionaryButton(...):

        def on_clicked(...):
            dashboard_button.show()
            language_model_button.hide()

Show/hide section hoặc button khác là trách nhiệm của parent UI hoặc
controller/binder.

Button chỉ được show/hide/chỉnh state của CHÍNH NÓ nếu thực sự cần.


======================================================================
11. KHÔNG ĐẶT FEATURE RULE TRONG COMPONENT
======================================================================

Các rule sau đều nằm ngoài `components`:

    Dictionary XOR Language Model

    ít nhất một trong:
        Dictionary
        Language Model
        Dashboard

    Fast OCR XOR Quality OCR

    Manual XOR Auto

    Dashboard có được hiển thị hay không

    Translation overlay có được hiển thị hay không

    Start có được enable hay không

Components chỉ cung cấp các primitive visual để module khác thể hiện các rule đó.


======================================================================
12. KHÔNG TỰ GỌI PIPELINE KHI CLICK
======================================================================

Cấm:

    self.clicked.connect(self._run_backend)

Cấm button tự:

    OCR
    translate
    open pipeline
    modify state
    start worker
    stop worker

Button chỉ phát UI event.

Execution thuộc layer khác.


======================================================================
13. PUBLIC API CỦA BUTTON PHẢI NHỎ
======================================================================

Ưu tiên API đơn giản.

Ví dụ selectable button:

    set_selected(selected: bool)

Có thể có thêm khi thực sự cần:

    set_busy(busy: bool)
    set_available(available: bool)

Nhưng không tạo các API mang business semantics như:

    activate_dictionary_mode()
    disable_language_model()
    start_translation_pipeline()

Business semantics thuộc controller/state/application layer.


======================================================================
14. OBJECT NAME PHẢI ỔN ĐỊNH
======================================================================

Mỗi button phải có `objectName` rõ ràng và ổn định.

Ví dụ:

    dictionaryButton
    languageModelButton
    dashboardButton
    fastOCRButton
    qualityOCRButton
    fullscreenButton
    selectRegionButton
    manualModeButton
    autoModeButton
    startButton

`objectName` là hook để stylesheet/theme bên ngoài có thể làm UI đẹp hơn
mà không phải sửa logic của component.


======================================================================
15. KHÔNG HARD-CODE TOÀN BỘ THEME VÀO LOGIC
======================================================================

Component có thể chứa visual behavior tối thiểu cần cho chính nó.

Nhưng màu sắc/theme tổng thể nên ưu tiên được áp từ stylesheet/theme chung
thông qua `objectName`, property hoặc widget state.

Mục tiêu là sau này có thể đổi toàn bộ giao diện SubVision mà không phải sửa
controller hoặc business logic.


======================================================================
16. SELECTED KHÁC DISABLED
======================================================================

Không được đánh đồng:

    unselected
    disabled

Unselected:

    button vẫn click được;
    chỉ có visual nhẹ hơn selected.

Disabled:

    button thực sự không thể tương tác.

Hai trạng thái phải có semantics khác nhau.

Controller/binder quyết định khi nào cần disabled.


======================================================================
17. COMPONENT KHÔNG PHẢI SOURCE OF TRUTH
======================================================================

Không đọc trạng thái ứng dụng bằng cách hỏi button:

    if dictionary_button._selected:
        ...

Application state phải nằm ở layer state.

Component chỉ là projection của state ra màn hình.

Luồng chuẩn:

    AppState
       |
       v
    Controller / Binder
       |
       v
    Button visual state

Không dùng:

    Button visual state
       |
       v
    suy ra AppState


======================================================================
18. MỖI FILE NÊN CÓ MỘT TRÁCH NHIỆM RÕ RÀNG
======================================================================

Ưu tiên:

    dictionary_button.py
        -> DictionaryButton

    language_model_button.py
        -> LanguageModelButton

    dashboard_button.py
        -> DashboardButton

    fast_ocr_button.py
        -> FastOCRButton

    quality_ocr_button.py
        -> QualityOCRButton

Các button rất nhỏ và cùng một nhóm chức năng có thể dùng chung một visual
base class nếu sau này thật sự cần, nhưng base class cũng chỉ được chứa
behavior UI dùng chung.

Base class KHÔNG được chứa business rule giữa các button.


======================================================================
19. COMPONENTS PACKAGE BOUNDARY
======================================================================

Code bên ngoài được phép:

    tạo button
    connect signal
    gọi public visual methods

Ví dụ:

    button = DictionaryButton()

    button.clicked.connect(...)

    button.set_selected(True)

Code bên ngoài không nên phụ thuộc:

    _selected
    _build_ui()
    _apply_visual_state()

Các tên bắt đầu bằng `_` là implementation detail của component.


======================================================================
20. NGUYÊN TẮC TÓM TẮT
======================================================================

Một component button phải có mental model:

    INPUT từ bên ngoài
        |
        +---- user interaction thông qua Qt signal
        |
        +---- visual command thông qua public method
                    |
                    v
              Button Component
                    |
              chỉ sửa chính nó
                    |
                    v
                 Visual

Button KHÔNG có đường:

    Button -> Button khác
    Button -> AppState
    Button -> Controller
    Button -> Backend
    Button -> Pipeline
    Button -> Window khác


======================================================================
GOLDEN RULE
======================================================================

`ui.components` chỉ chứa các button độc lập.

Mỗi button:

    - tự build chính nó;
    - tự render visual state của chính nó;
    - phát Qt event khi user tương tác;
    - nhận visual state từ bên ngoài.

Mỗi button KHÔNG:

    - biết button khác;
    - thực thi rule giữa các button;
    - sở hữu application state;
    - gọi controller;
    - gọi backend;
    - chạy pipeline;
    - điều khiển screen, overlay, dashboard hoặc runtime window.

Quan hệ giữa các component luôn được giải quyết ở layer bên ngoài.
"""

# Deliberately no imports / __all__ yet.
# This file currently defines the architectural contract for ui.components.
