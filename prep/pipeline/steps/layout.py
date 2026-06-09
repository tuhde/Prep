from prep.core.configurable import SettingField
from prep.core.path_model import PathCollection


class LayoutStep:
    name = "layout"
    order = 30
    offset_x: float = 0.0
    offset_y: float = 0.0

    def settings_schema(self) -> list[SettingField]:
        return [
            SettingField(key="offset_x", type=float, default=0.0, label="Offset X (mm)", min=-500.0, max=500.0),
            SettingField(key="offset_y", type=float, default=0.0, label="Offset Y (mm)", min=-500.0, max=500.0),
        ]

    def get_settings(self) -> dict[str, float]:
        return {"offset_x": self.offset_x, "offset_y": self.offset_y}

    def set_settings(self, values: dict) -> None:
        if "offset_x" in values:
            self.offset_x = float(values["offset_x"])
        if "offset_y" in values:
            self.offset_y = float(values["offset_y"])

    def process(self, collection: PathCollection) -> PathCollection:
        from copy import deepcopy
        from shapely.affinity import translate

        result = deepcopy(collection)

        all_coords = []
        for layer in result.layers:
            for path in layer.paths:
                if hasattr(path.geometry, "coords"):
                    all_coords.extend(path.geometry.coords)

        if not all_coords:
            return result

        min_x = min(c[0] for c in all_coords)
        min_y = min(c[1] for c in all_coords)
        max_x = max(c[0] for c in all_coords)
        max_y = max(c[1] for c in all_coords)

        geom_w = max_x - min_x
        geom_h = max_y - min_y

        if geom_w == 0 or geom_h == 0:
            return result

        scale_x = collection.material_width / geom_w if geom_w > 0 else 1.0
        scale_y = collection.material_height / geom_h if geom_h > 0 else 1.0
        scale = min(scale_x, scale_y)

        from prep.core.path_model import CutPath
        for layer in result.layers:
            new_paths = []
            for path in layer.paths:
                scaled = path.geometry
                if hasattr(scaled, "coords"):
                    new_coords = [(c[0] * scale + self.offset_x, c[1] * scale + self.offset_y) for c in scaled.coords]
                    from shapely.geometry import LineString, LinearRing
                    if isinstance(scaled, LinearRing):
                        scaled = LinearRing(new_coords)
                    else:
                        scaled = LineString(new_coords)
                new_paths.append(CutPath(geometry=scaled, closed=path.closed, z=path.z))
            layer.paths = new_paths

        return result