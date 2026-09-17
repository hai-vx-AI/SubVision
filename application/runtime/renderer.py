from __future__ import annotations

from application.state import (
    AppState,
    ScreenRegion,
)
from backend.pipeline import PipelineResult

from ui.functions import (
    DashboardEntryView,
    DictionaryDashboard03,
    OverlayTextItem,
    TranslationOverlay04,
)


class TranslationRenderer:
    """
    Render the latest PipelineResult into SubVision runtime UI.

    Despite the historical class name, this renderer handles TWO
    independent output branches:

        1. Translation Overlay
        2. Dictionary Dashboard

    Processing and visibility are deliberately separate.

    ==============================================================
    TRANSLATION OVERLAY
    ==============================================================

    Translation data may keep changing while the overlay is hidden.

    Desired visibility comes from:

        state.translation_visible

    Therefore:

        new result
            -> replace overlay data

    does NOT imply:

        new result
            -> show overlay

    The first-success default visibility is initialized by SessionRunner.
    Later visibility changes are state changes handled by
    ExecutionUseCase / Controller.

    ==============================================================
    DASHBOARD
    ==============================================================

    Dashboard has no user show/hide state.

    Its logical visibility rule is simply:

        state.dashboard_enabled
        AND
        a Dashboard result exists

    Therefore Dashboard appears when the first successful Dashboard result
    arrives and then remains part of the runtime session.

    New Auto results only replace Dashboard content.

    Dashboard may still be PHYSICALLY hidden for a very short time during
    screen capture so SubVision does not capture its own UI. This temporary
    suspension is NOT a Dashboard visibility state and is not stored in
    AppState.

    ==============================================================
    CAPTURE SUSPENSION
    ==============================================================

    Before capture:

        suspend_for_capture()

    physically hides both Overlay and Dashboard.

    After screenshot:

        resume_after_capture()

    restores them according to application state:

        Translation:
            state.translation_visible

        Dashboard:
            state.dashboard_enabled

    This means Auto may continue running while Translation Overlay is
    hidden by the user. Dashboard remains logically enabled throughout
    the session.

    ==============================================================
    COORDINATE CONTRACT
    ==============================================================

    Backend translation bbox:
        local to the captured ScreenRegion.

    UI OverlayTextItem bbox:
        global logical screen coordinates.

    Conversion is intentionally kept here:

        global = selected_region_origin + local_bbox

    This preserves the coordinate mapping that has already been verified
    against the screen-capture pipeline.
    """

    def __init__(
        self,
        *,
        state: AppState,
        overlay: TranslationOverlay04,
        dashboard: DictionaryDashboard03,
    ) -> None:
        self.state = state

        self.overlay = overlay
        self.dashboard = dashboard

        # True after at least one PipelineResult has been accepted.
        self._has_result = False

        # Whether the latest PipelineResult contains each enabled branch.
        #
        # `None` means the feature branch was disabled for that run.
        # An empty branch object still counts as a valid branch result.
        self._translation_has_result = False
        self._dashboard_has_result = False

        # Temporary physical suspension used only around capture.
        self._capture_suspended = False

    # ==================================================================
    # RESULT
    # ==================================================================

    def set_result(
        self,
        *,
        result: PipelineResult,
        region: ScreenRegion,
    ) -> None:
        """
        Replace the complete runtime UI snapshot.

        This method updates DATA first, then synchronizes visibility from
        AppState.

        Updating a result never changes application state.
        """

        self._set_translation_result(
            result=result,
            region=region,
        )

        self._set_dashboard_result(
            result=result,
        )

        self._has_result = True

        self.sync_visibility()

    # ==================================================================
    # TRANSLATION DATA
    # ==================================================================

    def _set_translation_result(
        self,
        *,
        result: PipelineResult,
        region: ScreenRegion,
    ) -> None:
        translation_result = (
            result.translation_result
        )

        if translation_result is None:
            self._translation_has_result = False
            self.overlay.clear()
            self.overlay.hide_overlay()
            return

        overlay_items: list[
            OverlayTextItem
        ] = []

        for item in translation_result.items:
            (
                x1,
                y1,
                x2,
                y2,
            ) = self._to_screen_bbox(
                region=region,
                local_bbox=(
                    item.bbox.coordinates
                ),
            )

            overlay_items.append(
                OverlayTextItem(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    text=item.translated_text,
                )
            )

        # IMPORTANT:
        #
        # screen_region and every OverlayTextItem are GLOBAL logical
        # coordinates expected by TranslationOverlay04.
        self.overlay.set_items(
            screen_region=region.coordinates,
            items=overlay_items,
        )

        self._translation_has_result = True

    # ==================================================================
    # DASHBOARD DATA
    # ==================================================================

    def _set_dashboard_result(
        self,
        *,
        result: PipelineResult,
    ) -> None:
        dashboard_result = (
            result.dashboard_result
        )

        if dashboard_result is None:
            self._dashboard_has_result = False
            self.dashboard.clear_entries()
            self.dashboard.hide_dashboard()
            return

        entries = [
            DashboardEntryView(
                term=entry.term,
                meanings=tuple(
                    entry.meanings
                ),
                ipas=tuple(
                    entry.ipas
                ),
            )
            for entry
            in dashboard_result.entries
        ]

        # Replace data only.
        #
        # Do NOT call show_dashboard() here. Visibility is synchronized
        # separately below.
        self.dashboard.set_entries(
            entries
        )

        self._dashboard_has_result = True

    # ==================================================================
    # VISIBILITY
    # ==================================================================

    def sync_visibility(
        self,
    ) -> None:
        """
        Render physical visibility from current AppState.

        This method never mutates AppState.
        """

        if self._capture_suspended:
            self._hide_physical_output()
            return

        self._sync_translation_visibility()
        self._sync_dashboard_visibility()

    def _sync_translation_visibility(
        self,
    ) -> None:
        should_show = (
            self.state.session_running
            and self._translation_has_result
            and self.state.translation_mode
            is not None
            and self.state.translation_visible
        )

        if should_show:
            self.overlay.show_overlay()
        else:
            self.overlay.hide_overlay()

    def _sync_dashboard_visibility(
        self,
    ) -> None:
        # Dashboard has no independent user visibility toggle.
        #
        # dashboard_enabled is therefore both:
        #     feature enabled
        # and
        #     desired runtime visibility
        #
        # once a Dashboard result exists.
        should_show = (
            self.state.session_running
            and self._dashboard_has_result
            and self.state.dashboard_enabled
        )

        if should_show:
            self.dashboard.show_dashboard()
        else:
            self.dashboard.hide_dashboard()

    # ==================================================================
    # CAPTURE SUSPENSION
    # ==================================================================

    def suspend_for_capture(
        self,
    ) -> None:
        """
        Temporarily hide SubVision output before screen capture.

        No application visibility state is changed.
        """

        self._capture_suspended = True
        self._hide_physical_output()

    def resume_after_capture(
        self,
    ) -> None:
        """
        End temporary capture suspension.

        Restore Overlay / Dashboard according to current AppState.
        """

        self._capture_suspended = False
        self.sync_visibility()

    def _hide_physical_output(
        self,
    ) -> None:
        self.overlay.hide_overlay()
        self.dashboard.hide_dashboard()

    # ==================================================================
    # SESSION CLEANUP
    # ==================================================================

    def clear(
        self,
    ) -> None:
        """
        Remove all runtime output.

        Intended for session shutdown.
        """

        self._capture_suspended = False

        self._has_result = False
        self._translation_has_result = False
        self._dashboard_has_result = False

        self.overlay.hide_overlay()
        self.overlay.clear()

        self.dashboard.hide_dashboard()
        self.dashboard.clear_entries()

    # ==================================================================
    # STATUS
    # ==================================================================

    @property
    def has_result(
        self,
    ) -> bool:
        return self._has_result

    @property
    def translation_has_result(
        self,
    ) -> bool:
        return self._translation_has_result

    @property
    def dashboard_has_result(
        self,
    ) -> bool:
        return self._dashboard_has_result

    @property
    def capture_suspended(
        self,
    ) -> bool:
        return self._capture_suspended

    # ==================================================================
    # COORDINATE MAPPING
    # ==================================================================

    @staticmethod
    def _to_screen_bbox(
        *,
        region: ScreenRegion,
        local_bbox: tuple[
            int,
            int,
            int,
            int,
        ],
    ) -> tuple[
        int,
        int,
        int,
        int,
    ]:
        """
        Convert one bbox from captured-region-local coordinates into
        global logical screen coordinates.

        KEEP THIS CONVERSION SIMPLE:

            global_x = region.x1 + local_x
            global_y = region.y1 + local_y

        ScreenCaptureAdapter already normalizes the captured image back to
        logical coordinate dimensions, so no DPR / PipeWire scaling belongs
        here.
        """

        x1, y1, x2, y2 = local_bbox

        return (
            region.x1 + x1,
            region.y1 + y1,
            region.x1 + x2,
            region.y1 + y2,
        )
