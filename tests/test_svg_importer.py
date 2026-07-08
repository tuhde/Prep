from pathlib import Path


from prep.io.importers.svg import SVGImporter
from prep.io.importers.svg.inkscape import (
    collect_transform,
    is_visible,
    parse_layer_tree,
    resolve_color,
    unit_to_mm,
)
from lxml import etree

FIXTURES = Path(__file__).parent / "fixtures"


def test_unit_to_mm():
    assert unit_to_mm("10mm") == 10.0
    assert unit_to_mm("1cm") == 10.0
    assert unit_to_mm("1in") == 25.4
    assert abs(unit_to_mm("96px") - 25.4) < 0.01
    assert unit_to_mm("72pt") == 25.4
    assert unit_to_mm("6pc") == 25.4
    assert unit_to_mm("50") == 50.0
    assert unit_to_mm("bad") == 0.0


def test_resolve_color_hex():
    el = etree.fromstring('<path stroke="#ff0000" xmlns="http://www.w3.org/2000/svg"/>')
    assert resolve_color(el) == "#ff0000"


def test_resolve_color_rgb():
    el = etree.fromstring('<path stroke="rgb(255,0,0)" xmlns="http://www.w3.org/2000/svg"/>')
    assert resolve_color(el) == "#ff0000"


def test_resolve_color_rgb_percent():
    el = etree.fromstring('<path stroke="rgb(100%,0%,50%)" xmlns="http://www.w3.org/2000/svg"/>')
    assert resolve_color(el) == "#ff0080"


def test_resolve_color_named():
    el = etree.fromstring('<path stroke="red" xmlns="http://www.w3.org/2000/svg"/>')
    assert resolve_color(el) == "#ff0000"


def test_resolve_color_none():
    el = etree.fromstring('<path stroke="none" xmlns="http://www.w3.org/2000/svg"/>')
    assert resolve_color(el) is None


def test_resolve_color_from_style():
    el = etree.fromstring('<path style="fill:none;stroke:#00ff00" xmlns="http://www.w3.org/2000/svg"/>')
    assert resolve_color(el) == "#00ff00"


def test_is_visible():
    el = etree.fromstring('<g xmlns="http://www.w3.org/2000/svg"><path d="M 0,0"/></g>')
    assert is_visible(el[0]) is True

    el = etree.fromstring('<g style="display:none" xmlns="http://www.w3.org/2000/svg"><path d="M 0,0"/></g>')
    assert is_visible(el[0]) is False


def test_collect_transform_identity():
    el = etree.fromstring('<g xmlns="http://www.w3.org/2000/svg"><path d="M 0,0"/></g>')
    import numpy as np
    mat = collect_transform(el[0])
    np.testing.assert_array_almost_equal(mat, np.eye(3))


def test_collect_transform_translate():
    el = etree.fromstring('<g transform="translate(10,20)" xmlns="http://www.w3.org/2000/svg"><path d="M 0,0"/></g>')
    mat = collect_transform(el[0])
    assert abs(mat[0, 2] - 10.0) < 0.01
    assert abs(mat[1, 2] - 20.0) < 0.01


def test_collect_transform_nested():
    el = etree.fromstring(
        '<g transform="translate(5,5)" xmlns="http://www.w3.org/2000/svg">'
        '<g transform="translate(10,10)"><path d="M 0,0"/></g></g>'
    )
    mat = collect_transform(el[0][0])
    assert abs(mat[0, 2] - 15.0) < 0.01
    assert abs(mat[1, 2] - 15.0) < 0.01


def test_parse_layer_tree():
    tree = etree.parse(FIXTURES / "inkscape_layers.svg").getroot()
    layers = parse_layer_tree(tree)
    assert len(layers) == 3
    assert layers[0].name == "Red Layer"
    assert layers[0].visible is True
    assert layers[2].name == "Hidden Layer"
    assert layers[2].visible is False


def test_svg_importer_simple_rect():
    imp = SVGImporter()
    col = imp.read(FIXTURES / "simple_rect.svg")
    assert col.material_width == 100.0
    assert col.material_height == 100.0
    total_paths = sum(len(layer.paths) for layer in col.layers)
    assert total_paths >= 1


def test_svg_importer_two_colors():
    imp = SVGImporter()
    col = imp.read(FIXTURES / "two_colors.svg")
    assert col.material_width == 200.0
    assert col.material_height == 150.0
    colors = {layer.color for layer in col.layers if layer.paths}
    assert "#ff0000" in colors
    assert "#0000ff" in colors


def test_svg_importer_inkscape_layers():
    imp = SVGImporter()
    col = imp.read(FIXTURES / "inkscape_layers.svg")
    visible_layers = [layer for layer in col.layers if layer.paths]
    colors = {layer.color for layer in visible_layers}
    assert "#ff0000" in colors
    assert "#0000ff" in colors
    assert "#00ff00" not in colors


def test_svg_importer_shapes():
    import tempfile
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
      <rect x="10" y="10" width="30" height="20" stroke="#ff0000" fill="none"/>
      <circle cx="60" cy="20" r="15" stroke="#00ff00" fill="none"/>
      <ellipse cx="30" cy="60" rx="20" ry="10" stroke="#0000ff" fill="none"/>
      <line x1="5" y1="90" x2="95" y2="90" stroke="#ffff00"/>
      <polyline points="70,50 80,60 90,50" stroke="#ff00ff" fill="none"/>
      <polygon points="70,70 80,90 60,90" stroke="#00ffff" fill="none"/>
    </svg>'''
    with tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False) as f:
        f.write(svg)
        f.flush()
        imp = SVGImporter()
        col = imp.read(Path(f.name))
        total = sum(len(layer.paths) for layer in col.layers)
        assert total == 6
        Path(f.name).unlink()
