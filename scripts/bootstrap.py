"""Idempotent project-local setup. Requires Python 3.12–3.14 and uv 0.12.11."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from native_tools import install_native


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline", action="store_true", help="use only previously cached packages"
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help="also require a verified native C17 compiler (needed for M10/M11)",
    )
    parser.add_argument(
        "--install-native",
        action="store_true",
        help="install pinned project-local Windows x64 Clang and verify C17",
    )
    parser.add_argument("--cc", help="single compiler executable name/path override")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not (3, 12) <= sys.version_info[:2] < (3, 15):
        print("Need Python >=3.12,<3.15", file=sys.stderr)
        return 1
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
    if uv is None:
        print(
            "Missing uv. Install with: python3 -m pip install --user uv==0.12.11", file=sys.stderr
        )
        return 1
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(root / ".uv-cache")
    temporary = root / ".uv-cache" / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(temporary)
    command = [uv, "sync", "--locked", "--python", sys.executable]
    if args.offline:
        command.append("--offline")
    result = subprocess.run(command, cwd=root, env=env, check=False)
    if result.returncode:
        return result.returncode
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if args.install_native:
        try:
            compiler = install_native(root, offline=args.offline)
            print(f"Project-local native compiler: {compiler}", flush=True)
        except (OSError, ValueError) as error:
            print(f"Native setup failed: {error}", file=sys.stderr)
            return 1
    verification = [
        str(python),
        "scripts/check_environment.py",
        "--phase",
        "native" if args.native or args.install_native else "frontend",
    ]
    if args.cc is not None:
        verification.extend(["--cc", args.cc])
    return subprocess.run(
        verification,
        cwd=root,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
