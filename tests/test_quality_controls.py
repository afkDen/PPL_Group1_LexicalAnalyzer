"""Quality controls remain discoverable without any remote tool or model call."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_all_quality_skills_have_bounded_instructions() -> None:
    for name in (
        "ternfold-test-design",
        "ternfold-debugging",
        "ternfold-verified-completion",
        "ternfold-lexical-conformance",
        "ternfold-native-safety",
    ):
        body = (ROOT / ".agents/skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert body.startswith(f"---\nname: {name}\n")
        assert "description:" in body
        assert len(body.strip().splitlines()) >= 15


def test_independent_auditors_are_read_only() -> None:
    for name in ("semantic-auditor", "native-safety-auditor", "reviewer"):
        data = tomllib.loads((ROOT / ".codex/agents" / f"{name}.toml").read_text(encoding="utf-8"))
        assert data["sandbox_mode"] == "read-only"
        assert (
            "do not" in data["developer_instructions"].lower()
            or "no edits" in data["developer_instructions"].lower()
        )


def test_quality_skills_are_routed_to_relevant_milestones() -> None:
    tasks = {
        t["id"]: t
        for t in json.loads((ROOT / "docs/tasks.json").read_text(encoding="utf-8"))["tasks"]
    }
    for task_id in ("M01", "M05", "M07", "M09", "M11", "M14"):
        skills = tasks[task_id]["orchestration"]["skills"]
        assert "ternfold-test-design" in skills
        assert "ternfold-verified-completion" in skills
    for task_id in ("M02", "M03", "M04"):
        assert "ternfold-lexical-conformance" in tasks[task_id]["orchestration"]["skills"]
    for task_id in ("M10", "M11", "M16"):
        assert "ternfold-native-safety" in tasks[task_id]["orchestration"]["skills"]


def test_no_external_dependencies_added() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["project"]["dependencies"] == []
    control = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))
    assert control["agents"]["enabled"] is True
    assert control["agents"]["max_concurrent_threads_per_session"] <= 3
