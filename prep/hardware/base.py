from importlib.metadata import EntryPoint, entry_points
from typing import Callable, Protocol

from prep.core.path_model import PathCollection


class HardwareDriverProtocol(Protocol):
    name: str
    driver_id: str

    def connect(self, port: str, baud: int) -> None: ...
    def send(self, collection: PathCollection, progress_cb: Callable[[float], None]) -> None: ...
    def disconnect(self) -> None: ...


class HardwareRegistry:
    _descriptors: dict[str, EntryPoint]
    _loaded: dict[str, HardwareDriverProtocol]

    def __init__(self) -> None:
        self._descriptors = {}
        self._loaded = {}

    def load_plugins(self) -> None:
        try:
            eps = entry_points(group="prep.hardware")
        except TypeError:
            eps = entry_points().get("prep.hardware", [])
        for ep in eps:
            self._descriptors[ep.name] = ep

    def drivers(self) -> list[HardwareDriverProtocol]:
        for name, ep in self._descriptors.items():
            if name not in self._loaded:
                driver_cls = ep.load()
                self._loaded[name] = driver_cls()
        return sorted(self._loaded.values(), key=lambda d: d.name)

    def by_id(self, driver_id: str) -> HardwareDriverProtocol:
        if driver_id not in self._loaded:
            if driver_id in self._descriptors:
                driver_cls = self._descriptors[driver_id].load()
                self._loaded[driver_id] = driver_cls()
            else:
                raise KeyError(f"Unknown driver: {driver_id}")
        return self._loaded[driver_id]


_registry = HardwareRegistry()


def get_registry() -> HardwareRegistry:
    return _registry
