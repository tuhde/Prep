from shapely.geometry import LineString

from prep.core.path_model import CutLayer, CutPath, PathCollection
from prep.io.gcode_writer import to_gcode
from prep.io.hpgl_writer import to_hpgl


def test_gcode_writer_basic():
    path = CutPath(geometry=LineString([(0, 0), (10, 10), (20, 0)]), closed=False)
    layer = CutLayer(color="#000", label="L", speed=100, power=0.8, force=50, paths=[path])
    col = PathCollection(material_width=100, material_height=100, layers=[layer])
    gcode = to_gcode(col)
    assert "G21" in gcode
    assert "G90" in gcode
    assert "M3 S800" in gcode
    assert "G0 X0.000 Y0.000" in gcode
    assert "G1 X10.000 Y10.000" in gcode
    assert "G1 X20.000 Y0.000" in gcode
    assert "M5" in gcode


def test_gcode_writer_2_5d():
    path = CutPath(geometry=LineString([(0, 0), (10, 10)]), closed=False, z=1.5)
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=[path])
    col = PathCollection(material_width=100, material_height=100, layers=[layer])
    gcode = to_gcode(col)
    assert "G1 Z1.500" in gcode
    assert "G0 Z5" in gcode


def test_gcode_writer_3d():
    import numpy as np
    path = CutPath(geometry=LineString([(0, 0), (10, 10), (20, 0)]), closed=False, z=np.array([0.5, 1.0, 1.5]))
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=[path])
    col = PathCollection(material_width=100, material_height=100, layers=[layer])
    gcode = to_gcode(col)
    assert "G1 X10.000 Y10.000 Z1.000" in gcode
    assert "G1 X20.000 Y0.000 Z1.500" in gcode


def test_hpgl_writer_basic():
    path = CutPath(geometry=LineString([(0, 0), (10, 10)]), closed=False)
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=[path])
    col = PathCollection(material_width=100, material_height=100, layers=[layer])
    hpgl = to_hpgl(col)
    assert "IN;" in hpgl
    assert "SP1;" in hpgl
    assert "PU0,0;" in hpgl
    assert "PD400,400;" in hpgl
    assert "SP0;" in hpgl


def test_hpgl_writer_closed_path():
    path = CutPath(geometry=LineString([(0, 0), (10, 0), (10, 10), (0, 0)]), closed=True)
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=[path])
    col = PathCollection(material_width=100, material_height=100, layers=[layer])
    hpgl = to_hpgl(col)
    assert "PU0,0;" in hpgl
    assert "PD400,0,400,400,0,0;" in hpgl


def test_hpgl_writer_multiple_paths():
    paths = [
        CutPath(geometry=LineString([(0, 0), (10, 10)]), closed=False),
        CutPath(geometry=LineString([(20, 20), (30, 30)]), closed=False),
    ]
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=paths)
    col = PathCollection(material_width=100, material_height=100, layers=[layer])
    hpgl = to_hpgl(col)
    assert hpgl.count("PU") == 2
    assert hpgl.count("PD") == 2
