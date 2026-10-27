"""Statically validate Codex repository agents, skills, routing and active docs.

Use --require-cli only to require local Codex CLI. Static validation does not
establish that a cloud or ChatGPT session can discover or spawn project agents.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = {
    "frontend-engineer",
    "semantics-core-engineer",
    "backend-runtime-engineer",
    "quality-engineer",
    "reviewer",
    "semantic-auditor",
    "native-safety-auditor",
}
SKILLS = {
    "ternfold-debugging",
    "ternfold-differential",
    "ternfold-feature",
    "ternfold-lexical-conformance",
    "ternfold-native-safety",
    "ternfold-orchestration",
    "ternfold-spec-audit",
    "ternfold-test-design",
    "ternfold-verified-completion",
}


def skill_frontmatter(path: Path) -> dict[str, str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n") or "\n---\n" not in raw[4:]:
        raise ValueError("invalid skill YAML header")
    header = raw[4:].split("\n---\n", 1)[0]
    result: dict[str, str] = {}
    for line in header.splitlines():
        if ":" in line:
            name, val = line.split(":", 1)
            result[name.strip()] = val.strip().strip("\"'")
    return result


def check() -> list[str]:
    errors: list[str] = []
    for rel in (
        "AGENTS.md",
        "MASTER_IMPLEMENTATION.md",
        "docs/codex-handoff.md",
        "docs/codex-init-prompt.txt",
        "docs/agent-orchestration.md",
        "docs/agent-skills.md",
        ".codex/config.toml",
    ):
        if not (ROOT / rel).is_file():
            errors.append(f"missing {rel}")
    config_path = ROOT / ".codex/config.toml"
    if config_path.exists():
        try:
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
            ag = config.get("agents", {})
            if ag.get("enabled") is not True:
                errors.append(".codex/config.toml: agents.enabled must be true")
            cap = ag.get("max_concurrent_threads_per_session")
            if not isinstance(cap, int) or not 1 <= cap <= 3:
                errors.append(".codex/config.toml: choose 1..3 concurrent subagents")
            if "model" in config or "model" in ag:
                errors.append("do not hard-pin model availability in project config")
        except (tomllib.TOMLDecodeError, ValueError) as exc:
            errors.append(f".codex/config.toml: {exc}")
    agents = {p.stem: p for p in (ROOT / ".codex/agents").glob("*.toml")}
    if set(agents) != AGENTS:
        errors.append(f"Codex agents expected {sorted(AGENTS)}, got {sorted(agents)}")
    for name, path in agents.items():
        try:
            obj = tomllib.loads(path.read_text(encoding="utf-8"))
            for field in ("name", "description", "developer_instructions"):
                if not isinstance(obj.get(field), str) or not obj[field].strip():
                    errors.append(f"{path.name}: missing {field}")
            if obj.get("name") != name:
                errors.append(f"{path.name}: mismatched name")
            if "model" in obj:
                errors.append(f"{path.name}: model ID must remain client-selectable")
            if "model_reasoning_effort" in obj and obj["model_reasoning_effort"] not in (
                "low",
                "medium",
                "high",
            ):
                errors.append(f"{path.name}: invalid model_reasoning_effort")
            if (
                name in {"reviewer", "semantic-auditor", "native-safety-auditor"}
                and obj.get("sandbox_mode") != "read-only"
            ):
                errors.append(f"{name} must be read-only")
        except (tomllib.TOMLDecodeError, ValueError) as exc:
            errors.append(f"{path.name}: invalid TOML: {exc}")
    skills = {p.parent.name: p for p in (ROOT / ".agents/skills").glob("*/SKILL.md")}
    if set(skills) != SKILLS:
        errors.append(f"Codex skills expected {sorted(SKILLS)}, got {sorted(skills)}")
    for name, path in skills.items():
        try:
            data = skill_frontmatter(path)
            if data.get("name") != name or not data.get("description"):
                errors.append(f"{name}: invalid frontmatter name/description")
        except ValueError as exc:
            errors.append(f"{name}: {exc}")
    task_path = ROOT / "docs/tasks.json"
    if task_path.exists():
        payload = json.loads(task_path.read_text(encoding="utf-8"))
        if payload.get("schema") != 2 or payload.get("language_revision") != 2:
            errors.append("task graph schema/language revision mismatch")
        statuses: dict[str, str] = {}
        for task in payload["tasks"]:
            name = task["id"]
            statuses[name] = task["status"]
            route = task.get("orchestration", {})
            if route.get("agent") not in AGENTS:
                errors.append(f"{name}: invalid agent")
            for key in ("effort", "review"):
                if route.get(key) not in ("low", "medium", "high"):
                    errors.append(f"{name}: invalid {key}")
            if not set(route.get("skills", [])) <= SKILLS:
                errors.append(f"{name}: invalid skills")
            if not (ROOT / task["brief"]).is_file():
                errors.append(f"{name}: missing brief")
        if statuses.get("M00") != "completed" or statuses.get("C00") != "completed":
            errors.append("M00/C00 must remain completed on restart")
    for rel in (
        "README.md",
        "AGENTS.md",
        "MASTER_IMPLEMENTATION.md",
        "docs/implementation-plan.md",
        "docs/codex-handoff.md",
        "docs/agent-orchestration.md",
    ):
        p = ROOT / rel
        if not p.is_file():
            continue
        body = p.read_text(encoding="utf-8")
        for old in (
            "docs/antigravity-handoff.md",
            "scripts/check_antigravity_workspace.py",
            ".agents/agents/",
        ):
            if old in body:
                errors.append(f"{rel}: obsolete active reference to {old}")
    init = ROOT / "docs/codex-init-prompt.txt"
    if init.exists() and "MASTER_IMPLEMENTATION.md" not in init.read_text(encoding="utf-8"):
        errors.append("codex-init-prompt.txt must reference MASTER_IMPLEMENTATION.md")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-cli", action="store_true")
    args = parser.parse_args()
    errors = check()
    binary = shutil.which("codex")
    if binary:
        try:
            result = subprocess.run(
                [binary, "--version"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
            )
            if result.returncode:
                errors.append(f"codex --version failed: {result.stderr.strip()}")
            else:
                print(f"INFO Codex CLI: {result.stdout.strip()}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"Codex CLI could not be queried: {exc}")
    elif args.require_cli:
        errors.append("Codex CLI not found")
    else:
        print("INFO Codex CLI not available; validating repository configuration only")
    for error in errors:
        print(f"ERROR {error}")
    if not errors:
        print(
            f"Validated {len(AGENTS)} Codex agents, {len(SKILLS)} project skills, "
            "task routing and active docs"
        )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
