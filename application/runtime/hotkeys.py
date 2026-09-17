from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class GlobalHotkeyService(QObject):
    """
    Global runtime hotkeys.

    Manual:
        R   -> translate once

    Manual + Auto:
        Tab -> show/hide translation

    The listener runs only while a SubVision session is active.
    pynput observes keys and does not suppress them.
    """

    manual_translate_requested = pyqtSignal()
    toggle_translation_requested = pyqtSignal()
    availability_changed = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()

        self._listener = None
        self._keyboard = None
        self._pressed: set[str] = set()

        try:
            from pynput import keyboard
            self._keyboard = keyboard
        except Exception:
            self._keyboard = None

    @property
    def available(self) -> bool:
        return self._keyboard is not None

    def start(self) -> None:
        if not self.available:
            self.availability_changed.emit(False)
            return

        if self._listener is not None:
            return

        self._pressed.clear()

        self._listener = self._keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=False,
        )

        self._listener.start()
        self.availability_changed.emit(True)

    def stop(self) -> None:
        if self._listener is None:
            return

        try:
            self._listener.stop()
        finally:
            self._listener = None
            self._pressed.clear()

    def _on_press(self, key) -> None:
        token = self._token_for_key(key)

        if token is None:
            return

        if token in self._pressed:
            return

        self._pressed.add(token)

        if token == "r":
            self.manual_translate_requested.emit()
            return

        if token == "tab":
            self.toggle_translation_requested.emit()

    def _on_release(self, key) -> None:
        token = self._token_for_key(key)

        if token is not None:
            self._pressed.discard(token)

    def _token_for_key(self, key) -> str | None:
        if self._keyboard is None:
            return None

        if key == self._keyboard.Key.tab:
            return "tab"

        char = getattr(key, "char", None)

        if isinstance(char, str) and char.lower() == "r":
            return "r"

        return None
