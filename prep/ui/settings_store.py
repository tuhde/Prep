from typing import Any

from PySide6.QtCore import QSettings


class SettingsStore:
    def __init__(self) -> None:
        self._settings = QSettings(QSettings.IniFormat, QSettings.UserScope, "Prep", "Prep")
        self._prefix = ""

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}" if self._prefix else key

    def get(self, key: str, default: Any = None) -> Any:
        value = self._settings.value(self._key(key), default)
        return value

    def set(self, key: str, value: Any) -> None:
        self._settings.setValue(self._key(key), value)

    def remove(self, key: str) -> None:
        self._settings.remove(self._key(key))

    def namespace(self, prefix: str) -> "SettingsStore":
        store = SettingsStore()
        store._settings = self._settings
        store._prefix = f"{self._prefix}{prefix}/" if self._prefix else f"{prefix}/"
        return store

    def save_window(self, window: Any) -> None:
        self._settings.setValue("window/geometry", window.saveGeometry())

    def restore_window(self, window: Any) -> None:
        geometry = self._settings.value("window/geometry")
        if geometry is not None:
            window.restoreGeometry(geometry)
