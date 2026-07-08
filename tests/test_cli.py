import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_run_stdout():
    result = subprocess.run(
        [sys.executable, "-m", "prep", "run", str(FIXTURES / "simple_rect.svg")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "G21" in result.stdout
    assert "G90" in result.stdout


def test_cli_run_output_gcode(tmp_path):
    output = tmp_path / "output.gcode"
    result = subprocess.run(
        [sys.executable, "-m", "prep", "run", str(FIXTURES / "simple_rect.svg"), "-o", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert output.exists()
    content = output.read_text()
    assert "G21" in content


def test_cli_run_output_hpgl(tmp_path):
    output = tmp_path / "output.hpgl"
    result = subprocess.run(
        [sys.executable, "-m", "prep", "run", str(FIXTURES / "simple_rect.svg"), "-o", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert output.exists()
    content = output.read_text()
    assert "IN;" in content


def test_cli_run_output_prep(tmp_path):
    output = tmp_path / "output.prep"
    result = subprocess.run(
        [sys.executable, "-m", "prep", "run", str(FIXTURES / "simple_rect.svg"), "-o", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert output.exists()
    content = output.read_text()
    assert "prep:format-version" in content


def test_cli_run_set_override():
    result = subprocess.run(
        [
            sys.executable, "-m", "prep", "run", str(FIXTURES / "simple_rect.svg"),
            "--set", "optimizer.tolerance=0.5",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_run_hardware_override():
    result = subprocess.run(
        [
            sys.executable, "-m", "prep", "run", str(FIXTURES / "simple_rect.svg"),
            "--driver", "preview",
            "--port", "/dev/null",
            "--baud", "9600",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_run_missing_file():
    result = subprocess.run(
        [sys.executable, "-m", "prep", "run", "nonexistent.svg"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Error" in result.stderr


def test_cli_run_unknown_format(tmp_path):
    unknown = tmp_path / "file.xyz"
    unknown.write_text("test")
    result = subprocess.run(
        [sys.executable, "-m", "prep", "run", str(unknown)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1


def test_cli_send_missing_driver():
    result = subprocess.run(
        [sys.executable, "-m", "prep", "send", str(FIXTURES / "simple_rect.svg")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "driver" in result.stderr.lower()


def test_cli_send_with_preview():
    result = subprocess.run(
        [
            sys.executable, "-m", "prep", "send", str(FIXTURES / "simple_rect.svg"),
            "--driver", "preview",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_set_invalid_format():
    result = subprocess.run(
        [
            sys.executable, "-m", "prep", "run", str(FIXTURES / "simple_rect.svg"),
            "--set", "invalid_format",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Invalid --set format" in result.stderr





def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "prep", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "run" in result.stdout
    assert "send" in result.stdout
    assert "ui" in result.stdout
