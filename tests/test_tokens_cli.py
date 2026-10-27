"""Real M03 command subprocesses, safe filesystem publication and OS failures."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from ternfold.cli import main
from ternfold.frontend.lexer import lex
from ternfold.frontend.lexical_report import render_symbol_table
from ternfold.frontend.render import RenderContext
from ternfold.frontend.source import SourceManager

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "lexer"


def command(*args: str, seed: str = "1") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "ternfold", "tokens", *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        check=False,
        timeout=15,
    )


def test_cli_valid_tokens_and_unchanged_status(tmp_path: Path) -> None:
    path = tmp_path / "hello.tfd"
    path.write_bytes(b"pub fn main() -> Unit { () }")
    result = command(str(path))
    assert result.returncode == 0 and result.stderr == b""
    dump = json.loads(result.stdout)
    assert dump["schema_version"] == 1 and dump["has_errors"] is False
    assert dump["file"] == path.name
    assert dump["tokens"][-1]["kind"] == "EOF"
    status = subprocess.run(
        [sys.executable, "-m", "ternfold", "status"], capture_output=True, check=True, timeout=15
    )
    assert json.loads(status.stdout)["next_task"] == "M09"
    assert json.loads(status.stdout)["frontend_components"] == [
        "source-snapshots",
        "structured-diagnostics",
        "lexer",
        "parser",
        "resolution",
        "types",
        "machine-planning",
        "Float",
    ]


@pytest.mark.parametrize("mode", ["text", "json"])
def test_cli_lexical_errors_keep_dump_report_and_structured_diagnostics(
    tmp_path: Path, mode: str
) -> None:
    path = tmp_path / "bad.tfd"
    path.write_bytes('"é" @ 09'.encode())
    table = tmp_path / "Symbol Table.txt"
    result = command(
        str(path), "--symbol-table", str(table), "--diagnostic-format", mode, "--color", "always"
    )
    assert result.returncode == 1
    dump = json.loads(result.stdout)
    assert dump["has_errors"] is True
    assert [token["kind"] for token in dump["tokens"]] == ["TEXT", "INVALID", "INVALID", "EOF"]
    assert table.read_text(encoding="utf-8").count("\tINVALID\tINVALID\t") == 2
    if mode == "json":
        diagnostics = json.loads(result.stderr)
        assert [item["code"] for item in diagnostics["diagnostics"]] == ["E101", "E102"]
        assert diagnostics["diagnostics"][0]["primary"]["span"]["start"] == {
            "byte": 5,
            "line": 1,
            "column": 5,
        }
        assert b"\x1b" not in result.stderr
    else:
        assert b"E101" in result.stderr and b"E102" in result.stderr
        assert b"\x1b[" in result.stderr


@pytest.mark.parametrize(
    ("data", "code"), [(b"\xff", "E001"), (b"\xef\xbb\xbf", "E002"), (b"\r", "E003")]
)
def test_cli_raw_source_errors_are_exit_one_without_fake_tokens(
    tmp_path: Path, data: bytes, code: str
) -> None:
    path = tmp_path / "bad.tfd"
    path.write_bytes(data)
    table = tmp_path / "Symbol Table.txt"
    result = command(str(path), "--diagnostic-format", "json", "--symbol-table", str(table))
    assert result.returncode == 1 and result.stdout == b""
    assert not table.exists()
    span = json.loads(result.stderr)["diagnostics"][0]["primary"]["span"]
    assert span["source_valid"] is False and span["start"]["line"] is None
    assert json.loads(result.stderr)["diagnostics"][0]["code"] == code


@pytest.mark.parametrize("name", ["wrong.txt", "wrong.TFD", "no-extension"])
def test_cli_extension_policy_is_host_error_before_loading(tmp_path: Path, name: str) -> None:
    result = command(str(tmp_path / name), "--diagnostic-format", "json")
    assert result.returncode == 2 and result.stdout == b""
    assert ".tfd extension" in json.loads(result.stderr)["host_error"]


def test_cli_missing_file_directory_and_outside_root_are_host_errors(tmp_path: Path) -> None:
    missing = command(str(tmp_path / "missing.tfd"))
    assert missing.returncode == 2 and b"Traceback" not in missing.stderr
    directory = tmp_path / "directory.tfd"
    directory.mkdir()
    assert command(str(directory)).returncode == 2
    path = tmp_path / "file.tfd"
    path.write_bytes(b"0")
    other = tmp_path / "other"
    other.mkdir()
    outside = command(str(path), "--root", str(other), "--diagnostic-format", "json")
    assert outside.returncode == 2
    assert "source root" in json.loads(outside.stderr)["host_error"]
    assert command(str(path), "--root", str(path)).returncode == 2


def test_cli_paths_with_spaces_and_shell_characters_are_literal(tmp_path: Path) -> None:
    # These names are legal on Windows and contain shell metacharacters.
    directory = tmp_path / "space & shell (literal)"
    directory.mkdir()
    path = directory / "source & input.tfd"
    path.write_bytes('"🙂"'.encode())
    table = directory / "Symbol Table & output.txt"
    result = command(str(path), "--symbol-table", str(table))
    assert result.returncode == 0 and result.stderr == b""
    loaded = SourceManager().load_path(path)
    assert loaded.source is not None
    assert (
        table.read_bytes()
        == render_symbol_table(lex(loaded.source), RenderContext(root=directory)).encode()
    )
    assert path.read_bytes() == '"🙂"'.encode()
    assert sorted(item.name for item in directory.iterdir()) == sorted([path.name, table.name])


def test_cli_report_cannot_overwrite_source_or_hardlink(tmp_path: Path) -> None:
    path = tmp_path / "source.tfd"
    path.write_bytes(b"0")
    assert command(str(path), "--symbol-table", str(path)).returncode == 2
    alias = tmp_path / "alias.txt"
    alias.hardlink_to(path)
    result = command(str(path), "--symbol-table", str(alias))
    assert result.returncode == 2 and b"overwrite" in result.stderr
    assert path.read_bytes() == alias.read_bytes() == b"0"


def test_cli_report_host_failures_do_not_mask_failure_or_leak_temporary_files(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.tfd"
    path.write_bytes(b"0")
    missing = command(str(path), "--symbol-table", str(tmp_path / "absent" / "table.txt"))
    assert missing.returncode == 2 and b"Traceback" not in missing.stderr
    table = tmp_path / "table.txt"
    table.write_bytes(b"previous complete output")
    before = set(tmp_path.iterdir())
    with patch.object(Path, "replace", side_effect=PermissionError("publication denied")):
        assert main(["tokens", str(path), "--symbol-table", str(table)]) == 2
    assert table.read_bytes() == b"previous complete output"
    assert set(tmp_path.iterdir()) == before


def test_cli_magnitude_6001_digits_has_no_host_conversion_limit(tmp_path: Path) -> None:
    path = tmp_path / "huge.tfd"
    digits = "9" * 6001
    path.write_text(digits, encoding="utf-8")
    result = command(str(path))
    assert result.returncode == 0 and result.stderr == b""
    assert json.loads(result.stdout)["tokens"][0]["value"] == {"decimal": digits}


def test_cli_report_and_dump_stable_across_hash_seeds(tmp_path: Path) -> None:
    path = FIXTURES / "report.tfd"
    table = tmp_path / "Symbol Table.txt"
    outputs = []
    for seed in ["1", "42", "98765"]:
        result = command(
            str(path), "--symbol-table", str(table), "--diagnostic-format", "json", seed=seed
        )
        assert result.returncode == 1
        outputs.append((result.stdout, result.stderr, table.read_bytes()))
    assert outputs[0] == outputs[1] == outputs[2]
    assert outputs[0][2] == (FIXTURES / "Symbol Table.txt").read_bytes()
    assert outputs[0][0] == (FIXTURES / "tokens.json").read_bytes()


def test_cli_closed_stdout_is_host_exit_two_without_shutdown_traceback(tmp_path: Path) -> None:
    path = tmp_path / "empty.tfd"
    path.write_bytes(b"")
    child = subprocess.Popen(
        [sys.executable, "-m", "ternfold", "tokens", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert child.stdout is not None and child.stderr is not None
    child.stdout.close()
    try:
        code = child.wait(timeout=15)
        error = child.stderr.read()
    finally:
        child.stderr.close()
    assert code == 2
    assert b"Traceback" not in error and b"Exception ignored" not in error


def test_cli_closed_stderr_is_host_exit_two_without_shutdown_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.tfd"
    path.write_bytes(b"@")
    child = subprocess.Popen(
        [sys.executable, "-m", "ternfold", "tokens", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert child.stdout is not None and child.stderr is not None
    child.stderr.close()
    try:
        output = child.stdout.read()
        code = child.wait(timeout=15)
    finally:
        child.stdout.close()
    assert code == 2 and json.loads(output)["has_errors"] is True


@pytest.mark.parametrize("stream_name", ["stdout", "stderr"])
def test_cli_closed_embedding_stream_is_host_error(tmp_path: Path, stream_name: str) -> None:
    path = tmp_path / "bad.tfd"
    path.write_bytes(b"@")
    stream = StringIO()
    stream.close()
    with patch.object(sys, stream_name, stream):
        assert main(["tokens", str(path)]) == 2
