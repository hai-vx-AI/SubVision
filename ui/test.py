"""
UI smoke/demo test for SubVision.

This file is intentionally backend-free.

It lets you inspect and interact with the packaged UI:

    - Full Screen
    - Select Region
    - Fast / Quality OCR
    - Dictionary / Language Model / Dashboard
    - Manual / Auto
    - Start
    - Translate / R
    - Show / Hide Translation / Tab
    - Stop
    - Translation Overlay
    - Dashboard
    - Region Selector
    - Runtime Controls

RUN
---
Preferred, from the project root:

    python -m ui.test

Direct execution is also supported when this file is placed beside
`control_panel.py` inside the `ui` package:

    python ui/test.py

This test does NOT use:
    - AppState
    - Controller
    - BackendPipeline
    - OCR
    - Translation model
    - GPU detection

Instead, DemoHarness provides tiny fake state and fake results so every UI
surface can be tested independently before the real controller is connected.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication


# ======================================================================
# PACKAGE-SAFE IMPORTS
# ======================================================================

if __package__:
    from .control_panel import ControlPanel
    from .functions import (
        DashboardEntryView,
        OverlayTextItem,
    )

else:
    # Support:
    #
    #     python ui/test.py
    #
    # even though control_panel.py itself correctly uses relative imports.

    package_dir = Path(__file__).resolve().parent
    project_root = package_dir.parent
    package_name = package_dir.name

    if str(project_root) not in sys.path:
        sys.path.insert(
            0,
            str(project_root),
        )

    control_panel_module = importlib.import_module(
        f"{package_name}.control_panel"
    )

    functions_module = importlib.import_module(
        f"{package_name}.functions"
    )

    ControlPanel = control_panel_module.ControlPanel
    DashboardEntryView = functions_module.DashboardEntryView
    OverlayTextItem = functions_module.OverlayTextItem


# ======================================================================
# DEMO CONFIG
# ======================================================================

# UI demo only.
#
# Set False if you also want to inspect how disabled Auto mode looks.
DEMO_AUTO_AVAILABLE = True

# Fake realtime interval for Auto mode.
DEMO_AUTO_INTERVAL_MS = 1_500

# Fake processing delay for Manual Translate / R.
DEMO_PROCESSING_DELAY_MS = 350


# ======================================================================
# DEMO HARNESS
# ======================================================================

class DemoHarness(QObject):
    """
    Tiny fake controller used only for UI testing.

    It intentionally mirrors the future controller boundary:

        UI intent
            ->
        tiny fake state
            ->
        render UI state
            ->
        generate fake result
            ->
        update Overlay / Dashboard

    No production application logic should be copied from this class.
    """

    def __init__(
        self,
        panel: ControlPanel,
    ) -> None:

        super().__init__(panel)

        self.panel = panel

        # --------------------------------------------------------------
        # Fake setup state
        # --------------------------------------------------------------

        self.screen_region = (
            self._virtual_desktop_region()
        )

        self.ocr_mode = "fast"

        self.translation_mode: (
            str | None
        ) = "dictionary"

        self.dashboard_enabled = False

        self.execution_mode = "manual"

        # --------------------------------------------------------------
        # Fake runtime state
        # --------------------------------------------------------------

        self.session_running = False
        self.processing = False
        self.result_version = 0

        # Only the latest fake result conceptually exists.
        self.current_result_version: (
            int | None
        ) = None

        self.auto_timer = QTimer(self)

        self.auto_timer.setInterval(
            DEMO_AUTO_INTERVAL_MS
        )

        self.auto_timer.timeout.connect(
            self._request_processing
        )

        self._connect_panel()
        self._install_shortcuts()
        self._render_setup_state()

        self.panel.set_auto_available(
            DEMO_AUTO_AVAILABLE,
            reason=(
                "Auto disabled in this UI demo. "
                "Set DEMO_AUTO_AVAILABLE = True in test.py."
            ),
        )

        self._log(
            "UI ready. Default: Full desktop / Fast OCR / "
            "Dictionary / Manual."
        )

    # ==================================================================
    # CONNECTIONS
    # ==================================================================

    def _connect_panel(self) -> None:

        self.panel.fullscreen_requested.connect(
            self._on_fullscreen_requested
        )

        self.panel.region_selected.connect(
            self._on_region_selected
        )

        self.panel.region_selection_cancelled.connect(
            lambda: self._log(
                "Region selection cancelled."
            )
        )

        self.panel.ocr_mode_requested.connect(
            self._on_ocr_mode_requested
        )

        self.panel.feature_requested.connect(
            self._on_feature_requested
        )

        self.panel.execution_mode_requested.connect(
            self._on_execution_mode_requested
        )

        self.panel.start_requested.connect(
            self._on_start_requested
        )

        self.panel.translate_requested.connect(
            self._request_processing
        )

        self.panel.stop_requested.connect(
            self._on_stop_requested
        )

        self.panel.translation_visibility_changed.connect(
            self._on_translation_visibility_changed
        )

    # ==================================================================
    # KEYBOARD
    # ==================================================================

    def _install_shortcuts(self) -> None:
        """
        Test application shortcuts.

        These are application-level Qt shortcuts, NOT OS-global hotkeys.
        They work while SubVision is the active application.
        """

        self.translate_shortcut = QShortcut(
            QKeySequence("R"),
            self.panel,
        )

        self.translate_shortcut.setContext(
            Qt.ShortcutContext.ApplicationShortcut
        )

        self.translate_shortcut.activated.connect(
            self._on_r_pressed
        )

        self.toggle_shortcut = QShortcut(
            QKeySequence("Tab"),
            self.panel,
        )

        self.toggle_shortcut.setContext(
            Qt.ShortcutContext.ApplicationShortcut
        )

        self.toggle_shortcut.activated.connect(
            self._on_tab_pressed
        )

    def _on_r_pressed(self) -> None:

        if not self.session_running:
            self._log(
                "R ignored: session has not started."
            )
            return

        if self.execution_mode != "manual":
            self._log(
                "R ignored: Auto mode is running."
            )
            return

        self._log(
            "Shortcut R -> request processing."
        )

        self._request_processing()

    def _on_tab_pressed(self) -> None:

        if not self.session_running:
            self._log(
                "Tab ignored: session has not started."
            )
            return

        if self.translation_mode is None:
            self._log(
                "Tab ignored: Dashboard-only session "
                "has no Translation Overlay."
            )
            return

        self._log(
            "Shortcut Tab -> toggle Translation Overlay."
        )

        self.panel.toggle_translation_visibility()

    # ==================================================================
    # SETUP — SCREEN
    # ==================================================================

    def _on_fullscreen_requested(self) -> None:

        self.screen_region = (
            self._virtual_desktop_region()
        )

        self._log(
            "Full Screen selected: "
            f"{self.screen_region}"
        )

    def _on_region_selected(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> None:

        self.screen_region = (
            x1,
            y1,
            x2,
            y2,
        )

        self.panel.accept_region_selection()

        self._log(
            "Region selected: "
            f"{self.screen_region}"
        )

    # ==================================================================
    # SETUP — OCR
    # ==================================================================

    def _on_ocr_mode_requested(
        self,
        mode: str,
    ) -> None:

        self.ocr_mode = mode

        self.panel.set_ocr_mode(
            self.ocr_mode
        )

        self._log(
            f"OCR mode -> {self.ocr_mode}"
        )

    # ==================================================================
    # SETUP — FEATURES
    # ==================================================================

    def _on_feature_requested(
        self,
        feature: str,
    ) -> None:
        """
        Fake state logic used only to exercise the UI.

        Rules mirrored from the agreed UI contract:

            Dictionary XOR Language Model

            At least one of:
                Dictionary
                Language Model
                Dashboard
        """

        if feature == "dictionary":
            self._toggle_dictionary()

        elif feature == "language_model":
            self._toggle_language_model()

        elif feature == "dashboard":
            self._toggle_dashboard()

        else:
            self._log(
                f"Unknown feature request: {feature}"
            )
            return

        self._render_feature_state()

        self._log(
            "Features -> "
            f"translation={self.translation_mode}, "
            f"dashboard={self.dashboard_enabled}"
        )

    def _toggle_dictionary(self) -> None:

        if self.translation_mode == "dictionary":

            # Cannot remove the final enabled feature.
            if not self.dashboard_enabled:
                self._log(
                    "Dictionary kept ON: at least one "
                    "feature must remain enabled."
                )
                return

            self.translation_mode = None
            return

        # Selecting Dictionary automatically replaces LM.
        self.translation_mode = "dictionary"

    def _toggle_language_model(self) -> None:

        if self.translation_mode == "language_model":

            if not self.dashboard_enabled:
                self._log(
                    "Language Model kept ON: at least one "
                    "feature must remain enabled."
                )
                return

            self.translation_mode = None
            return

        # Selecting LM automatically replaces Dictionary.
        self.translation_mode = "language_model"

    def _toggle_dashboard(self) -> None:

        if self.dashboard_enabled:

            # Dashboard cannot be removed if it is the only feature.
            if self.translation_mode is None:
                self._log(
                    "Dashboard kept ON: at least one "
                    "feature must remain enabled."
                )
                return

            self.dashboard_enabled = False
            return

        self.dashboard_enabled = True

    # ==================================================================
    # SETUP — EXECUTION MODE
    # ==================================================================

    def _on_execution_mode_requested(
        self,
        mode: str,
    ) -> None:

        if (
            mode == "auto"
            and not DEMO_AUTO_AVAILABLE
        ):
            self._log(
                "Auto ignored: unavailable in this demo."
            )
            return

        self.execution_mode = mode

        self.panel.set_execution_mode(
            self.execution_mode
        )

        self._log(
            f"Execution mode -> {self.execution_mode}"
        )

    # ==================================================================
    # START / STOP
    # ==================================================================

    def _on_start_requested(self) -> None:

        if self.session_running:
            self._log(
                "Start ignored: session already running."
            )
            return

        self.session_running = True

        translation_enabled = (
            self.translation_mode is not None
        )

        self.panel.enter_runtime(
            mode=self.execution_mode,
            translation_enabled=translation_enabled,
        )

        self.panel.set_runtime_status(
            "Ready"
        )

        self._log(
            "Runtime started: "
            f"mode={self.execution_mode}, "
            f"translation={self.translation_mode}, "
            f"dashboard={self.dashboard_enabled}"
        )

        # Give the user something to inspect immediately.
        self._request_processing()

        if self.execution_mode == "auto":
            self.auto_timer.start()

            self._log(
                "Auto demo timer started "
                f"({DEMO_AUTO_INTERVAL_MS} ms)."
            )

    def _on_stop_requested(self) -> None:

        if not self.session_running:
            return

        self.auto_timer.stop()

        self.session_running = False
        self.processing = False

        self.panel.leave_runtime()

        self._log(
            "Runtime stopped."
        )

    # ==================================================================
    # FAKE PIPELINE
    # ==================================================================

    def _request_processing(self) -> None:

        if not self.session_running:
            self._log(
                "Processing ignored: press Start first."
            )
            return

        if self.processing:
            self._log(
                "Processing ignored: previous cycle still running."
            )
            return

        self.processing = True

        self.panel.set_pipeline_running(
            True
        )

        self.panel.set_runtime_status(
            "Processing..."
        )

        self._log(
            "Fake processing started..."
        )

        QTimer.singleShot(
            DEMO_PROCESSING_DELAY_MS,
            self._finish_processing,
        )

    def _finish_processing(self) -> None:

        if not self.session_running:
            return

        self.result_version += 1
        self.current_result_version = (
            self.result_version
        )

        # --------------------------------------------------------------
        # Translation snapshot
        # --------------------------------------------------------------

        if self.translation_mode is not None:

            self.panel.update_translation_overlay(
                screen_region=self.screen_region,
                items=self._fake_overlay_items(
                    self.result_version
                ),
            )

        else:
            self.panel.clear_translation_overlay()

        # --------------------------------------------------------------
        # Dashboard snapshot
        # --------------------------------------------------------------

        if self.dashboard_enabled:

            self.panel.update_dashboard(
                self._fake_dashboard_entries(
                    self.result_version
                ),
                show=True,
            )

        else:
            self.panel.hide_dashboard()
            self.panel.clear_dashboard()

        self.processing = False

        self.panel.set_pipeline_running(
            False
        )

        self.panel.set_runtime_status(
            f"Ready · Result {self.result_version}"
        )

        self._log(
            "Fake current_result replaced -> "
            f"Result {self.result_version}"
        )

    # ==================================================================
    # FAKE RESULTS
    # ==================================================================

    def _fake_overlay_items(
        self,
        version: int,
    ) -> list[OverlayTextItem]:

        x1, y1, x2, y2 = self.screen_region

        width = max(
            1,
            x2 - x1,
        )

        height = max(
            1,
            y2 - y1,
        )

        left = x1 + int(
            width * 0.12
        )

        right = x1 + int(
            width * 0.88
        )

        top = y1 + int(
            height * 0.70
        )

        line_height = max(
            34,
            int(height * 0.055),
        )

        first_bottom = min(
            y2,
            top + line_height,
        )

        second_top = min(
            y2 - 1,
            first_bottom + 8,
        )

        second_bottom = min(
            y2,
            second_top + line_height,
        )

        if right <= left:
            right = min(
                x2,
                left + 1,
            )

        items = [
            OverlayTextItem(
                x1=left,
                y1=top,
                x2=right,
                y2=max(
                    top + 1,
                    first_bottom,
                ),
                text=(
                    f"Kết quả giả lập #{version} — "
                    f"{self.translation_mode}"
                ),
            ),
        ]

        if second_bottom > second_top:

            items.append(
                OverlayTextItem(
                    x1=left,
                    y1=second_top,
                    x2=right,
                    y2=second_bottom,
                    text=(
                        "Nhấn Tab hoặc nút Show/Hide "
                        "để kiểm tra overlay."
                    ),
                )
            )

        return items

    @staticmethod
    def _fake_dashboard_entries(
        version: int,
    ) -> list[DashboardEntryView]:

        datasets = [
            [
                DashboardEntryView(
                    term="machine learning",
                    ipas=(
                        "/məˈʃiːn ˈlɜːnɪŋ/",
                    ),
                    meanings=(
                        "học máy",
                        "máy học",
                    ),
                ),
                DashboardEntryView(
                    term="subtitle",
                    ipas=(
                        "/ˈsʌbtaɪtl/",
                    ),
                    meanings=(
                        "phụ đề",
                        "dòng phụ đề",
                    ),
                ),
                DashboardEntryView(
                    term="context",
                    ipas=(
                        "/ˈkɒntekst/",
                    ),
                    meanings=(
                        "ngữ cảnh",
                        "bối cảnh",
                    ),
                ),
            ],
            [
                DashboardEntryView(
                    term="translation",
                    ipas=(
                        "/trænzˈleɪʃən/",
                    ),
                    meanings=(
                        "sự dịch",
                        "bản dịch",
                    ),
                ),
                DashboardEntryView(
                    term="recognition",
                    ipas=(
                        "/ˌrekəɡˈnɪʃən/",
                    ),
                    meanings=(
                        "sự nhận dạng",
                        "sự nhận biết",
                    ),
                ),
                DashboardEntryView(
                    term="overlay",
                    ipas=(
                        "/ˈəʊvəleɪ/",
                    ),
                    meanings=(
                        "lớp phủ",
                        "phần hiển thị chồng lên",
                    ),
                ),
            ],
        ]

        return datasets[
            (version - 1)
            % len(datasets)
        ]

    # ==================================================================
    # RENDER SETUP STATE
    # ==================================================================

    def _render_setup_state(self) -> None:

        self.panel.set_ocr_mode(
            self.ocr_mode
        )

        self._render_feature_state()

        self.panel.set_execution_mode(
            self.execution_mode
        )

        self.panel.set_start_enabled(
            True
        )

    def _render_feature_state(self) -> None:

        self.panel.set_feature_state(
            translation_mode=self.translation_mode,
            dashboard_enabled=self.dashboard_enabled,
        )

    # ==================================================================
    # VISIBILITY
    # ==================================================================

    def _on_translation_visibility_changed(
        self,
        visible: bool,
    ) -> None:

        self._log(
            "Translation Overlay -> "
            f"{'visible' if visible else 'hidden'}"
        )

    # ==================================================================
    # SCREEN HELPERS
    # ==================================================================

    @staticmethod
    def _virtual_desktop_region(
    ) -> tuple[int, int, int, int]:

        screens = QGuiApplication.screens()

        if not screens:
            raise RuntimeError(
                "No screen is available."
            )

        geometry = screens[0].geometry()

        for screen in screens[1:]:
            geometry = geometry.united(
                screen.geometry()
            )

        return (
            geometry.x(),
            geometry.y(),
            geometry.x() + geometry.width(),
            geometry.y() + geometry.height(),
        )

    # ==================================================================
    # DEBUG LOG
    # ==================================================================

    @staticmethod
    def _log(
        message: str,
    ) -> None:

        print(
            f"[SubVision UI TEST] {message}",
            flush=True,
        )


# ======================================================================
# MAIN
# ======================================================================

def main() -> int:

    app = QApplication(
        sys.argv
    )

    print(
        "Qt platform:",
        QGuiApplication.platformName(),
    )

    app.setApplicationName(
        "SubVision UI Test"
    )

    panel = ControlPanel()

    # Keep harness alive for the lifetime of the panel.
    harness = DemoHarness(
        panel
    )

    panel._demo_harness = harness

    panel.show()
    panel.raise_()
    panel.activateWindow()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
