from PySide6.QtWidgets import (
    QWidget,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QVBoxLayout,
    QHBoxLayout,
)

from prep.pipeline.base import PipelineRegistry
from prep.ui.settings import SettingsDialog


class PipelinePanel(QWidget):
    def __init__(self, registry: PipelineRegistry, parent=None) -> None:
        super().__init__(parent)
        self._registry = registry

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        self._settings_btn = QToolButton()
        self._settings_btn.setText("⚙")
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.clicked.connect(self._on_settings)
        btn_layout.addWidget(self._settings_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._on_step_selected = None

    def set_step_selected_callback(self, callback) -> None:
        self._on_step_selected = callback

    def populate(self) -> None:
        self._list.clear()
        trace = self._registry.trace()
        for entry in trace:
            item = QListWidgetItem(entry.label.title())
            self._list.addItem(item)
        if trace:
            self._list.setCurrentRow(len(trace) - 1)

    def _on_row_changed(self, row: int) -> None:
        if self._on_step_selected and row >= 0:
            self._on_step_selected(row)

    def _on_settings(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        trace = self._registry.trace()
        if row >= len(trace):
            return
        entry = trace[row]
        if entry.step and hasattr(entry.step, "settings_schema"):
            dialog = SettingsDialog(entry.step, self)
            dialog.exec()
