from copy import deepcopy

import shapely
from shapely.geometry import LinearRing

from prep.core.configurable import SettingField
from prep.core.path_model import CutPath, PathCollection


class OptimizerStep:
    name = "optimizer"
    order = 10
    tolerance: float = 0.1

    def settings_schema(self) -> list[SettingField]:
        return [SettingField(key="tolerance", type=float, default=0.1, label="Simplify tolerance (mm)", min=0.001, max=10.0)]

    def get_settings(self) -> dict[str, float]:
        return {"tolerance": self.tolerance}

    def set_settings(self, values: dict) -> None:
        if "tolerance" in values:
            self.tolerance = float(values["tolerance"])

    def process(self, collection: PathCollection) -> PathCollection:
        result = deepcopy(collection)
        for layer in result.layers:
            simplified_paths = []
            seen: set[str] = set()
            for path in layer.paths:
                simplified = shapely.simplify(path.geometry, self.tolerance, preserve_topology=True)
                if isinstance(simplified, LinearRing) and not simplified.is_ccw:
                    simplified = LinearRing(list(simplified.coords)[::-1])
                wkt = simplified.wkt
                if wkt in seen:
                    continue
                seen.add(wkt)
                simplified_paths.append(CutPath(geometry=simplified, closed=path.closed, z=path.z))
            layer.paths = simplified_paths
        return result
