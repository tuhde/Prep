from pathlib import Path

from lxml import etree
from svgpathtools import parse_path

from prep.core.path_model import CutLayer, CutPath, HardwareConfig, PathCollection
from shapely.geometry import LineString, LinearRing


INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
INKSCAPE_PREFIX = f"{{{INKSCAPE_NS}}}"


def unit_to_mm(value: str, dpi: float = 96.0) -> float:
    value = value.strip()
    units = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72, "pc": 25.4 / 6, "px": 25.4 / dpi}
    for unit, factor in units.items():
        if value.endswith(unit):
            return float(value[: -len(unit)].strip()) * factor
    try:
        return float(value)
    except ValueError:
        return 0.0


def resolve_color(el: etree._Element) -> str | None:
    style = el.get("style", "")
    stroke = None
    if "stroke:" in style:
        for part in style.split(";"):
            if part.strip().startswith("stroke:"):
                stroke = part.split(":")[1].strip()
                break
    if not stroke:
        stroke = el.get("stroke")
    if not stroke or stroke == "none":
        return None
    if stroke.startswith("#"):
        return stroke
    if stroke.startswith("rgb"):
        return _rgb_to_hex(stroke)
    return None


def _rgb_to_hex(rgb: str) -> str:
    rgb = rgb.strip()
    if rgb.startswith("rgb(") and rgb.endswith(")"):
        vals = rgb[4:-1].split(",")
        if len(vals) == 3:
            def _component(s: str) -> int:
                s = s.strip()
                if s.endswith("%"):
                    return round(float(s[:-1]) * 255 / 100)
                return int(float(s))
            r, g, b = _component(vals[0]), _component(vals[1]), _component(vals[2])
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#000000"


def _is_visible(el: etree._Element) -> bool:
    for ancestor in [el] + list(el.iterancestors()):
        style = ancestor.get("style", "")
        if "display:none" in style or "visibility:hidden" in style or "opacity:0" in style:
            return False
    return True


def _element_to_shapely(
    el: etree._Element,
    scale_x: float,
    scale_y: float,
) -> list[tuple[LineString | LinearRing, bool]]:
    results = []
    d = el.get("d")
    if not d:
        return results
    path = parse_path(d)
    for subpath in path.continuous_subpaths():
        if len(subpath) == 0:
            continue
        pts = [subpath[0].start] + [seg.end for seg in subpath]
        coords = [(p.real * scale_x, p.imag * scale_y) for p in pts]
        if len(coords) < 2:
            continue
        closed = subpath.isclosed()
        geom = LinearRing(coords) if closed else LineString(coords)
        results.append((geom, closed))
    return results


class SVGImporter:
    name = "SVG / Inkscape"
    extensions = frozenset({".svg", ".svgz"})

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def read(self, path: Path) -> PathCollection:
        if path.suffix.lower() == ".svgz":
            import gzip
            with gzip.open(path, "rb") as f:
                tree = etree.fromstring(f.read())
        else:
            tree = etree.parse(path).getroot()

        svg_width = unit_to_mm(tree.get("width", "100"))
        svg_height = unit_to_mm(tree.get("height", "100"))

        viewbox = tree.get("viewBox", "").split()
        if len(viewbox) == 4:
            _vb_x0, _vb_y0, vb_w, vb_h = (float(v) for v in viewbox)
            if vb_w and vb_h:
                svg_width = unit_to_mm(tree.get("width", str(vb_w)))
                svg_height = unit_to_mm(tree.get("height", str(vb_h)))
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

        def process_element(el: etree._Element) -> None:
            if not _is_visible(el):
                return
            color = resolve_color(el) or "#000000"
            if color not in layers_map:
                layers_map[color] = CutLayer(color=color, label=f"Layer {len(layers_map) + 1}", speed=800.0, power=0.8, force=100)
            for geom, closed in _element_to_shapely(el, scale_x, scale_y):
                cp = CutPath(geometry=geom, closed=closed)
                layers_map[color].paths.append(cp)

        def walk(els: list[etree._Element]) -> None:
            for el in els:
                tag_local = etree.QName(el.tag).localname
                if tag_local in ("defs", "clipPath", "mask", "symbol"):
                    continue
                if tag_local in ("path", "rect", "circle", "ellipse", "line", "polyline", "polygon"):
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
