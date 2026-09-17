"""
Session Action Buttons
======================

PURPOSE
-------
Package `actions` chỉ chứa action bắt đầu toàn bộ SubVision runtime session.

Public component:

    StartButton
        Chuyển application từ setup/configuration sang runtime session.

Start KHÔNG phải execution mode.

Mental model:

    Setup
        -> Start
        -> Runtime Session

StartButton chỉ phát Qt `clicked` signal.

Nó KHÔNG:
    - validate toàn bộ config;
    - chọn Manual / Auto;
    - gọi BackendPipeline;
    - tạo worker;
    - mở runtime windows;
    - sửa AppState trực tiếp.

USAGE
-----
    from ui.components.actions import StartButton

    start_button = StartButton()
    start_button.clicked.connect(on_start_requested)

BOUNDARY
--------
Toàn bộ logic bắt đầu session thuộc layer ngoài:

    StartButton
        -> clicked
        -> Controller / Application
        -> validate state
        -> create/start runtime session
"""

from __future__ import annotations

from .start_button import StartButton

__all__ = [
    "StartButton",
]
