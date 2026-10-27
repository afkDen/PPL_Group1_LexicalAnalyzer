"""Check local Markdown targets and example/task manifests without compiling Ternfold."""

import json
import re
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    for document in [
        root / "README.md",
        root / "AGENTS.md",
        root / "MASTER_IMPLEMENTATION.md",
        *sorted(
            path
            for path in (root / "docs").rglob("*.md")
            if "archive" not in path.relative_to(root / "docs").parts
        ),
        *sorted((root / ".agents" / "skills").rglob("*.md")),
    ]:
        for target in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if target.startswith(("https://", "http://", "#")):
                continue
            if not (document.parent / target.split("#", 1)[0]).exists():
                errors.append(f"{document.relative_to(root)}: missing {target}")
    task_payload = json.loads((root / "docs/tasks.json").read_text(encoding="utf-8"))
    if task_payload.get("schema") != 2:
        errors.append("tasks.json: expected schema 2")
    tasks = task_payload["tasks"]
    ids = {task["id"] for task in tasks}
    agents = {path.stem for path in (root / ".codex/agents").glob("*.toml")}
    skills = {path.parent.name for path in (root / ".agents/skills").glob("*/SKILL.md")}
    completed: set[str] = set()
    for task in tasks:
        if not set(task["requires"]) <= completed:
            errors.append(f"{task['id']}: dependencies missing or out of topological order")
        if not (root / task["brief"]).exists():
            errors.append(f"{task['id']}: missing task brief")
        route = task.get("orchestration", {})
        if route.get("agent") not in agents:
            errors.append(f"{task['id']}: unknown orchestration agent {route.get('agent')}")
        if route.get("effort") not in {"low", "medium", "high"}:
            errors.append(f"{task['id']}: invalid orchestration effort")
        if route.get("review") not in {"low", "medium", "high"}:
            errors.append(f"{task['id']}: invalid review effort")
        if not set(route.get("skills", [])) <= skills:
            errors.append(f"{task['id']}: orchestration references missing skill")
        completed.add(task["id"])
    if len(ids) != len(tasks):
        errors.append("duplicate task IDs")
    for error in errors:
        print(error)
    if not errors:
        print(f"Documentation targets and {len(tasks)} task dependencies passed")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
