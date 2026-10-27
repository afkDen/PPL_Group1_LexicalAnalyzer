"""M07 real plan/check CLI output, origins and full semantic example gates."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ternfold.cli import main
from ternfold.driver import check, type_source
from ternfold.frontend.diagnostics import ErrorResult, ValidResult

ROOT = Path(__file__).resolve().parents[1]


def command(
    path: Path, *args: str, command: str = "plan", seed: str = "1"
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "ternfold", command, str(path), *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        check=False,
        timeout=20,
    )


def test_json_schema_origins_order_and_hash_seed_determinism(tmp_path: Path) -> None:
    path = tmp_path / "space & (machine).tfd"
    text = """machine M(x:Int)yields Int rejects Text{
    state a:Int=0;state b:Int=0;state z:Int=0;
    next z=x;next a=next.b+next.b+a;next b=x;
    guard next.z>0 else int_text(a);
    guard next.a>0 else int_text(next.b);
    emit next.a;emit z;
}
"""
    path.write_text(text, encoding="utf-8")
    original = path.read_bytes()
    results = [
        command(path, "--root", str(tmp_path), "--color", "always", seed=seed)
        for seed in ("1", "42", "98765")
    ]
    assert all(r.returncode == 0 and r.stderr == b"" for r in results)
    assert len({r.stdout for r in results}) == 1
    assert b"\r\n" not in results[0].stdout and b"\x1b" not in results[0].stdout
    payload = json.loads(results[0].stdout)
    assert payload["schema_version"] == 1 and payload["phase"] == "machine-plan"
    assert payload["language_execution"] is False
    assert payload["entry"] == path.name
    assert "runtime checks" in payload["notes"][0] and "not prove" in payload["notes"][0]
    assert "first failed guard" in payload["notes"][1]
    assert "runtime faults are not typed rejections" in payload["notes"][2]
    machine = payload["machines"][0]
    assert machine["type_id"] == {"module": path.name, "declaration_index": 0}
    assert [s["name"] for s in machine["schedule"]] == ["b", "a", "z"]
    assert [s["symbol"]["name"] for s in machine["cells"]] == ["a", "b", "z"]
    assert [s["target"]["name"] for s in machine["writers"]] == ["z", "a", "b"]
    edge = machine["dependencies"][0]
    assert len(machine["dependencies"]) == 1
    assert edge["source"]["name"] == "b" and edge["target"]["name"] == "a"
    assert len(edge["projections"]) == 2
    for projection in edge["projections"]:
        span = projection["origin"]["span"]
        assert span["file"] == path.name
        assert original[span["start"]["byte"] : span["end"]["byte"]] == b"next.b"
        assert span["start"]["line"] == 3 and span["end"]["line"] == 3
    assert [g["condition_reads"]["candidate_cells"][0]["name"] for g in machine["guards"]] == [
        "z",
        "a",
    ]
    assert machine["guards"][0]["error_reads"]["candidate_cells"] == []
    assert machine["guards"][1]["error_reads"]["candidate_cells"][0]["name"] == "b"
    assert [e["reads"]["candidate_cells"] for e in machine["emissions"]][1] == []
    quiet = command(path, command="check")
    assert quiet.returncode == 0 and quiet.stdout == quiet.stderr == b""


def test_library_without_main_and_without_machines(tmp_path: Path) -> None:
    entry = tmp_path / "library.tfd"
    entry.write_text("fn f(x:Int)->Int{x}", encoding="utf-8")
    result = command(entry)
    assert result.returncode == 0 and result.stderr == b""
    assert json.loads(result.stdout)["machines"] == []
    assert isinstance(check(entry), ValidResult)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("machine M(x:Int)yields Int rejects Text{state a:Int=0;state b:Int=0;next a=a;}", "E401"),
        ("machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=a;next a=x;}", "E402"),
        ("machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=next.a;}", "E404"),
        ("machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=next.b;}", "E403"),
        (
            "machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=(fn()->Int{next.a})();}",
            "E406",
        ),
        ("fn f()->Int{next.a}", "E405"),
        ("fn f()->Int{true}", "E302"),
        ("fn f()->Int{unknown}", "E203"),
        ("fn f()->Int{}", "E110"),
        ("@", "E101"),
    ],
)
def test_invalid_programs_publish_no_partial_plan_and_reuse_diagnostic_renderer(
    tmp_path: Path,
    text: str,
    code: str,
) -> None:
    entry = tmp_path / "bad.tfd"
    entry.write_text(text, encoding="utf-8")
    result = command(entry, "--diagnostic-format", "json", "--color", "always")
    assert result.returncode == 1 and result.stdout == b""
    payload = json.loads(result.stderr)
    assert payload["has_errors"] is True
    assert code in [d["code"] for d in payload["diagnostics"]]
    assert b"Traceback" not in result.stderr and b"\x1b" not in result.stderr


def test_imported_unused_machines_are_planned_and_source_identity_is_retained(
    tmp_path: Path,
) -> None:
    library = tmp_path / "library.tfd"
    library.write_text(
        "machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=x;}", encoding="utf-8"
    )
    entry = tmp_path / "entry.tfd"
    entry.write_text('import "library.tfd" as unused;fn f()->Int{0}', encoding="utf-8")
    result = command(entry)
    assert result.returncode == 0
    plan = json.loads(result.stdout)["machines"][0]
    assert plan["type_id"]["module"] == "library.tfd"
    assert plan["origin"]["span"]["file"] == "library.tfd"
    library.write_text(
        "machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=next.a;}", encoding="utf-8"
    )
    result = command(entry, "--diagnostic-format", "json")
    assert result.returncode == 1 and result.stdout == b""
    assert json.loads(result.stderr)["diagnostics"][0]["code"] == "E404"


def test_raw_import_error_missing_import_and_host_failures_stay_distinct(tmp_path: Path) -> None:
    entry = tmp_path / "entry.tfd"
    entry.write_text('import "bad.tfd" as bad;', encoding="utf-8")
    imported = tmp_path / "bad.tfd"
    imported.write_bytes(b"\xff")
    result = command(entry, "--diagnostic-format", "json")
    assert result.returncode == 1 and result.stdout == b""
    error = json.loads(result.stderr)["diagnostics"][0]
    assert error["code"] == "E001" and error["primary"]["span"]["source_valid"] is False
    imported.unlink()
    result = command(entry, "--diagnostic-format", "json")
    assert result.returncode == 1 and result.stdout == b""
    assert json.loads(result.stderr)["diagnostics"][0]["code"] == "E204"
    for file, args in (
        (tmp_path / "missing.tfd", ()),
        (entry, ("--root", str(ROOT))),
        (tmp_path / "wrong.txt", ()),
    ):
        result = command(file, *args, "--diagnostic-format", "json")
        assert result.returncode == 2 and result.stdout == b""
        assert "host_error" in json.loads(result.stderr)


def test_cycle_json_labels_precisely_match_actual_cycle_and_are_stable(tmp_path: Path) -> None:
    entry = tmp_path / "cycle.tfd"
    text = "machine M(x:Int)yields Int rejects Text{state a:Int=0;state b:Int=0;state z:Int=0;"
    text += "next a=next.b;next b=next.a;next z=next.a;}"
    entry.write_text(text, encoding="utf-8")
    results = [command(entry, "--diagnostic-format", "json", seed=seed) for seed in ("1", "42")]
    assert all(r.returncode == 1 and r.stdout == b"" for r in results)
    assert results[0].stderr == results[1].stderr
    error = json.loads(results[0].stderr)["diagnostics"][0]
    assert error["code"] == "E404"
    assert "a -> b -> a" in error["message"]
    labels = [error["primary"], *error["secondary"]]
    assert len(labels) == 2
    assert sorted(
        text[label["span"]["start"]["byte"] : label["span"]["end"]["byte"]] for label in labels
    ) == [
        "next.a",
        "next.b",
    ]
    assert all(label["span"]["start"]["byte"] < text.index("next z=") for label in labels)


def test_type_source_preserves_m06_boundary_and_check_adds_machine_validation(
    tmp_path: Path,
) -> None:
    entry = tmp_path / "boundary.tfd"
    entry.write_text(
        "machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=next.a;}", encoding="utf-8"
    )
    assert isinstance(type_source(entry), ValidResult)
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E404"]


def test_plan_output_pipe_failure_is_host_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ternfold.cli

    entry = tmp_path / "library.tfd"
    entry.write_text("fn f()->Int{0}", encoding="utf-8")

    def broken(*args: object) -> None:
        raise BrokenPipeError("closed plan pipe")

    monkeypatch.setattr(ternfold.cli, "_write", broken)
    assert main(["plan", str(entry)]) == 2


def test_all_examples_match_full_semantic_manifest_without_execution() -> None:
    cases = json.loads((ROOT / "examples/manifest.json").read_text(encoding="utf-8"))["cases"]
    invalid = 0
    for case in cases:
        result = command(ROOT / case["path"], "--diagnostic-format", "json")
        code = case.get("diagnostic", "")
        if code.startswith("E"):
            invalid += 1
            assert result.returncode == 1 and result.stdout == b"", (case["path"], result.stderr)
            assert code in [d["code"] for d in json.loads(result.stderr)["diagnostics"]]
        else:
            assert result.returncode == 0 and result.stderr == b"", (case["path"], result.stderr)
            assert json.loads(result.stdout)["language_execution"] is False
    assert invalid == 6
