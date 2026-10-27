"""Verify tools by actually invoking them, importing the package and compiling C17."""

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from native_tools import discover_compiler

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="also write JSON report to this path")
    parser.add_argument("--cc", help="compiler override; default: project cache, GCC or Clang")
    parser.add_argument(
        "--phase",
        choices=["frontend", "native"],
        default="frontend",
        help="frontend defers native C17 failures; native requires C17 compile/run",
    )
    args = parser.parse_args()
    checks: list[dict[str, object]] = []

    def record(name: str, ok: bool, detail: str, *, native_only: bool = False) -> None:
        status = (
            "pass" if ok else "deferred" if native_only and args.phase == "frontend" else "fail"
        )
        checks.append({"name": name, "ok": status == "pass", "status": status, "detail": detail})

    record("python", (3, 12) <= sys.version_info[:2] < (3, 15), sys.version.splitlines()[0])
    record(
        "virtual_environment",
        sys.prefix != sys.base_prefix,
        sys.prefix.replace(str(ROOT), "<project>"),
    )
    versions = {
        "pytest": "9.1.1",
        "ruff": "0.16.7",
        "mypy": "2.3.1",
        "hypothesis": "6.168.0",
        "coverage": "7.16.0",
        "build": "1.6.1",
        "setuptools": "84.0.0",
    }
    for package, expected in versions.items():
        try:
            installed = importlib.metadata.version(package)
            record(package, installed == expected, installed)
        except importlib.metadata.PackageNotFoundError:
            record(package, False, "not installed; run scripts/bootstrap.py")

    def command(name: str, argv: list[str], *, native_only: bool = False) -> None:
        try:
            result = subprocess.run(
                argv, cwd=ROOT, capture_output=True, text=True, check=False, timeout=30
            )
            record(
                name,
                result.returncode == 0,
                (result.stdout + result.stderr).strip().replace(str(ROOT), "<project>")[:3000],
                native_only=native_only,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            record(name, False, str(error).replace(str(ROOT), "<project>"), native_only=native_only)

    for module in ["pytest", "ruff", "mypy", "coverage", "build"]:
        command(f"{module}_command", [sys.executable, "-m", module, "--version"])
    command(
        "package_import", [sys.executable, "-c", "import ternfold; print(ternfold.__version__)"]
    )
    command("cli_module", [sys.executable, "-m", "ternfold", "status"])
    entry = Path(sys.executable).parent / ("ternfold.exe" if os.name == "nt" else "ternfold")
    command("cli_entrypoint", [str(entry), "--version"])
    uv = shutil.which("uv")
    if uv is None and os.name == "nt":
        home = Path.home()
        candidates = [
            home / ".local" / "bin" / "uv.exe",
            home / ".cargo" / "bin" / "uv.exe",
            home
            / "AppData"
            / "Roaming"
            / "Python"
            / f"Python{sys.version_info.major}{sys.version_info.minor}"
            / "Scripts"
            / "uv.exe",
        ]
        uv = next((str(candidate) for candidate in candidates if candidate.is_file()), None)
    command("uv", [uv or "uv", "--version"])
    command("git", ["git", "--version"])
    compiler = discover_compiler(ROOT, args.cc)
    if compiler is None:
        record(
            "c17_compile_run",
            False,
            f"missing {args.cc or 'GCC/Clang'}; see docs/environment.md",
            native_only=True,
        )
    else:
        command("c_compiler_version", [compiler, "--version"], native_only=True)
        with tempfile.TemporaryDirectory(prefix="ternfold-probe-", dir=ROOT) as temporary:
            probe = Path(temporary)
            source = probe / "probe.c"
            executable = probe / ("probe.exe" if os.name == "nt" else "probe")
            source.write_text(
                "#include <stdint.h>\n#include <stdio.h>\n"
                '_Static_assert(sizeof(int64_t) == 8, "int64_t required");\n'
                "int main(void) { int64_t a = -7, b = 3; "
                "if (a / b != -2 || a % b != -1) return 1; "
                'puts("C17 arithmetic probe passed"); return 0; }\n',
                encoding="utf-8",
            )
            before = len(checks)
            command(
                "c17_compile",
                [
                    compiler,
                    "-std=c17",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-pedantic",
                    str(source),
                    "-o",
                    str(executable),
                ],
                native_only=True,
            )
            if checks[before]["ok"]:
                command("c17_run", [str(executable)], native_only=True)
    command("skill_validation", [sys.executable, "scripts/validate_skills.py"])
    command(
        "codex_workspace",
        [sys.executable, "scripts/check_codex_workspace.py"],
    )
    command("course_contract", [sys.executable, "scripts/course_audit.py"])
    ok = all(check["status"] != "fail" for check in checks)
    payload = {"schema": 2, "phase": args.phase, "ok": ok, "checks": checks}
    output = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    for check in checks:
        print(f"{str(check['status']).upper()} {check['name']}: {check['detail']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
