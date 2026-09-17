from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from PyQt6.QtCore import (
    QPoint,
    Qt,
)

from PyQt6.QtGui import (
    QEnterEvent,
    QMouseEvent,
)

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class DashboardEntryView:
    """
    UI-neutral data required to render one Dashboard vocabulary entry.

    The controller/application layer is responsible for converting backend
    DashboardEntry objects into this view model. Any backend entry_type field is intentionally ignored.

    Dashboard itself does not import backend models.
    """

    term: str
    meanings: tuple[str, ...]
    ipas: tuple[str, ...] = ()


# ==============================================================
# DASHBOARD HEADER
# ==============================================================

class _DashboardDragHeader(
    QFrame
):
    """
    Header nội bộ dùng để kéo Dashboard.

    Đây là local UI behavior.
    """

    def __init__(
        self,
        parent=None,
    ) -> None:

        super().__init__(parent)

        self._dragging = False

        self._drag_position: (
            QPoint | None
        ) = None

        self._build_ui()

    # ==========================================================
    # UI
    # ==========================================================

    def _build_ui(
        self,
    ) -> None:

        self.setObjectName(
            "dashboardHeader"
        )

        layout = QHBoxLayout(
            self
        )

        layout.setContentsMargins(
            10,
            6,
            10,
            6,
        )

        self.title_label = QLabel(
            "Dictionary"
        )

        self.title_label.setObjectName(
            "dashboardTitle"
        )

        self.title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        layout.addWidget(
            self.title_label
        )

        layout.addStretch()

    # ==========================================================
    # DRAG
    # ==========================================================

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:

        if (
            event.button()
            != Qt.MouseButton.LeftButton
        ):
            super().mousePressEvent(event)
            return

        dashboard = self.window()

        handle = dashboard.windowHandle()

        if (
            handle is not None
            and handle.startSystemMove()
        ):
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(
        self,
        event: QMouseEvent,
    ) -> None:

        if not self._dragging:

            return

        if self._drag_position is None:

            return

        current_position = (
            event.globalPosition().toPoint()
        )

        delta = (
            current_position
            - self._drag_position
        )

        window = self.window()

        window.move(
            window.pos()
            + delta
        )

        self._drag_position = (
            current_position
        )

    def mouseReleaseEvent(
        self,
        event: QMouseEvent,
    ) -> None:

        if (
            event.button()
            != Qt.MouseButton.LeftButton
        ):

            return

        self._dragging = False

        self._drag_position = None


# ==============================================================
# DICTIONARY DASHBOARD
# ==============================================================

class DictionaryDashboard03(
    QWidget
):
    """
    UI shell của Dictionary Dashboard.

    Passive mode:

        - transparent;
        - white text;
        - không có nền;
        - scrollbar ẩn;
        - resize grip ẩn.

    Khi mouse hover:

        - nền trắng gần opaque;
        - text đen;
        - header hiện;
        - scrollbar hiện nếu cần;
        - resize grip hiện.

    Có thể:

        - drag bằng header;
        - resize;
        - scroll.

    Module này KHÔNG:

        - import DictionaryTranslator;
        - dịch text;
        - biết AppState;
        - biết Controller;
        - tự quyết định khi nào được show.

    Execution use case sau này sẽ gọi:

        dashboard.set_entries(...)
        dashboard.show_dashboard()
    """

    def __init__(
        self,
        parent=None,
    ) -> None:

        super().__init__(parent)

        self._interactive = False

        self._entry_widgets: list[
            QWidget
        ] = []

        self._build_ui()

        self._apply_passive_style()

    # ==========================================================
    # ROOT UI
    # ==========================================================

    def _build_ui(
        self,
    ) -> None:

        # ------------------------------------------------------
        # Window
        # ------------------------------------------------------

        self.setWindowTitle(
            "SubVision Dictionary"
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

        self.setMinimumSize(
            260,
            180,
        )

        self.resize(
            360,
            420,
        )

        # ------------------------------------------------------
        # Main layout
        # ------------------------------------------------------

        root_layout = QVBoxLayout(
            self
        )

        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        # ------------------------------------------------------
        # Main container
        # ------------------------------------------------------

        self.container = QFrame()

        self.container.setObjectName(
            "dictionaryDashboardContainer"
        )

        container_layout = QVBoxLayout(
            self.container
        )

        container_layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        container_layout.setSpacing(
            4
        )

        root_layout.addWidget(
            self.container
        )

        # ------------------------------------------------------
        # Header
        # ------------------------------------------------------

        self.header = (
            _DashboardDragHeader(
                self.container
            )
        )

        container_layout.addWidget(
            self.header
        )

        # ------------------------------------------------------
        # Scroll Area
        # ------------------------------------------------------

        self.scroll_area = QScrollArea(
            self.container
        )

        self.scroll_area.setWidgetResizable(
            True
        )

        self.scroll_area.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # ------------------------------------------------------
        # Scroll Content
        # ------------------------------------------------------

        self.content = QWidget()

        self.content.setObjectName(
            "dictionaryDashboardContent"
        )

        self.content_layout = QVBoxLayout(
            self.content
        )

        self.content_layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        self.content_layout.setSpacing(
            10
        )

        self.content_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )

        self.scroll_area.setWidget(
            self.content
        )

        container_layout.addWidget(
            self.scroll_area,
            1,
        )

        # ------------------------------------------------------
        # Bottom bar
        # ------------------------------------------------------

        bottom_layout = QHBoxLayout()

        bottom_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        bottom_layout.addStretch()

        self.size_grip = QSizeGrip(
            self.container
        )

        bottom_layout.addWidget(
            self.size_grip
        )

        container_layout.addLayout(
            bottom_layout
        )

    # ==========================================================
    # PUBLIC — ENTRIES
    # ==========================================================

    def set_entries(
        self,
        entries: Iterable[DashboardEntryView],
    ) -> None:
        """
        Replace the complete Dashboard snapshot.

        Input is UI-neutral:

            DashboardEntryView(
                term="machine learning",
                meanings=("học máy", "máy học"),
                ipas=("/məˈʃiːn ˈlɜːnɪŋ/",),
            )

        The application/controller layer converts backend DashboardEntry
        objects into DashboardEntryView before calling this method.
        """

        self.clear_entries()

        for item in entries:
            entry_widget = self._create_entry_widget(
                item
            )

            self.content_layout.addWidget(
                entry_widget
            )

            self._entry_widgets.append(
                entry_widget
            )

    def clear_entries(
        self,
    ) -> None:

        for widget in self._entry_widgets:

            self.content_layout.removeWidget(
                widget
            )

            widget.deleteLater()

        self._entry_widgets.clear()

    # ==========================================================
    # ENTRY UI
    # ==========================================================

    def _create_entry_widget(
        self,
        item: DashboardEntryView,
    ) -> QWidget:
        """
        Render one vocabulary entry using two columns.

        Layout:

            machine learning       • học máy
            /məˈʃiːn .../          • máy học

        Left:
            term
            IPA directly below the term

        Right:
            meanings

        IPA is omitted when unavailable.
        """

        frame = QFrame()

        frame.setObjectName(
            "dictionaryEntry"
        )

        root = QHBoxLayout(
            frame
        )

        root.setContentsMargins(
            8,
            7,
            8,
            7,
        )

        root.setSpacing(
            14
        )

        # ------------------------------------------------------
        # LEFT COLUMN — term + IPA
        # ------------------------------------------------------

        left_column = QVBoxLayout()

        left_column.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        left_column.setSpacing(
            3
        )

        term_label = QLabel(
            item.term
        )

        term_label.setObjectName(
            "dictionarySource"
        )

        term_label.setTextInteractionFlags(
            Qt.TextInteractionFlag
            .TextSelectableByMouse
        )

        term_label.setWordWrap(
            True
        )

        left_column.addWidget(
            term_label
        )

        ipa_values = tuple(
            ipa.strip()
            for ipa in item.ipas
            if ipa and ipa.strip()
        )

        if ipa_values:
            ipa_label = QLabel(
                "  •  ".join(ipa_values)
            )

            ipa_label.setObjectName(
                "dictionaryIPA"
            )

            ipa_label.setTextInteractionFlags(
                Qt.TextInteractionFlag
                .TextSelectableByMouse
            )

            ipa_label.setWordWrap(
                True
            )

            left_column.addWidget(
                ipa_label
            )

        left_column.addStretch()

        # ------------------------------------------------------
        # RIGHT COLUMN — meanings
        # ------------------------------------------------------

        right_column = QVBoxLayout()

        right_column.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        right_column.setSpacing(
            3
        )

        meaning_values = tuple(
            meaning.strip()
            for meaning in item.meanings
            if meaning and meaning.strip()
        )

        if not meaning_values:
            meaning_values = ("—",)

        for meaning in meaning_values:
            meaning_label = QLabel(
                f"• {meaning}"
            )

            meaning_label.setObjectName(
                "dictionaryMeaning"
            )

            meaning_label.setTextInteractionFlags(
                Qt.TextInteractionFlag
                .TextSelectableByMouse
            )

            meaning_label.setWordWrap(
                True
            )

            right_column.addWidget(
                meaning_label
            )

        right_column.addStretch()

        # Give both sides useful room.
        root.addLayout(
            left_column,
            5,
        )

        root.addLayout(
            right_column,
            6,
        )

        return frame

    # ==========================================================
    # PUBLIC VISIBILITY
    # ==========================================================

    def show_dashboard(
        self,
    ) -> None:

        self.show()

        self.raise_()

    def hide_dashboard(
        self,
    ) -> None:

        self.hide()

    # ==========================================================
    # HOVER
    # ==========================================================

    def enterEvent(
        self,
        event: QEnterEvent,
    ) -> None:

        self._interactive = True

        self._apply_interactive_style()

        super().enterEvent(
            event
        )

    def leaveEvent(
        self,
        event,
    ) -> None:

        self._interactive = False

        self._apply_passive_style()

        super().leaveEvent(
            event
        )

    # ==========================================================
    # PASSIVE STYLE
    # ==========================================================

    def _apply_passive_style(
        self,
    ) -> None:
        """
        Normal viewing mode.
        """

        self.header.hide()

        self.size_grip.hide()

        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.setStyleSheet(
            """
            QFrame#dictionaryDashboardContainer {
                background: transparent;
                border: none;
            }

            QWidget#dictionaryDashboardContent {
                background: transparent;
            }

            QFrame#dictionaryEntry {
                background: transparent;
                border: none;
            }

            QLabel#dictionarySource {
                color: white;
                font-weight: 700;
                font-size: 15px;
                background: transparent;
            }

            QLabel#dictionaryIPA {
                color: rgba(255, 255, 255, 205);
                font-size: 13px;
                font-style: italic;
                background: transparent;
            }

            QLabel#dictionaryMeaning {
                color: white;
                font-size: 14px;
                background: transparent;
            }

            QScrollArea {
                background: transparent;
                border: none;
            }
            """
        )

    # ==========================================================
    # INTERACTIVE STYLE
    # ==========================================================

    def _apply_interactive_style(
        self,
    ) -> None:
        """
        Mouse hover mode.
        """

        self.header.show()

        self.size_grip.show()

        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.setStyleSheet(
            """
            QFrame#dictionaryDashboardContainer {
                background-color: rgba(
                    250,
                    250,
                    250,
                    235
                );

                border: 1px solid #b8b8b8;

                border-radius: 8px;
            }

            QFrame#dashboardHeader {
                background-color: rgba(
                    235,
                    235,
                    235,
                    240
                );

                border-radius: 5px;
            }

            QLabel#dashboardTitle {
                color: #111111;
                font-size: 14px;
                font-weight: 700;
            }

            QWidget#dictionaryDashboardContent {
                background: transparent;
            }

            QFrame#dictionaryEntry {
                background-color: rgba(
                    255,
                    255,
                    255,
                    180
                );

                border-bottom: 1px solid #dddddd;
            }

            QLabel#dictionarySource {
                color: #111111;
                font-weight: 700;
                font-size: 15px;
                background: transparent;
            }

            QLabel#dictionaryIPA {
                color: #666666;
                font-size: 13px;
                font-style: italic;
                background: transparent;
            }

            QLabel#dictionaryMeaning {
                color: #333333;
                font-size: 14px;
                background: transparent;
            }

            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollBar:vertical {
                width: 10px;
                background: transparent;
            }

            QScrollBar::handle:vertical {
                background: #a0a0a0;
                border-radius: 5px;
                min-height: 24px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )