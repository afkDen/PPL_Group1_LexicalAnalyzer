"""Core command publishes only verified IR and preserves source/host distinctions."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ternfold.cli import main
from ternfold.core.verify import Issue, VerificationError


def command(path: Path, seed: str = "1") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "ternfold", "core", str(path), "--diagnostic-format", "json"],
        env={**os.environ, "PYTHONHASHSEED": seed},
        capture_output=True,
        check=False,
        timeout=15,
    )


def test_library_core_is_verified_root_relative_deterministic_utf8_lf(tmp_path: Path) -> None:
    entry = tmp_path / "library & (space).tfd"
    entry.write_text('fn f()->Text{"Ω"}', encoding="utf-8")
    results = [command(entry, seed) for seed in ("1", "42")]
    assert all(r.returncode == 0 and r.stderr == b"" for r in results)
    assert results[0].stdout == results[1].stdout
    assert b"\r\n" not in results[0].stdout
    payload = json.loads(results[0].stdout)
    assert payload["phase"] == "verified-core" and payload["language_execution"] is False
    assert payload["program"]["entry"] is None
    assert payload["program"]["functions"][0]["origin"]["span"]["file"] == entry.name
    assert str(tmp_path).encode() not in results[0].stdout


@pytest.mark.parametrize(
    ("source", "code"),
    [
        ("@", "E101"),
        ("fn f()->Int{true}", "E302"),
        ("machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=next.a;}", "E404"),
    ],
)
def test_source_errors_never_publish_core(tmp_path: Path, source: str, code: str) -> None:
    entry = tmp_path / "invalid.tfd"
    entry.write_text(source, encoding="utf-8")
    result = command(entry)
    assert result.returncode == 1 and result.stdout == b""
    assert code in [d["code"] for d in json.loads(result.stderr)["diagnostics"]]


def test_core_host_failure_is_two(tmp_path: Path) -> None:
    result = command(tmp_path / "wrong.txt")
    assert result.returncode == 2 and result.stdout == b""
    assert "host_error" in json.loads(result.stderr)


def test_verifier_failure_is_internal_seventy_without_invalid_dump(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import ternfold.cli

    def fail(*args: object, **kwargs: object) -> None:
        raise VerificationError((Issue("forged dominance"),))

    monkeypatch.setattr(ternfold.cli, "compile_source", fail)
    assert main(["core", str(tmp_path / "entry.tfd"), "--diagnostic-format", "json"]) == 70
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["phase"] == "Core verification"
    assert "Traceback" not in captured.err


def test_failed_frontend_cannot_reach_lowering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ternfold.driver
    from ternfold.frontend.diagnostics import ErrorResult

    entry = tmp_path / "entry.tfd"
    entry.write_text("fn f()->Int{unknown}", encoding="utf-8")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("invalid source reached Core")

    monkeypatch.setattr(ternfold.driver, "lower", forbidden)
    assert isinstance(ternfold.driver.compile_source(entry), ErrorResult)


def test_maintained_machine_core_golden_has_exact_ids_origins_and_guard_structure() -> None:
    fixture = Path(__file__).parent / "fixtures/core/machine.tfd"
    result = command(fixture)
    assert result.returncode == 0 and result.stderr == b""
    assert result.stdout == fixture.with_suffix(".json").read_bytes()
