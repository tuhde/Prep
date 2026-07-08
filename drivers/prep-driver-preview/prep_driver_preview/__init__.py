import time
from typing import Callable

from prep.core.configurable import SettingField
from prep.core.path_model import PathCollection


class PreviewDriver:
    name = "Preview"
    driver_id = "preview"
    speed_factor: float = 1.0

    def settings_schema(self) -> list[SettingField]:
        return [SettingField(key="speed_factor", type=float, default=1.0, label="Preview speed multiplier", min=0.1, max=10.0)]

    def get_settings(self) -> dict[str, float]:
        return {"speed_factor": self.speed_factor}

    def set_settings(self, values: dict) -> None:
        if "speed_factor" in values:
            self.speed_factor = float(values["speed_factor"])

    def connect(self, port: str, baud: int) -> None:
        pass

    def send(self, collection: PathCollection, progress_cb: Callable[[float], None]) -> None:
        total_paths = sum(len(layer.paths) for layer in collection.layers)
        if total_paths == 0:
            progress_cb(1.0)
            return

        completed = 0
        for layer in collection.layers:
            for path in layer.paths:
                coords = list(path.geometry.coords)
                if len(coords) < 2:
                    completed += 1
                    progress_cb(completed / total_paths)
                    continue

                for i in range(len(coords) - 1):
                    x1, y1 = coords[i]
                    x2, y2 = coords[i + 1]
                    dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
                    delay = (dist / 100.0) * self.speed_factor
                    time.sleep(delay)

                completed += 1
                progress_cb(completed / total_paths)

    def disconnect(self) -> None:
        pass
