"""Validate repository-local Antigravity agents, skills and active control documents.

This is a static/reproducible repository check. Antigravity CLI is optional; use
--require-cli when CLI installation itself is a requirement for the current host.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SKILLS = {
    "ternfold-differential",
    "ternfold-feature",
    "ternfold-orchestration",
    "ternfold-spec-audit",
}
EXPECTED_AGENTS = {
    "frontend-engineer",
    "semantics-core-engineer",
    "backend-runtime-engineer",
    "quality-engineer",
    "reviewer",
}
DOCUMENTED_TOOLS = {
    "view_file",
    "list_dir",
    "find_by_name",
    "grep_search",
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
    "run_command",
}
ACTIVE_TEXT_FILES = [
    ROOT / "MASTER_IMPLEMENTATION.md",
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "docs" / "antigravity-handoff.md",
    ROOT / "docs" / "antigravity-init-prompt.txt",
    ROOT / "docs" / "agent-orchestration.md",
    ROOT / "docs" / "agent-skills.md",
    ROOT / "docs" / "implementation-plan.md",
    *sorted((ROOT / "docs" / "tasks").glob("*.md")),
]


def frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter opener")
    try:
        header, _body = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError("missing YAML frontmatter closer") from exc
    result: dict[str, object] = {}
    current_list: str | None = None
    for raw in header.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith("  - "):
            if current_list is None:
                raise ValueError(f"list item without list field: {line}")
            value = line[4:].strip()
            assert isinstance(result[current_list], list)
            result[current_list].append(value)
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_list = None
        if not value:
            result[key] = []
            current_list = key
        elif value in {"true", "false"}:
            result[key] = value == "true"
        else:
            result[key] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-cli",
        action="store_true",
        help="fail when the Antigravity CLI executable (agy) is unavailable",
    )
    args = parser.parse_args()
    errors: list[str] = []
    notes: list[str] = []

    required = [
        ROOT / "MASTER_IMPLEMENTATION.md",
        ROOT / "AGENTS.md",
        ROOT / "docs" / "antigravity-handoff.md",
        ROOT / "docs" / "antigravity-init-prompt.txt",
        ROOT / "docs" / "agent-orchestration.md",
        ROOT / "docs" / "agent-skills.md",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"missing required control file: {path.relative_to(ROOT)}")

    skill_paths = {
        path.parent.name: path
        for path in (ROOT / ".agents" / "skills").glob("*/SKILL.md")
    }
    if set(skill_paths) != EXPECTED_SKILLS:
        errors.append(
            "workspace skills differ from expected set: "
            f"expected={sorted(EXPECTED_SKILLS)} actual={sorted(skill_paths)}"
        )
    for name, path in sorted(skill_paths.items()):
        try:
            meta = frontmatter(path)
        except ValueError as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
            continue
        if meta.get("name") != name:
            errors.append(f"{path.relative_to(ROOT)}: name does not match directory")
        if not str(meta.get("description", "")).strip():
            errors.append(f"{path.relative_to(ROOT)}: missing description")

    agent_paths = {
        path.parent.name: path for path in (ROOT / ".agents" / "agents").glob("*/agent.md")
    }
    if set(agent_paths) != EXPECTED_AGENTS:
        errors.append(
            "workspace agents differ from expected set: "
            f"expected={sorted(EXPECTED_AGENTS)} actual={sorted(agent_paths)}"
        )
    for name, path in sorted(agent_paths.items()):
        try:
            meta = frontmatter(path)
        except ValueError as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")
            continue
        if meta.get("name") != name:
            errors.append(f"{path.relative_to(ROOT)}: name does not match directory")
        if not str(meta.get("description", "")).strip():
            errors.append(f"{path.relative_to(ROOT)}: missing description")
        if meta.get("mainAgent") is not False or meta.get("subagent") is not True:
            errors.append(f"{path.relative_to(ROOT)}: must be subagent-only")
        if meta.get("model") != "inherit":
            errors.append(f"{path.relative_to(ROOT)}: model must inherit supervisor selection")
        if meta.get("commandExecutionPolicy") != "sandbox":
            errors.append(f"{path.relative_to(ROOT)}: commandExecutionPolicy must be sandbox")
        tools = meta.get("tools", [])
        if not isinstance(tools, list) or not tools:
            errors.append(f"{path.relative_to(ROOT)}: explicit tool list required")
        else:
            unknown = set(tools) - DOCUMENTED_TOOLS
            if unknown:
                errors.append(
                    f"{path.relative_to(ROOT)}: undocumented tool names {sorted(unknown)}"
                )
        skills = meta.get("skills", [])
        if not isinstance(skills, list):
            errors.append(f"{path.relative_to(ROOT)}: skills must be a list")
        else:
            for item in skills:
                if not isinstance(item, str) or not item.startswith("skills/"):
                    errors.append(f"{path.relative_to(ROOT)}: invalid skill reference {item!r}")
                    continue
                skill = item.split("/", 1)[1]
                if skill not in EXPECTED_SKILLS:
                    errors.append(f"{path.relative_to(ROOT)}: unknown skill {skill}")

    tasks_path = ROOT / "docs" / "tasks.json"
    if tasks_path.is_file():
        payload = json.loads(tasks_path.read_text(encoding="utf-8"))
        if payload.get("schema") != 2:
            errors.append("docs/tasks.json: expected schema 2 with orchestration metadata")
        for task in payload.get("tasks", []):
            route = task.get("orchestration")
            if not isinstance(route, dict):
                errors.append(f"docs/tasks.json: {task.get('id')} missing orchestration metadata")
                continue
            if route.get("agent") not in EXPECTED_AGENTS:
                errors.append(
                    f"docs/tasks.json: {task.get('id')} unknown agent {route.get('agent')}"
                )
            if route.get("effort") not in {"low", "medium", "high"}:
                errors.append(f"docs/tasks.json: {task.get('id')} invalid effort")
            if route.get("review") not in {"low", "medium", "high"}:
                errors.append(f"docs/tasks.json: {task.get('id')} invalid review effort")
            for skill in route.get("skills", []):
                if skill not in EXPECTED_SKILLS:
                    errors.append(f"docs/tasks.json: {task.get('id')} unknown skill {skill}")

    stale_terms = ("docs/codex-handoff.md", "GPT-5.6 Sol Medium", "open Codex", ".codex/")
    for path in ACTIVE_TEXT_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for term in stale_terms:
            if term in text:
                errors.append(f"{path.relative_to(ROOT)}: stale active workflow reference {term!r}")

    init_path = ROOT / "docs" / "antigravity-init-prompt.txt"
    if init_path.exists() and "MASTER_IMPLEMENTATION.md" not in init_path.read_text(encoding="utf-8"):
        errors.append(
            "docs/antigravity-init-prompt.txt must direct the supervisor to "
            "MASTER_IMPLEMENTATION.md"
        )

    agy = shutil.which("agy")
    if agy is None:
        message = "Antigravity CLI (agy) not installed; static workspace validation only"
        if args.require_cli:
            errors.append(message)
        else:
            notes.append(message)
    else:
        try:
            result = subprocess.run(
                [agy, "--version"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            detail = (result.stdout + result.stderr).strip()
            if result.returncode:
                errors.append(f"agy --version failed ({result.returncode}): {detail}")
            else:
                notes.append(f"Antigravity CLI: {detail or agy}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"agy --version could not run: {exc}")

    for note in notes:
        print(f"INFO {note}")
    for error in errors:
        print(f"ERROR {error}")
    if not errors:
        print(
            f"Validated {len(agent_paths)} Antigravity agents, {len(skill_paths)} skills, "
            "task routing and active control files"
        )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
