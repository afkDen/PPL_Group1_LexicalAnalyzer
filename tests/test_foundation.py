import json
import subprocess
import sys
from pathlib import Path

from ternfold.cli import main


def test_status_is_explicit_about_missing_compiler() -> None:
    # subprocess also verifies python -m entry point without relying on pytest capture typing.
    result = subprocess.run(
        [sys.executable, "-m", "ternfold", "status"], capture_output=True, text=True, check=True
    )
    status = json.loads(result.stdout)
    assert status["language_execution"] is False
    assert status["next_task"] == "M09"
    assert status["frontend_components"] == [
        "source-snapshots",
        "structured-diagnostics",
        "lexer",
        "parser",
        "resolution",
        "types",
        "machine-planning",
        "Float",
    ]
    assert {"tokens", "ast"} <= set(status["implemented"])


def test_main_status() -> None:
    assert main(["status"]) == 0


def test_unimplemented_command_is_an_error() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ternfold", "run", "missing.tfd"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_example_manifest_covers_all_programs() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "examples/manifest.json").read_text(encoding="utf-8"))
    listed = {case["path"] for case in manifest["cases"]}
    actual = {path.relative_to(root).as_posix() for path in (root / "examples").rglob("*.tfd")}
    assert listed == actual
