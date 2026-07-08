import gzip
from pathlib import Path

from lxml import etree
from svgpathtools import parse_path

from prep.core.path_model import CutLayer, CutPath, HardwareConfig, PathCollection
from prep.io.importers.svg import inkscape
from shapely.geometry import LineString, LinearRing


def _shape_to_d(el: etree._Element) -> str | None:
    tag_local = etree.QName(el.tag).localname

    if tag_local == "path":
        return el.get("d")

    if tag_local == "rect":
        x = float(el.get("x", "0"))
        y = float(el.get("y", "0"))
        w = float(el.get("width", "0"))
        h = float(el.get("height", "0"))
        rx = float(el.get("rx", "0"))
        ry = float(el.get("ry", "0"))
        if w <= 0 or h <= 0:
            return None
        if rx > 0 or ry > 0:
            rx = min(rx, w / 2)
            ry = min(ry, h / 2)
            return (
                f"M {x + rx},{y} "
                f"L {x + w - rx},{y} "
                f"A {rx},{ry} 0 0 1 {x + w},{y + ry} "
                f"L {x + w},{y + h - ry} "
                f"A {rx},{ry} 0 0 1 {x + w - rx},{y + h} "
                f"L {x + rx},{y + h} "
                f"A {rx},{ry} 0 0 1 {x},{y + h - ry} "
                f"L {x},{y + ry} "
                f"A {rx},{ry} 0 0 1 {x + rx},{y} Z"
            )
        return f"M {x},{y} L {x + w},{y} L {x + w},{y + h} L {x},{y + h} Z"

    if tag_local == "circle":
        cx = float(el.get("cx", "0"))
        cy = float(el.get("cy", "0"))
        r = float(el.get("r", "0"))
        if r <= 0:
            return None
        return (
            f"M {cx - r},{cy} "
            f"A {r},{r} 0 1 0 {cx + r},{cy} "
            f"A {r},{r} 0 1 0 {cx - r},{cy} Z"
        )

    if tag_local == "ellipse":
        cx = float(el.get("cx", "0"))
        cy = float(el.get("cy", "0"))
        rx = float(el.get("rx", "0"))
        ry = float(el.get("ry", "0"))
        if rx <= 0 or ry <= 0:
            return None
        return (
            f"M {cx - rx},{cy} "
            f"A {rx},{ry} 0 1 0 {cx + rx},{cy} "
            f"A {rx},{ry} 0 1 0 {cx - rx},{cy} Z"
        )

    if tag_local == "line":
        x1 = float(el.get("x1", "0"))
        y1 = float(el.get("y1", "0"))
        x2 = float(el.get("x2", "0"))
        y2 = float(el.get("y2", "0"))
        return f"M {x1},{y1} L {x2},{y2}"

    if tag_local == "polyline":
        points = el.get("points", "").strip()
        if not points:
            return None
        coords = _parse_points(points)
        if len(coords) < 2:
            return None
        return "M " + " L ".join(f"{x},{y}" for x, y in coords)

    if tag_local == "polygon":
        points = el.get("points", "").strip()
        if not points:
            return None
        coords = _parse_points(points)
        if len(coords) < 3:
            return None
        return "M " + " L ".join(f"{x},{y}" for x, y in coords) + " Z"

    return None


def _parse_points(s: str) -> list[tuple[float, float]]:
    nums = [float(x) for x in s.replace(",", " ").split() if x]
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def _element_to_shapely(
    el: etree._Element,
    scale_x: float,
    scale_y: float,
) -> list[tuple[LineString | LinearRing, bool]]:
    results = []
    d = _shape_to_d(el)
    if not d:
        return results

    transform = inkscape.collect_transform(el)

    path = parse_path(d)
    for subpath in path.continuous_subpaths():
        if len(subpath) == 0:
            continue
        pts = [subpath[0].start] + [seg.end for seg in subpath]
        coords = []
        for p in pts:
            x_user = p.real * scale_x
            y_user = p.imag * scale_y
            v = transform @ [x_user, y_user, 1.0]
            coords.append((v[0], v[1]))
        if len(coords) < 2:
            continue
        closed = subpath.isclosed()
        if closed and len(coords) >= 3:
            coords.append(coords[0])
            geom = LinearRing(coords)
        else:
            geom = LineString(coords)
        results.append((geom, closed))
    return results


class SVGImporter:
    name = "SVG / Inkscape"
    extensions = frozenset({".svg", ".svgz"})

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def read(self, path: Path) -> PathCollection:
        if path.suffix.lower() == ".svgz":
            with gzip.open(path, "rb") as f:
                tree = etree.fromstring(f.read())
        else:
            tree = etree.parse(path).getroot()

        svg_width = inkscape.unit_to_mm(tree.get("width", "100"))
        svg_height = inkscape.unit_to_mm(tree.get("height", "100"))

        viewbox = tree.get("viewBox", "").split()
        if len(viewbox) == 4:
            _vb_x0, _vb_y0, vb_w, vb_h = (float(v) for v in viewbox)
            if vb_w and vb_h:
                svg_width = inkscape.unit_to_mm(tree.get("width", str(vb_w)))
                svg_height = inkscape.unit_to_mm(tree.get("height", str(vb_h)))
                scale_x = svg_width / vb_w
                scale_y = svg_height / vb_h
            else:
                scale_x = scale_y = 1.0
        else:
            scale_x = 25.4 / 96.0
            scale_y = 25.4 / 96.0

        layers_map: dict[str, CutLayer] = {}
        default_layer = CutLayer(color="#000000", label="Default", speed=800.0, power=0.8, force=100)
        layers_map["#000000"] = default_layer

        shape_tags = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}

        def process_element(el: etree._Element) -> None:
            if not inkscape.is_visible(el):
                return
            tag_local = etree.QName(el.tag).localname
            if tag_local not in shape_tags:
                return
            color = inkscape.resolve_color(el) or "#000000"
            if color not in layers_map:
                layers_map[color] = CutLayer(color=color, label=f"Layer {len(layers_map) + 1}", speed=800.0, power=0.8, force=100)
            for geom, closed in _element_to_shapely(el, scale_x, scale_y):
                cp = CutPath(geometry=geom, closed=closed)
                layers_map[color].paths.append(cp)

        def walk(els: list[etree._Element]) -> None:
            for el in els:
                if not isinstance(el.tag, str):
                    continue
                tag_local = etree.QName(el.tag).localname
                if tag_local in ("defs", "clipPath", "mask", "symbol"):
                    continue
                if tag_local in shape_tags:
                    process_element(el)
                walk(list(el))

        walk(list(tree))

        all_layers = list(layers_map.values())
        return PathCollection(
            material_width=svg_width,
            material_height=svg_height,
            layers=all_layers,
            hardware=HardwareConfig(driver="grbl", port="", baud=115200),
        )
