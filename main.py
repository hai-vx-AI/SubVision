from __future__ import annotations

import os

# IMPORTANT:
# TranslationOverlay04 uses absolute top-level screen coordinates.
# On a Wayland desktop this overlay is intentionally run through
# XWayland/xcb, where QWidget.setGeometry(x, y, ...) can represent the
# global position expected by Renderer / ScreenRegion.
#
# This MUST be set before importing anything from PyQt6.
os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "xcb",
)

import sys
import traceback

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from application.controller import AppController
from application.state import (
    AppState,
    ScreenRegion,
)
from backend.pipeline import BackendPipeline
from ui.control_panel import ControlPanel


def get_virtual_desktop_region() -> ScreenRegion:
    """
    Return the complete Qt virtual desktop in global logical coordinates.

    RegionSelector uses the union of all QScreen geometries, so AppState
    must use the same coordinate space.

    ScreenRegion uses an exclusive x2/y2 boundary:

        x2 = x1 + width
        y2 = y1 + height
    """

    screens = QGuiApplication.screens()

    if not screens:
        raise RuntimeError(
            "No screen is available."
        )

    geometry = QRect(
        screens[0].geometry()
    )

    for screen in screens[1:]:
        geometry = geometry.united(
            screen.geometry()
        )

    x1 = geometry.x()
    y1 = geometry.y()

    return ScreenRegion(
        x1=x1,
        y1=y1,
        x2=x1 + geometry.width(),
        y2=y1 + geometry.height(),
    )


def show_application_error(
    message: str,
) -> None:
    """
    Development-time error reporter.

    Runtime errors are printed in full and also surfaced through a simple
    Qt dialog so failures are visible even while the setup panel is hidden.
    """

    text = str(message)

    print(
        text,
        file=sys.stderr,
    )

    box = QMessageBox()
    box.setIcon(
        QMessageBox.Icon.Critical
    )
    box.setWindowTitle(
        "SubVision Error"
    )
    box.setText(
        "SubVision encountered an error."
    )
    box.setDetailedText(
        text
    )
    box.exec()


def install_exception_hook() -> None:
    """
    Keep uncaught exceptions visible instead of silently terminating inside
    the Qt event loop.
    """

    default_hook = sys.excepthook

    def _hook(
        exc_type,
        exc_value,
        exc_traceback,
    ) -> None:
        formatted = "".join(
            traceback.format_exception(
                exc_type,
                exc_value,
                exc_traceback,
            )
        )

        print(
            formatted,
            file=sys.stderr,
        )

        try:
            show_application_error(
                formatted
            )
        except Exception:
            default_hook(
                exc_type,
                exc_value,
                exc_traceback,
            )

    sys.excepthook = _hook


def build_application(
    qt_app: QApplication,
) -> tuple[
    ControlPanel,
    AppController,
]:
    """
    Build the complete SubVision application graph.

    app.py owns only bootstrap/lifecycle.

    AppController owns application composition after construction.
    """

    # --------------------------------------------------------------
    # Shared application state
    # --------------------------------------------------------------

    screen_region = (
        get_virtual_desktop_region()
    )

    state = AppState.create(
        screen_region
    )

    # --------------------------------------------------------------
    # UI
    # --------------------------------------------------------------

    control_panel = ControlPanel()

    # --------------------------------------------------------------
    # Backend
    #
    # BackendPipeline lazily creates the concrete OCR / correction /
    # translation / dashboard services only when a selected branch needs
    # them, so no model initialization is required here.
    # --------------------------------------------------------------

    pipeline = BackendPipeline()

    # --------------------------------------------------------------
    # Application composition root
    # --------------------------------------------------------------

    controller = AppController(
        state=state,
        control_panel=control_panel,
        pipeline=pipeline,

        # Keep current Auto available for integration testing.
        # Its UX policy can be revisited independently later.
        auto_available=True,

        on_error=show_application_error,
    )

    # --------------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------------

    qt_app.aboutToQuit.connect(
        controller.shutdown
    )

    return (
        control_panel,
        controller,
    )


def main() -> int:
    install_exception_hook()

    qt_app = QApplication(
        sys.argv
    )

    qt_app.setApplicationName(
        "SubVision"
    )

    qt_app.setOrganizationName(
        "SubVision"
    )

    # Useful integration check. For the current absolute-position overlay
    # implementation this should print:
    #
    #     [SubVision] Qt platform: xcb
    #
    print(
        "[SubVision] Qt platform:",
        QGuiApplication.platformName(),
    )

    control_panel, controller = (
        build_application(
            qt_app
        )
    )

    # Keep an explicit Python reference for the full Qt lifetime.
    #
    # `controller` owns runtime services and must not be garbage-collected
    # while the event loop is running.
    qt_app._subvision_controller = controller  # type: ignore[attr-defined]

    control_panel.show()
    control_panel.raise_()
    control_panel.activateWindow()

    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
