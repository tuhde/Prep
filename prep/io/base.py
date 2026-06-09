from importlib.metadata import entry_points
from pathlib import Path
from typing import Protocol

from prep.core.path_model import PathCollection


class ImporterProtocol(Protocol):
    name: str
    extensions: frozenset[str]

    def can_handle(self, path: Path) -> bool: ...
    def read(self, path: Path) -> PathCollection: ...


class ImporterRegistry:
    _descriptors: dict[str, entry_points.EntryPoint]
    _loaded: dict[str, ImporterProtocol]

    def __init__(self) -> None:
        self._descriptors = {}
        self._loaded = {}

    def register(self, importer: ImporterProtocol) -> None:
        self._loaded[type(importer).__name__] = importer

    def for_path(self, path: Path) -> ImporterProtocol:
        for name, importer in self._loaded.items():
            if importer.can_handle(path):
                return importer
        raise ValueError(f"No importer found for {path.suffix}")

    def load_plugins(self) -> None:
        try:
            eps = entry_points(group="prep.importers")
        except TypeError:
            eps = entry_points().get("prep.importers", [])
        for ep in eps:
            importer = ep.load()
            self._loaded[ep.name] = importer()


_registry = ImporterRegistry()


def get_registry() -> ImporterRegistry:
    return _registry