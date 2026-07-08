from dataclasses import dataclass
from typing import Callable, Protocol
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget, QMainWindow, QGraphicsItem

from prep.core.path_model import PathCollection
from prep.pipeline.base import PipelineRegistry
from prep.ui.settings_store import SettingsStore


@dataclass
class AppEvent:
    pass


@dataclass
class FileOpenedEvent(AppEvent):
    path: Path
    collection: PathCollection


@dataclass
class PipelineCompletedEvent(AppEvent):
    collection: PathCollection


@dataclass
class HardwareConnectedEvent(AppEvent):
    driver: object


@dataclass
class HardwareDisconnectedEvent(AppEvent):
    driver: object


class AppContext:
    def __init__(
        self,
        window: QMainWindow,
        store: SettingsStore,
        pipeline_registry: PipelineRegistry,
    ) -> None:
        self._window = window
        self._store = store
        self._pipeline_registry = pipeline_registry
        self._collection: PathCollection | None = None
        self._panels: list[QWidget] = []
        self._menu_actions: list[tuple[str, QAction]] = []
        self._toolbar_actions: list[QAction] = []
        self._canvas_overlays: list[QGraphicsItem] = []
        self._event_handlers: dict[type[AppEvent], list[Callable]] = {}

    def collection(self) -> PathCollection | None:
        return self._collection

    def set_collection(self, collection: PathCollection) -> None:
        self._collection = collection

    def run_pipeline(self) -> None:
        from prep.ui.main_window import MainWindow
        if isinstance(self._window, MainWindow):
            self._window.run_pipeline()

    def add_panel(self, widget: QWidget, title: str, area: Qt.DockWidgetArea = Qt.RightDockWidgetArea) -> None:
        from PySide6.QtWidgets import QDockWidget
        dock = QDockWidget(title, self._window)
        dock.setWidget(widget)
        dock.setObjectName(f"view.plugin.{title.lower().replace(' ', '_')}")
        self._window.addDockWidget(area, dock)
        self._panels.append(dock)

    def add_menu_action(self, menu: str, action: QAction) -> None:
        self._menu_actions.append((menu, action))

    def add_toolbar_action(self, action: QAction) -> None:
        self._toolbar_actions.append(action)

    def add_canvas_overlay(self, item: QGraphicsItem) -> None:
        self._canvas_overlays.append(item)

    def subscribe(self, event_type: type[AppEvent], handler: Callable[[AppEvent], None]) -> None:
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def emit(self, event: AppEvent) -> None:
        event_type = type(event)
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                handler(event)

    def settings(self) -> SettingsStore:
        return self._store


class UIPluginProtocol(Protocol):
    name: str
    plugin_id: str
    description: str
    author: str
    tags: list[str]

    def activate(self, ctx: AppContext) -> None: ...
    def deactivate(self) -> None: ...


class UIPluginRegistry:
    def __init__(self) -> None:
        from importlib.metadata import entry_points
        self._descriptors: dict = {}
        self._active: dict[str, UIPluginProtocol] = {}
        try:
            eps = entry_points(group="prep.ui")
        except TypeError:
            eps = entry_points().get("prep.ui", [])
        for ep in eps:
            self._descriptors[ep.name] = ep

    def load_plugins(self) -> None:
        pass

    def plugins(self) -> list[UIPluginProtocol]:
        result = []
        for name, ep in self._descriptors.items():
            try:
                plugin_cls = ep.load()
                result.append(plugin_cls())
            except Exception:
                pass
        return sorted(result, key=lambda p: p.name)

    def activate(self, plugin_id: str, ctx: AppContext) -> None:
        if plugin_id in self._active:
            return
        if plugin_id not in self._descriptors:
            raise KeyError(f"Unknown plugin: {plugin_id}")
        plugin_cls = self._descriptors[plugin_id].load()
        plugin = plugin_cls()
        plugin.activate(ctx)
        self._active[plugin_id] = plugin

    def deactivate(self, plugin_id: str) -> None:
        if plugin_id not in self._active:
            return
        plugin = self._active[plugin_id]
        plugin.deactivate()
        del self._active[plugin_id]


_registry = UIPluginRegistry()


def get_registry() -> UIPluginRegistry:
    return _registry
