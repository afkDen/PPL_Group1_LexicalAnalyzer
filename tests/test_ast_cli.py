"""M04 actual AST command exits, deterministic bytes and host resource boundaries."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "parser"


def command(path: Path, *args: str, seed: str = "1") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "ternfold", "ast", str(path), *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        check=False,
        timeout=15,
    )


@pytest.mark.parametrize("fixture", ["surface", "recovery"])
def test_cli_exact_golden_bytes_and_hash_seed_stability(fixture: str) -> None:
    results = [
        command(FIXTURES / f"{fixture}.tfd", "--diagnostic-format", "json", seed=seed)
        for seed in ["1", "42", "98765"]
    ]
    assert results[0].stdout == results[1].stdout == results[2].stdout
    assert results[0].stderr == results[1].stderr == results[2].stderr
    assert results[0].stdout == (FIXTURES / f"{fixture}.json").read_bytes()
    assert results[0].returncode == (1 if fixture == "recovery" else 0)
    assert b"\r\n" not in results[0].stdout
    if fixture == "recovery":
        assert json.loads(results[0].stderr)["has_errors"] is True
    else:
        assert results[0].stderr == b""


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"\xff", "E001"),
        (b"\xef\xbb\xbf", "E002"),
        (b"\r", "E003"),
        (b"@", "E101"),
        (b"09", "E102"),
        (b'"\\q"', "E103"),
        (b"/*", "E104"),
        (b"''", "E105"),
    ],
)
def test_cli_source_and_lexical_errors_block_ast_dump(
    tmp_path: Path, data: bytes, code: str
) -> None:
    path = tmp_path / "bad.tfd"
    path.write_bytes(data)
    result = command(path, "--diagnostic-format", "json", "--color", "always")
    assert result.returncode == 1 and result.stdout == b""
    assert json.loads(result.stderr)["diagnostics"][0]["code"] == code
    assert b"\x1b" not in result.stderr and b"Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("fn f()->Int {}", "E110"),
        ("fn f()->Bool{a<b<c}", "E111"),
        ("fn f()->X{f(1,x:2)}", "E112"),
        ('fn main()->Unit{output "x";()}', "E208"),
    ],
)
def test_cli_syntax_errors_emit_inspectable_recovery_ast(
    tmp_path: Path, text: str, code: str
) -> None:
    path = tmp_path / "bad.tfd"
    path.write_text(text, encoding="utf-8")
    result = command(path, "--diagnostic-format", "json", "--color", "always")
    assert result.returncode == 1
    assert json.loads(result.stdout)["has_errors"] is True
    assert code in [item["code"] for item in json.loads(result.stderr)["diagnostics"]]
    assert b"\x1b" not in result.stdout + result.stderr


def test_cli_root_extension_and_literal_filesystem_paths(tmp_path: Path) -> None:
    directory = tmp_path / "space & (literal)"
    directory.mkdir()
    path = directory / "a & b.tfd"
    path.write_bytes(b"fn f()->Int{0}")
    good = command(path, "--root", str(tmp_path))
    assert good.returncode == 0
    assert json.loads(good.stdout)["file"] == "space & (literal)/a & b.tfd"
    wrong = directory / "a.txt"
    wrong.write_bytes(path.read_bytes())
    for target in (wrong, directory / "missing.tfd"):
        result = command(target, "--diagnostic-format", "json")
        assert result.returncode == 2 and result.stdout == b""
        assert "host_error" in json.loads(result.stderr)
        assert b"Traceback" not in result.stderr
    outside = command(path, "--root", str(ROOT), "--diagnostic-format", "json")
    assert outside.returncode == 2
    assert "source root" in json.loads(outside.stderr)["host_error"]


def test_cli_deep_nesting_reports_host_failure_instead_of_syntax_error(tmp_path: Path) -> None:
    path = tmp_path / "deep.tfd"
    path.write_text("fn f()->Int{" + "(" * 2000 + "0" + ")" * 2000 + "}", encoding="utf-8")
    result = command(path, "--diagnostic-format", "json")
    assert result.returncode == 2 and result.stdout == b""
    assert "recursion" in json.loads(result.stderr)["host_error"]
    assert b"Traceback" not in result.stderr and b"E110" not in result.stderr


def test_cli_deep_left_associative_dump_resource_failure_is_host_failure(tmp_path: Path) -> None:
    path = tmp_path / "deep-tree.tfd"
    path.write_text("fn f()->Int{" + "+".join(["1"] * 1500) + "}", encoding="utf-8")
    result = command(path, "--diagnostic-format", "json")
    assert result.returncode == 2 and result.stdout == b""
    assert "recursion" in json.loads(result.stderr)["host_error"]
    assert b"Traceback" not in result.stderr


@pytest.mark.parametrize("pipe", ["stdout", "stderr"])
def test_ast_command_closed_pipes_preserve_host_exit_two(tmp_path: Path, pipe: str) -> None:
    path = tmp_path / "bad.tfd"
    path.write_bytes(b"fn f()->Int {}")
    process = subprocess.Popen(
        [sys.executable, "-m", "ternfold", "ast", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None and process.stderr is not None
    closed = process.stdout if pipe == "stdout" else process.stderr
    other = process.stderr if pipe == "stdout" else process.stdout
    closed.close()
    try:
        output = other.read()
        code = process.wait(timeout=15)
    finally:
        other.close()
    assert code == 2
    assert b"Traceback" not in output and b"Exception ignored" not in output


def test_ast_command_huge_decimal_payload_is_preserved(tmp_path: Path) -> None:
    path = tmp_path / "huge.tfd"
    digits = "9" * 6001
    path.write_text(f"fn f()->Int{{-{digits}}}", encoding="utf-8")
    result = command(path)
    assert result.returncode == 0
    dump = json.loads(result.stdout)
    operand = dump["program"]["declarations"][0]["body"]["result"]["operand"]
    assert operand["node_type"] == "LiteralExpr" and operand["kind"] == "INT"
    assert operand["value"] == {"decimal": digits}
