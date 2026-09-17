"""
OCR Selection Buttons
=====================

PURPOSE
-------
Nhóm các button dùng để chọn OCR mode cho một SubVision session.

Public components:

    FastOCRButton
        Lựa chọn OCR mode "fast".

    QualityOCRButton
        Lựa chọn OCR mode "quality".

Hai button chỉ giữ visual selected state của chính mình.

Rule:

    Fast OCR XOR Quality OCR

KHÔNG được xử lý trong package này.

Module bên ngoài sẽ cập nhật application state rồi phản chiếu xuống UI:

    fast_button.set_selected(True)
    quality_button.set_selected(False)

USAGE
-----
    from ui.components.ocr import (
        FastOCRButton,
        QualityOCRButton,
    )

    fast_button = FastOCRButton()
    quality_button = QualityOCRButton()

    fast_button.clicked.connect(on_fast_clicked)
    quality_button.clicked.connect(on_quality_clicked)

BOUNDARY
--------
Các button không được:
    - biết button còn lại;
    - enforce exclusivity;
    - import FastOCR / QualityOCR backend;
    - sửa AppState;
    - gọi Controller.
"""

from __future__ import annotations

from .fast_ocr_button import FastOCRButton
from .quality_ocr_button import QualityOCRButton

__all__ = [
    "FastOCRButton",
    "QualityOCRButton",
]
