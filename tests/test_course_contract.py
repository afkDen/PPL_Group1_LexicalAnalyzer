"""Spec/bootstrap contract only. These are not language runtime tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from course_audit import acceptance_errors, audit  # noqa: E402


def test_course_spec_markers() -> None:
    assert audit() == []


def test_course_task_dependency() -> None:
    data = json.loads((ROOT / "docs/tasks.json").read_text(encoding="utf-8"))
    tasks = {t["id"]: t for t in data["tasks"]}
    assert tasks["C00"]["status"] == "completed"
    assert "C00" in tasks["M01"]["requires"]
    assert set(tasks["M03"]["requires"]) == {"M01", "M02"}
    for task in tasks.values():
        if task["status"] in {"in_progress", "completed"}:
            assert all(tasks[required]["status"] == "completed" for required in task["requires"])


def test_course_examples_are_tracked_as_future_fixtures() -> None:
    data = json.loads((ROOT / "examples/manifest.json").read_text(encoding="utf-8"))
    course = [item for item in data["cases"] if item["path"].startswith("examples/course/")]
    assert len(course) == 3
    assert all(item["language_revision"] == 2 and item["ready_after"] == "M09" for item in course)


@pytest.mark.parametrize("state", ["implemented", "tested", "reviewed", "verified"])
def test_acceptance_claims_require_existing_evidence(tmp_path: Path, state: str) -> None:
    record: dict[str, object] = {"id": "numeric", "owner": "C01", "status": state}
    assert acceptance_errors(record, {"C01"}, tmp_path) == ["course claim lacks evidence: numeric"]
    record["evidence"] = ["missing.txt"]
    assert acceptance_errors(record, {"C01"}, tmp_path) == ["course evidence missing: missing.txt"]
    (tmp_path / "evidence.txt").write_text("Actual command evidence", encoding="utf-8")
    record["evidence"] = ["evidence.txt"]
    assert acceptance_errors(record, {"C01"}, tmp_path) == []


def test_blocked_acceptance_requires_reason_without_fabricating_progress(tmp_path: Path) -> None:
    record: dict[str, object] = {"id": "numeric", "owner": "C01", "status": "blocked"}
    assert acceptance_errors(record, {"C01"}, tmp_path) == [
        "course blocked state lacks reason: numeric"
    ]
    record["blocker"] = "Required external capability unavailable"
    assert acceptance_errors(record, {"C01"}, tmp_path) == []
    record["status"] = "approved"
    assert "course status invalid: numeric" in acceptance_errors(record, {"C01"}, tmp_path)


def test_numeric_amendment_has_an_explicit_owner_and_fixed_operator_inventory() -> None:
    ledger = json.loads((ROOT / "docs/course-acceptance.json").read_text(encoding="utf-8"))
    assert ledger["schema"] == 2
    inventory = ledger["mandatory_operator_inventory"]
    assert inventory["arithmetic"] == ["+", "-", "/", "*", "%", "div", "^"]
    assert inventory["boolean_relational"] == ["&&", "||", "!", ">", "<", "==", "!=", ">=", "<="]
    assert ledger["amendments"][0]["owner"] == "C01"
    tasks = json.loads((ROOT / "docs/tasks.json").read_text(encoding="utf-8"))["tasks"]
    assert "C01" in next(task for task in tasks if task["id"] == "M08")["requires"]


def test_separate_evidence_stages_cannot_bypass_claim_validation(tmp_path: Path) -> None:
    record: dict[str, object] = {
        "id": "numeric",
        "owner": "C01",
        "status": "specified",
        "stages": {"execution": {"status": "verified", "evidence": []}},
    }
    assert acceptance_errors(record, {"C01"}, tmp_path) == [
        "course claim lacks evidence: numeric.execution"
    ]
    record["stages"] = {"execution": {"status": "blocked"}}
    assert acceptance_errors(record, {"C01"}, tmp_path) == [
        "course blocked state lacks reason: numeric.execution"
    ]


def test_professor_operator_demo_publishes_exact_report_and_original_spans(tmp_path: Path) -> None:
    source = ROOT / "examples/course/operator_inventory.tfd"
    expected = {
        "+": "PLUS",
        "-": "MINUS",
        "/": "SLASH",
        "*": "STAR",
        "%": "PERCENT",
        "div": "DIV",
        "^": "CARET",
        "&&": "AND_AND",
        "||": "OR_OR",
        "!": "BANG",
        ">": "GREATER",
        "<": "LESS",
        "==": "EQUAL_EQUAL",
        "!=": "BANG_EQUAL",
        ">=": "GREATER_EQUAL",
        "<=": "LESS_EQUAL",
    }
    original = source.read_bytes()
    outputs: list[bytes] = []
    for seed in ("1", "42"):
        report = tmp_path / seed / "Symbol Table.txt"
        report.parent.mkdir()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ternfold",
                "tokens",
                str(source),
                "--root",
                str(ROOT),
                "--symbol-table",
                str(report),
                "--diagnostic-format",
                "json",
            ],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            check=False,
            timeout=15,
        )
        assert result.returncode == 0 and result.stderr == b"", result.stderr
        data = report.read_bytes()
        assert not data.startswith(b"\xef\xbb\xbf") and b"\r" not in data
        outputs.append(data)
        seen: set[str] = set()
        literal_categories: set[str] = set()
        for line in data.decode("utf-8").splitlines()[3:]:
            start, end, row, column, end_row, end_column, view, category, kind, lexeme, code = (
                line.split("\t")
            )
            text = json.loads(lexeme)
            assert original[int(start) : int(end)].decode("utf-8") == text
            prefix = original[: int(start)].decode("utf-8")
            assert (int(row), int(column)) == (
                prefix.count("\n") + 1,
                len(prefix.rsplit("\n", 1)[-1]) + 1,
            )
            suffix = original[: int(end)].decode("utf-8")
            assert (int(end_row), int(end_column)) == (
                suffix.count("\n") + 1,
                len(suffix.rsplit("\n", 1)[-1]) + 1,
            )
            if view == "token" and text in expected:
                assert kind == expected[text] and category == "OPERATOR" and code == ""
                seen.add(text)
            if category.endswith("_LITERAL"):
                literal_categories.add(category)
        assert seen == set(expected)
        assert {
            "INT_LITERAL",
            "FLOAT_LITERAL",
            "BOOL_LITERAL",
            "TEXT_LITERAL",
            "CHAR_LITERAL",
        } <= literal_categories
    assert outputs[0] == outputs[1]
    assert outputs[0] == (ROOT / "docs/verification/C01/Symbol Table.txt").read_bytes()
