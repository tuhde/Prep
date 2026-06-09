from lxml import etree

from prep.core.path_model import CutLayer, CutPath, HardwareConfig, PathCollection
from prep.core.configurable import PipelineStepProtocol


PREP_NS = "https://prep.app/ns/1.0"
PREP_PREFIX = f"{{{PREP_NS}}}"


def _coords_from_geometry(geom) -> list[tuple[float, float]]:
    if hasattr(geom, "coords"):
        return list(geom.coords)
    return []


def to_prep_svg(collection: PathCollection, steps: list[PipelineStepProtocol]) -> str:
    root = etree.Element(
        "svg",
        nsmap={"svg": "http://www.w3.org/2000/svg", "prep": PREP_NS, "inkscape": "http://www.inkscape.org/namespaces/inkscape"},
    )
    root.set("width", f"{collection.material_width}mm")
    root.set("height", f"{collection.material_height}mm")
    root.set(f"{PREP_PREFIX}format-version", "1")
    root.set(f"{PREP_PREFIX}material-depth", str(collection.material_depth))

    metadata = etree.SubElement(root, f"{{{PREP_NS}}}metadata")

    if steps:
        pipeline_el = etree.SubElement(metadata, f"{{{PREP_NS}}}pipeline")
        for step in steps:
            step_el = etree.SubElement(pipeline_el, f"{{{PREP_NS}}}step")
            step_el.set("name", step.name)
            step_el.set("enabled", "true")
            if hasattr(step, "get_settings"):
                settings = step.get_settings()
                for key, value in settings.items():
                    setting_el = etree.SubElement(step_el, f"{{{PREP_NS}}}setting")
                    setting_el.set("key", key)
                    setting_el.set("value", str(value))

    hw_el = etree.SubElement(metadata, f"{{{PREP_NS}}}hardware")
    hw_el.set("driver", collection.hardware.driver)
    hw_el.set("port", collection.hardware.port)
    hw_el.set("baud", str(collection.hardware.baud))

    for layer in collection.layers:
        g = etree.SubElement(root, "g")
        g.set(f"{{{PREP_NS}}}groupmode", "layer")
        g.set(f"{{{INKSCAPE_NS}}}label", layer.label)
        g.set(f"{PREP_PREFIX}speed", str(layer.speed))
        g.set(f"{PREP_PREFIX}power", str(layer.power))
        g.set(f"{PREP_PREFIX}force", str(layer.force))
        g.set("stroke", layer.color)
        g.set("fill", "none")

        for path in layer.paths:
            path_el = etree.SubElement(g, "path")
            coords = _coords_from_geometry(path.geometry)
            d = "M " + " L ".join(f"{x},{y}" for x, y in coords) + " Z" if path.closed else "M " + " L ".join(f"{x},{y}" for x, y in coords)
            path_el.set("d", d)
            if path.z is not None:
                if isinstance(path.z, float):
                    path_el.set(f"{PREP_PREFIX}z", str(path.z))

    INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True).decode("UTF-8")


INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
INKSCAPE_PREFIX = f"{{{INKSCAPE_NS}}}"