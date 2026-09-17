"""
Feature Buttons
===============

PURPOSE
-------
Nhóm các feature chính mà người dùng muốn SubVision tạo ra trong một run.

Public components:

    DictionaryButton
        Chọn Dictionary translation.

    LanguageModelButton
        Chọn Language Model translation.

    DashboardButton
        Chọn Vocabulary Dashboard.

Ba button ngang hàng và độc lập.

Application rules hiện tại:

    Valid:
        Dictionary
        Language Model
        Dashboard
        Dictionary + Dashboard
        Language Model + Dashboard

    Invalid:
        không feature nào được chọn
        Dictionary + Language Model

Các rule này chỉ mô tả contract.
Button KHÔNG được tự enforce chúng.

USAGE
-----
    from ui.components.features import (
        DictionaryButton,
        LanguageModelButton,
        DashboardButton,
    )

    dictionary_button = DictionaryButton()
    language_model_button = LanguageModelButton()
    dashboard_button = DashboardButton()

    dictionary_button.clicked.connect(on_dictionary_clicked)
    language_model_button.clicked.connect(on_language_model_clicked)
    dashboard_button.clicked.connect(on_dashboard_clicked)

    # Sau khi state được cập nhật:
    dictionary_button.set_selected(True)
    language_model_button.set_selected(False)
    dashboard_button.set_selected(True)

BOUNDARY
--------
Không button nào được:
    - điều khiển button khác;
    - enforce feature combination;
    - mở Dashboard window;
    - gọi translator;
    - gọi BackendPipeline;
    - sở hữu application state.
"""

from __future__ import annotations

from .dashboard_button import DashboardButton
from .dictionary_button import DictionaryButton
from .language_model_button import LanguageModelButton

__all__ = [
    "DictionaryButton",
    "LanguageModelButton",
    "DashboardButton",
]
