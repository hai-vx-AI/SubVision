from __future__ import annotations

from PyQt6.QtCore import (
    QPoint,
    QRect,
    Qt,
    pyqtSignal,
)

from PyQt6.QtGui import (
    QColor,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
)

from PyQt6.QtWidgets import QWidget


class RegionSelector01(QWidget):
    """
    UI component phục vụ UC-01.

    Output:

        region_selected(
            x1,
            y1,
            x2,
            y2,
        )

    Coordinates là global desktop coordinates.

    Selector không biết:
        - AppState;
        - Controller;
        - RegionUseCase01.
    """

    region_selected = pyqtSignal(
        int,
        int,
        int,
        int,
    )

    selection_cancelled = pyqtSignal()

    def __init__(
        self,
        parent=None,
    ) -> None:

        super().__init__(parent)

        # ======================================================
        # LOCAL UI STATE
        # ======================================================

        self._dragging = False

        self._drag_start: QPoint | None = None

        self._drag_current: QPoint | None = None

        # ======================================================
        # UI STYLE
        # ======================================================

        self._overlay_color = QColor(
            0,
            0,
            0,
            150,
        )

        self._border_color = QColor(
            66,
            153,
            225,
            255,
        )

        self._build_ui()

    # ==========================================================
    # UI
    #
    # Muốn thay đổi ngoại hình selector:
    # sửa chủ yếu section này.
    # ==========================================================

    def _build_ui(
        self,
    ) -> None:

        self.setWindowTitle(
            "SubVision Region Selector"
        )

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.setMouseTracking(
            True
        )

        self.setCursor(
            Qt.CursorShape.CrossCursor
        )

        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

    # ==========================================================
    # PUBLIC CONTROL
    # ==========================================================

    def start_selection(
        self,
    ) -> None:
        """
        Bắt đầu chọn vùng.
        """

        self._reset_drag()

        geometry = (
            self._get_virtual_desktop_geometry()
        )

        self.setGeometry(
            geometry
        )

        self.show()

        self.raise_()

        self.activateWindow()

        self.setFocus()

        self.update()

    def retry_selection(
        self,
    ) -> None:
        """
        Candidate không hợp lệ.

        Overlay vẫn mở.
        User chọn lại.
        """

        self._reset_drag()

        self.setCursor(
            Qt.CursorShape.CrossCursor
        )

        self.setFocus()

        self.update()

    def finish_selection(
        self,
    ) -> None:
        """
        Selection đã hoàn tất.
        """

        self._reset_drag()

        self.hide()

    # ==========================================================
    # MOUSE PRESS
    # ==========================================================

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:

        # Right click = cancel

        if (
            event.button()
            == Qt.MouseButton.RightButton
        ):

            self._cancel()

            return

        # Chỉ nhận left click

        if (
            event.button()
            != Qt.MouseButton.LeftButton
        ):

            return

        point = self._event_point(
            event
        )

        self._drag_start = point

        self._drag_current = point

        self._dragging = True

        self.update()

    # ==========================================================
    # MOUSE MOVE
    # ==========================================================

    def mouseMoveEvent(
        self,
        event: QMouseEvent,
    ) -> None:

        if not self._dragging:
            return

        self._drag_current = (
            self._event_point(
                event
            )
        )

        self.update()

    # ==========================================================
    # MOUSE RELEASE
    # ==========================================================

    def mouseReleaseEvent(
        self,
        event: QMouseEvent,
    ) -> None:

        if (
            event.button()
            != Qt.MouseButton.LeftButton
        ):
            return

        if not self._dragging:
            return

        self._drag_current = (
            self._event_point(
                event
            )
        )

        coordinates = (
            self._current_local_coordinates()
        )

        self._dragging = False

        if coordinates is None:

            self.retry_selection()

            return

        (
            x1,
            y1,
            x2,
            y2,
        ) = coordinates

        # ======================================================
        # LOCAL -> GLOBAL
        # ======================================================

        geometry = self.geometry()

        global_x1 = (
            geometry.x() + x1
        )

        global_y1 = (
            geometry.y() + y1
        )

        global_x2 = (
            geometry.x() + x2
        )

        global_y2 = (
            geometry.y() + y2
        )

        # Không hide tại đây.
        #
        # Controller / Application sẽ quyết định:
        #
        # accepted
        #     → finish_selection()
        #
        # rejected
        #     → retry_selection()

        self.region_selected.emit(
            global_x1,
            global_y1,
            global_x2,
            global_y2,
        )

    # ==========================================================
    # KEYBOARD
    # ==========================================================

    def keyPressEvent(
        self,
        event: QKeyEvent,
    ) -> None:

        if (
            event.key()
            == Qt.Key.Key_Escape
        ):

            self._cancel()

            return

        super().keyPressEvent(
            event
        )

    # ==========================================================
    # PAINT
    # ==========================================================

    def paintEvent(
        self,
        event,
    ) -> None:

        painter = QPainter(
            self
        )

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            False,
        )

        # ======================================================
        # DARK OVERLAY
        # ======================================================

        painter.fillRect(
            self.rect(),
            self._overlay_color,
        )

        selected_rect = (
            self._current_qrect()
        )

        if selected_rect is None:
            return

        if (
            selected_rect.width() <= 0
            or selected_rect.height() <= 0
        ):
            return

        # ======================================================
        # CLEAR SELECTED AREA
        #
        # Vùng user chọn sẽ sáng hơn phần còn lại.
        # ======================================================

        painter.setCompositionMode(
            QPainter.CompositionMode
            .CompositionMode_Clear
        )

        painter.fillRect(
            selected_rect,
            Qt.GlobalColor.transparent,
        )

        # ======================================================
        # BORDER
        # ======================================================

        painter.setCompositionMode(
            QPainter.CompositionMode
            .CompositionMode_SourceOver
        )

        pen = QPen(
            self._border_color,
            2,
        )

        painter.setPen(
            pen
        )

        painter.drawRect(
            selected_rect
        )

    # ==========================================================
    # CANCEL
    # ==========================================================

    def _cancel(
        self,
    ) -> None:

        self._reset_drag()

        self.hide()

        self.selection_cancelled.emit()

    # ==========================================================
    # VIRTUAL DESKTOP
    # ==========================================================

    @staticmethod
    def _get_virtual_desktop_geometry(
    ) -> QRect:

        screens = (
            QGuiApplication.screens()
        )

        if not screens:

            raise RuntimeError(
                "No screen is available."
            )

        geometry = QRect(
            screens[0].geometry()
        )

        for screen in screens[1:]:

            geometry = (
                geometry.united(
                    screen.geometry()
                )
            )

        return geometry

    # ==========================================================
    # EVENT -> POINT
    # ==========================================================

    @staticmethod
    def _event_point(
        event: QMouseEvent,
    ) -> QPoint:

        position = event.position()

        return QPoint(
            round(
                position.x()
            ),
            round(
                position.y()
            ),
        )

    # ==========================================================
    # CURRENT RECTANGLE
    # ==========================================================

    def _current_local_coordinates(
        self,
    ) -> tuple[
        int,
        int,
        int,
        int,
    ] | None:

        if (
            self._drag_start is None
            or self._drag_current is None
        ):

            return None

        x1 = min(
            self._drag_start.x(),
            self._drag_current.x(),
        )

        y1 = min(
            self._drag_start.y(),
            self._drag_current.y(),
        )

        x2 = max(
            self._drag_start.x(),
            self._drag_current.x(),
        )

        y2 = max(
            self._drag_start.y(),
            self._drag_current.y(),
        )

        if (
            x2 <= x1
            or y2 <= y1
        ):

            return None

        return (
            x1,
            y1,
            x2,
            y2,
        )

    def _current_qrect(
        self,
    ) -> QRect | None:

        coordinates = (
            self._current_local_coordinates()
        )

        if coordinates is None:
            return None

        (
            x1,
            y1,
            x2,
            y2,
        ) = coordinates

        return QRect(
            x1,
            y1,
            x2 - x1,
            y2 - y1,
        )

    # ==========================================================
    # RESET LOCAL UI STATE
    # ==========================================================

    def _reset_drag(
        self,
    ) -> None:

        self._dragging = False

        self._drag_start = None

        self._drag_current = None