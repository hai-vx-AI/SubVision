"""
Capture Buttons
===============

PURPOSE
-------
Nhóm các button dùng để chọn phạm vi màn hình mà SubVision sẽ xử lý.

Public components:

    FullscreenButton
        Chọn toàn bộ màn hình làm capture area.

    SelectRegionButton
        Yêu cầu người dùng chọn một vùng màn hình.

Các button trong package này chỉ là UI component độc lập.
Chúng chỉ phát Qt `clicked` signal và hiển thị chính mình.

Chúng KHÔNG:
    - tự tạo RegionSelector;
    - lưu region;
    - sửa AppState;
    - gọi Controller;
    - gọi backend.

USAGE
-----
    from ui.components.capture import (
        FullscreenButton,
        SelectRegionButton,
    )

    fullscreen_button = FullscreenButton()
    select_region_button = SelectRegionButton()

    fullscreen_button.clicked.connect(on_fullscreen_requested)
    select_region_button.clicked.connect(on_region_requested)

BOUNDARY
--------
Quan hệ mong muốn:

    Button
        -> clicked signal
        -> Controller / Binder
        -> region logic
        -> state

Button không biết các bước phía sau.
"""

from __future__ import annotations

from .fullscreen_button import FullscreenButton
from .select_region_button import SelectRegionButton

__all__ = [
    "FullscreenButton",
    "SelectRegionButton",
]
