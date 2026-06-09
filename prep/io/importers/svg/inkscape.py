INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
SVG_NS = "http://www.w3.org/2000/svg"

INKSCAPE_PREFIX = f"{{{INKSCAPE_NS}}}"
SVG_PREFIX = f"{{{SVG_NS}}}"


def is_visible(el) -> bool:
    for ancestor in [el] + list(el.iterancestors()):
        style = ancestor.get("style", "")
        if "display:none" in style or "visibility:hidden" in style or "opacity:0" in style:
            return False
    return True