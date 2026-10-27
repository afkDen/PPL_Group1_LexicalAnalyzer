"""Audit *specified* course requirement mapping; never claim compiler feature readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_STATES = frozenset(
    {"specified", "implemented", "tested", "reviewed", "verified", "blocked"}
)


def acceptance_errors(requirement: dict[str, object], owners: set[str], root: Path) -> list[str]:
    """Validate evidence metadata; never infer execution from a declared state."""
    errors: list[str] = []
    identifier = requirement.get("id")
    if requirement.get("owner") not in owners:
        errors.append(f"course owner unknown: {identifier}")
    state = requirement.get("status")
    if state not in ACCEPTANCE_STATES:
        errors.append(f"course status invalid: {identifier}")
    evidence = requirement.get("evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(path, str) for path in evidence):
        errors.append(f"course evidence invalid: {identifier}")
        return errors
    if state in {"implemented", "tested", "reviewed", "verified"} and not evidence:
        errors.append(f"course claim lacks evidence: {identifier}")
    if state == "blocked" and not requirement.get("blocker"):
        errors.append(f"course blocked state lacks reason: {identifier}")
    for rel in evidence:
        if not (root / rel).exists():
            errors.append(f"course evidence missing: {rel}")
    stages = requirement.get("stages", {})
    if not isinstance(stages, dict):
        errors.append(f"course stages invalid: {identifier}")
    else:
        for name, stage in stages.items():
            if not isinstance(name, str) or not isinstance(stage, dict):
                errors.append(f"course stage invalid: {identifier}")
                continue
            errors.extend(
                acceptance_errors(
                    {**stage, "id": f"{identifier}.{name}", "owner": requirement.get("owner")},
                    owners,
                    root,
                )
            )
    return errors


NEEDED = {
    "docs/language-spec.md": [
        "for item",
        "R006",
        "Char",
        "div",
        "Symbol Table.txt",
        "from stdin",
        "to stdout",
        "^",
    ],
    "docs/grammar.md": [
        "for-expression",
        "main-block",
        "CHAR",
        "power",
        "input-clause",
        "output-clause",
    ],
    "docs/automata.md": ["DFA", "COMMENT_BLOCK", "E102", "E104", "CHAR_LITERAL"],
    "docs/course-requirements.md": [
        "Finite automata",
        "Nested loop",
        "Four constant types",
        "Symbol Table.txt",
    ],
    "docs/decisions/0009.md": ["accepted", "machine", "Char"],
    "docs/runtime.md": ["R006", "R005", "snapshot"],
    "examples/course/main_io.tfd": ["input visitor", "output", "for row", "for col", "^", "div"],
}


def audit() -> list[str]:
    errors: list[str] = []
    for rel, tokens in NEEDED.items():
        p = ROOT / rel
        if not p.is_file():
            errors.append(f"missing {rel}")
            continue
        txt = p.read_text(encoding="utf-8")
        for token in tokens:
            if token.casefold() not in txt.casefold():
                errors.append(f"{rel}: missing normative course marker {token!r}")
    tasks = json.loads((ROOT / "docs/tasks.json").read_text(encoding="utf-8"))
    ledger = json.loads((ROOT / "docs/course-acceptance.json").read_text(encoding="utf-8"))
    if ledger.get("schema") not in {1, 2}:
        errors.append("course-acceptance.json: expected schema 1 or 2")
    owners = {t["id"] for t in tasks["tasks"]}
    entries = ledger.get("requirements", [])
    required_ids = {
        "intro",
        "sigma",
        "identifiers",
        "arithmetic",
        "relational",
        "logical",
        "words",
        "automata",
        "noise",
        "comments",
        "spaces",
        "delimiters",
        "format",
        "constants",
        "precedence",
        "input",
        "output",
        "assignment",
        "conditionals",
        "single_loop",
        "nested_loop",
        "extension",
        "invalid",
        "symbol_table",
        "native",
    }
    if {e.get("id") for e in entries} != required_ids or len(entries) != len(required_ids):
        errors.append("course acceptance ledger: missing/duplicate requirement IDs")
    for requirement in entries:
        errors.extend(acceptance_errors(requirement, owners, ROOT))
    for amendment in ledger.get("amendments", []):
        errors.extend(acceptance_errors(amendment, owners, ROOT))
    for tid in ["C00", "M03", "M04", "M06", "M08", "M09", "M11", "M14"]:
        if tid not in [item["id"] for item in tasks["tasks"]]:
            errors.append(f"tasks.json: missing owner {tid}")
    if not errors and tasks.get("target", "").find("0.2") < 0:
        errors.append("tasks.json: target is not 0.2")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print machine-readable result")
    opts = parser.parse_args()
    issues = audit()
    result = {
        "schema": 1,
        "scope": "static specification mapping only",
        "status": "pass" if not issues else "fail",
        "language_implemented": False,
        "issues": issues,
    }
    if opts.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            "PASS" if not issues else "FAIL",
            "course specification mapping (NOT executable implementation)",
        )
        for issue in issues:
            print(" -", issue)
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
