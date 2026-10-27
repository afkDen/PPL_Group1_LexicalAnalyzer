"""Real typed CLI, unchanged resolution boundary and ordered diagnostics."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ternfold.analysis.check import check as check_types
from ternfold.driver import resolve_source
from ternfold.driver import type_source as check
from ternfold.frontend.diagnostics import ErrorResult, ValidResult


def command(path: Path, *, seed: str = "1") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "ternfold", "check", str(path), "--diagnostic-format", "json"],
        env={**os.environ, "PYTHONHASHSEED": seed},
        capture_output=True,
        check=False,
        timeout=15,
    )


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("fn f()->Int{true}", "E302"),
        ("fn f()->Int{9223372036854775808}", "E301"),
        ("fn f(x:Int)->Int{x}fn g()->Int{f()}", "E303"),
        ("fn f()->Int{let a=[];0}", "E304"),
        ("fn f(x:fn()->Int)->Bool{x==x}", "E305"),
        ("machine M(x:Int)yields Int rejects Text{state a:Int=1 div 0;next a=a;}", "E306"),
        ("record R{x:R}", "E307"),
        ("fn f(x:Bool)->Int{match x{true=>{0}}}", "E310"),
        ("fn f(x:Bool)->Int{match x{_=>{0},true=>{1}}}", "E311"),
        ("fn f(x:Bool)->Int{match x{1=>{0},_=>{1}}}", "E312"),
        ("machine M(x:Int)yields Int rejects Text{state a:List[fn()->Int]=[];next a=a;}", "E407"),
    ],
)
def test_each_type_diagnostic_family_and_resolution_boundary(
    tmp_path: Path, text: str, code: str
) -> None:
    entry = tmp_path / "space & (library).tfd"
    entry.write_text(text, encoding="utf-8")
    assert isinstance(resolve_source(entry), ValidResult)
    result = command(entry)
    assert result.returncode == 1 and result.stdout == b""
    payload = json.loads(result.stderr)
    assert payload["has_errors"] is True
    assert code in [d["code"] for d in payload["diagnostics"]]
    assert b"Traceback" not in result.stderr and b"\x1b" not in result.stderr


def test_phase_failure_blocks_types_and_type_failure_does_not_publish_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ternfold.driver

    entry = tmp_path / "entry.tfd"
    entry.write_text("fn f()->Int{unknown}", encoding="utf-8")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("invalid resolution reached M06")

    with monkeypatch.context() as scoped:
        scoped.setattr(ternfold.driver, "check_types", forbidden)
        assert isinstance(check(entry), ErrorResult)
    entry.write_text("fn f()->Int{true}", encoding="utf-8")
    resolved = resolve_source(entry)
    assert isinstance(resolved, ValidResult)
    result = check_types(resolved.value, max_diagnostics=0)
    assert isinstance(result, ErrorResult)
    assert result.diagnostics.diagnostics == ()
    assert result.diagnostics.suppressed[0].error_count > 0


def test_crossfile_expected_span_and_hash_seed_determinism(tmp_path: Path) -> None:
    entry = tmp_path / "entry.tfd"
    entry.write_text('import "lib.tfd" as lib;fn f()->Int{lib::f(true)}', encoding="utf-8")
    (tmp_path / "lib.tfd").write_text("pub fn f(x:Int)->Int{x}", encoding="utf-8")
    results = [command(entry, seed=seed) for seed in ("1", "42", "98765")]
    assert all(r.returncode == 1 and r.stdout == b"" for r in results)
    assert len({r.stderr for r in results}) == 1
    error = json.loads(results[0].stderr)["diagnostics"][0]
    assert error["code"] == "E302"
    assert error["primary"]["span"]["file"] == "entry.tfd"
    assert error["secondary"][0]["span"]["file"] == "lib.tfd"


def test_unreachable_imported_function_is_still_typechecked(tmp_path: Path) -> None:
    (tmp_path / "lib.tfd").write_text("fn unreachable()->Int{false}", encoding="utf-8")
    entry = tmp_path / "entry.tfd"
    entry.write_text('import "lib.tfd" as unused;fn f()->Int{0}', encoding="utf-8")
    result = command(entry)
    assert result.returncode == 1
    assert json.loads(result.stderr)["diagnostics"][0]["code"] == "E302"
