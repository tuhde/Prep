import numpy as np
from prep.core.path_model import PathCollection


class CutOrderStep:
    name = "cut_order"
    order = 40

    def process(self, collection: PathCollection) -> PathCollection:
        from copy import deepcopy
        from prep.core.path_model import CutPath

        result = deepcopy(collection)

        for layer in result.layers:
            if len(layer.paths) <= 1:
                continue

            coords = []
            for path in layer.paths:
                if hasattr(path.geometry, "coords"):
                    coord_list = list(path.geometry.coords)
                    if coord_list:
                        coords.append(coord_list[0])
                    else:
                        coords.append((0.0, 0.0))
                else:
                    coords.append((0.0, 0.0))

            if len(coords) < 2:
                continue

            n = len(coords)
            dist_matrix = np.zeros((n, n))
            for i in range(n):
                for j in range(n):
                    dx = coords[i][0] - coords[j][0]
                    dy = coords[i][1] - coords[j][1]
                    dist_matrix[i, j] = np.sqrt(dx * dx + dy * dy)

            visited = [False] * n
            order = [0]
            visited[0] = True

            for _ in range(n - 1):
                last = order[-1]
                nearest = -1
                nearest_dist = np.inf
                for j in range(n):
                    if not visited[j] and dist_matrix[last, j] < nearest_dist:
                        nearest_dist = dist_matrix[last, j]
                        nearest = j
                if nearest != -1:
                    order.append(nearest)
                    visited[nearest] = True

            layer.paths = [layer.paths[i] for i in order]

        return result