"""
Runtime Control Buttons
=======================

PURPOSE
-------
Nhóm các action button dùng SAU KHI SubVision runtime session đã bắt đầu.

Public components:

    TranslateButton
        Yêu cầu một processing / translation cycle mới.

        Trong Manual mode, hành động này tương đương với global hotkey R.

    ShowHideTranslationButton
        Yêu cầu show/hide Vietnamese Translation Overlay.

        Chỉ ảnh hưởng phần tiếng Việt được in lên màn hình.
        Dashboard KHÔNG bị ảnh hưởng.

    StopButton
        Yêu cầu kết thúc runtime session hiện tại.

Các button chỉ là UI component độc lập.
Chúng không tự thực thi runtime behavior.

RUNTIME MODEL
-------------
Session có thể giữ một kết quả hiện tại:

    current_result

Mỗi processing cycle mới:

    old current_result
        -> replace
        -> new current_result

TranslateButton không quản lý result stream.

ShowHideTranslationButton không xóa result.
Nó chỉ phản ánh trạng thái visibility của Translation Overlay.

Dashboard có lifecycle riêng:
    - trong suốt khi passive;
    - interactive khi hover;
    - có thể resize;
    - có nút đóng riêng;
    - không bị Show/Hide Translation tác động.

USAGE
-----
    from ui.components.runtime import (
        TranslateButton,
        ShowHideTranslationButton,
        StopButton,
    )

    translate_button = TranslateButton()
    visibility_button = ShowHideTranslationButton()
    stop_button = StopButton()

    translate_button.clicked.connect(on_translate_requested)
    visibility_button.clicked.connect(on_toggle_translation_requested)
    stop_button.clicked.connect(on_stop_requested)

    # External layer owns actual overlay visibility:
    visibility_button.set_translation_visible(True)

BOUNDARY
--------
Package này không:
    - chạy BackendPipeline;
    - quản lý current_result;
    - tạo/dừng worker;
    - implement global keyboard shortcut R hoặc Tab;
    - show/hide TranslationOverlay trực tiếp;
    - show/hide Dashboard;
    - sửa AppState trực tiếp.
"""

from __future__ import annotations

from .show_hide_translation_button import ShowHideTranslationButton
from .stop_button import StopButton
from .translate_button import TranslateButton

__all__ = [
    "TranslateButton",
    "ShowHideTranslationButton",
    "StopButton",
]
