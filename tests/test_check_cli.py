"""Real M05 CLI boundaries, deterministic diagnostics and no execution claims."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ternfold.cli import main
from ternfold.frontend import diagnostics

ROOT = Path(__file__).resolve().parents[1]


def command(path: Path, *args: str, seed: str = "1") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "ternfold", "check", str(path), *args],
        env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"},
        cwd=ROOT,
        capture_output=True,
        check=False,
        timeout=30,
    )


def test_successful_library_is_quiet_with_typed_help_and_metadata(tmp_path: Path) -> None:
    path = tmp_path / "library & (space).tfd"
    path.write_text("fn f()->Int{0}", encoding="utf-8")
    result = command(path, "--diagnostic-format", "json")
    assert result.returncode == 0 and result.stdout == result.stderr == b""
    status = subprocess.run(
        [sys.executable, "-m", "ternfold", "status"], capture_output=True, check=False, timeout=15
    )
    metadata = json.loads(status.stdout)
    assert metadata["next_task"] == "M09"
    assert metadata["frontend_components"][-2:] == ["machine-planning", "Float"]
    assert metadata["check_scope"] == "full-frontend"
    assert metadata["type_checking"] is True and metadata["language_execution"] is False
    help_result = subprocess.run(
        [sys.executable, "-m", "ternfold", "check", "--help"],
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert help_result.returncode == 0
    assert b"names, types and machine dependency plans" in help_result.stdout
    assert b"Does not execute programs" in help_result.stdout


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"\xff", "E001"),
        (b"\xef\xbb\xbf", "E002"),
        (b"\r", "E003"),
        (b"@", "E101"),
        (b"fn f()->Int{}", "E110"),
        (b"fn f()->Int{unknown}", "E203"),
        (b'import "missing.tfd" as lib;', "E204"),
        (b'import "entry.tfd" as lib;', "E205"),
    ],
)
def test_source_diagnostics_use_existing_renderer_and_exit_one(
    tmp_path: Path, data: bytes, code: str
) -> None:
    path = tmp_path / "entry.tfd"
    path.write_bytes(data)
    result = command(
        path, "--root", str(tmp_path), "--diagnostic-format", "json", "--color", "always"
    )
    assert result.returncode == 1 and result.stdout == b""
    payload = json.loads(result.stderr)
    assert payload["has_errors"] is True
    diagnostic = payload["diagnostics"][0]
    assert diagnostic["code"] == code
    assert diagnostic["primary"]["span"]["file"] == "entry.tfd"
    assert b"Traceback" not in result.stderr and b"\x1b" not in result.stderr
    if code in {"E001", "E002", "E003"}:
        span = diagnostic["primary"]["span"]
        assert span["source_valid"] is False
        assert span["start"]["line"] is None and span["start"]["column"] is None
        assert span["start"]["byte"] == 0 and span["end"]["byte"] == len(data)


def test_import_source_error_and_privacy_multispans(tmp_path: Path) -> None:
    path = tmp_path / "entry.tfd"
    path.write_text('import "lib.tfd" as lib;fn f()->Int{lib::private()}', encoding="utf-8")
    library = tmp_path / "lib.tfd"
    library.write_bytes(b"\xff")
    result = command(path, "--diagnostic-format", "json")
    assert result.returncode == 1 and result.stdout == b""
    assert json.loads(result.stderr)["diagnostics"][0]["primary"]["span"]["file"] == "lib.tfd"
    library.write_text("fn private()->Int{1}", encoding="utf-8")
    result = command(path, "--diagnostic-format", "json")
    payload = json.loads(result.stderr)["diagnostics"][0]
    assert result.returncode == 1 and payload["code"] == "E206"
    assert payload["primary"]["span"]["file"] == "entry.tfd"
    assert payload["secondary"][0]["span"]["file"] == "lib.tfd"
    colored = command(path, "--color", "always")
    plain = command(path, "--color", "never")
    assert colored.returncode == plain.returncode == 1
    assert b"\x1b[" in colored.stderr and b"\x1b" not in plain.stderr
    assert b"entry.tfd" in plain.stderr and b"lib.tfd" in plain.stderr


def test_missing_entry_wrong_extension_and_root_are_host_errors(tmp_path: Path) -> None:
    path = tmp_path / "entry.tfd"
    path.write_text("fn f()->Int{0}", encoding="utf-8")
    wrong = tmp_path / "entry.txt"
    wrong.write_bytes(path.read_bytes())
    for file, args in (
        (tmp_path / "missing.tfd", ()),
        (wrong, ()),
        (path, ("--root", str(ROOT))),
        (path, ("--root", str(tmp_path / "missing"))),
    ):
        result = command(file, *args, "--diagnostic-format", "json")
        assert result.returncode == 2 and result.stdout == b""
        assert "host_error" in json.loads(result.stderr)
        assert b"Traceback" not in result.stderr


@pytest.mark.parametrize(
    "text",
    [
        "fn f()->Int{" + "+".join(["1"] * 1500) + "}",
        "fn f()->Int{" + "(" * 2000 + "0" + ")" * 2000 + "}",
    ],
)
def test_deep_ast_or_parse_capacity_is_host_error(tmp_path: Path, text: str) -> None:
    path = tmp_path / "deep.tfd"
    path.write_text(text, encoding="utf-8")
    result = command(path, "--diagnostic-format", "json")
    assert result.returncode == 2 and result.stdout == b""
    assert "recursion" in json.loads(result.stderr)["host_error"]
    assert b"Traceback" not in result.stderr


def test_symbol_nominal_and_capture_ids_are_hash_seed_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "entry.tfd"
    path.write_text(
        'import "lib.tfd" as a;import "./lib.tfd" as b;'
        "fn f(x:Int,y:Int)->Int{let c=fn()->Int{y+x};let _=a::R();0}",
        encoding="utf-8",
    )
    (tmp_path / "lib.tfd").write_text("pub record R{}", encoding="utf-8")
    script = """
from dataclasses import asdict
import json, sys
from ternfold.driver import resolve_source as check
from ternfold.frontend.diagnostics import ValidResult
r=check(sys.argv[1]); assert isinstance(r,ValidResult), r.diagnostics
p=r.value
print(json.dumps({'symbols': [asdict(s) for s in p.symbols],
                 'refs': [asdict(r) for r in p.references.values()],
                 'captures': [[asdict(s) for s in c] for c in p.captures.values()]},
                sort_keys=True))
"""
    results = [
        subprocess.run(
            [sys.executable, "-c", script, str(path)],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            check=False,
            timeout=15,
        )
        for seed in ("1", "42", "98765")
    ]
    assert all(r.returncode == 0 and r.stderr == b"" for r in results)
    assert len({r.stdout for r in results}) == 1
    path.write_text('import "missing.tfd" as a;fn f()->Int{unknown}', encoding="utf-8")
    failures = [
        command(path, "--diagnostic-format", "json", seed=seed) for seed in ("1", "42", "98765")
    ]
    assert all(r.returncode == 1 for r in failures)
    assert len({r.stderr for r in failures}) == 1


def test_all_manifest_examples_resolve_at_their_owning_phase() -> None:
    manifest = json.loads((ROOT / "examples/manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["cases"]) == 22
    for case in manifest["cases"]:
        result = command(ROOT / case["path"])
        expected = {
            "examples/invalid/closure_candidate.tfd": b"E406",
            "examples/invalid/non_bool_guard.tfd": b"E302",
            "examples/invalid/non_exhaustive.tfd": b"E310",
            "examples/invalid/candidate_cycle.tfd": b"E404",
            "examples/invalid/missing_writer.tfd": b"E401",
            "examples/invalid/duplicate_writer.tfd": b"E402",
        }.get(case["path"])
        if expected is not None:
            assert result.returncode == 1 and expected in result.stderr
        else:
            assert result.returncode == 0, (case["path"], result.stderr)
        assert result.stdout == b""  # static checks, never course execution


def test_invalid_frontend_cannot_call_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ternfold.driver

    def forbidden(*args: object, **kwargs: object) -> diagnostics.ErrorResult:
        raise AssertionError("invalid frontend reached resolution")

    monkeypatch.setattr(ternfold.driver, "resolve", forbidden)
    path = tmp_path / "entry.tfd"
    for data in (b"\xff", b"@", b"fn f()->Int{}"):
        path.write_bytes(data)
        assert main(["check", str(path)]) == 1


def test_diagnostic_write_failure_returns_host_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ternfold.cli

    path = tmp_path / "entry.tfd"
    path.write_text("fn f()->Int{unknown}", encoding="utf-8")

    def broken(*args: object) -> None:
        raise BrokenPipeError("closed diagnostic pipe")

    monkeypatch.setattr(ternfold.cli, "_write", broken)
    assert main(["check", str(path)]) == 2
