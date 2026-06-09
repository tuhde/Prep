from dataclasses import dataclass
from typing import Any, Protocol

from prep.core.path_model import PathCollection


@dataclass
class SettingField:
    key: str
    type: type
    default: Any
    label: str
    description: str = ""
    min: float | None = None
    max: float | None = None
    choices: list[str] | None = None


class Configurable(Protocol):
    def settings_schema(self) -> list[SettingField]: ...
    def get_settings(self) -> dict[str, Any]: ...
    def set_settings(self, values: dict[str, Any]) -> None: ...


class PipelineStepProtocol(Protocol):
    name: str
    order: int

    def process(self, collection: PathCollection) -> PathCollection: ...