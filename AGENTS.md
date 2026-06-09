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

Define these in `prep/core/path_model.py` as dataclasses:

```python
class Dimensionality(Enum):
    D2   = "2d"    # flat; z is None
    D2_5 = "2.5d"  # constant Z for the whole path; z is float
    D3   = "3d"    # per-vertex Z; z is ndarray

@dataclass
class CutPath:
    geometry: LineString | LinearRing  # XY projection (Shapely); always present
    closed: bool
    z: float | np.ndarray | None = None
    # None       → 2D flat cut (default; fully backward compatible)
    # float      → 2.5D: constant Z depth for this path, e.g. 1.5 mm engrave depth
    # np.ndarray → 3D: per-vertex Z, shape (N,) matching len(geometry.coords)

    @property
    def dimensionality(self) -> Dimensionality:
        if self.z is None:
            return Dimensionality.D2
        if isinstance(self.z, float):
            return Dimensionality.D2_5
        return Dimensionality.D3

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
    driver: str         # driver_id from HardwareRegistry
    port: str           # e.g. "/dev/ttyUSB0"
    baud: int

@dataclass
class PathCollection:
    material_width: float         # mm
    material_height: float        # mm
    material_depth: float = 0.0   # mm; 0.0 = flat sheet (2D); > 0 = workpiece thickness
    layers: list[CutLayer] = field(default_factory=list)
    hardware: HardwareConfig = field(default_factory=lambda: HardwareConfig("", "", 0))
```

**Dimensionality rules across the stack:**

- **Importers**: SVG produces `z=None` on all paths. Future importers (DXF, STEP, G-code) may produce 2.5D or 3D paths.
- **Pipeline steps**: all steps use `path.geometry` (XY) for spatial operations and carry `path.z` through unchanged. A step that is explicitly 3D-aware may modify `z` — it must document this. Steps must never drop `z` silently.
- **Hardware drivers**: drivers check `path.dimensionality`. A 2D-only driver (e.g. CT630) raises `ValueError` if it receives a path with `z` set. A GCODE driver emits `Z{value}` moves when `z` is present.
- **Canvas**: renders the XY projection for all dimensionalities; a future 3D view can use `z` for depth cues.

**Units and coordinate representation:**

All internal coordinates and dimensions are `float64` in **millimetres** (SI). This is the only unit used inside the model, pipeline, and hardware layers.

Precision note: `float64` at a 1000 mm bed gives sub-nanometre resolution — orders of magnitude beyond hardware accuracy (≥ 0.05 mm). Accumulated rounding error over a typical path stays in the 1e-12 mm range and is inconsequential. The dominant source of precision loss is the Douglas-Peucker simplification tolerance (~0.1 mm), not floating-point arithmetic. If heavy polygon boolean operations are added later (union, intersection, difference), consider a Clipper-based pipeline step that converts to `int64` µm at its own boundary and back — that boundary conversion is the right place to handle exact arithmetic, not the model.

Imperial units (inches, thou) may appear at import (e.g. DXF files authored in inches) or export (e.g. HPGL for US-market plotters). Importers convert to mm before handing off a `PathCollection`. Writers convert from mm to the target unit before emitting output. No imperial values ever enter the model.

## Implementation Phases

### Phase 1 — Project scaffold

Create `pyproject.toml`:

```toml
[project]
name = "prep"
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
prep = "prep.__main__:main"

[project.entry-points."prep.importers"]
svg = "prep.io.importers.svg:SVGImporter"

[project.entry-points."prep.pipeline"]
optimizer = "prep.pipeline.steps.optimizer:OptimizerStep"
splitter  = "prep.pipeline.steps.splitter:SplitterStep"
layout    = "prep.pipeline.steps.layout:LayoutStep"
cut_order = "prep.pipeline.steps.cut_order:CutOrderStep"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Create `prep/__main__.py` with a `main()` that launches the Qt app.

Create all `__init__.py` files for the package structure.

### Phase 2 — Core pipeline

**`prep/core/configurable.py`** — settings protocol (no Qt dependency)

```python
@dataclass
class SettingField:
    key: str
    type: type                    # float | int | str | bool
    default: Any
    label: str
    description: str = ""
    min: float | None = None      # float/int only
    max: float | None = None      # float/int only
    choices: list[str] | None = None  # present → renders as QComboBox

class Configurable(Protocol):
    def settings_schema(self) -> list[SettingField]: ...
    def get_settings(self) -> dict[str, Any]: ...
    def set_settings(self, values: dict[str, Any]) -> None: ...
```

Any plugin (importer, pipeline step, hardware driver) that has user-configurable parameters implements `Configurable`. Plugins without settings simply omit it. The UI checks `isinstance(plugin, Configurable)` before offering a settings action.

Escape hatch: a plugin may additionally define `settings_widget(self) -> QWidget` (not part of the protocol — checked at runtime with `hasattr`). When present, `SettingsDialog` embeds the returned widget instead of auto-generating a form. Use this only when the schema cannot express what's needed (e.g. a port list that reads live serial devices).

---

**`prep/io/base.py`** — importer protocol and registry

```python
class ImporterProtocol(Protocol):
    name: str                   # e.g. "SVG / Inkscape"
    extensions: frozenset[str]  # e.g. frozenset({".svg", ".svgz"})
    def can_handle(self, path: Path) -> bool: ...
    def read(self, path: Path) -> PathCollection: ...

class ImporterRegistry:
    def register(self, importer: ImporterProtocol) -> None: ...
    def for_path(self, path: Path) -> ImporterProtocol:
        # iterate registered importers, return first whose can_handle() is True
        # raise ValueError with helpful message if none match
    def load_plugins(self) -> None:
        # importlib.metadata.entry_points(group="prep.importers")
        # instantiate each class and register it

_registry = ImporterRegistry()
```

Call `_registry.load_plugins()` once at app startup (in `__main__.py`). All code that reads files goes through `_registry.for_path(path).read(path)`.

> **Security note — plugin trust model**
> A loaded importer runs as ordinary Python inside the app process with no sandbox. There is no reliable runtime mechanism to verify that a plugin is safe before loading it. The trust boundary is the same as any other `pip` dependency: only install plugins from sources you trust. For plugin vetting in CI, `bandit` can flag dangerous call patterns (`eval`, `exec`, `subprocess`, `socket`, etc.) in plugin source, but this is bypassable and not a runtime guarantee. If Prep ever gains a plugin marketplace or auto-install path, re-evaluate with OS-level sandboxing (container, `seccomp`/`bubblewrap`) rather than Python-level checks.

---

**`prep/io/importers/svg/inkscape.py`** — Inkscape extension helpers

Constants: `INKSCAPE_NS`, `SODIPODI_NS`, `SVG_NS` (the standard SVG namespace URI).

- `parse_layer_tree(root: _Element) -> list[_LayerInfo]` — recursively walk `<g inkscape:groupmode="layer">` elements; extract `inkscape:label` as layer name; detect hidden layers via `display:none` in `style` attribute or `visibility="hidden"`; preserve nesting order
- `resolve_color(el: _Element) -> str | None` — read `stroke` from inline `style` first, fall back to `stroke` attribute, then `fill`; handle `currentColor` (resolve from parent), `inherit` (walk up), `none` (return `None`); always return a CSS hex string (`#rrggbb`)
- `collect_transform(el: _Element) -> numpy.ndarray` — accumulate the 3×3 affine matrix from the element up to the SVG root; parse `translate`, `scale`, `rotate`, `matrix`, `skewX`, `skewY` tokens
- `is_visible(el: _Element) -> bool` — return `False` if any ancestor (including self) has `display:none`, `visibility:hidden`, or `opacity:0`; skip Inkscape's internal guide layer (`id="svg_guides"` or `inkscape:groupmode="guide"`)
- `unit_to_mm(value: str, dpi: float = 96.0) -> float` — convert SVG length string (px, mm, cm, in, pt, pc, or bare number) to millimetres

---

**`prep/io/importers/svg/reader.py`** — `SVGImporter`

```python
class SVGImporter:
    name = "SVG / Inkscape"
    extensions = frozenset({".svg", ".svgz"})

    def can_handle(self, path: Path) -> bool:
        # True if suffix in extensions; optionally sniff XML root tag for <svg
    def read(self, path: Path) -> PathCollection:
        ...
```

Implementation:
- Open `.svgz` with `gzip.open` before passing bytes to `lxml.etree.fromstring`; plain `.svg` with `lxml.etree.parse`
- Extract document size: prefer `viewBox` attribute; fall back to `width`/`height`; convert to mm via `unit_to_mm`
- Call `inkscape.parse_layer_tree(root)` to get layer structure; paths not inside any layer element go into a synthetic default layer
- For each visible element (filter with `is_visible`): handle `<path>`, `<rect>`, `<circle>`, `<ellipse>`, `<line>`, `<polyline>`, `<polygon>` — convert non-path shapes to a `d` attribute string, then parse with `svgpathtools.parse_path`
- Apply cumulative affine transform from `collect_transform` to every coordinate before building Shapely geometry
- A path is closed if the last point equals the first (within 1e-6 tolerance) or the svgpathtools path ends with a `Close` segment → use `LinearRing`; otherwise `LineString`
- Assign each path to its `CutLayer` using `resolve_color` for the color key; create the layer if it does not yet exist
- Return `PathCollection(material_width=…, material_height=…, layers=[…], hardware=HardwareConfig("grbl","",115200))`

**`prep/io/importers/svg/__init__.py`**
```python
from .reader import SVGImporter
__all__ = ["SVGImporter"]
```

**`prep/pipeline/base.py`** — pipeline protocol and registry

```python
class PipelineStepProtocol(Protocol):
    name: str   # e.g. "optimizer"
    order: int  # execution order; lower runs first

    def process(self, collection: PathCollection) -> PathCollection: ...

@dataclass
class TraceEntry:
    label: str                          # "input" or step.name
    step: PipelineStepProtocol | None   # None for the input entry
    collection: PathCollection

class PipelineRegistry:
    _descriptors: dict[str, EntryPoint]
    _loaded: dict[str, PipelineStepProtocol]
    _trace: list[TraceEntry]            # populated by run(); empty before first run

    def load_plugins(self) -> None:
        # entry_points(group="prep.pipeline"), lazy — no .load() calls yet

    def steps(self) -> list[PipelineStepProtocol]:
        # load all descriptors, sort by .order, return list

    def run(self, collection: PathCollection) -> PathCollection:
        # reset _trace; prepend TraceEntry("input", None, collection)
        # for each step: apply, append TraceEntry(step.name, step, result)
        # return final result

    def trace(self) -> list[TraceEntry]:
        # returns _trace; empty list if run() has not been called yet

_registry = PipelineRegistry()
```

Call `_registry.load_plugins()` alongside the importer registry at app startup. The UI runs the pipeline via `_registry.run(collection)`. Same security posture as importers — see the security note above.

---

**`prep/pipeline/steps/optimizer.py`** — `OptimizerStep`
- `name = "optimizer"`, `order = 10`
- `tolerance: float = 0.1` — Douglas-Peucker tolerance in mm
- Implements `Configurable`: one field — `SettingField("tolerance", float, 0.1, "Simplify tolerance (mm)", min=0.001, max=10.0)`
- `process(collection)`: for each layer, simplify each path with `shapely.simplify(tolerance)`; normalize winding (exterior rings counter-clockwise); remove duplicate or fully-overlapping paths within a layer; return new `PathCollection`

**`prep/pipeline/steps/splitter.py`** — `SplitterStep`
- `name = "splitter"`, `order = 20`
- `process(collection)`: ensure each unique `CutLayer.color` value has exactly one layer; merge paths from layers that share a color into one; return new `PathCollection`

**`prep/pipeline/steps/layout.py`** — `LayoutStep`
- `name = "layout"`, `order = 30`
- `offset_x: float = 0.0`, `offset_y: float = 0.0` — manual nudge in mm
- Implements `Configurable`: two fields — `offset_x` and `offset_y`, both `float`, range −500 to 500 mm
- `process(collection)`: scale all paths uniformly to fit within `collection.material_width` × `collection.material_height` while preserving aspect ratio; apply offset; raise `ValueError` if any path still falls outside sheet bounds after scaling; return new `PathCollection`
- Reads sheet dimensions from the collection itself — no extra parameters needed

**`prep/pipeline/steps/cut_order.py`** — `CutOrderStep`
- `name = "cut_order"`, `order = 40`
- `process(collection)`: for each `CutLayer`, reorder paths using nearest-neighbor heuristic — build pairwise distance matrix with `numpy` (start point = first coordinate of each path's geometry), greedy sort; return new `PathCollection` with layers replaced by reordered copies

### Phase 3 — Hardware layer

**`prep/hardware/base.py`** — driver protocol and registry

```python
class HardwareDriverProtocol(Protocol):
    name: str       # human-readable, e.g. "Creation CT630"
    driver_id: str  # stable key, e.g. "creation_ct630"

    def connect(self, port: str, baud: int) -> None: ...
    def send(self, collection: PathCollection, progress_cb: Callable[[float], None]) -> None: ...
    def disconnect(self) -> None: ...

class HardwareRegistry:
    _descriptors: dict[str, EntryPoint]
    _loaded: dict[str, HardwareDriverProtocol]

    def load_plugins(self) -> None:
        # entry_points(group="prep.hardware"), lazy

    def drivers(self) -> list[HardwareDriverProtocol]:
        # load all, return sorted by name

    def by_id(self, driver_id: str) -> HardwareDriverProtocol:
        # load and return; raise KeyError if unknown

_registry = HardwareRegistry()
```

Call `_registry.load_plugins()` at app startup alongside the other registries. Same security posture — see the security note above.

**`prep/hardware/serial_comm.py`** — `SerialComm`
- Thin wrapper around `pyserial`: `connect(port, baud)`, `disconnect()`, `writeline(line: str)`, `readline() -> str`
- Shared utility; driver packages import it from `prep.hardware.serial_comm`

**`prep/io/gcode_writer.py`** — `to_gcode(collection: PathCollection) -> str`
- `G21` (mm), `G90` (absolute), `M3 S{power}` per layer
- `G0` rapid to path start, `M3` spindle on, `G1` feed moves along path, `M5` off
- `G0 Z5` safe height between paths

**`prep/io/hpgl_writer.py`** — `to_hpgl(collection: PathCollection) -> str`
- `IN;` initialize, `SP1;` select pen
- `PU x,y;` pen up move, `PD x,y,...;` pen down draw
- Coordinates in HPGL units (1 unit = 0.025mm), convert from mm

---

Driver packages live in `drivers/` and each has its own `pyproject.toml` so extraction to a separate repo is moving a directory. Install both during development with `pip install -e drivers/prep-driver-preview -e drivers/prep-driver-creation-ct630`.

**`drivers/prep-driver-preview/`**

```toml
# pyproject.toml
[project]
name = "prep-driver-preview"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["prep"]

[project.entry-points."prep.hardware"]
preview = "prep_driver_preview:PreviewDriver"
```

`prep_driver_preview/__init__.py` — `PreviewDriver`
- `name = "Preview"`, `driver_id = "preview"`
- `connect()` / `disconnect()` are no-ops
- Implements `Configurable`: one field — `SettingField("speed_factor", float, 1.0, "Preview speed multiplier", min=0.1, max=10.0)`
- `send(collection, progress_cb)`: iterate all paths across all layers in cut order; emit each segment as a Qt signal so the canvas draws it progressively; call `progress_cb` with fraction complete after each path; `speed_factor` scales simulated travel time

**`drivers/prep-driver-creation-ct630/`**

```toml
# pyproject.toml
[project]
name = "prep-driver-creation-ct630"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["prep", "pyserial"]

[project.entry-points."prep.hardware"]
creation_ct630 = "prep_driver_creation_ct630:CT630Driver"
```

`prep_driver_creation_ct630/__init__.py` — `CT630Driver`
- `name = "Creation CT630"`, `driver_id = "creation_ct630"`
- `port: str = ""`, `baud: int = 9600`
- Implements `Configurable` via the **escape hatch** (`settings_widget()`): returns a `QWidget` with a port `QComboBox` populated live from `serial.tools.list_ports` and a baud `QSpinBox`; the schema-based auto-form cannot handle the dynamic port list
- `connect(port, baud)`: open serial via `prep.hardware.serial_comm.SerialComm`; send HPGL `IN;` and wait for the machine to respond
- `send(collection, progress_cb)`: call `prep.io.hpgl_writer.to_hpgl(collection)` to get the full HPGL string; write in fixed-size chunks; call `progress_cb` with bytes-sent / total-bytes after each chunk
- `disconnect()`: send `SP0;` (select pen 0 / pen up), close serial

### Phase 4 — UI

All dialogs and panels define their layout in a Qt Designer `.ui` file under `prep/ui/forms/`. Load with `uic.loadUi(Path(__file__).parent / "forms" / "<name>.ui", self)` in `__init__` — this populates `self` with all named child widgets. The `.ui` file is the single source of truth for structure and property defaults; Python code only connects signals and drives runtime data. `MainWindow` and `Canvas` are exceptions — their layout is fully imperative.

---

**`prep/ui/settings.py`** — `SettingsDialog(QDialog)`

```python
class SettingsDialog(QDialog):
    def __init__(self, plugin: Configurable, parent: QWidget | None = None):
        ...
```

- `settings_dialog.ui`: dialog frame with a `QScrollArea` named `content_area` as the body placeholder and a `QDialogButtonBox` (OK/Cancel) in the footer
- Window title set at runtime: `plugin.name + " — Settings"`
- Body: if `hasattr(plugin, "settings_widget")` returns a non-`None` widget, set it as the `content_area` widget; otherwise auto-generate a `QFormLayout` and install it:
  - `float` / `int` → `QDoubleSpinBox` / `QSpinBox`; apply `min`/`max` if set
  - `str` with `choices` → `QComboBox`
  - `str` without `choices` → `QLineEdit`
  - `bool` → `QCheckBox`
- Pre-populate all widgets from `plugin.get_settings()`
- On OK: collect widget values into `dict[str, Any]` and call `plugin.set_settings(values)`
- Plugins that do not implement `Configurable` must not be passed to this dialog

---

**`prep/ui/plugin.py`** — UI plugin protocol, application context, and event bus

```python
# Events
@dataclass
class AppEvent: pass

@dataclass
class FileOpenedEvent(AppEvent):
    path: Path
    collection: PathCollection

@dataclass
class PipelineCompletedEvent(AppEvent):
    collection: PathCollection

@dataclass
class HardwareConnectedEvent(AppEvent):
    driver: HardwareDriverProtocol

@dataclass
class HardwareDisconnectedEvent(AppEvent):
    driver: HardwareDriverProtocol

# Controlled API surface passed to each plugin on activation
class AppContext:
    def collection(self) -> PathCollection | None: ...
    def set_collection(self, collection: PathCollection) -> None: ...
    def run_pipeline(self) -> None: ...
    def add_panel(self, widget: QWidget, title: str,
                  area: Qt.DockWidgetArea = Qt.RightDockWidgetArea) -> None: ...
    def add_menu_action(self, menu: str, action: QAction) -> None: ...
    def add_toolbar_action(self, action: QAction) -> None: ...
    def add_canvas_overlay(self, item: QGraphicsItem) -> None: ...
    def subscribe(self, event_type: type[AppEvent],
                  handler: Callable[[AppEvent], None]) -> None: ...
    def settings(self) -> SettingsStore: ...
    # returns a SettingsStore scoped to ui_plugins/{plugin_id}/ — plugins use this
    # to persist arbitrary data beyond what Configurable.get_settings() covers

# Plugin protocol
class UIPluginProtocol(Protocol):
    name: str
    plugin_id: str
    description: str
    author: str
    tags: list[str]      # for future marketplace browsing/filtering

    def activate(self, ctx: AppContext) -> None: ...
    def deactivate(self) -> None: ...

# Registry
class UIPluginRegistry:
    _descriptors: dict[str, EntryPoint]
    _active: dict[str, UIPluginProtocol]

    def load_plugins(self) -> None:
        # entry_points(group="prep.ui"), lazy

    def plugins(self) -> list[UIPluginProtocol]:
        # load all descriptors, return list sorted by name

    def activate(self, plugin_id: str, ctx: AppContext) -> None: ...
    def deactivate(self, plugin_id: str) -> None: ...

_registry = UIPluginRegistry()
```

- `AppContext` tracks every UI element and event subscription added by each plugin; `deactivate()` removes them all automatically without requiring the plugin to clean up manually
- UI plugins may implement `Configurable`; `SettingsDialog` works for them as-is
- No bundled UI plugins — the group is `prep.ui`; third-party plugins install their own packages
- Same security posture as all other plugin layers — see the security note

**`prep/ui/plugin_panel.py`** — `PluginPanel(QWidget)`
- `plugin_panel.ui`: `QListWidget` (`plugin_list`), `QToolButton` (`settings_btn`, gear icon), `QPushButton` (`toggle_btn`), `QPushButton` (`marketplace_btn`, disabled, labelled "Browse Marketplace")
- `plugin_list` populated at runtime from `_registry.plugins()`; each row shows name, author, and description
- `toggle_btn` enables/disables the selected plugin via `_registry.activate/deactivate`
- `settings_btn` opens `SettingsDialog(plugin)` when plugin implements `Configurable`
- `marketplace_btn` is a placeholder; will open a filtered PyPI index for `prep.ui` packages once the marketplace exists

---

**`prep/ui/pipeline_panel.py`** — `PipelinePanel(QWidget)`
- `pipeline_panel.ui`: `QListWidget` (`step_list`), `QToolButton` (`settings_btn`, gear icon)
- Populated from `pipeline._registry.trace()` after each run; each row shows the `TraceEntry.label` — "Input" first, then one row per step in execution order
- Selecting a row calls `MainWindow._show_step(index)` which sets the canvas to display `trace[index].collection`
- The row matching the final step is selected by default after each run
- `settings_btn` opens `SettingsDialog(entry.step)` for the selected row when `entry.step` is not `None` and implements `Configurable`
- Before the first run the list is empty; `MainWindow` repopulates it after every `run_pipeline()` call

---

**`prep/ui/settings_store.py`** — `SettingsStore`

```python
class SettingsStore:
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def remove(self, key: str) -> None: ...
    def namespace(self, prefix: str) -> "SettingsStore": ...
    def save_window(self, window: QMainWindow) -> None: ...
    def restore_window(self, window: QMainWindow) -> None: ...
```

- Wraps `QSettings(QSettings.IniFormat, QSettings.UserScope, "Prep", "Prep")`
- `namespace("pipeline")` returns a scoped store where all keys are prefixed `pipeline/`; prevents key collisions across subsystems
- `save_window` / `restore_window` handle `saveGeometry()` / `restoreGeometry()`

Key layout (all state in one INI file):
```
window/geometry
perspectives/current
perspectives/{id}/name
perspectives/{id}/state         ← QMainWindow.saveState() bytes
pipeline/{name}/settings/{key}
hardware/{id}/settings/{key}
ui_plugins/{id}/enabled
ui_plugins/{id}/settings/{key}
```

---

**`prep/ui/perspective.py`** — `Perspective`, `PerspectiveManager`

```python
@dataclass
class Perspective:
    perspective_id: str
    name: str
    description: str = ""
    builtin: bool = False      # built-ins cannot be deleted
    window_state: bytes = b""  # QMainWindow.saveState() snapshot

class PerspectiveManager:
    def register(self, perspective: Perspective) -> None: ...

    def switch_to(self, perspective_id: str, window: QMainWindow) -> None:
        # restoreState(perspective.window_state) if non-empty

    def save_current(self, window: QMainWindow) -> None:
        # overwrite current perspective's window_state; persist to SettingsStore

    def create_from_current(self, name: str, window: QMainWindow) -> Perspective:
        # snapshot current dock layout as a new named user perspective; persist it

    def delete(self, perspective_id: str) -> None:
        # raise ValueError if builtin=True

    def all(self) -> list[Perspective]: ...
    def current(self) -> Perspective | None: ...
```

Built-in perspectives registered at startup:
- **Prepare** (`prepare`, `builtin=True`) — Canvas central; Pipeline docked left; Layers and Layout docked right; Hardware hidden
- **Cut** (`cut`, `builtin=True`) — Canvas central; Hardware docked right and prominent; Pipeline tabbed behind it; Layers and Layout hidden

First launch: built-ins have no `window_state` yet; the workbench arranges docks programmatically (`addDockWidget`, `tabifyDockWidget`) then calls `perspective_manager.save_current()` to capture the initial state.

---

**`prep/ui/main_window.py`** — `MainWindow(QMainWindow)` — workbench

All views are `QDockWidget` instances with unique `objectName`s (required for `saveState`/`restoreState`). Built-in views and their object names:

| View | objectName |
|---|---|
| Canvas | `"canvas"` (central widget, not dockable) |
| Pipeline | `"view.pipeline"` |
| Layers | `"view.layers"` |
| Layout | `"view.layout"` |
| Hardware | `"view.hardware"` |
| Plugins | `"view.plugins"` |

Plugin-contributed panels (via `ctx.add_panel()`) receive `objectName = f"view.plugin.{plugin_id}"`.

**Menu bar:**
- File → Open SVG, Recent Files, separator, Quit
- View → one checkable action per registered dock view (show/hide)
- Perspective → one action per registered perspective + separator + "Save Current Layout" + "New Perspective…" + "Reset to Default"
- Plugins → Manage Plugins

**Perspective bar:** `QToolBar` fixed at the top-right of the window; one `QToolButton` per perspective, checkable, acts like a radio group. Clicking switches perspectives via `PerspectiveManager.switch_to()`.

**Startup sequence:**
1. `SettingsStore.restore_window(self)` — geometry
2. Load and restore all `Configurable` settings for pipeline steps, hardware drivers, active UI plugins
3. `UIPluginRegistry.load_plugins()` + activate enabled plugins
4. `PerspectiveManager.switch_to(store.get("perspectives/current", "prepare"))`

**Shutdown sequence (closeEvent):**
1. `PerspectiveManager.save_current(self)`
2. `SettingsStore.save_window(self)`
3. Persist all `Configurable` settings: iterate `pipeline._registry.steps()`, `hardware._registry.drivers()`, `ui._registry.plugins()` — call `get_settings()` and write via namespaced `SettingsStore`
4. Persist enabled state for each UI plugin

`run_pipeline()` calls `pipeline._registry.run(collection)`, fires `PipelineCompletedEvent`, repopulates `PipelinePanel`, and calls `_show_step(len(_registry.trace()) - 1)` to display the final step in the canvas.
`_show_step(index: int)` sets the canvas to display `pipeline._registry.trace()[index].collection`; called by `PipelinePanel` on row selection and by `run_pipeline()` after each run.
Constructs and holds the single `AppContext` instance passed to all UI plugins.

**`prep/ui/canvas.py`** — `Canvas(QGraphicsView)`
- Renders `PathCollection` using `QGraphicsScene`
- Each `CutLayer` drawn in its own color
- Draws material sheet boundary as a grey rectangle
- Supports zoom (wheel) and pan (middle-click drag)

**`prep/ui/layer_panel.py`** — `LayerPanel(QWidget)`
- `layer_panel.ui`: `QListWidget` (`layer_list`) at top; `QFormLayout` below with `QDoubleSpinBox` for speed, power, force
- Selecting a row in `layer_list` populates the spinboxes from the corresponding `CutLayer`; changes update the `PathCollection` in place

**`prep/ui/layout_panel.py`** — `LayoutPanel(QWidget)`
- `layout_panel.ui`: `QFormLayout` with `QDoubleSpinBox` for width and height (`width_spin`, `height_spin`) and a `QPushButton` (`fit_button`) labelled "Fit to Sheet"
- Button updates `collection.material_width/height` then calls `run_pipeline()`

**`prep/ui/hardware_panel.py`** — `HardwarePanel(QWidget)`
- `hardware_panel.ui`: `QComboBox` (`driver_combo`), `QToolButton` (`settings_btn`, gear icon), `QPushButton` (`connect_btn`), `QPushButton` (`send_btn`), `QProgressBar` (`progress_bar`)
- `driver_combo` populated at runtime from `hardware._registry.drivers()`
- `settings_btn` enabled only when selected driver implements `Configurable`; opens `SettingsDialog(driver)`
- `send_btn` disabled until connected; `progress_bar` driven via `progress_cb`

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
