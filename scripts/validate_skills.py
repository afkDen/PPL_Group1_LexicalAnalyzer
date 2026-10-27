"""Validate Ternfold's repository-local Codex skill bundles."""

from pathlib import Path

EXPECTED = {
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


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    skills = sorted((root / ".agents/skills").glob("*/SKILL.md"))
    errors: list[str] = []
    actual = {path.parent.name for path in skills}
    if actual != EXPECTED:
        errors.append(f"expected project skills {sorted(EXPECTED)}, found {sorted(actual)}")
    for path in skills:
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) != 3 or parts[0].strip():
            errors.append(f"{path}: invalid frontmatter delimiters")
            continue
        fields = dict(line.split(":", 1) for line in parts[1].strip().splitlines() if ":" in line)
        if fields.get("name", "").strip() != path.parent.name:
            errors.append(f"{path}: name does not match directory")
        if not fields.get("description", "").strip():
            errors.append(f"{path}: missing description")
        if "TODO" in text or "[TODO" in text:
            errors.append(f"{path}: unfinished scaffold")
    for error in errors:
        print(error)
    if not errors:
        print(f"Validated {len(skills)} Codex workspace skills")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
