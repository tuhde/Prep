# Prep — Claude Code Guide

## Role

Claude Code **orchestrates** this project. It plans, reviews, directs, and prepares handoff specs. **openCode implements** (writes the actual code). Do not write implementation code directly — instead produce or update `AGENTS.md` with precise instructions for openCode.

## Project Overview

**Prep** is the stage between designing a motif and sending it to a laser or vinyl cutter. It takes SVG input, runs a processing pipeline, and sends output to hardware over USB/serial.

## Architecture

### Data Flow

```
file → ImporterRegistry → PathCollection
                        → PipelineRegistry.run()
                              optimizer   (simplify nodes, merge overlaps, fix winding)
                              splitter    (split by color/layer → CutLayers)
                              layout      (fit/position on material sheet)
                              cut_order   (reorder paths to minimize travel)
                        → PathCollection → HardwareDriver → hardware
```

`PathCollection` is the single type that crosses every boundary: importer output, pipeline step input and output, hardware driver input. All four plugin layers — importer, pipeline, hardware, and UI — are discovered via `importlib.metadata` entry points (groups `prep.importers`, `prep.pipeline`, `prep.hardware`, `prep.ui`). Built-in implementations register the same way; third-party plugins add their own packages.

### Internal Model

| Class | Purpose |
|---|---|
| `PathCollection` | Top-level document: material rect + depth, layers, hardware config |
| `CutLayer` | One color/pass: color, label, speed/power, list of paths |
| `CutPath` | One contiguous path: Shapely XY geometry, closed flag, optional Z for 2.5D/3D |
| `Dimensionality` | Enum: `D2` (z=None) / `D2_5` (z=float) / `D3` (z=ndarray); derived from `CutPath.z` |

## Project Structure

```
Prep/
├── CLAUDE.md               # This file
├── AGENTS.md               # openCode implementation spec
├── pyproject.toml
├── prep/
│   ├── cli.py               # headless runner: prep run / prep send / prep ui
│   ├── io/
│   │   ├── base.py              # ImporterProtocol, ImporterRegistry
│   │   ├── importers/
│   │   │   ├── svg/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── reader.py    # SVGImporter
│   │   │   │   └── inkscape.py  # layer tree, transforms, color, visibility
│   │   │   └── prep/
│   │   │       ├── __init__.py
│   │   │       └── reader.py    # PrepProjectImporter (.prep files)
│   │   ├── prep_writer.py       # to_prep_svg() — saves PathCollection as .prep
│   │   ├── gcode_writer.py
│   │   └── hpgl_writer.py
│   ├── core/
│   │   ├── path_model.py
│   │   └── configurable.py      # SettingField, Configurable protocol
│   ├── pipeline/
│   │   ├── base.py              # PipelineStepProtocol, PipelineRegistry
│   │   └── steps/
│   │       ├── optimizer.py
│   │       ├── splitter.py
│   │       ├── layout.py
│   │       └── cut_order.py
│   ├── hardware/
│   │   ├── base.py              # HardwareDriverProtocol, HardwareRegistry
│   │   └── serial_comm.py       # shared serial utility for driver packages
│   └── ui/
│       ├── forms/               # Qt Designer .ui files; loaded at runtime with uic.loadUi()
│       │   ├── settings_dialog.ui
│       │   ├── pipeline_panel.ui
│       │   ├── layer_panel.ui
│       │   ├── layout_panel.ui
│       │   ├── hardware_panel.ui
│       │   └── plugin_panel.ui
│       ├── main_window.py       # workbench: dock registry, perspective bar, save/restore on close
│       ├── pipeline_panel.py    # step list; selecting a row drives the canvas
│       ├── canvas.py
│       ├── layer_panel.py
│       ├── layout_panel.py
│       ├── hardware_panel.py
│       ├── settings.py          # SettingsDialog (auto-generates from Configurable)
│       ├── settings_store.py    # QSettings wrapper; single persistence point for all state
│       ├── perspective.py       # Perspective dataclass, PerspectiveManager, built-in perspectives
│       ├── plugin.py            # UIPluginProtocol, AppContext, UIPluginRegistry, AppEvent types
│       └── plugin_panel.py      # installed plugin list with enable/disable
├── drivers/                     # bundled drivers; move to separate repos when stable
│   ├── prep-driver-preview/
│   │   ├── pyproject.toml
│   │   └── prep_driver_preview/
│   └── prep-driver-creation-ct630/
│       ├── pyproject.toml
│       └── prep_driver_creation_ct630/
└── tests/
```

## Stack

| Package | Purpose |
|---|---|
| `PySide6` | Desktop UI (Qt6) |
| `svgpathtools` | SVG path parsing |
| `lxml` | SVG XML / attribute parsing |
| `shapely` | Geometry: simplification, boolean ops |
| `pyserial` | USB/serial hardware comms |
| `numpy` | Distance matrix for cut order |

## Hardware Targets

The hardware layer is plugin-based (`prep.hardware` entry-point group). Each machine is a separately installable package.

Bundled drivers (in `drivers/`, move to separate repos once the interface stabilises):
- **Preview** — software-only; animates the cut path on the canvas without hardware
- **Creation CT630** — vinyl cutter; HPGL over serial at 9600 baud

New machines are added without modifying the core package.

## Conventions

- Python 3.11+, typed throughout (`dataclasses`, `typing`)
- No comments unless the why is non-obvious
- Tests live in `tests/` with SVG fixtures in `tests/fixtures/`
- Entry point: `python -m prep`

## GitHub

Remote named `github` → `git@github.com:tuhde/Prep.git`
