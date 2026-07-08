from PySide6.QtWidgets import (
    QWidget,
    QComboBox,
    QToolButton,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QHBoxLayout,
)

from prep.hardware.base import HardwareRegistry, HardwareDriverProtocol
from prep.core.path_model import PathCollection
from prep.ui.settings import SettingsDialog


class HardwarePanel(QWidget):
    def __init__(self, registry: HardwareRegistry, parent=None) -> None:
        super().__init__(parent)
        self._registry = registry
        self._collection: PathCollection | None = None
        self._current_driver: HardwareDriverProtocol | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        driver_layout = QHBoxLayout()
        self._driver_combo = QComboBox()
        self._driver_combo.currentIndexChanged.connect(self._on_driver_changed)
        driver_layout.addWidget(self._driver_combo)

        self._settings_btn = QToolButton()
        self._settings_btn.setText("⚙")
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.clicked.connect(self._on_settings)
        driver_layout.addWidget(self._settings_btn)
        layout.addLayout(driver_layout)

        btn_layout = QHBoxLayout()
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.clicked.connect(self._on_connect)
        btn_layout.addWidget(self._connect_btn)

        self._send_btn = QPushButton("Send")
        self._send_btn.setEnabled(False)
        self._send_btn.clicked.connect(self._on_send)
        btn_layout.addWidget(self._send_btn)
        layout.addLayout(btn_layout)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        layout.addStretch()

        self._populate_drivers()

    def _populate_drivers(self) -> None:
        self._driver_combo.clear()
        drivers = self._registry.drivers()
        for driver in drivers:
            self._driver_combo.addItem(driver.name, driver.driver_id)

    def set_collection(self, collection: PathCollection | None) -> None:
        self._collection = collection

    def _on_driver_changed(self, index: int) -> None:
        if index < 0:
            self._current_driver = None
            self._settings_btn.setEnabled(False)
            return
        driver_id = self._driver_combo.itemData(index)
        try:
            self._current_driver = self._registry.by_id(driver_id)
            self._settings_btn.setEnabled(hasattr(self._current_driver, "settings_schema"))
        except KeyError:
            self._current_driver = None
            self._settings_btn.setEnabled(False)

    def _on_settings(self) -> None:
        if self._current_driver and hasattr(self._current_driver, "settings_schema"):
            dialog = SettingsDialog(self._current_driver, self)
            dialog.exec()

    def _on_connect(self) -> None:
        if not self._current_driver:
            return
        if self._connect_btn.text() == "Connect":
            if self._collection:
                port = self._collection.hardware.port
                baud = self._collection.hardware.baud
            else:
                port = ""
                baud = 9600
            try:
                self._current_driver.connect(port, baud)
                self._connect_btn.setText("Disconnect")
                self._send_btn.setEnabled(True)
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Connection Error", str(e))
        else:
            try:
                self._current_driver.disconnect()
            except Exception:
                pass
            self._connect_btn.setText("Connect")
            self._send_btn.setEnabled(False)

    def _on_send(self) -> None:
        if not self._current_driver or not self._collection:
            return
        try:
            self._current_driver.send(self._collection, self._on_progress)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Send Error", str(e))

    def _on_progress(self, fraction: float) -> None:
        self._progress_bar.setValue(int(fraction * 100))
