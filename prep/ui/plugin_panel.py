from PySide6.QtWidgets import (
    QWidget,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
)

from prep.ui.plugin import UIPluginRegistry, AppContext
from prep.ui.settings import SettingsDialog


class PluginPanel(QWidget):
    def __init__(self, registry: UIPluginRegistry, ctx: AppContext, parent=None) -> None:
        super().__init__(parent)
        self._registry = registry
        self._ctx = ctx

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._plugin_list = QListWidget()
        self._plugin_list.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self._plugin_list)

        btn_layout = QHBoxLayout()
        self._settings_btn = QToolButton()
        self._settings_btn.setText("⚙")
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.clicked.connect(self._on_settings)
        btn_layout.addWidget(self._settings_btn)

        self._toggle_btn = QPushButton("Enable")
        self._toggle_btn.clicked.connect(self._on_toggle)
        btn_layout.addWidget(self._toggle_btn)

        self._marketplace_btn = QPushButton("Browse Marketplace")
        self._marketplace_btn.setEnabled(False)
        btn_layout.addWidget(self._marketplace_btn)

        layout.addLayout(btn_layout)

        self._populate()

    def _populate(self) -> None:
        self._plugin_list.clear()
        plugins = self._registry.plugins()
        for plugin in plugins:
            text = f"{plugin.name}\n{plugin.author}\n{plugin.description}"
            item = QListWidgetItem(text)
            self._plugin_list.addItem(item)

    def _on_selection_changed(self, row: int) -> None:
        if row < 0:
            self._settings_btn.setEnabled(False)
            self._toggle_btn.setEnabled(False)
            return
        plugins = self._registry.plugins()
        if row >= len(plugins):
            return
        plugin = plugins[row]
        self._settings_btn.setEnabled(hasattr(plugin, "settings_schema"))
        self._toggle_btn.setEnabled(True)
        is_active = plugin.plugin_id in self._registry._active
        self._toggle_btn.setText("Disable" if is_active else "Enable")

    def _on_settings(self) -> None:
        row = self._plugin_list.currentRow()
        if row < 0:
            return
        plugins = self._registry.plugins()
        if row >= len(plugins):
            return
        plugin = plugins[row]
        if hasattr(plugin, "settings_schema"):
            dialog = SettingsDialog(plugin, self)
            dialog.exec()

    def _on_toggle(self) -> None:
        row = self._plugin_list.currentRow()
        if row < 0:
            return
        plugins = self._registry.plugins()
        if row >= len(plugins):
            return
        plugin = plugins[row]
        if plugin.plugin_id in self._registry._active:
            self._registry.deactivate(plugin.plugin_id)
            self._toggle_btn.setText("Enable")
        else:
            self._registry.activate(plugin.plugin_id, self._ctx)
            self._toggle_btn.setText("Disable")
