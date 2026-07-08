from unittest.mock import patch

from shapely.geometry import LineString

from prep.core.path_model import CutLayer, CutPath, PathCollection
from prep.hardware.base import HardwareRegistry
from prep.hardware.serial_comm import SerialComm


def test_hardware_registry_loads_plugins():
    reg = HardwareRegistry()
    reg.load_plugins()
    drivers = reg.drivers()
    assert len(drivers) >= 2
    driver_ids = {d.driver_id for d in drivers}
    assert "preview" in driver_ids
    assert "creation_ct630" in driver_ids


def test_hardware_registry_by_id():
    reg = HardwareRegistry()
    reg.load_plugins()
    preview = reg.by_id("preview")
    assert preview.name == "Preview"
    assert preview.driver_id == "preview"


def test_hardware_registry_unknown_driver():
    reg = HardwareRegistry()
    reg.load_plugins()
    try:
        reg.by_id("nonexistent")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass


def test_serial_comm_connect_disconnect():
    with patch("serial.Serial") as mock_serial:
        comm = SerialComm()
        comm.connect("/dev/ttyUSB0", 9600)
        mock_serial.assert_called_once_with("/dev/ttyUSB0", 9600, timeout=1)
        comm.disconnect()
        mock_serial.return_value.close.assert_called_once()


def test_serial_comm_writeline():
    with patch("serial.Serial") as mock_serial:
        comm = SerialComm()
        comm.connect("/dev/ttyUSB0", 9600)
        comm.writeline("IN;")
        mock_serial.return_value.write.assert_called_once_with(b"IN;\n")


def test_serial_comm_readline():
    with patch("serial.Serial") as mock_serial:
        mock_serial.return_value.readline.return_value = b"OK\n"
        comm = SerialComm()
        comm.connect("/dev/ttyUSB0", 9600)
        result = comm.readline()
        assert result == "OK"


def test_serial_comm_not_connected():
    comm = SerialComm()
    try:
        comm.writeline("test")
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass


def test_preview_driver_connect_disconnect():
    from prep_driver_preview import PreviewDriver
    driver = PreviewDriver()
    driver.connect("", 0)
    driver.disconnect()


def test_preview_driver_send():
    from prep_driver_preview import PreviewDriver
    driver = PreviewDriver()
    driver.speed_factor = 0.0

    path = CutPath(geometry=LineString([(0, 0), (10, 10)]), closed=False)
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=[path])
    col = PathCollection(material_width=100, material_height=100, layers=[layer])

    progress_values = []
    def progress_cb(fraction):
        progress_values.append(fraction)

    driver.send(col, progress_cb)
    assert len(progress_values) > 0
    assert progress_values[-1] == 1.0


def test_preview_driver_settings():
    from prep_driver_preview import PreviewDriver
    driver = PreviewDriver()
    schema = driver.settings_schema()
    assert len(schema) == 1
    assert schema[0].key == "speed_factor"

    settings = driver.get_settings()
    assert "speed_factor" in settings

    driver.set_settings({"speed_factor": 2.5})
    assert driver.speed_factor == 2.5


def test_ct630_driver_settings_widget():
    from prep_driver_creation_ct630 import CT630Driver
    driver = CT630Driver()
    assert hasattr(driver, "settings_widget")
