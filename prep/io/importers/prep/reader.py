from pathlib import Path

from lxml import etree

from prep.core.path_model import CutLayer, CutPath, HardwareConfig, PathCollection
from prep.io.importers.svg.reader import SVGImporter, _is_visible, resolve_color, unit_to_mm, _element_to_shapely

PREP_NS = "https://prep.app/ns/1.0"
PREP_PREFIX = f"{{{PREP_NS}}}"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
INKSCAPE_PREFIX = f"{{{INKSCAPE_NS}}}"


class PrepProjectImporter:
    name = "Prep Project"
    extensions = frozenset({".prep"})

    def can_handle(self, path: Path) -> bool:
        if path.suffix.lower() != ".prep":
            return False
        try:
            tree = etree.parse(path).getroot()
            version = tree.get(f"{PREP_PREFIX}format-version")
            return version is not None
        except Exception:
            return False

    def read(self, path: Path) -> PathCollection:
        tree = etree.parse(path).getroot()

        version_str = tree.get(f"{PREP_PREFIX}format-version")
        if version_str:
            version = int(version_str)
            if version > 1:
                raise ValueError(f"Unsupported .prep format version: {version}")

        svg_width = unit_to_mm(tree.get("width", "100"))
        svg_height = unit_to_mm(tree.get("height", "100"))

        material_depth = 0.0
        depth_str = tree.get(f"{PREP_PREFIX}material-depth")
        if depth_str:
            material_depth = float(depth_str)

        metadata = tree.find(f"{{{PREP_NS}}}metadata")
        pipeline_settings: dict[str, dict[str, object]] | None = None
        hardware_config = HardwareConfig(driver="grbl", port="", baud=115200)

        if metadata is not None:
            pipeline_el = metadata.find(f"{{{PREP_NS}}}pipeline")
            if pipeline_el is not None:
                pipeline_settings = {}
                for step_el in pipeline_el.findall(f"{{{PREP_NS}}}step"):
                    step_name = step_el.get("name", "")
                    if step_name:
                        settings = {}
                        for setting_el in step_el.findall(f"{{{PREP_NS}}}setting"):
                            key = setting_el.get("key", "")
                            value = setting_el.get("value", "")
                            if key:
                                try:
                                    settings[key] = float(value)
                                except ValueError:
                                    settings[key] = value
                        pipeline_settings[step_name] = settings

            hw_el = metadata.find(f"{{{PREP_NS}}}hardware")
            if hw_el is not None:
                driver = hw_el.get("driver", "")
                port = hw_el.get("port", "")
                baud_str = hw_el.get("baud", "115200")
                try:
                    baud = int(baud_str)
                except ValueError:
                    baud = 115200
                hardware_config = HardwareConfig(driver=driver, port=port, baud=baud)

        layers_map: dict[str, CutLayer] = {}
        default_layer = CutLayer(color="#000000", label="Default", speed=800.0, power=0.8, force=100)
        layers_map["#000000"] = default_layer

        def walk(els: list[etree._Element], parent_layer: CutLayer | None = None) -> None:
            for el in els:
                tag_local = etree.QName(el.tag).localname
                is_layer_group = (
                    el.tag == f"{{{INKSCAPE_NS}}}g"
                    and el.get(f"{{{INKSCAPE_NS}}}groupmode") == "layer"
                )
                if is_layer_group:
                    label = el.get(f"{{{INKSCAPE_NS}}}label", "Unnamed")
                    style = el.get("style", "")
                    visible = "display:none" not in style and "visibility:hidden" not in style
                    if not visible:
                        continue
                    speed_str = el.get(f"{PREP_PREFIX}speed")
                    power_str = el.get(f"{PREP_PREFIX}power")
                    force_str = el.get(f"{PREP_PREFIX}force")
                    color = resolve_color(el) or "#000000"
                    layer = CutLayer(
                        color=color,
                        label=label,
                        speed=float(speed_str) if speed_str else 800.0,
                        power=float(power_str) if power_str else 0.8,
                        force=int(force_str) if force_str else 100,
                    )
                    layers_map[color] = layer
                    walk(list(el), layer)
                else:
                    if _is_visible(el) and tag_local in ("path", "rect", "circle", "ellipse", "line", "polyline", "polygon"):
                        target = parent_layer if parent_layer is not None else default_layer
                        d = el.get("d", "")
                        from svgpathtools import parse as parse_svg_path
                        from shapely.geometry import LineString, LinearRing
                        if d:
                            svg_path = parse_svg_path(d)
                            for subpath in svg_path.continuous_subpaths():
                                coords = [(p.real / svg_width, p.imag / svg_height) for p in subpath]
                                if len(coords) < 2:
                                    continue
                                closed = subpath.isclosed()
                                geom = LinearRing(coords) if closed else LineString(coords)
                                z: float | None = None
                                z_str = el.get(f"{PREP_PREFIX}z")
                                if z_str:
                                    z = float(z_str)
                                cp = CutPath(geometry=geom, closed=closed, z=z)
                                target.paths.append(cp)

        walk(list(tree))

        all_layers = list(layers_map.values())
        return PathCollection(
            material_width=svg_width,
            material_height=svg_height,
            material_depth=material_depth,
            layers=all_layers,
            hardware=hardware_config,
            pipeline_settings=pipeline_settings,
        )