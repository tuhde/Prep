from typing import Callable

from prep.core.path_model import PathCollection
from prep.hardware.serial_comm import SerialComm
from prep.io.hpgl_writer import to_hpgl


class CT630Driver:
    name = "Creation CT630"
    driver_id = "creation_ct630"

    def __init__(self) -> None:
        self._comm = SerialComm()
        self._port = ""
        self._baud = 9600

    def connect(self, port: str, baud: int) -> None:
        self._port = port
        self._baud = baud
        self._comm.connect(port, baud)
        self._comm.writeline("IN;")
        self._comm.readline()

    def send(self, collection: PathCollection, progress_cb: Callable[[float], None]) -> None:
        hpgl = to_hpgl(collection)
        total_bytes = len(hpgl)
        sent_bytes = 0
        chunk_size = 64

        for i in range(0, len(hpgl), chunk_size):
            chunk = hpgl[i:i + chunk_size]
            self._comm.writeline(chunk)
            sent_bytes += len(chunk)
            progress_cb(sent_bytes / total_bytes)

    def disconnect(self) -> None:
        self._comm.writeline("SP0;")
        self._comm.disconnect()

    def settings_widget(self):
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QSpinBox, QLabel
        from serial.tools import list_ports

        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Port:"))
        port_combo = QComboBox()
        ports = [p.device for p in list_ports.comports()]
        port_combo.addItems(ports)
        if self._port in ports:
            port_combo.setCurrentText(self._port)
        layout.addWidget(port_combo)

        layout.addWidget(QLabel("Baud:"))
        baud_spin = QSpinBox()
        baud_spin.setRange(1200, 115200)
        baud_spin.setValue(self._baud)
        layout.addWidget(baud_spin)

        def on_port_changed(index):
            self._port = port_combo.itemText(index)

        def on_baud_changed(value):
            self._baud = value

        port_combo.currentIndexChanged.connect(on_port_changed)
        baud_spin.valueChanged.connect(on_baud_changed)

        return widget
