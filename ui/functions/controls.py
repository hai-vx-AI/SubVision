from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QEnterEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..components.runtime import (
    ShowHideTranslationButton,
    StopButton,
    TranslateButton,
)


class RuntimeControls04(QWidget):
    """
    Floating UI for an active SubVision runtime session.

    Manual mode:
        Translate (R)
        Show/Hide Translation (Tab)
        Stop

    Auto mode:
        Show/Hide Translation (Tab)
        Stop

    This class owns only LOCAL runtime-control UI behavior:

        - button composition;
        - status display;
        - Manual/Auto visual layout;
        - passive/interactive appearance;
        - drag behavior;
        - forwarding button clicks as high-level signals.

    It does NOT:

        - run BackendPipeline;
        - own current_result;
        - show/hide TranslationOverlay directly;
        - show/hide Dashboard directly;
        - own application state;
        - implement global hotkeys;
        - detect GPU.
    """

    translate_requested = pyqtSignal()
    toggle_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(parent)

        # --------------------------------------------------------------
        # Local UI state
        # --------------------------------------------------------------

        self._dragging = False

        self._drag_position: (
            QPoint | None
        ) = None

        self._interactive = False

        # --------------------------------------------------------------
        # Build
        # --------------------------------------------------------------

        self._build_ui()
        self._apply_passive_style()

    # ==================================================================
    # BUILD UI
    # ==================================================================

    def _build_ui(self) -> None:
        """
        Build the runtime-control window.

        Visual styling is intentionally NOT defined here.
        Styling lives in:

            _apply_passive_style()
            _apply_interactive_style()
        """

        self.setWindowTitle(
            "SubVision Runtime"
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

        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )

        self.setObjectName(
            "runtimeControls04"
        )

        # --------------------------------------------------------------
        # Layout
        # --------------------------------------------------------------

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            10,
            10,
            10,
            10,
        )

        layout.setSpacing(
            6
        )

        # --------------------------------------------------------------
        # Status / drag area
        # --------------------------------------------------------------

        self.status_label = QLabel(
            "Ready"
        )

        self.status_label.setObjectName(
            "runtimeStatus"
        )

        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        # Mouse events pass through the label to RuntimeControls04.
        # Therefore the status/header area naturally works as a drag handle.
        self.status_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        # --------------------------------------------------------------
        # Runtime buttons
        # --------------------------------------------------------------

        self.translate_button = (
            TranslateButton()
        )

        self.toggle_button = (
            ShowHideTranslationButton()
        )

        self.stop_button = (
            StopButton()
        )

        # --------------------------------------------------------------
        # Composition
        # --------------------------------------------------------------

        layout.addWidget(
            self.status_label
        )

        layout.addWidget(
            self.translate_button
        )

        layout.addWidget(
            self.toggle_button
        )

        layout.addWidget(
            self.stop_button
        )

        # --------------------------------------------------------------
        # Forward component events
        # --------------------------------------------------------------

        self.translate_button.clicked.connect(
            self.translate_requested.emit
        )

        self.toggle_button.clicked.connect(
            self.toggle_requested.emit
        )

        self.stop_button.clicked.connect(
            self.stop_requested.emit
        )

        self.adjustSize()

    # ==================================================================
    # PUBLIC — MODE
    # ==================================================================

    def set_mode(
        self,
        mode: str,
    ) -> None:
        """
        Render runtime mode.

        manual:
            Translate visible.

        auto:
            Translate hidden.

        This method only changes the local UI.
        It does not change application state.
        """

        if mode not in {
            "manual",
            "auto",
        }:
            raise ValueError(
                "mode must be 'manual' or 'auto'."
            )

        self.translate_button.setVisible(
            mode == "manual"
        )

        self.adjustSize()

    # ==================================================================
    # PUBLIC — TRANSLATION CONTROL
    # ==================================================================

    def set_translation_visible(
        self,
        visible: bool,
    ) -> None:
        """
        Reflect the ACTUAL TranslationOverlay visibility in the toggle button.

        RuntimeControls04 does not show/hide the overlay itself.
        """

        self.toggle_button.set_translation_visible(
            visible
        )

    def set_translation_control_visible(
        self,
        visible: bool,
    ) -> None:
        """
        Show/hide the Show/Hide Translation control itself.

        Useful for Dashboard-only runtime sessions, where no Vietnamese
        TranslationOverlay exists.
        """

        self.toggle_button.setVisible(
            visible
        )

        self.adjustSize()

    # ==================================================================
    # PUBLIC — PIPELINE STATUS
    # ==================================================================

    def set_pipeline_running(
        self,
        running: bool,
    ) -> None:
        """
        Disable Manual Translate while one processing cycle is running.

        In Auto mode Translate is already hidden.
        """

        self.translate_button.setEnabled(
            not running
        )

    def set_status(
        self,
        text: str,
    ) -> None:
        """Update the runtime status label."""

        self.status_label.setText(
            text
        )

    # ==================================================================
    # HOVER — PASSIVE / INTERACTIVE
    # ==================================================================

    def enterEvent(
        self,
        event: QEnterEvent,
    ) -> None:
        """
        Mouse enters RuntimeControls:

            passive -> interactive
        """

        self._interactive = True

        self._apply_interactive_style()

        super().enterEvent(
            event
        )

    def leaveEvent(
        self,
        event,
    ) -> None:
        """
        Mouse leaves RuntimeControls:

            interactive -> passive
        """

        self._interactive = False

        self._apply_passive_style()

        super().leaveEvent(
            event
        )

    # ==================================================================
    # STYLE — PASSIVE
    # ==================================================================

    def _apply_passive_style(
        self,
    ) -> None:
        """
        Passive viewing state.

        The panel background disappears and controls remain softly visible,
        so they do not obstruct video/content underneath.
        """

        self.setStyleSheet(
            """
            QWidget#runtimeControls04 {
                background: transparent;
                border: none;
            }

            QLabel#runtimeStatus {
                color: rgba(255, 255, 255, 180);
                background: transparent;

                font-size: 12px;

                padding: 3px;
            }

            QPushButton {
                min-width: 180px;
                min-height: 32px;

                color: rgba(255, 255, 255, 210);

                background-color: rgba(
                    20,
                    20,
                    20,
                    90
                );

                border: 1px solid rgba(
                    255,
                    255,
                    255,
                    25
                );

                border-radius: 6px;

                padding: 4px 8px;
            }

            QPushButton:disabled {
                color: rgba(255, 255, 255, 90);

                background-color: rgba(
                    20,
                    20,
                    20,
                    50
                );

                border-color: rgba(
                    255,
                    255,
                    255,
                    15
                );
            }
            """
        )

    # ==================================================================
    # STYLE — INTERACTIVE
    # ==================================================================

    def _apply_interactive_style(
        self,
    ) -> None:
        """
        Interactive hover state.

        The panel becomes clearly visible so the user can operate or drag it.
        """

        self.setStyleSheet(
            """
            QWidget#runtimeControls04 {
                background-color: rgba(
                    24,
                    24,
                    24,
                    235
                );

                border: 1px solid rgba(
                    255,
                    255,
                    255,
                    70
                );

                border-radius: 8px;
            }

            QLabel#runtimeStatus {
                color: white;
                background: transparent;

                font-size: 12px;

                padding: 3px;
            }

            QPushButton {
                min-width: 180px;
                min-height: 32px;

                color: white;

                background-color: #343434;

                border: 1px solid #555555;
                border-radius: 6px;

                padding: 4px 8px;
            }

            QPushButton:hover {
                background-color: #454545;
            }

            QPushButton:pressed {
                background-color: #505050;
            }

            QPushButton:disabled {
                color: #888888;

                background-color: #292929;

                border-color: #444444;
            }
            """
        )

    # ==================================================================
    # DRAG — PRESS
    # ==================================================================

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

        child = self.childAt(
            event.position().toPoint()
        )

        # Bấm button = action, không phải drag.
        if isinstance(
            child,
            QPushButton,
        ):
            super().mousePressEvent(event)
            return

        handle = self.windowHandle()

        if (
            handle is not None
            and handle.startSystemMove()
        ):
            event.accept()
            return

        super().mousePressEvent(event)

    # ==================================================================
    # DRAG — MOVE
    # ==================================================================

    def mouseMoveEvent(
        self,
        event: QMouseEvent,
    ) -> None:

        if (
            not self._dragging
            or self._drag_position is None
        ):
            super().mouseMoveEvent(
                event
            )
            return

        current = (
            event.globalPosition().toPoint()
        )

        delta = (
            current
            - self._drag_position
        )

        self.move(
            self.pos()
            + delta
        )

        self._drag_position = (
            current
        )

        event.accept()

    # ==================================================================
    # DRAG — RELEASE
    # ==================================================================

    def mouseReleaseEvent(
        self,
        event: QMouseEvent,
    ) -> None:

        if (
            event.button()
            != Qt.MouseButton.LeftButton
        ):
            super().mouseReleaseEvent(
                event
            )
            return

        self._dragging = False
        self._drag_position = None

        event.accept()
