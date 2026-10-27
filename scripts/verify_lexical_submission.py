"""Extract the actual ZIP outside checkout, create a pip-free venv, follow README."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    archive = ROOT / "output" / "Ternfold_Lexical_Analyzer_Submission.zip"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="ternfold-standalone-extracted-") as temporary:
        base = Path(temporary).resolve()
        if base.is_relative_to(ROOT.resolve()):
            raise RuntimeError("fresh verification must be outside the compiler checkout")
        extracted = base / "submission"
        with zipfile.ZipFile(archive) as zipped:
            for name in zipped.namelist():
                path = (extracted / name).resolve()
                if not path.is_relative_to(extracted.resolve()):
                    raise RuntimeError("archive path escapes extraction root")
            zipped.extractall(extracted)
        venv.EnvBuilder(with_pip=False).create(base / "environment")
        python = base / "environment" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        report = extracted / "Symbol Table.txt"
        report.unlink()  # Require a genuinely new file, not the bundled demonstration.
        commands = [
            [str(python), "-S", "analyzer.py", "examples/complete.tfd"],
            [str(python), "-S", "-m", "unittest", "discover", "-s", "tests", "-v"],
        ]
        for command in commands:
            result = subprocess.run(
                command, cwd=extracted, env=env, capture_output=True, check=False, timeout=90
            )
            if result.returncode:
                print(result.stderr.decode("utf-8", "replace"))
                return result.returncode
            print(result.stdout.decode("utf-8", "replace"))
            print(result.stderr.decode("utf-8", "replace"))
        assert report.read_bytes() == (extracted / "expected/complete.tfd.txt").read_bytes()
        probe = subprocess.run(
            [
                str(python),
                "-S",
                "-c",
                "import sys,ternfold; from pathlib import Path; "
                "assert Path(ternfold.__file__).resolve().is_relative_to(Path.cwd()); "
                "blocked=('ternfold.analysis','ternfold.core'); "
                "assert not any(n.startswith(blocked) for n in sys.modules)",
            ],
            cwd=extracted,
            env=env,
            capture_output=True,
            check=True,
            timeout=15,
        )
        assert probe.stderr == b""
        # The Windows classroom launcher is independently exercised too.
        launcher_tested = False
        if os.name == "nt":
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "run_lexer.bat"],
                cwd=extracted,
                env=env,
                capture_output=True,
                check=False,
                timeout=30,
            )
            if result.returncode:
                print(result.stderr.decode("utf-8", "replace"))
                return result.returncode
            assert report.read_bytes() == (extracted / "expected/complete.tfd.txt").read_bytes()
            launcher_tested = True
        evidence = {
            "zip": archive.name,
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "bytes": archive.stat().st_size,
            "fresh_extraction_outside_checkout": True,
            "fresh_environment": "venv without pip, Python -S; PYTHONPATH/PYTHONHOME removed",
            "readme_commands_passed": True,
            "new_report_equals_expected": True,
            "windows_launcher_passed": launcher_tested,
            "posix_launcher_executed": False,
            "python": sys.version.split()[0],
            "platform": sys.platform,
        }
        target = ROOT / "docs/verification/lexical-submission-2026-10-28.json"
        target.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
