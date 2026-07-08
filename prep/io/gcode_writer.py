from prep.core.path_model import PathCollection


def to_gcode(collection: PathCollection) -> str:
    lines = ["G21", "G90"]

    for layer in collection.layers:
        power = int(layer.power * 1000) if layer.power <= 1.0 else int(layer.power)
        lines.append(f"M3 S{power}")

        for path in layer.paths:
            coords = list(path.geometry.coords)
            if not coords:
                continue

            x, y = coords[0]
            lines.append(f"G0 X{x:.3f} Y{y:.3f}")

            if path.z is not None:
                if isinstance(path.z, float):
                    lines.append(f"G1 Z{path.z:.3f}")
                elif hasattr(path.z, "__len__"):
                    for i, (cx, cy) in enumerate(coords):
                        if i == 0:
                            continue
                        z_val = path.z[i] if i < len(path.z) else path.z[-1]
                        lines.append(f"G1 X{cx:.3f} Y{cy:.3f} Z{z_val:.3f}")
                    continue

            lines.append("M3")
            for cx, cy in coords[1:]:
                lines.append(f"G1 X{cx:.3f} Y{cy:.3f}")
            lines.append("M5")

            if path.z is not None and isinstance(path.z, float):
                lines.append("G0 Z5")

        lines.append("M5")

    lines.append("M5")
    return "\n".join(lines) + "\n"
