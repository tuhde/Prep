from pathlib import Path

import numpy as np
from shapely.geometry import LineString

from prep.core.path_model import (
    CutLayer,
    CutPath,
    Dimensionality,
    HardwareConfig,
    PathCollection,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_cut_path_2d():
    geom = LineString([(0, 0), (1, 1)])
    path = CutPath(geometry=geom, closed=False)
    assert path.dimensionality == Dimensionality.D2
    assert path.z is None


def test_cut_path_2_5d():
    geom = LineString([(0, 0), (1, 1)])
    path = CutPath(geometry=geom, closed=False, z=1.5)
    assert path.dimensionality == Dimensionality.D2_5
    assert path.z == 1.5


def test_cut_path_3d():
    geom = LineString([(0, 0), (1, 1), (2, 2)])
    z = np.array([0.5, 1.0, 1.5])
    path = CutPath(geometry=geom, closed=False, z=z)
    assert path.dimensionality == Dimensionality.D3
    assert isinstance(path.z, np.ndarray)
    assert len(path.z) == 3


def test_cut_layer():
    paths = [CutPath(geometry=LineString([(0, 0), (1, 1)]), closed=False)]
    layer = CutLayer(color="#ff0000", label="Test", speed=800.0, power=0.8, force=100, paths=paths)
    assert layer.color == "#ff0000"
    assert len(layer.paths) == 1


def test_path_collection():
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50)
    hw = HardwareConfig(driver="test", port="/dev/tty0", baud=9600)
    col = PathCollection(material_width=100.0, material_height=200.0, layers=[layer], hardware=hw)
    assert col.material_width == 100.0
    assert col.material_height == 200.0
    assert col.material_depth == 0.0
    assert len(col.layers) == 1
    assert col.hardware.driver == "test"
    assert col.pipeline_settings is None
