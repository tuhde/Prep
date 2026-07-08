import re
from dataclasses import dataclass

import numpy as np
from lxml import etree

INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
SODIPODI_NS = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
SVG_NS = "http://www.w3.org/2000/svg"

INKSCAPE_PREFIX = f"{{{INKSCAPE_NS}}}"
SVG_PREFIX = f"{{{SVG_NS}}}"


@dataclass
class _LayerInfo:
    name: str
    element: etree._Element
    visible: bool
    children: list["_LayerInfo"]


def parse_layer_tree(root: etree._Element) -> list[_LayerInfo]:
    def _walk(el: etree._Element) -> list[_LayerInfo]:
        layers = []
        for child in el:
            if not isinstance(child.tag, str):
                continue
            tag_local = etree.QName(child.tag).localname
            if tag_local == "g" and child.get(f"{INKSCAPE_PREFIX}groupmode") == "layer":
                style = child.get("style", "")
                visible = (
                    "display:none" not in style
                    and "visibility:hidden" not in style
                    and "opacity:0" not in style
                )
                label = child.get(f"{INKSCAPE_PREFIX}label", "Unnamed")
                info = _LayerInfo(
                    name=label,
                    element=child,
                    visible=visible,
                    children=_walk(child),
                )
                layers.append(info)
        return layers

    return _walk(root)


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
    if not stroke:
        stroke = el.get("fill")
    if not stroke or stroke == "none":
        return None
    if stroke == "currentColor":
        for ancestor in el.iterancestors():
            color = ancestor.get("color")
            if color and color != "inherit":
                stroke = color
                break
        else:
            return None
    elif stroke == "inherit":
        for ancestor in el.iterancestors():
            inherited = resolve_color(ancestor)
            if inherited:
                return inherited
        return None
    if stroke.startswith("#"):
        if len(stroke) == 4:
            return f"#{stroke[1]*2}{stroke[2]*2}{stroke[3]*2}"
        return stroke
    if stroke.startswith("rgb"):
        return _rgb_to_hex(stroke)
    named = _NAMED_COLORS.get(stroke.lower())
    if named:
        return named
    return None


_NAMED_COLORS: dict[str, str] = {
    "black": "#000000",
    "white": "#ffffff",
    "red": "#ff0000",
    "green": "#008000",
    "blue": "#0000ff",
    "yellow": "#ffff00",
    "cyan": "#00ffff",
    "magenta": "#ff00ff",
    "orange": "#ffa500",
    "purple": "#800080",
    "pink": "#ffc0cb",
    "brown": "#a52a2a",
    "gray": "#808080",
    "grey": "#808080",
    "lime": "#00ff00",
    "navy": "#000080",
    "teal": "#008080",
    "maroon": "#800000",
    "olive": "#808000",
    "aqua": "#00ffff",
    "silver": "#c0c0c0",
    "fuchsia": "#ff00ff",
}


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


def collect_transform(el: etree._Element) -> np.ndarray:
    matrices = []
    current = el
    while current is not None:
        transform_str = current.get("transform")
        if transform_str:
            mat = _parse_transform(transform_str)
            matrices.append(mat)
        parent = current.getparent()
        if parent is not None and isinstance(parent.tag, str):
            current = parent
        else:
            break
    result = np.eye(3)
    for mat in reversed(matrices):
        result = result @ mat
    return result


def _parse_transform(s: str) -> np.ndarray:
    result = np.eye(3)
    tokens = re.findall(r'(\w+)\s*\(([^)]*)\)', s)
    for func_name, args_str in tokens:
        args = [float(x) for x in re.split(r'[\s,]+', args_str.strip()) if x]
        mat = np.eye(3)
        if func_name == "translate":
            tx = args[0] if len(args) > 0 else 0.0
            ty = args[1] if len(args) > 1 else 0.0
            mat[0, 2] = tx
            mat[1, 2] = ty
        elif func_name == "scale":
            sx = args[0] if len(args) > 0 else 1.0
            sy = args[1] if len(args) > 1 else sx
            mat[0, 0] = sx
            mat[1, 1] = sy
        elif func_name == "rotate":
            angle = np.radians(args[0]) if len(args) > 0 else 0.0
            cx = args[1] if len(args) > 1 else 0.0
            cy = args[2] if len(args) > 2 else 0.0
            if cx or cy:
                t1 = np.eye(3)
                t1[0, 2] = -cx
                t1[1, 2] = -cy
                r = np.eye(3)
                r[0, 0] = np.cos(angle)
                r[0, 1] = -np.sin(angle)
                r[1, 0] = np.sin(angle)
                r[1, 1] = np.cos(angle)
                t2 = np.eye(3)
                t2[0, 2] = cx
                t2[1, 2] = cy
                mat = t2 @ r @ t1
            else:
                mat[0, 0] = np.cos(angle)
                mat[0, 1] = -np.sin(angle)
                mat[1, 0] = np.sin(angle)
                mat[1, 1] = np.cos(angle)
        elif func_name == "matrix":
            if len(args) >= 6:
                mat[0, 0] = args[0]
                mat[1, 0] = args[1]
                mat[0, 1] = args[2]
                mat[1, 1] = args[3]
                mat[0, 2] = args[4]
                mat[1, 2] = args[5]
        elif func_name == "skewX":
            angle = np.radians(args[0]) if len(args) > 0 else 0.0
            mat[0, 1] = np.tan(angle)
        elif func_name == "skewY":
            angle = np.radians(args[0]) if len(args) > 0 else 0.0
            mat[1, 0] = np.tan(angle)
        result = result @ mat
    return result


def is_visible(el: etree._Element) -> bool:
    for ancestor in [el] + list(el.iterancestors()):
        if not isinstance(ancestor.tag, str):
            continue
        tag_local = etree.QName(ancestor.tag).localname
        if tag_local == "g" and ancestor.get(f"{INKSCAPE_PREFIX}groupmode") == "guide":
            return False
        if ancestor.get("id") == "svg_guides":
            return False
        style = ancestor.get("style", "")
        if "display:none" in style or "visibility:hidden" in style or "opacity:0" in style:
            return False
        display = ancestor.get("display")
        if display == "none":
            return False
        visibility = ancestor.get("visibility")
        if visibility == "hidden":
            return False
    return True


def unit_to_mm(value: str, dpi: float = 96.0) -> float:
    value = value.strip()
    units = {
        "mm": 1.0,
        "cm": 10.0,
        "in": 25.4,
        "pt": 25.4 / 72,
        "pc": 25.4 / 6,
        "px": 25.4 / dpi,
    }
    for unit, factor in units.items():
        if value.endswith(unit):
            return float(value[: -len(unit)].strip()) * factor
    try:
        return float(value)
    except ValueError:
        return 0.0
