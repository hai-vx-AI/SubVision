from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QFont, QFontMetrics, QGuiApplication
from PyQt6.QtWidgets import QLabel, QWidget


@dataclass(frozen=True, slots=True)
class OverlayTextItem:
    """Vietnamese text with a bbox in global screen coordinates."""

    x1: int
    y1: int
    x2: int
    y2: int
    text: str


class TranslationOverlay04(QWidget):
    """
    Click-through translation overlay.

    Contract
    --------
    - ``screen_region`` uses global screen coordinates.
    - every ``OverlayTextItem`` also uses global screen coordinates.
    - this widget only renders; OCR, translation and local->global mapping
      belong to other layers.

    The current SubVision desktop UI is expected to run through Qt's
    ``xcb`` platform (XWayland on a Wayland session) so absolute top-level
    positioning is available for this overlay.
    """

    MIN_FONT_PX = 6
    MAX_FONT_PX = 24

    HORIZONTAL_PADDING = 3
    VERTICAL_PADDING = 1

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._labels: list[QLabel] = []

        self._build_window()

    # ==========================================================
    # WINDOW
    # ==========================================================

    def _build_window(self) -> None:
        self.setWindowTitle(
            "SubVision Translation Overlay"
        )

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )

        # On X11/XWayland this turns the overlay into an override-redirect
        # style window, preventing the window manager from repositioning it.
        if QGuiApplication.platformName() == "xcb":
            flags |= Qt.WindowType.X11BypassWindowManagerHint

        try:
            flags |= Qt.WindowType.WindowTransparentForInput
        except AttributeError:
            pass

        self.setWindowFlags(flags)

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_NoSystemBackground,
            True,
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )

        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def set_items(
        self,
        *,
        screen_region: tuple[int, int, int, int],
        items: list[OverlayTextItem],
    ) -> None:
        """Replace the current overlay content."""

        self.clear()

        (
            region_x1,
            region_y1,
            region_x2,
            region_y2,
        ) = screen_region

        region_width = region_x2 - region_x1
        region_height = region_y2 - region_y1

        if region_width <= 0 or region_height <= 0:
            raise ValueError(
                "screen_region must have positive width and height."
            )

        # With xcb/XWayland this is an absolute screen position.
        self.setGeometry(
            region_x1,
            region_y1,
            region_width,
            region_height,
        )

        for item in items:
            text = item.text.strip()

            if not text:
                continue

            # Clamp to the selected region. Normally backend bboxes are
            # already inside it; this is only numerical/rendering safety.
            global_x1 = max(region_x1, item.x1)
            global_y1 = max(region_y1, item.y1)
            global_x2 = min(region_x2, item.x2)
            global_y2 = min(region_y2, item.y2)

            if global_x2 <= global_x1 or global_y2 <= global_y1:
                continue

            local_x = global_x1 - region_x1
            local_y = global_y1 - region_y1
            width = global_x2 - global_x1
            height = global_y2 - global_y1

            self._create_label(
                text=text,
                x=local_x,
                y=local_y,
                width=width,
                height=height,
            )

    def clear(self) -> None:
        for label in self._labels:
            label.hide()
            label.deleteLater()

        self._labels.clear()

    def show_overlay(self) -> None:
        self.show()
        self.raise_()

    def hide_overlay(self) -> None:
        self.hide()

    # ==========================================================
    # LABEL RENDERING
    # ==========================================================

    def _create_label(
        self,
        *,
        text: str,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        label = QLabel(text, self)

        label.setTextFormat(
            Qt.TextFormat.PlainText
        )
        label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        label.setWordWrap(True)
        label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        label.setGeometry(
            x,
            y,
            width,
            height,
        )

        font = QFont(self.font())
        font.setBold(True)
        label.setFont(font)

        self._fit_font_to_bbox(
            label=label,
            text=text,
            width=width,
            height=height,
        )

        # Only each translated text box is dark. The parent overlay itself
        # remains fully transparent.
        label.setStyleSheet(
            """
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 215);
                border-radius: 3px;
                padding: 1px 3px;
            }
            """
        )

        label.show()
        self._labels.append(label)

    def _fit_font_to_bbox(
        self,
        *,
        label: QLabel,
        text: str,
        width: int,
        height: int,
    ) -> None:
        """Choose the largest font that fits inside the bbox."""

        available_width = max(
            1,
            width - 2 * self.HORIZONTAL_PADDING,
        )
        available_height = max(
            1,
            height - 2 * self.VERTICAL_PADDING,
        )

        low = self.MIN_FONT_PX
        high = self.MAX_FONT_PX
        best = self.MIN_FONT_PX

        flags = (
            Qt.AlignmentFlag.AlignCenter.value
            | Qt.TextFlag.TextWordWrap.value
        )

        while low <= high:
            size = (low + high) // 2

            font = QFont(label.font())
            font.setPixelSize(size)

            metrics = QFontMetrics(font)
            text_rect = metrics.boundingRect(
                QRect(
                    0,
                    0,
                    available_width,
                    100_000,
                ),
                flags,
                text,
            )

            if (
                text_rect.width() <= available_width
                and text_rect.height() <= available_height
            ):
                best = size
                low = size + 1
            else:
                high = size - 1

        font = QFont(label.font())
        font.setPixelSize(best)
        label.setFont(font)
