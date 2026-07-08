from PySide6.QtWidgets import (
    QWidget,
    QListWidget,
    QListWidgetItem,
    QFormLayout,
    QDoubleSpinBox,
    QVBoxLayout,
)

from prep.core.path_model import PathCollection


class LayerPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._collection: PathCollection | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        form = QFormLayout()
        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setRange(0, 10000)
        self._speed_spin.setSuffix(" mm/min")
        self._speed_spin.valueChanged.connect(self._on_speed_changed)
        form.addRow("Speed:", self._speed_spin)

        self._power_spin = QDoubleSpinBox()
        self._power_spin.setRange(0, 1)
        self._power_spin.setSingleStep(0.01)
        self._power_spin.setDecimals(2)
        self._power_spin.valueChanged.connect(self._on_power_changed)
        form.addRow("Power:", self._power_spin)

        self._force_spin = QDoubleSpinBox()
        self._force_spin.setRange(0, 1000)
        self._force_spin.setSuffix(" g")
        self._force_spin.valueChanged.connect(self._on_force_changed)
        form.addRow("Force:", self._force_spin)

        layout.addLayout(form)

    def set_collection(self, collection: PathCollection | None) -> None:
        self._collection = collection
        self._list.clear()
        if collection:
            for layer in collection.layers:
                item = QListWidgetItem(f"{layer.label} ({layer.color})")
                self._list.addItem(item)

    def _on_row_changed(self, row: int) -> None:
        if not self._collection or row < 0 or row >= len(self._collection.layers):
            return
        layer = self._collection.layers[row]
        self._speed_spin.blockSignals(True)
        self._power_spin.blockSignals(True)
        self._force_spin.blockSignals(True)
        self._speed_spin.setValue(layer.speed)
        self._power_spin.setValue(layer.power)
        self._force_spin.setValue(layer.force)
        self._speed_spin.blockSignals(False)
        self._power_spin.blockSignals(False)
        self._force_spin.blockSignals(False)

    def _on_speed_changed(self, value: float) -> None:
        row = self._list.currentRow()
        if self._collection and 0 <= row < len(self._collection.layers):
            self._collection.layers[row].speed = value

    def _on_power_changed(self, value: float) -> None:
        row = self._list.currentRow()
        if self._collection and 0 <= row < len(self._collection.layers):
            self._collection.layers[row].power = value

    def _on_force_changed(self, value: float) -> None:
        row = self._list.currentRow()
        if self._collection and 0 <= row < len(self._collection.layers):
            self._collection.layers[row].force = int(value)
