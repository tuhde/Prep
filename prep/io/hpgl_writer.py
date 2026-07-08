from prep.core.path_model import PathCollection


def to_hpgl(collection: PathCollection) -> str:
    lines = ["IN;", "SP1;"]

    for layer in collection.layers:
        for path in layer.paths:
            coords = list(path.geometry.coords)
            if not coords:
                continue

            x, y = coords[0]
            hpgl_x = int(x / 0.025)
            hpgl_y = int(y / 0.025)
            lines.append(f"PU{hpgl_x},{hpgl_y};")

            if len(coords) > 1:
                points = []
                for cx, cy in coords[1:]:
                    px = int(cx / 0.025)
                    py = int(cy / 0.025)
                    points.append(f"{px},{py}")
                lines.append("PD" + ",".join(points) + ";")

    lines.append("SP0;")
    return "\n".join(lines) + "\n"
