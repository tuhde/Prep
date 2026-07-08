import argparse
import sys
from pathlib import Path


def run_cli(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="prep")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("input", type=str)
    run_parser.add_argument("-o", "--output", type=str)
    run_parser.add_argument("--set", action="append", default=[])
    run_parser.add_argument("--driver", type=str)
    run_parser.add_argument("--port", type=str)
    run_parser.add_argument("--baud", type=int)

    send_parser = subparsers.add_parser("send")
    send_parser.add_argument("input", type=str)
    send_parser.add_argument("--set", action="append", default=[])
    send_parser.add_argument("--driver", type=str)
    send_parser.add_argument("--port", type=str)
    send_parser.add_argument("--baud", type=int)

    subparsers.add_parser("ui")

    args = parser.parse_args(argv)

    if args.command == "ui":
        from prep.ui.main_window import main as run_ui
        run_ui()
        return

    if args.command in ("run", "send"):
        from prep.io.base import get_registry as get_importer_registry
        from prep.pipeline.base import get_registry as get_pipeline_registry
        from prep.hardware.base import get_registry as get_hardware_registry
        from prep.io.gcode_writer import to_gcode
        from prep.io.hpgl_writer import to_hpgl
        from prep.io.prep_writer import to_prep_svg

        importer_registry = get_importer_registry()
        pipeline_registry = get_pipeline_registry()
        hardware_registry = get_hardware_registry()

        importer_registry.load_plugins()
        pipeline_registry.load_plugins()
        hardware_registry.load_plugins()

        input_path = Path(args.input)
        try:
            importer = importer_registry.for_path(input_path)
            collection = importer.read(input_path)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if collection.pipeline_settings:
            for step_name, settings in collection.pipeline_settings.items():
                for step in pipeline_registry.steps():
                    if step.name == step_name and hasattr(step, "set_settings"):
                        step.set_settings(settings)

        for setting in args.set:
            if "." not in setting or "=" not in setting:
                print(f"Invalid --set format: {setting} (expected STEP.KEY=VALUE)", file=sys.stderr)
                sys.exit(1)
            step_key, value = setting.split("=", 1)
            step_name, key = step_key.split(".", 1)
            for step in pipeline_registry.steps():
                if step.name == step_name and hasattr(step, "set_settings"):
                    try:
                        coerced = float(value)
                        if coerced == int(coerced):
                            coerced = int(coerced)
                    except ValueError:
                        if value.lower() in ("true", "false"):
                            coerced = value.lower() == "true"
                        else:
                            coerced = value
                    step.set_settings({key: coerced})

        if args.driver:
            collection.hardware.driver = args.driver
        if args.port:
            collection.hardware.port = args.port
        if args.baud:
            collection.hardware.baud = args.baud

        collection = pipeline_registry.run(collection)

        if args.command == "run":
            if args.output:
                output_path = Path(args.output)
                suffix = output_path.suffix.lower()
                try:
                    if suffix == ".gcode":
                        content = to_gcode(collection)
                    elif suffix == ".hpgl":
                        content = to_hpgl(collection)
                    elif suffix in (".prep", ".svg"):
                        content = to_prep_svg(collection, pipeline_registry.steps())
                    else:
                        content = to_gcode(collection)
                    output_path.write_text(content)
                    print(f"Written to {output_path}")
                except Exception as e:
                    print(f"Error writing output: {e}", file=sys.stderr)
                    sys.exit(1)
            else:
                print(to_gcode(collection))
        elif args.command == "send":
            if not collection.hardware.driver:
                print("Error: No driver specified", file=sys.stderr)
                sys.exit(1)
            try:
                driver = hardware_registry.by_id(collection.hardware.driver)
                driver.connect(collection.hardware.port, collection.hardware.baud)

                def progress_cb(fraction):
                    print(f"\rSending… {int(fraction * 100)}%", end="", file=sys.stderr)

                driver.send(collection, progress_cb)
                driver.disconnect()
                print(file=sys.stderr)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)

        return

    parser.print_help()
    sys.exit(1)
