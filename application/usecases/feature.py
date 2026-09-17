from __future__ import annotations

from application.state import AppState, TranslationMode


class FeatureUseCase:
    """
    Primitive feature-state operations.

    Managed axes:
        translation_mode: "dictionary" | "language_model" | None
        dashboard_enabled: bool

    This use case deliberately does NOT enforce cross-feature rules such as:
        - button toggle policy between Dictionary and Language Model;
        - at least one feature must remain enabled;
        - whether Dashboard may be disabled in a given combination.

    Those relationships belong to the Controller.
    """

    def __init__(self, state: AppState) -> None:
        self.state = state

    # Translation -------------------------------------------------------

    def set_translation_mode(self, mode: TranslationMode) -> None:
        self.state.set_translation_mode(mode)

    def set_dictionary(self) -> None:
        self.set_translation_mode("dictionary")

    def set_language_model(self) -> None:
        self.set_translation_mode("language_model")

    def clear_translation(self) -> None:
        self.set_translation_mode(None)

    # Dashboard ---------------------------------------------------------

    def set_dashboard_enabled(self, enabled: bool) -> None:
        self.state.set_dashboard_enabled(enabled)

    def enable_dashboard(self) -> None:
        self.set_dashboard_enabled(True)

    def disable_dashboard(self) -> None:
        self.set_dashboard_enabled(False)
