from pathlib import Path

import numpy as np
from shapely.geometry import LineString, LinearRing

from prep.core.path_model import CutLayer, CutPath, HardwareConfig, PathCollection
from prep.io.importers.prep import PrepProjectImporter
from prep.io.prep_writer import to_prep_svg
from prep.pipeline.base import PipelineRegistry
from prep.pipeline.steps.optimizer import OptimizerStep
from prep.pipeline.steps.splitter import SplitterStep
from prep.pipeline.steps.layout import LayoutStep
from prep.pipeline.steps.cut_order import CutOrderStep

FIXTURES = Path(__file__).parent / "fixtures"


def _make_collection() -> PathCollection:
    paths = [
        CutPath(geometry=LineString([(10, 10), (50, 10), (50, 50), (10, 50)]), closed=True),
    ]
    layer = CutLayer(color="#ff0000", label="Red", speed=800.0, power=0.8, force=100, paths=paths)
    return PathCollection(
        material_width=100.0,
        material_height=100.0,
        layers=[layer],
        hardware=HardwareConfig(driver="test", port="/dev/tty0", baud=9600),
    )


def test_prep_writer_basic():
    col = _make_collection()
    svg = to_prep_svg(col, [])
    assert "prep:format-version" in svg
    assert "100.0mm" in svg
    assert "#ff0000" in svg
    assert "viewBox" in svg


def test_prep_writer_z_2_5d():
    path = CutPath(geometry=LineString([(0, 0), (1, 1)]), closed=False, z=1.5)
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=[path])
    col = PathCollection(material_width=10, material_height=10, layers=[layer])
    svg = to_prep_svg(col, [])
    assert 'prep:z="1.5"' in svg


def test_prep_writer_z_3d():
    path = CutPath(geometry=LineString([(0, 0), (1, 1), (2, 2)]), closed=False, z=np.array([0.5, 1.0, 1.5]))
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=[path])
    col = PathCollection(material_width=10, material_height=10, layers=[layer])
    svg = to_prep_svg(col, [])
    assert 'prep:z-data="0.5,1.0,1.5"' in svg


def test_prep_roundtrip():
    col = _make_collection()
    steps = [OptimizerStep(), SplitterStep(), LayoutStep(), CutOrderStep()]
    svg = to_prep_svg(col, steps)
    p = Path("/tmp/test_roundtrip.prep")
    p.write_text(svg)
    col2 = PrepProjectImporter().read(p)
    assert col2.material_width == col.material_width
    assert col2.material_height == col.material_height
    assert col2.hardware.driver == "test"
    assert col2.pipeline_settings is not None
    assert "optimizer" in col2.pipeline_settings
    p.unlink()


def test_optimizer_simplifies():
    coords = [(i, i * 0.001) for i in range(100)]
    path = CutPath(geometry=LineString(coords), closed=False)
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=[path])
    col = PathCollection(material_width=100, material_height=100, layers=[layer])
    step = OptimizerStep()
    step.tolerance = 0.1
    result = step.process(col)
    assert len(list(result.layers[0].paths[0].geometry.coords)) < 100


def test_optimizer_removes_duplicates():
    geom = LineString([(0, 0), (1, 1), (2, 2)])
    paths = [
        CutPath(geometry=geom, closed=False),
        CutPath(geometry=LineString([(0, 0), (1, 1), (2, 2)]), closed=False),
    ]
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=paths)
    col = PathCollection(material_width=100, material_height=100, layers=[layer])
    step = OptimizerStep()
    result = step.process(col)
    assert len(result.layers[0].paths) == 1


def test_optimizer_normalizes_winding():
    coords = [(0, 0), (0, 10), (10, 10), (10, 0)]
    ring = LinearRing(coords)
    assert not ring.is_ccw
    path = CutPath(geometry=ring, closed=True)
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=[path])
    col = PathCollection(material_width=100, material_height=100, layers=[layer])
    step = OptimizerStep()
    result = step.process(col)
    result_geom = result.layers[0].paths[0].geometry
    assert isinstance(result_geom, LinearRing)
    assert result_geom.is_ccw


def test_splitter_merges_colors():
    l1 = CutLayer(color="#ff0000", label="R1", speed=100, power=0.5, force=50,
                  paths=[CutPath(geometry=LineString([(0, 0), (1, 1)]), closed=False)])
    l2 = CutLayer(color="#ff0000", label="R2", speed=200, power=0.6, force=60,
                  paths=[CutPath(geometry=LineString([(2, 2), (3, 3)]), closed=False)])
    col = PathCollection(material_width=100, material_height=100, layers=[l1, l2])
    step = SplitterStep()
    result = step.process(col)
    assert len(result.layers) == 1
    assert len(result.layers[0].paths) == 2


def test_layout_fits_to_sheet():
    path = CutPath(geometry=LineString([(0, 0), (200, 0), (200, 200), (0, 200)]), closed=True)
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=[path])
    col = PathCollection(material_width=100, material_height=100, layers=[layer])
    step = LayoutStep()
    result = step.process(col)
    coords = list(result.layers[0].paths[0].geometry.coords)
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    assert max(xs) <= 100.0 + 0.01
    assert max(ys) <= 100.0 + 0.01


def test_layout_offset():
    path = CutPath(geometry=LineString([(0, 0), (10, 10)]), closed=False)
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=[path])
    col = PathCollection(material_width=100, material_height=100, layers=[layer])
    step = LayoutStep()
    step.offset_x = 5.0
    step.offset_y = 3.0
    result = step.process(col)
    coords = list(result.layers[0].paths[0].geometry.coords)
    assert abs(coords[0][0] - 5.0) < 0.01
    assert abs(coords[0][1] - 3.0) < 0.01


def test_cut_order_nearest_neighbor():
    paths = [
        CutPath(geometry=LineString([(0, 0), (1, 0)]), closed=False),
        CutPath(geometry=LineString([(100, 100), (101, 100)]), closed=False),
        CutPath(geometry=LineString([(2, 0), (3, 0)]), closed=False),
    ]
    layer = CutLayer(color="#000", label="L", speed=100, power=0.5, force=50, paths=paths)
    col = PathCollection(material_width=200, material_height=200, layers=[layer])
    step = CutOrderStep()
    result = step.process(col)
    starts = [list(p.geometry.coords)[0] for p in result.layers[0].paths]
    assert starts[0] == (0.0, 0.0)
    assert starts[1] == (2.0, 0.0)
    assert starts[2] == (100.0, 100.0)


def test_pipeline_registry():
    reg = PipelineRegistry()
    reg.register(OptimizerStep())
    reg.register(SplitterStep())
    reg.register(LayoutStep())
    reg.register(CutOrderStep())
    steps = reg.steps()
    assert len(steps) == 4
    assert steps[0].name == "optimizer"
    assert steps[-1].name == "cut_order"


def test_pipeline_run():
    col = _make_collection()
    reg = PipelineRegistry()
    reg.register(OptimizerStep())
    reg.register(SplitterStep())
    reg.register(LayoutStep())
    reg.register(CutOrderStep())
    reg.run(col)
    trace = reg.trace()
    assert len(trace) == 5
    assert trace[0].label == "input"
    assert trace[-1].label == "cut_order"
