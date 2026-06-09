from prep.core.path_model import PathCollection


class SplitterStep:
    name = "splitter"
    order = 20

    def process(self, collection: PathCollection) -> PathCollection:
        from copy import deepcopy
        from prep.core.path_model import CutLayer

        result = deepcopy(collection)
        color_to_layer: dict = {}
        for layer in result.layers:
            if layer.color not in color_to_layer:
                color_to_layer[layer.color] = layer
            else:
                color_to_layer[layer.color].paths.extend(layer.paths)

        result.layers = list(color_to_layer.values())
        return result