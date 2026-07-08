import serial


class SerialComm:
    def __init__(self) -> None:
        self._serial: serial.Serial | None = None

    def connect(self, port: str, baud: int) -> None:
        self._serial = serial.Serial(port, baud, timeout=1)

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def writeline(self, line: str) -> None:
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Not connected")
        self._serial.write((line + "\n").encode("utf-8"))

    def readline(self) -> str:
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Not connected")
        return self._serial.readline().decode("utf-8").strip()
