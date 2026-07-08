import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QDockWidget,
    QToolBar,
    QToolButton,
    QFileDialog,
    QMessageBox,
    QApplication,
)
from PySide6.QtGui import QAction, QKeySequence

from prep.core.path_model import PathCollection
from prep.io.base import get_registry as get_importer_registry
from prep.io.prep_writer import to_prep_svg
from prep.pipeline.base import get_registry as get_pipeline_registry
from prep.hardware.base import get_registry as get_hardware_registry
from prep.ui.canvas import Canvas
from prep.ui.pipeline_panel import PipelinePanel
from prep.ui.layer_panel import LayerPanel
from prep.ui.layout_panel import LayoutPanel
from prep.ui.hardware_panel import HardwarePanel
from prep.ui.plugin_panel import PluginPanel
from prep.ui.plugin import AppContext, get_registry as get_ui_registry
from prep.ui.settings_store import SettingsStore
from prep.ui.perspective import Perspective, PerspectiveManager


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Prep")
        self.resize(1200, 800)

        self._store = SettingsStore()
        self._importer_registry = get_importer_registry()
        self._pipeline_registry = get_pipeline_registry()
        self._hardware_registry = get_hardware_registry()
        self._ui_registry = get_ui_registry()

        self._importer_registry.load_plugins()
        self._pipeline_registry.load_plugins()
        self._hardware_registry.load_plugins()
        self._ui_registry.load_plugins()

        self._collection: PathCollection | None = None
        self._current_file: Path | None = None

        self._canvas = Canvas(self)
        self.setCentralWidget(self._canvas)
        self._canvas.setObjectName("canvas")

        self._pipeline_panel = PipelinePanel(self._pipeline_registry, self)
        self._pipeline_panel.set_step_selected_callback(self._show_step)
        pipeline_dock = QDockWidget("Pipeline", self)
        pipeline_dock.setWidget(self._pipeline_panel)
        pipeline_dock.setObjectName("view.pipeline")
        self.addDockWidget(Qt.LeftDockWidgetArea, pipeline_dock)

        self._layer_panel = LayerPanel(self)
        layer_dock = QDockWidget("Layers", self)
        layer_dock.setWidget(self._layer_panel)
        layer_dock.setObjectName("view.layers")
        self.addDockWidget(Qt.RightDockWidgetArea, layer_dock)

        self._layout_panel = LayoutPanel(self)
        self._layout_panel.set_fit_callback(self.run_pipeline)
        layout_dock = QDockWidget("Layout", self)
        layout_dock.setWidget(self._layout_panel)
        layout_dock.setObjectName("view.layout")
        self.addDockWidget(Qt.RightDockWidgetArea, layout_dock)

        self._hardware_panel = HardwarePanel(self._hardware_registry, self)
        hardware_dock = QDockWidget("Hardware", self)
        hardware_dock.setWidget(self._hardware_panel)
        hardware_dock.setObjectName("view.hardware")
        self.addDockWidget(Qt.RightDockWidgetArea, hardware_dock)
        hardware_dock.hide()

        self._ctx = AppContext(self, self._store, self._pipeline_registry)
        self._plugin_panel = PluginPanel(self._ui_registry, self._ctx, self)
        plugin_dock = QDockWidget("Plugins", self)
        plugin_dock.setWidget(self._plugin_panel)
        plugin_dock.setObjectName("view.plugins")
        self.addDockWidget(Qt.RightDockWidgetArea, plugin_dock)
        plugin_dock.hide()

        self._perspective_manager = PerspectiveManager(self._store)
        self._perspective_manager.register(Perspective("prepare", "Prepare", builtin=True))
        self._perspective_manager.register(Perspective("cut", "Cut", builtin=True))
        self._setup_perspectives()

        self._setup_menus()
        self._setup_toolbar()

        self._store.restore_window(self)
        self._load_settings()

        enabled_plugins = self._store.get("ui_plugins/enabled", [])
        if isinstance(enabled_plugins, list):
            for plugin_id in enabled_plugins:
                try:
                    self._ui_registry.activate(plugin_id, self._ctx)
                except Exception:
                    pass

        self._perspective_manager.switch_to(
            self._store.get("perspectives/current", "prepare"),
            self,
        )

    def _setup_menus(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        new_action = QAction("&New", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._new_file)
        file_menu.addAction(new_action)

        open_action = QAction("&Open…", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As…", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._save_file_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        import_action = QAction("Import &SVG…", self)
        import_action.triggered.connect(self._import_svg)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = menubar.addMenu("&View")
        for dock in self.findChildren(QDockWidget):
            view_menu.addAction(dock.toggleViewAction())

        perspective_menu = menubar.addMenu("&Perspective")
        for perspective in self._perspective_manager.all():
            action = QAction(perspective.name, self)
            action.triggered.connect(lambda checked, pid=perspective.perspective_id: self._switch_perspective(pid))
            perspective_menu.addAction(action)

        plugins_menu = menubar.addMenu("&Plugins")
        manage_action = QAction("Manage Plugins", self)
        manage_action.triggered.connect(self._show_plugin_panel)
        plugins_menu.addAction(manage_action)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Perspectives", self)
        toolbar.setObjectName("perspective_toolbar")
        self.addToolBar(toolbar)

        for perspective in self._perspective_manager.all():
            btn = QToolButton()
            btn.setText(perspective.name)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, pid=perspective.perspective_id: self._switch_perspective(pid))
            toolbar.addWidget(btn)

    def _setup_perspectives(self) -> None:
        self.saveState()

    def _switch_perspective(self, perspective_id: str) -> None:
        self._perspective_manager.switch_to(perspective_id, self)

    def _show_plugin_panel(self) -> None:
        for dock in self.findChildren(QDockWidget):
            if dock.objectName() == "view.plugins":
                dock.show()
                dock.raise_()

    def _new_file(self) -> None:
        self._collection = None
        self._current_file = None
        self._canvas.set_collection(None)
        self._layer_panel.set_collection(None)
        self._layout_panel.set_collection(None)
        self._hardware_panel.set_collection(None)

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",
            "All Supported (*.svg *.svgz *.prep);;SVG Files (*.svg *.svgz);;Prep Projects (*.prep)",
        )
        if path:
            self._open_file(Path(path))

    def _open_file(self, path: Path) -> None:
        try:
            importer = self._importer_registry.for_path(path)
            self._collection = importer.read(path)
            self._current_file = path

            if self._collection.pipeline_settings:
                for step_name, settings in self._collection.pipeline_settings.items():
                    for step in self._pipeline_registry.steps():
                        if step.name == step_name and hasattr(step, "set_settings"):
                            step.set_settings(settings)

            self.run_pipeline()
        except Exception as e:
            QMessageBox.critical(self, "Open Error", str(e))

    def _save_file(self) -> None:
        if not self._collection:
            return
        if not self._current_file:
            self._save_file_as()
            return
        if self._current_file.suffix != ".prep":
            self._save_file_as()
            return
        self._save_to_path(self._current_file)

    def _save_file_as(self) -> None:
        if not self._collection:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save As",
            "",
            "Prep Project (*.prep);;SVG Files (*.svg)",
        )
        if path:
            self._save_to_path(Path(path))
            self._current_file = Path(path)

    def _save_to_path(self, path: Path) -> None:
        try:
            svg = to_prep_svg(self._collection, self._pipeline_registry.steps())
            path.write_text(svg)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _import_svg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import SVG",
            "",
            "SVG Files (*.svg *.svgz)",
        )
        if path:
            try:
                from prep.io.importers.svg import SVGImporter
                importer = SVGImporter()
                self._collection = importer.read(Path(path))
                self.run_pipeline()
            except Exception as e:
                QMessageBox.critical(self, "Import Error", str(e))

    def run_pipeline(self) -> None:
        if not self._collection:
            return
        result = self._pipeline_registry.run(self._collection)
        self._collection = result
        self._pipeline_panel.populate()
        self._canvas.set_collection(result)
        self._layer_panel.set_collection(result)
        self._layout_panel.set_collection(result)
        self._hardware_panel.set_collection(result)

    def _show_step(self, index: int) -> None:
        trace = self._pipeline_registry.trace()
        if 0 <= index < len(trace):
            self._canvas.set_collection(trace[index].collection)

    def _load_settings(self) -> None:
        for step in self._pipeline_registry.steps():
            if hasattr(step, "set_settings"):
                settings = self._store.namespace("pipeline").namespace(step.name).get("settings")
                if isinstance(settings, dict):
                    step.set_settings(settings)

        for driver in self._hardware_registry.drivers():
            if hasattr(driver, "set_settings"):
                settings = self._store.namespace("hardware").namespace(driver.driver_id).get("settings")
                if isinstance(settings, dict):
                    driver.set_settings(settings)

    def _save_settings(self) -> None:
        for step in self._pipeline_registry.steps():
            if hasattr(step, "get_settings"):
                settings = step.get_settings()
                self._store.namespace("pipeline").namespace(step.name).set("settings", settings)

        for driver in self._hardware_registry.drivers():
            if hasattr(driver, "get_settings"):
                settings = driver.get_settings()
                self._store.namespace("hardware").namespace(driver.driver_id).set("settings", settings)

        enabled = list(self._ui_registry._active.keys())
        self._store.set("ui_plugins/enabled", enabled)

    def closeEvent(self, event) -> None:
        self._perspective_manager.save_current(self)
        self._store.save_window(self)
        self._save_settings()
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
