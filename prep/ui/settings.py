from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QScrollArea,
    QWidget,
    QFormLayout,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QDialogButtonBox,
    QVBoxLayout,
)

from prep.core.configurable import Configurable, SettingField


class SettingsDialog(QDialog):
    def __init__(self, plugin: Configurable, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._plugin = plugin
        self._widgets: dict[str, QWidget] = {}

        self.setWindowTitle(f"{getattr(plugin, 'name', 'Plugin')} — Settings")
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        if hasattr(plugin, "settings_widget"):
            widget = plugin.settings_widget()
            if widget:
                scroll.setWidget(widget)
            else:
                self._build_form(scroll)
        else:
            self._build_form(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_form(self, scroll: QScrollArea) -> None:
        container = QWidget()
        form = QFormLayout(container)
        scroll.setWidget(container)

        schema = self._plugin.settings_schema()
        current = self._plugin.get_settings()

        for field in schema:
            widget = self._create_widget(field, current.get(field.key, field.default))
            self._widgets[field.key] = widget
            form.addRow(field.label, widget)

    def _create_widget(self, field: SettingField, value: Any) -> QWidget:
        if field.choices:
            combo = QComboBox()
            combo.addItems(field.choices)
            if value in field.choices:
                combo.setCurrentText(str(value))
            return combo

        if field.type is bool:
            cb = QCheckBox()
            cb.setChecked(bool(value))
            return cb

        if field.type is int:
            spin = QSpinBox()
            if field.min is not None:
                spin.setMinimum(int(field.min))
            else:
                spin.setMinimum(-999999)
            if field.max is not None:
                spin.setMaximum(int(field.max))
            else:
                spin.setMaximum(999999)
            spin.setValue(int(value) if value is not None else int(field.default))
            return spin

        if field.type is float:
            spin = QDoubleSpinBox()
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            if field.min is not None:
                spin.setMinimum(float(field.min))
            else:
                spin.setMinimum(-999999.0)
            if field.max is not None:
                spin.setMaximum(float(field.max))
            else:
                spin.setMaximum(999999.0)
            spin.setValue(float(value) if value is not None else float(field.default))
            return spin

        line = QLineEdit()
        line.setText(str(value) if value is not None else str(field.default))
        return line

    def accept(self) -> None:
        values: dict[str, Any] = {}
        for key, widget in self._widgets.items():
            if isinstance(widget, QComboBox):
                values[key] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                values[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                values[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                values[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                values[key] = widget.text()
        self._plugin.set_settings(values)
        super().accept()
