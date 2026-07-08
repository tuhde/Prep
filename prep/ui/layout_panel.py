from PySide6.QtWidgets import (
    QWidget,
    QFormLayout,
    QDoubleSpinBox,
    QPushButton,
    QVBoxLayout,
)

from prep.core.path_model import PathCollection


class LayoutPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._collection: PathCollection | None = None
        self._on_fit_clicked = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        form = QFormLayout()
        self._width_spin = QDoubleSpinBox()
        self._width_spin.setRange(1, 10000)
        self._width_spin.setSuffix(" mm")
        self._width_spin.setDecimals(1)
        form.addRow("Width:", self._width_spin)

        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(1, 10000)
        self._height_spin.setSuffix(" mm")
        self._height_spin.setDecimals(1)
        form.addRow("Height:", self._height_spin)

        layout.addLayout(form)

        self._fit_btn = QPushButton("Fit to Sheet")
        self._fit_btn.clicked.connect(self._on_fit)
        layout.addWidget(self._fit_btn)

        layout.addStretch()

    def set_fit_callback(self, callback) -> None:
        self._on_fit_clicked = callback

    def set_collection(self, collection: PathCollection | None) -> None:
        self._collection = collection
        if collection:
            self._width_spin.blockSignals(True)
            self._height_spin.blockSignals(True)
            self._width_spin.setValue(collection.material_width)
            self._height_spin.setValue(collection.material_height)
            self._width_spin.blockSignals(False)
            self._height_spin.blockSignals(False)

    def _on_fit(self) -> None:
        if not self._collection:
            return
        self._collection.material_width = self._width_spin.value()
        self._collection.material_height = self._height_spin.value()
        if self._on_fit_clicked:
            self._on_fit_clicked()
