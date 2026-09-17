"""
SubVision UI Functions
======================

PURPOSE
-------
Package `ui.functions` chứa các UI unit có behavior cụ thể.

Khác với `ui.components`, package này không chỉ chứa button đơn lẻ.

Các module ở đây là những phần UI hoàn chỉnh hơn:

    - chọn vùng màn hình;
    - hiển thị translation overlay;
    - hiển thị vocabulary dashboard;
    - hiển thị runtime control panel.

Mental model:

    ui.components
        -> các button độc lập

    ui.functions
        -> các UI function / interactive surface độc lập

Các module trong `ui.functions` có thể có local UI behavior riêng
như drag, resize, hover, show/hide hoặc phát signal.

Nhưng chúng KHÔNG sở hữu application state, KHÔNG gọi backend trực tiếp
và KHÔNG điều phối toàn bộ ứng dụng.


======================================================================
1. REGION SELECTOR
======================================================================

FILE
----
    selector.py

PUBLIC CLASS
------------
    RegionSelector01

PURPOSE
-------
Cho phép user dùng chuột để chọn một vùng trên desktop.

Output chính là global desktop coordinates:

    x1
    y1
    x2
    y2

Public signals:

    region_selected(int, int, int, int)
        Phát ra khi user chọn xong một vùng hợp lệ.

    selection_cancelled()
        Phát ra khi user hủy selection.

Public control methods:

    start_selection()
        Mở selector trên toàn virtual desktop và bắt đầu selection mới.

    retry_selection()
        Reset selection nhưng giữ selector mở để user chọn lại.

    finish_selection()
        Kết thúc selection và hide selector.

Example:

    from ui.functions import RegionSelector01

    selector = RegionSelector01()

    selector.region_selected.connect(on_region_selected)
    selector.selection_cancelled.connect(on_region_cancelled)

    selector.start_selection()

    def on_region_selected(
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        ...

BOUNDARY
--------
RegionSelector01 chỉ chịu trách nhiệm UI selection.

Nó KHÔNG:
    - capture screenshot;
    - gọi OCR;
    - gọi backend;
    - lưu region vào AppState;
    - tự quyết định candidate region có được application chấp nhận hay không.

Application/controller layer quyết định:

    accepted
        -> selector.finish_selection()

    rejected
        -> selector.retry_selection()


======================================================================
2. TRANSLATION OVERLAY
======================================================================

FILE
----
    overlay.py

PUBLIC TYPES
------------
    OverlayTextItem
    TranslationOverlay04

PURPOSE
-------
Hiển thị Vietnamese translation trực tiếp lên vùng màn hình đã chọn.

Overlay là click-through UI surface.
Nó chỉ render text tại các bounding box đã được tính sẵn.

OverlayTextItem:

    OverlayTextItem(
        x1=...,
        y1=...,
        x2=...,
        y2=...,
        text="..."
    )

Coordinates của OverlayTextItem là GLOBAL screen coordinates.

Public API:

    overlay.set_items(
        screen_region=(x1, y1, x2, y2),
        items=[...],
    )

    overlay.show_overlay()
    overlay.hide_overlay()
    overlay.clear()

Example:

    from ui.functions import (
        OverlayTextItem,
        TranslationOverlay04,
    )

    overlay = TranslationOverlay04()

    overlay.set_items(
        screen_region=(100, 100, 1000, 700),
        items=[
            OverlayTextItem(
                x1=150,
                y1=500,
                x2=700,
                y2=550,
                text="Đây là phụ đề tiếng Việt.",
            ),
        ],
    )

    overlay.show_overlay()

Visibility:

    overlay.show_overlay()
        -> hiển thị translation overlay.

    overlay.hide_overlay()
        -> ẩn translation overlay.

Việc hide overlay không xóa result hiện tại.
Application có thể show lại cùng result sau đó.

IMPORTANT
---------
Show/Hide Translation chỉ áp dụng cho TranslationOverlay04.

Dashboard KHÔNG bị ảnh hưởng.

BOUNDARY
--------
TranslationOverlay04 chỉ render.

Nó KHÔNG:
    - OCR;
    - translate;
    - grouping;
    - map backend local bbox sang global screen coordinates;
    - quyết định khi nào translation được show;
    - biết Dashboard;
    - biết RuntimeControls;
    - quản lý current_result.


======================================================================
3. DASHBOARD
======================================================================

FILE
----
    dashboard.py

PUBLIC TYPES
------------
    DashboardEntryView
    DictionaryDashboard03

PURPOSE
-------
Hiển thị vocabulary dashboard độc lập với Translation Overlay.

Mỗi vocabulary entry được render theo hai cột:

    LEFT COLUMN                 RIGHT COLUMN

    machine learning            • học máy
    /məˈʃiːn ˈlɜːnɪŋ/          • máy học

Left column:
    - term;
    - IPA ngay bên dưới term.

Right column:
    - danh sách meanings.

Dashboard không hiển thị backend `entry_type`
như WORD / PHRASE.

DashboardEntryView:

    DashboardEntryView(
        term="machine learning",
        meanings=(
            "học máy",
            "máy học",
        ),
        ipas=(
            "/məˈʃiːn ˈlɜːnɪŋ/",
        ),
    )

Nếu không có IPA:

    ipas=()

thì UI bỏ dòng IPA.

Public API:

    dashboard.set_entries(entries)
        Replace toàn bộ vocabulary snapshot hiện tại.

    dashboard.clear_entries()
        Xóa toàn bộ entry đang render.

    dashboard.show_dashboard()
        Show và raise Dashboard window.

    dashboard.hide_dashboard()
        Hide Dashboard window.

Example:

    from ui.functions import (
        DashboardEntryView,
        DictionaryDashboard03,
    )

    dashboard = DictionaryDashboard03()

    dashboard.set_entries(
        [
            DashboardEntryView(
                term="machine learning",
                meanings=(
                    "học máy",
                    "máy học",
                ),
                ipas=(
                    "/məˈʃiːn ˈlɜːnɪŋ/",
                ),
            ),
            DashboardEntryView(
                term="model",
                meanings=(
                    "mô hình",
                ),
                ipas=(
                    "/ˈmɒdəl/",
                ),
            ),
        ]
    )

    dashboard.show_dashboard()

UI behavior hiện tại:

    Passive:
        - transparent;
        - text hiển thị trực tiếp;
        - header ẩn;
        - scrollbar ẩn;
        - resize grip ẩn.

    Hover / Interactive:
        - background hiện;
        - header hiện;
        - scrollbar hiện khi cần;
        - resize grip hiện.

Dashboard có local behavior:
    - drag;
    - resize;
    - scroll;
    - hover interactive mode.

Dashboard visibility độc lập với Translation Overlay.

Ví dụ:

    Translation Overlay = hidden
    Dashboard = visible

là hợp lệ.

BACKEND MAPPING
---------------
Dashboard KHÔNG import backend DashboardEntry.

Application/controller layer convert:

    backend DashboardEntry
        ->
    DashboardEntryView
        ->
    dashboard.set_entries(...)

Conceptual mapping:

    DashboardEntryView(
        term=backend_entry.term,
        meanings=backend_entry.meanings,
        ipas=backend_entry.ipas,
    )

Nếu backend có `entry_type`, UI bỏ qua field đó.

BOUNDARY
--------
Dashboard KHÔNG:
    - chạy DictionaryTranslator;
    - extract vocabulary;
    - gọi backend;
    - biết AppState;
    - biết Controller;
    - phụ thuộc TranslationOverlay visibility;
    - tự quyết định khi nào feature Dashboard được bật.


======================================================================
4. RUNTIME CONTROLS
======================================================================

FILE
----
    controls.py

PUBLIC CLASS
------------
    RuntimeControls04

PURPOSE
-------
Floating control window dùng trong một SubVision runtime session.

Runtime controls đại diện cho ba runtime actions:

    Translate
    Show / Hide Translation
    Stop

Signals:

    translate_requested
        User yêu cầu một processing / translation cycle mới.

    toggle_requested
        User yêu cầu toggle Vietnamese Translation Overlay visibility.

    stop_requested
        User yêu cầu kết thúc runtime session.

Example:

    from ui.functions import RuntimeControls04

    controls = RuntimeControls04()

    controls.translate_requested.connect(on_translate_requested)
    controls.toggle_requested.connect(on_toggle_requested)
    controls.stop_requested.connect(on_stop_requested)

    controls.show()

MODE
----
    controls.set_mode("manual")
        Translate button được hiển thị.

    controls.set_mode("auto")
        Translate button được ẩn vì Auto mode tự chạy processing liên tục.

TRANSLATION VISIBILITY
----------------------
External layer sở hữu actual Translation Overlay visibility.

Sau khi visibility thay đổi:

    controls.set_translation_visible(True)

button hiển thị:

    Hide Translation (Tab)

và:

    controls.set_translation_visible(False)

button hiển thị:

    Show Translation (Tab)

Method này chỉ cập nhật UI label.
Nó KHÔNG show/hide TranslationOverlay trực tiếp.

PIPELINE RUNNING STATE
----------------------
Trong Manual mode, khi một processing cycle đang chạy:

    controls.set_pipeline_running(True)

Translate button bị disable.

Khi xong:

    controls.set_pipeline_running(False)

Translate button được enable lại.

STATUS
------
Có thể cập nhật status:

    controls.set_status("Ready")
    controls.set_status("Translating...")
    controls.set_status("Error")

BOUNDARY
--------
RuntimeControls04 KHÔNG:
    - chạy BackendPipeline;
    - quản lý current_result;
    - quản lý worker;
    - tự show/hide TranslationOverlay;
    - tự show/hide Dashboard;
    - implement application state;
    - enforce feature rules.


======================================================================
5. EXPECTED RUNTIME RELATIONSHIP
======================================================================

Các function không nên điều khiển trực tiếp lẫn nhau.

Expected architecture:

    RuntimeControls04
        |
        | signal
        v
    Controller / Runtime Coordinator
        |
        +-------------------------------+
        |                               |
        v                               v
    Backend Pipeline             TranslationOverlay04
        |
        v
    current_result
        |
        +-------------------------------+
        |                               |
        v                               v
    Translation Overlay          DictionaryDashboard03

Translate flow:

    User
        -> Translate
        -> RuntimeControls04.translate_requested
        -> Controller
        -> BackendPipeline
        -> replace current_result
        -> update Overlay
        -> update Dashboard

Show/Hide flow:

    User
        -> Show/Hide
        -> RuntimeControls04.toggle_requested
        -> Controller
        -> TranslationOverlay04.show_overlay()
           OR
           TranslationOverlay04.hide_overlay()

Dashboard không bị tác động.

Stop flow:

    User
        -> Stop
        -> RuntimeControls04.stop_requested
        -> Controller
        -> stop runtime session


======================================================================
6. PACKAGE BOUNDARY
======================================================================

`ui.functions` được phép chứa:
    - QWidget / QFrame UI;
    - local mouse behavior;
    - drag;
    - resize;
    - hover;
    - scroll;
    - local show/hide methods;
    - Qt signals;
    - UI-neutral view models.

`ui.functions` không được chứa:
    - BackendPipeline orchestration;
    - OCR execution;
    - translation execution;
    - application state;
    - feature-selection rules;
    - GPU detection;
    - runtime scheduling;
    - worker ownership;
    - business logic giữa các function.


======================================================================
7. PUBLIC IMPORTS
======================================================================

Code bên ngoài nên import từ package boundary:

    from ui.functions import (
        DashboardEntryView,
        DictionaryDashboard03,
        OverlayTextItem,
        RegionSelector01,
        RuntimeControls04,
        TranslationOverlay04,
    )

thay vì import sâu từ từng module.

Internal helper classes không được export.


======================================================================
GOLDEN RULE
======================================================================

`ui.functions` chứa UI behavior hoàn chỉnh nhưng vẫn là UI-only.

Mỗi function:
    - tự quản lý local UI behavior của chính nó;
    - expose signal hoặc public UI API;
    - không sở hữu application state;
    - không gọi backend;
    - không điều phối function khác.

Controller / application layer là nơi kết nối chúng với nhau.
"""

from __future__ import annotations

from .controls import RuntimeControls04
from .dashboard import DashboardEntryView, DictionaryDashboard03
from .overlay import OverlayTextItem, TranslationOverlay04
from .selector import RegionSelector01

__all__ = [
    "RegionSelector01",
    "OverlayTextItem",
    "TranslationOverlay04",
    "DashboardEntryView",
    "DictionaryDashboard03",
    "RuntimeControls04",
]
