# Prep — Claude Code Guide

## Role

Claude Code **orchestrates** this project. It plans, reviews, directs, and prepares handoff specs. **openCode implements** (writes the actual code). Do not write implementation code directly — instead produce or update `AGENTS.md` with precise instructions for openCode.

## Project Overview

**Prep** is the stage between designing a motif and sending it to a laser or vinyl cutter. It takes SVG input, runs a processing pipeline, and sends output to hardware over USB/serial.

## Architecture

### Data Flow

```
SVG file → svg_reader → PathCollection
         → optimizer    (node simplify, merge overlaps, fix winding)
         → splitter     (split by color/layer → CutLayers)
         → layout       (position/scale/rotate on material sheet)
         → cut_order    (reorder paths to minimize travel)
         → writer       (GCODE or HPGL)
         → hardware     (send over serial)
```

### Internal Model

| Class | Purpose |
|---|---|
| `PathCollection` | Top-level document: material rect, layers, hardware config |
| `CutLayer` | One color/pass: color, label, speed/power, list of paths |
| `CutPath` | One contiguous path: Shapely geometry, closed flag |

## Project Structure

```
Prep/
├── CLAUDE.md               # This file
├── AGENTS.md               # openCode implementation spec
├── pyproject.toml
├── postprocess/
│   ├── io/
│   │   ├── svg_reader.py
│   │   ├── gcode_writer.py
│   │   └── hpgl_writer.py
│   ├── core/
│   │   ├── path_model.py
│   │   ├── optimizer.py
│   │   ├── splitter.py
│   │   ├── layout.py
│   │   └── cut_order.py
│   ├── hardware/
│   │   ├── base.py
│   │   ├── grbl.py
│   │   ├── hpgl.py
│   │   └── serial_comm.py
│   └── ui/
│       ├── main_window.py
│       ├── canvas.py
│       ├── layer_panel.py
│       ├── layout_panel.py
│       └── hardware_panel.py
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

- **GRBL** laser cutters — GCODE over serial
- **HPGL** vinyl cutters — HPGL commands over serial
- Hardware layer is abstracted via `hardware/base.py`; new drivers added without touching the pipeline

## Conventions

- Python 3.11+, typed throughout (`dataclasses`, `typing`)
- No comments unless the why is non-obvious
- Tests live in `tests/` with SVG fixtures in `tests/fixtures/`
- Entry point: `python -m postprocess`

## GitHub

Remote named `github` → `git@github.com:tuhde/Prep.git`
