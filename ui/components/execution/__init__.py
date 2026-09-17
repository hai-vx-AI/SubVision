"""
Execution Mode Buttons
======================

PURPOSE
-------
Nhóm các button dùng để chọn CÁCH một SubVision runtime session sẽ chạy.

Public components:

    ManualModeButton
        User chủ động yêu cầu từng processing cycle,
        ví dụ bằng Translate button hoặc phím R.

    AutoModeButton
        Session chạy processing liên tục theo cơ chế automatic / real-time.

Manual và Auto là MODE SELECTION.

StartButton KHÔNG thuộc package này.
Start là action bắt đầu toàn bộ runtime session.

Rule:

    Manual XOR Auto

được enforce bởi state/controller, không phải button.

GPU RULE
--------
Auto mode chỉ có thể được dùng khi application xác nhận GPU phù hợp.

Việc kiểm tra GPU KHÔNG nằm trong AutoModeButton.

Layer ngoài có thể:

    auto_button.setEnabled(gpu_available)

USAGE
-----
    from ui.components.execution import (
        ManualModeButton,
        AutoModeButton,
    )

    manual_button = ManualModeButton()
    auto_button = AutoModeButton()

    manual_button.clicked.connect(on_manual_clicked)
    auto_button.clicked.connect(on_auto_clicked)

    manual_button.set_selected(True)
    auto_button.set_selected(False)

BOUNDARY
--------
Package này không:
    - detect GPU;
    - start pipeline;
    - tạo timer / worker;
    - enforce Manual/Auto exclusivity;
    - biết StartButton;
    - sửa AppState trực tiếp.
"""

from __future__ import annotations

from .auto_mode_button import AutoModeButton
from .manual_mode_button import ManualModeButton

__all__ = [
    "ManualModeButton",
    "AutoModeButton",
]
