from dataclasses import dataclass

from PySide6.QtWidgets import QMainWindow

from prep.ui.settings_store import SettingsStore


@dataclass
class Perspective:
    perspective_id: str
    name: str
    description: str = ""
    builtin: bool = False
    window_state: bytes = b""


class PerspectiveManager:
    def __init__(self, store: SettingsStore) -> None:
        self._store = store.namespace("perspectives")
        self._perspectives: dict[str, Perspective] = {}
        self._current_id: str | None = None

    def register(self, perspective: Perspective) -> None:
        self._perspectives[perspective.perspective_id] = perspective
        saved_state = self._store.get(f"{perspective.perspective_id}/state")
        if saved_state is not None:
            perspective.window_state = bytes(saved_state)

    def switch_to(self, perspective_id: str, window: QMainWindow) -> None:
        if perspective_id not in self._perspectives:
            raise KeyError(f"Unknown perspective: {perspective_id}")
        perspective = self._perspectives[perspective_id]
        if perspective.window_state:
            window.restoreState(perspective.window_state)
        self._current_id = perspective_id
        self._store.set("current", perspective_id)

    def save_current(self, window: QMainWindow) -> None:
        if self._current_id and self._current_id in self._perspectives:
            perspective = self._perspectives[self._current_id]
            perspective.window_state = bytes(window.saveState())
            self._store.set(f"{self._current_id}/state", perspective.window_state)

    def create_from_current(self, name: str, window: QMainWindow) -> Perspective:
        pid = f"user_{len(self._perspectives)}"
        perspective = Perspective(
            perspective_id=pid,
            name=name,
            window_state=bytes(window.saveState()),
        )
        self._perspectives[pid] = perspective
        self._store.set(f"{pid}/name", name)
        self._store.set(f"{pid}/state", perspective.window_state)
        return perspective

    def delete(self, perspective_id: str) -> None:
        if perspective_id not in self._perspectives:
            raise KeyError(f"Unknown perspective: {perspective_id}")
        if self._perspectives[perspective_id].builtin:
            raise ValueError("Cannot delete built-in perspective")
        del self._perspectives[perspective_id]
        self._store.remove(perspective_id)

    def all(self) -> list[Perspective]:
        return list(self._perspectives.values())

    def current(self) -> Perspective | None:
        if self._current_id and self._current_id in self._perspectives:
            return self._perspectives[self._current_id]
        return None
