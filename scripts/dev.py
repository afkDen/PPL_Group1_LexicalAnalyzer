"""Canonical quality commands; exits nonzero on the first failed gate."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["check", "test", "lint", "types", "format", "build", "course"]
    )
    args = parser.parse_args()
    commands = {
        "test": [[sys.executable, "-m", "pytest"]],
        "lint": [
            [sys.executable, "-m", "ruff", "check", "."],
            [sys.executable, "-m", "ruff", "format", "--check", "."],
        ],
        "types": [[sys.executable, "-m", "mypy"]],
        "format": [[sys.executable, "-m", "ruff", "format", "."]],
        "build": [[sys.executable, "-m", "build", "--no-isolation"]],
        "course": [
            [sys.executable, "scripts/course_audit.py"],
            [sys.executable, "scripts/audit_docs.py"],
            [sys.executable, "scripts/check_codex_workspace.py"],
        ],
    }
    selected = ["lint", "types", "test", "course"] if args.command == "check" else [args.command]
    for group in selected:
        for command in commands[group]:
            result = subprocess.run(command, cwd=ROOT, check=False)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
