from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
from shapely.geometry import LineString, LinearRing


class Dimensionality(Enum):
    D2 = "2d"
    D2_5 = "2.5d"
    D3 = "3d"


@dataclass
class CutPath:
    geometry: LineString | LinearRing
    closed: bool
    z: float | np.ndarray | None = None

    @property
    def dimensionality(self) -> Dimensionality:
        if self.z is None:
            return Dimensionality.D2
        if isinstance(self.z, float):
            return Dimensionality.D2_5
        return Dimensionality.D3


@dataclass
class CutLayer:
    color: str
    label: str
    speed: float
    power: float
    force: int
    paths: list[CutPath] = field(default_factory=list)


@dataclass
class HardwareConfig:
    driver: str
    port: str
    baud: int


@dataclass
class PathCollection:
    material_width: float
    material_height: float
    material_depth: float = 0.0
    layers: list[CutLayer] = field(default_factory=list)
    hardware: HardwareConfig = field(default_factory=lambda: HardwareConfig("", "", 0))
    pipeline_settings: dict[str, dict[str, Any]] | None = None