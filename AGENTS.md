# Prep — openCode Implementation Spec

## What You're Building

**Prep** is a Python desktop application (PySide6) for the stage between designing a motif and cutting it on a laser or vinyl cutter. It takes SVG input, processes it through a pipeline, and sends the result to hardware over USB/serial.

## Stack

- Python 3.11+
- PySide6 (Qt6 desktop UI)
- svgpathtools (SVG path parsing)
- lxml (SVG XML parsing)
- shapely (geometry operations)
- pyserial (serial/USB hardware comms)
- numpy (distance matrix for cut order)

## Internal Data Model

Define these in `postprocess/core/path_model.py` as dataclasses:

```python
@dataclass
class CutPath:
    geometry: LineString | LinearRing  # shapely
    closed: bool

@dataclass
class CutLayer:
    color: str          # hex or named color
    label: str
    speed: float        # mm/min (laser) or mm/s (vinyl)
    power: float        # 0.0–1.0 (laser only)
    force: int          # grams (vinyl only)
    paths: list[CutPath]

@dataclass
class HardwareConfig:
    driver: str         # "grbl" | "hpgl"
    port: str           # e.g. "/dev/ttyUSB0"
    baud: int

@dataclass
class PathCollection:
    material_width: float   # mm
    material_height: float  # mm
    layers: list[CutLayer]
    hardware: HardwareConfig
```

## Implementation Phases

### Phase 1 — Project scaffold

Create `pyproject.toml`:

```toml
[project]
name = "postprocess"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "PySide6",
    "svgpathtools",
    "lxml",
    "shapely",
    "pyserial",
    "numpy",
]

[project.scripts]
prep = "postprocess.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Create `postprocess/__main__.py` with a `main()` that launches the Qt app.

Create all `__init__.py` files for the package structure.

### Phase 2 — Core pipeline

**`postprocess/io/svg_reader.py`**
- Parse SVG using `lxml` + `svgpathtools`
- Extract all `<path>` elements with their `stroke` or `fill` color and Inkscape layer (`inkscape:label`)
- Convert each path to a Shapely `LineString` or `LinearRing` (closed if path ends at start)
- Group paths into `CutLayer` objects by color
- Return a `PathCollection`

**`postprocess/core/optimizer.py`** — `optimize(collection: PathCollection) -> PathCollection`
- Simplify path nodes using `shapely.simplify()` (Douglas-Peucker, configurable tolerance)
- Normalize winding order (exterior rings counter-clockwise)
- Merge overlapping or duplicate paths within a layer

**`postprocess/core/splitter.py`** — `split_by_color(collection: PathCollection) -> PathCollection`
- Ensure each unique stroke/fill color is its own `CutLayer`
- Merge layers with the same color

**`postprocess/core/layout.py`** — `layout(collection: PathCollection, width: float, height: float) -> PathCollection`
- Scale all paths to fit within the material sheet while preserving aspect ratio
- Support manual offset (translate all paths by dx, dy)
- Raise if any path falls outside sheet bounds

**`postprocess/core/cut_order.py`** — `optimize_cut_order(layer: CutLayer) -> CutLayer`
- For each layer, reorder paths using nearest-neighbor heuristic
- Start point of each path is the first coordinate of its geometry
- Build distance matrix with `numpy`, greedy nearest-neighbor sort
- Return layer with paths reordered

### Phase 3 — Hardware layer

**`postprocess/hardware/base.py`**
```python
class HardwareDriver(ABC):
    @abstractmethod
    def connect(self, port: str, baud: int) -> None: ...
    @abstractmethod
    def send(self, collection: PathCollection, progress_cb: Callable[[float], None]) -> None: ...
    @abstractmethod
    def disconnect(self) -> None: ...
```

**`postprocess/hardware/serial_comm.py`**
- Thin wrapper around `pyserial`: `connect()`, `disconnect()`, `writeline()`, `readline()`

**`postprocess/hardware/grbl.py`**
- `GRBLDriver(HardwareDriver)`
- `send()` converts `PathCollection` to GCODE via `gcode_writer`, streams line-by-line
- After each line, poll `?` status and wait for `ok` response
- Call `progress_cb` with fraction complete

**`postprocess/hardware/hpgl.py`**
- `HPGLDriver(HardwareDriver)`
- `send()` converts `PathCollection` to HPGL via `hpgl_writer`, writes as one block

**`postprocess/io/gcode_writer.py`** — `to_gcode(collection: PathCollection) -> str`
- `G21` (mm), `G90` (absolute), `M3 S{power}` per layer
- `G0` rapid to path start, `M3` spindle on, `G1` feed moves along path, `M5` off
- `G0 Z5` safe height between paths

**`postprocess/io/hpgl_writer.py`** — `to_hpgl(collection: PathCollection) -> str`
- `IN;` initialize, `SP1;` select pen
- `PU x,y;` pen up move, `PD x,y,...;` pen down draw
- Coordinates in HPGL units (1 unit = 0.025mm), convert from mm

### Phase 4 — UI

**`postprocess/ui/main_window.py`** — `MainWindow(QMainWindow)`
- Menu: File → Open SVG, File → Quit
- Toolbar: Open, Run Pipeline, Send to Hardware
- Central widget: horizontal splitter — canvas left, panels right
- Status bar shows connection state and progress
- `run_pipeline()` chains optimizer → splitter → layout → cut_order on the loaded collection

**`postprocess/ui/canvas.py`** — `Canvas(QGraphicsView)`
- Renders `PathCollection` using `QGraphicsScene`
- Each `CutLayer` drawn in its own color
- Draws material sheet boundary as a grey rectangle
- Supports zoom (wheel) and pan (middle-click drag)

**`postprocess/ui/layer_panel.py`** — `LayerPanel(QWidget)`
- `QListWidget` listing each `CutLayer` (colored icon + label)
- Selecting a layer shows speed/power/force spinboxes
- Changes update the `PathCollection` in place

**`postprocess/ui/layout_panel.py`** — `LayoutPanel(QWidget)`
- Width/height `QDoubleSpinBox` for material sheet
- "Fit to sheet" button triggers `layout.layout()`

**`postprocess/ui/hardware_panel.py`** — `HardwarePanel(QWidget)`
- Port `QComboBox` (populated from `serial.tools.list_ports`)
- Baud rate selector, driver selector (GRBL / HPGL)
- Connect/Disconnect button
- Send button (disabled until connected)
- `QProgressBar` updated via `progress_cb`

## Tests

Write unit tests in `tests/` using `pytest`. Include SVG fixture files in `tests/fixtures/`:
- `simple_rect.svg` — one closed path, one color
- `two_colors.svg` — two colors, multiple paths each
- `inkscape_layers.svg` — Inkscape-style layer groups

Test each core module independently. Mock serial for hardware tests.

## Style

- Python 3.11+, fully typed
- Dataclasses for the model; no Pydantic
- No comments unless the why is non-obvious
- `ruff` for linting
