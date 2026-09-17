from __future__ import annotations

from collections.abc import Iterable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .components.actions import StartButton
from .components.capture import (
    FullscreenButton,
    SelectRegionButton,
)
from .components.execution import (
    AutoModeButton,
    ManualModeButton,
)
from .components.features import (
    DashboardButton,
    DictionaryButton,
    LanguageModelButton,
)
from .components.ocr import (
    FastOCRButton,
    QualityOCRButton,
)
from .functions import (
    DashboardEntryView,
    DictionaryDashboard03,
    OverlayTextItem,
    RegionSelector01,
    RuntimeControls04,
    TranslationOverlay04,
)


class ControlPanel(QWidget):
    """
    Main UI composition root for SubVision.

    Responsibilities
    ----------------
    1. Build the setup window.
    2. Create the independent UI-function windows:
       - RegionSelector01
       - TranslationOverlay04
       - DictionaryDashboard03
       - RuntimeControls04
    3. Connect UI-only relationships.
    4. Forward user intent as high-level Qt signals.
    5. Expose public render/update methods for the future controller.

    This class DOES NOT:
        - own AppState;
        - enforce business rules;
        - construct PipelineConfig;
        - call BackendPipeline;
        - run OCR or translation;
        - detect GPU;
        - own worker/timer logic.

    Expected architecture:

        ControlPanel / UI functions
                |
                | signals
                v
            Controller
                |
                v
             AppState
                |
                v
         BackendPipeline
                |
                v
         controller maps result
                |
                v
        ControlPanel render API
    """

    # ==================================================================
    # HIGH-LEVEL USER INTENT SIGNALS
    # ==================================================================

    fullscreen_requested = pyqtSignal()

    # Emitted after RegionSelector creates global desktop coordinates.
    region_selected = pyqtSignal(
        int,
        int,
        int,
        int,
    )
    region_selection_cancelled = pyqtSignal()

    # Payload:
    #     "fast"
    #     "quality"
    ocr_mode_requested = pyqtSignal(str)

    # Payload:
    #     "dictionary"
    #     "language_model"
    #     "dashboard"
    #
    # This is an intent signal only.
    # Controller/state decides the final valid combination.
    feature_requested = pyqtSignal(str)

    # Payload:
    #     "manual"
    #     "auto"
    execution_mode_requested = pyqtSignal(str)

    # Start the whole runtime session.
    start_requested = pyqtSignal()

    # Runtime requests forwarded from RuntimeControls04.
    translate_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    # UI-only overlay visibility changed.
    translation_visibility_changed = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Translation visibility is UI-local state.
        #
        # It does not say whether translation feature is enabled.
        # It only says whether the current Vietnamese overlay is visible.
        self._translation_visible = False

        self._build_ui()
        self._build_functions()
        self._connect_signals()
        self._apply_stylesheet()

    # ==================================================================
    # BUILD — MAIN CONTROL PANEL
    # ==================================================================

    def _build_ui(self) -> None:
        """Build only the setup/control-panel window."""

        self.setWindowTitle("SubVision")
        self.setObjectName("subvisionControlPanel")

        self.setMinimumWidth(560)
        self.resize(620, 590)

        root = QVBoxLayout(self)

        root.setContentsMargins(
            22,
            22,
            22,
            22,
        )

        root.setSpacing(14)

        # --------------------------------------------------------------
        # Header
        # --------------------------------------------------------------

        self.header_frame = QFrame()
        self.header_frame.setObjectName("headerFrame")

        header_layout = QVBoxLayout(
            self.header_frame
        )

        header_layout.setContentsMargins(
            4,
            4,
            4,
            8,
        )

        header_layout.setSpacing(3)

        self.title_label = QLabel(
            "SubVision"
        )

        self.title_label.setObjectName(
            "titleLabel"
        )

        self.subtitle_label = QLabel(
            "Screen translation & vocabulary assistant"
        )

        self.subtitle_label.setObjectName(
            "subtitleLabel"
        )

        header_layout.addWidget(
            self.title_label
        )

        header_layout.addWidget(
            self.subtitle_label
        )

        root.addWidget(
            self.header_frame
        )

        # --------------------------------------------------------------
        # Capture
        # --------------------------------------------------------------

        self.capture_group = QGroupBox(
            "Screen Area"
        )

        capture_layout = QHBoxLayout(
            self.capture_group
        )

        capture_layout.setSpacing(10)

        self.fullscreen_button = FullscreenButton()
        self.select_region_button = SelectRegionButton()

        capture_layout.addWidget(
            self.fullscreen_button,
            1,
        )

        capture_layout.addWidget(
            self.select_region_button,
            1,
        )

        root.addWidget(
            self.capture_group
        )

        # --------------------------------------------------------------
        # OCR
        # --------------------------------------------------------------

        self.ocr_group = QGroupBox(
            "OCR"
        )

        ocr_layout = QHBoxLayout(
            self.ocr_group
        )

        ocr_layout.setSpacing(10)

        self.fast_ocr_button = FastOCRButton()
        self.quality_ocr_button = QualityOCRButton()

        ocr_layout.addWidget(
            self.fast_ocr_button,
            1,
        )

        ocr_layout.addWidget(
            self.quality_ocr_button,
            1,
        )

        root.addWidget(
            self.ocr_group
        )

        # --------------------------------------------------------------
        # Features
        # --------------------------------------------------------------

        self.features_group = QGroupBox(
            "Features"
        )

        features_layout = QHBoxLayout(
            self.features_group
        )

        features_layout.setSpacing(10)

        self.dictionary_button = DictionaryButton()
        self.language_model_button = LanguageModelButton()
        self.dashboard_button = DashboardButton()

        features_layout.addWidget(
            self.dictionary_button,
            1,
        )

        features_layout.addWidget(
            self.language_model_button,
            1,
        )

        features_layout.addWidget(
            self.dashboard_button,
            1,
        )

        root.addWidget(
            self.features_group
        )

        # --------------------------------------------------------------
        # Execution mode
        # --------------------------------------------------------------

        self.execution_group = QGroupBox(
            "Execution Mode"
        )

        execution_layout = QHBoxLayout(
            self.execution_group
        )

        execution_layout.setSpacing(10)

        self.manual_mode_button = ManualModeButton()
        self.auto_mode_button = AutoModeButton()

        execution_layout.addWidget(
            self.manual_mode_button,
            1,
        )

        execution_layout.addWidget(
            self.auto_mode_button,
            1,
        )

        root.addWidget(
            self.execution_group
        )

        root.addStretch()

        # --------------------------------------------------------------
        # Start — deliberately outside Execution Mode
        # --------------------------------------------------------------

        self.start_button = StartButton()

        self.start_button.setObjectName(
            "startButton"
        )

        root.addWidget(
            self.start_button
        )

    # ==================================================================
    # BUILD — UI FUNCTION WINDOWS
    # ==================================================================

    def _build_functions(self) -> None:
        """
        Create the independent UI-function objects.

        They are top-level UI surfaces and are initially hidden.
        """

        self.region_selector = RegionSelector01()

        self.translation_overlay = (
            TranslationOverlay04()
        )

        self.dashboard = (
            DictionaryDashboard03()
        )

        self.runtime_controls = (
            RuntimeControls04()
        )

        self.translation_overlay.hide()
        self.dashboard.hide()
        self.runtime_controls.hide()

    # ==================================================================
    # SIGNAL CONNECTIONS
    # ==================================================================

    def _connect_signals(self) -> None:
        """
        Connect only UI intent and UI-local relationships.

        Business state transitions remain outside this class.
        """

        # --------------------------------------------------------------
        # Capture
        # --------------------------------------------------------------

        self.fullscreen_button.clicked.connect(
            self.fullscreen_requested.emit
        )

        # This relationship is UI-only:
        # SelectRegionButton opens RegionSelector.
        self.select_region_button.clicked.connect(
            self._begin_region_selection
        )

        self.region_selector.region_selected.connect(
            self._on_region_selector_selected
        )

        self.region_selector.selection_cancelled.connect(
            self._on_region_selector_cancelled
        )

        # --------------------------------------------------------------
        # OCR intent
        # --------------------------------------------------------------

        self.fast_ocr_button.clicked.connect(
            lambda: self.ocr_mode_requested.emit(
                "fast"
            )
        )

        self.quality_ocr_button.clicked.connect(
            lambda: self.ocr_mode_requested.emit(
                "quality"
            )
        )

        # --------------------------------------------------------------
        # Feature intent
        # --------------------------------------------------------------

        self.dictionary_button.clicked.connect(
            lambda: self.feature_requested.emit(
                "dictionary"
            )
        )

        self.language_model_button.clicked.connect(
            lambda: self.feature_requested.emit(
                "language_model"
            )
        )

        self.dashboard_button.clicked.connect(
            lambda: self.feature_requested.emit(
                "dashboard"
            )
        )

        # --------------------------------------------------------------
        # Execution intent
        # --------------------------------------------------------------

        self.manual_mode_button.clicked.connect(
            lambda: self.execution_mode_requested.emit(
                "manual"
            )
        )

        self.auto_mode_button.clicked.connect(
            lambda: self.execution_mode_requested.emit(
                "auto"
            )
        )

        # --------------------------------------------------------------
        # Start
        # --------------------------------------------------------------

        self.start_button.clicked.connect(
            self.start_requested.emit
        )

        # --------------------------------------------------------------
        # Runtime controls
        # --------------------------------------------------------------

        self.runtime_controls.translate_requested.connect(
            self.translate_requested.emit
        )

        self.runtime_controls.stop_requested.connect(
            self.stop_requested.emit
        )

        # Show/Hide Translation is strictly an UI-overlay action.
        self.runtime_controls.toggle_requested.connect(
            self.toggle_translation_visibility
        )

    # ==================================================================
    # PUBLIC — REGION SELECTOR
    # ==================================================================

    def accept_region_selection(self) -> None:
        """
        Tell RegionSelector that the selected region was accepted.

        Controller may call this after validating/storing the region.
        """

        self.region_selector.finish_selection()

    def retry_region_selection(self) -> None:
        """
        Keep RegionSelector open and let the user select again.
        """

        self.region_selector.retry_selection()

    # ==================================================================
    # PUBLIC — RENDER SETUP STATE
    # ==================================================================

    def _begin_region_selection(self) -> None:
        self.hide()
        self.region_selector.start_selection()


    def _on_region_selector_selected(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:
        self._restore_after_region_selection()

        self.region_selected.emit(
            x1,
            y1,
            x2,
            y2,
        )


    def _on_region_selector_cancelled(self) -> None:
        self._restore_after_region_selection()

        self.region_selection_cancelled.emit()


    def _restore_after_region_selection(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def set_ocr_mode(
        self,
        mode: str,
    ) -> None:
        """
        Render OCR selection.

        This method does not modify application state.
        """

        self.fast_ocr_button.set_selected(
            mode == "fast"
        )

        self.quality_ocr_button.set_selected(
            mode == "quality"
        )

    def set_feature_state(
        self,
        *,
        translation_mode: str | None,
        dashboard_enabled: bool,
    ) -> None:
        """
        Render feature selection.

        Expected translation_mode:
            "dictionary"
            "language_model"
            None

        This method intentionally does NOT validate combinations.
        Validation belongs to controller/state.
        """

        self.dictionary_button.set_selected(
            translation_mode == "dictionary"
        )

        self.language_model_button.set_selected(
            translation_mode == "language_model"
        )

        self.dashboard_button.set_selected(
            dashboard_enabled
        )

    def set_execution_mode(
        self,
        mode: str,
    ) -> None:
        """
        Render Manual / Auto mode selection.
        """

        self.manual_mode_button.set_selected(
            mode == "manual"
        )

        self.auto_mode_button.set_selected(
            mode == "auto"
        )

    def set_auto_available(
        self,
        available: bool,
        *,
        reason: str | None = None,
    ) -> None:
        """
        Enable/disable Auto mode based on capability decided elsewhere.

        Example:
            controller detects GPU
                ->
            panel.set_auto_available(gpu_available)
        """

        self.auto_mode_button.setEnabled(
            bool(available)
        )

        if available:
            self.auto_mode_button.setToolTip(
                "Continuous real-time mode."
            )
            return

        self.auto_mode_button.setToolTip(
            reason
            or "Auto mode is unavailable on this system."
        )

    def set_start_enabled(
        self,
        enabled: bool,
    ) -> None:
        """
        Allow controller to disable Start when configuration is invalid
        or application is busy.
        """

        self.start_button.setEnabled(
            bool(enabled)
        )

    # ==================================================================
    # PUBLIC — RUNTIME SESSION UI
    # ==================================================================

    def enter_runtime(
        self,
        *,
        mode: str,
        translation_enabled: bool,
    ) -> None:
        """
        Enter runtime UI after controller successfully starts a session.

        `translation_enabled` means the session has a Vietnamese translation
        branch (Dictionary or Language Model).

        Dashboard-only mode:
            translation_enabled=False

        RuntimeControls04 currently exposes its toggle button as a public
        widget attribute, so this composition layer hides that control when
        the session has no translation overlay.
        """

        self.hide()

        self.runtime_controls.set_mode(
            mode
        )

        self.runtime_controls.adjustSize()

        self._position_runtime_windows()

        self.runtime_controls.show()
        self.runtime_controls.raise_()

        self.runtime_controls.set_translation_control_visible(
            translation_enabled
        )

        if translation_enabled:
            self.set_translation_visible(
                True
            )
        else:
            self.set_translation_visible(
                False
            )

        self.runtime_controls.set_status(
            "Ready"
        )

        self.runtime_controls.show()
        self.runtime_controls.raise_()

    def leave_runtime(self) -> None:
        """
        Clear/hide runtime UI after controller finishes stopping the session.
        """

        self.runtime_controls.hide()

        self.translation_overlay.hide_overlay()
        self.translation_overlay.clear()

        self.dashboard.hide_dashboard()
        self.dashboard.clear_entries()

        self._translation_visible = False

        self.runtime_controls.set_translation_visible(
            False
        )

        self.runtime_controls.set_pipeline_running(
            False
        )

        self.runtime_controls.set_status(
            "Ready"
        )

        self.show()
        self.raise_()
        self.activateWindow()

    def set_runtime_status(
        self,
        text: str,
    ) -> None:
        """Update RuntimeControls status text."""

        self.runtime_controls.set_status(
            text
        )

    def set_pipeline_running(
        self,
        running: bool,
    ) -> None:
        """
        Render current manual-pipeline busy state.

        RuntimeControls disables Translate while running.
        """

        self.runtime_controls.set_pipeline_running(
            running
        )

    # ==================================================================
    # PUBLIC — TRANSLATION OVERLAY
    # ==================================================================

    def update_translation_overlay(
        self,
        *,
        screen_region: tuple[
            int,
            int,
            int,
            int,
        ],
        items: list[OverlayTextItem],
    ) -> None:
        """
        Replace the current translation-overlay snapshot.

        Important:
            updating data does NOT force visibility on.

        Therefore Auto mode may keep updating current_result while the user
        has manually hidden the Vietnamese overlay.
        """

        self.translation_overlay.set_items(
            screen_region=screen_region,
            items=items,
        )

        if self._translation_visible:
            self.translation_overlay.show_overlay()

    def clear_translation_overlay(self) -> None:
        """Remove all rendered translation text."""

        self.translation_overlay.clear()

    def toggle_translation_visibility(
        self,
    ) -> None:
        """
        Toggle Vietnamese Translation Overlay only.

        Dashboard is intentionally untouched.
        """

        self.set_translation_visible(
            not self._translation_visible
        )

    def set_translation_visible(
        self,
        visible: bool,
    ) -> None:
        """
        Set current Translation Overlay visibility.

        This is UI-local visibility state, not feature-selection state.
        """

        self._translation_visible = bool(
            visible
        )

        if self._translation_visible:
            self.translation_overlay.show_overlay()
        else:
            self.translation_overlay.hide_overlay()

        self.runtime_controls.set_translation_visible(
            self._translation_visible
        )

        self.translation_visibility_changed.emit(
            self._translation_visible
        )

    # ==================================================================
    # PUBLIC — DASHBOARD
    # ==================================================================

    def _position_runtime_windows(self) -> None:
        screen = self.screen()

        if screen is None:
            return

        area = screen.availableGeometry()

        margin = 24

        # Runtime controls: góc trên bên phải
        controls_x = (
            area.right()
            - self.runtime_controls.width()
            - margin
        )

        controls_y = (
            area.top()
            + margin
        )

        self.runtime_controls.move(
            controls_x,
            controls_y,
        )

        # Dashboard: bên phải nhưng thấp hơn controls
        dashboard_x = (
            area.right()
            - self.dashboard.width()
            - margin
        )

        dashboard_y = (
            controls_y
            + self.runtime_controls.height()
            + 20
        )

        self.dashboard.move(
            dashboard_x,
            dashboard_y,
        )

    def update_dashboard(
        self,
        entries: Iterable[DashboardEntryView],
        *,
        show: bool = True,
    ) -> None:
        """
        Replace the complete vocabulary Dashboard snapshot.

        Dashboard visibility is independent from Translation Overlay.
        """

        self.dashboard.set_entries(
            entries
        )

        if show:
            self.dashboard.show_dashboard()

            self.runtime_controls.show()
            self.runtime_controls.raise_()

    def clear_dashboard(self) -> None:
        """Clear Dashboard content without changing feature state."""

        self.dashboard.clear_entries()

    def show_dashboard(self) -> None:
        """Show Dashboard independently from Translation Overlay."""

        self.dashboard.show_dashboard()

    def hide_dashboard(self) -> None:
        """Hide Dashboard independently from Translation Overlay."""

        self.dashboard.hide_dashboard()

    # ==================================================================
    # STYLE
    # ==================================================================

    def _apply_stylesheet(self) -> None:
        """
        Main setup-panel theme.

        All styling is isolated here so visual design can later be changed
        without touching UI wiring or controller logic.
        """

        self.setStyleSheet(
            """
            QWidget#subvisionControlPanel {
                background-color: #0f172a;
                color: #f8fafc;
            }

            QFrame#headerFrame {
                background: transparent;
                border: none;
            }

            QLabel#titleLabel {
                color: #f8fafc;
                font-size: 26px;
                font-weight: 800;
            }

            QLabel#subtitleLabel {
                color: #94a3b8;
                font-size: 12px;
            }

            QGroupBox {
                color: #cbd5e1;
                font-size: 12px;
                font-weight: 700;

                background-color: #111827;

                border: 1px solid #263449;
                border-radius: 10px;

                margin-top: 10px;
                padding-top: 10px;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;

                color: #94a3b8;
                background-color: #0f172a;
            }

            QPushButton {
                color: #f8fafc;

                background-color: #1f2937;

                border: 1px solid #334155;
                border-radius: 8px;

                padding: 8px 12px;

                font-size: 12px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #293548;
                border-color: #64748b;
            }

            QPushButton:pressed {
                background-color: #334155;
            }

            QPushButton:disabled {
                color: #64748b;
                background-color: #172033;
                border-color: #263449;
            }

            QPushButton#startButton {
                min-height: 44px;

                color: white;

                background-color: #4f46e5;

                border: 1px solid #6366f1;
                border-radius: 10px;

                font-size: 14px;
                font-weight: 800;
            }

            QPushButton#startButton:hover {
                background-color: #5b54e8;
                border-color: #818cf8;
            }

            QPushButton#startButton:pressed {
                background-color: #4338ca;
            }

            QPushButton#startButton:disabled {
                color: #94a3b8;
                background-color: #312e81;
                border-color: #3730a3;
            }
            """
        )

    # ==================================================================
    # CLEANUP
    # ==================================================================

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """
        Close all top-level UI-function windows with the main panel.

        This is UI resource cleanup only.
        """

        self.region_selector.close()
        self.translation_overlay.close()
        self.dashboard.close()
        self.runtime_controls.close()

        super().closeEvent(event)
