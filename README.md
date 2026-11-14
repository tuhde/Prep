<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="logo-dark.svg">
    <img alt="Prep" src="logo-light.svg" width="300">
  </picture>
</p>

# Prep

Prep is the stage between designing a motif and sending it to a laser or vinyl cutter. It takes SVG input, runs it through a processing pipeline, and sends the result to hardware over USB/serial.

## How it works

```
file → ImporterRegistry → PathCollection
                        → PipelineRegistry.run()
                              optimizer   (simplify nodes, merge overlaps, fix winding)
                              splitter    (split by color/layer → CutLayers)
                              layout      (fit/position on material sheet)
                              cut_order   (reorder paths to minimize travel)
                        → PathCollection → HardwareDriver → hardware
```

`PathCollection` is the single type that crosses every boundary: importer output, pipeline step input and output, and hardware driver input.

| Class | Purpose |
|---|---|
| `PathCollection` | Document: material rect + depth, layers, hardware config |
| `CutLayer` | One color/pass: color, label, speed/power, paths |
| `CutPath` | One contiguous path: Shapely XY geometry, closed flag, optional Z (2D / 2.5D / 3D) |

## Installation

Requires Python 3.11+.

```bash
pip install -e .
pip install -e drivers/prep-driver-preview
pip install -e drivers/prep-driver-creation-ct630
```

The drivers are separate packages and are discovered through entry points, so install the ones you need.

## Usage

```bash
python -m prep ui                          # desktop UI
python -m prep run design.svg -o out.hpgl  # headless: import → pipeline → file
python -m prep send design.svg --driver creation_ct630 --port /dev/ttyUSB0
```

After installation the `prep` command is available as well (`prep run ...`).

### `run`

Processes a file and writes the result. The output format follows the extension of `-o`:

| Extension | Output |
|---|---|
| `.gcode` | G-code |
| `.hpgl` | HPGL |
| `.prep`, `.svg` | `.prep` project (SVG with Prep metadata) |
| anything else | G-code |

Without `-o`, G-code is printed to stdout.

### `send`

Processes a file and sends it to a hardware driver.

### Options

| Option | Commands | Description |
|---|---|---|
| `-o`, `--output` | `run` | Output file |
| `--set STEP.KEY=VALUE` | `run`, `send` | Override a pipeline step setting; repeatable |
| `--driver ID` | `run`, `send` | Hardware driver id |
| `--port PORT` | `run`, `send` | Serial port |
| `--baud RATE` | `run`, `send` | Baud rate |

Run `python -m prep --help` for the full list.

## Plugins

Everything is pluggable through `importlib.metadata` entry points. Built-in implementations register the same way third-party packages do.

| Group | Purpose |
|---|---|
| `prep.importers` | File importers (built in: SVG, `.prep`) |
| `prep.pipeline` | Pipeline steps (built in: optimizer, splitter, layout, cut_order) |
| `prep.hardware` | Machine drivers |
| `prep.ui` | UI plugins |

### Bundled drivers

| Driver | Description |
|---|---|
| `preview` | Software-only; animates the cut path on the canvas |
| `creation_ct630` | Creation CT630 vinyl cutter; HPGL over serial at 9600 baud |

New machines are added as separate packages without modifying the core.

## Stack

PySide6 (UI), svgpathtools (SVG path parsing), lxml (SVG XML), Shapely (geometry), pyserial (hardware comms), numpy (cut order).

## Development

Tests live in `tests/` with SVG fixtures in `tests/fixtures/`.

```bash
pytest
```
