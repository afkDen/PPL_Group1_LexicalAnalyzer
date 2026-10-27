from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_codex_control_files_exist() -> None:
    for item in (
        "MASTER_IMPLEMENTATION.md",
        "docs/codex-handoff.md",
        "docs/codex-init-prompt.txt",
        ".codex/config.toml",
        "docs/agent-orchestration.md",
        "docs/agent-skills.md",
    ):
        assert (ROOT / item).is_file(), item


def test_task_routing_references_codex_agents_and_skills() -> None:
    data = json.loads((ROOT / "docs/tasks.json").read_text(encoding="utf-8"))
    agents = {
        tomllib.loads(path.read_text(encoding="utf-8"))["name"]
        for path in (ROOT / ".codex/agents").glob("*.toml")
    }
    skills = {path.parent.name for path in (ROOT / ".agents/skills").glob("*/SKILL.md")}
    assert data["schema"] == 2
    for task in data["tasks"]:
        route = task["orchestration"]
        assert route["agent"] in agents
        assert route["effort"] in {"low", "medium", "high"}
        assert route["review"] in {"low", "medium", "high"}
        assert set(route["skills"]) <= skills


def test_phase1_codex_handoff_is_distinct_from_current() -> None:
    assert (ROOT / "docs/archive/phase1-codex-handoff.md").is_file()
    assert (ROOT / "docs/codex-handoff.md").is_file()
    assert "Ternfold 0.2" in (ROOT / "docs/codex-handoff.md").read_text(encoding="utf-8")
