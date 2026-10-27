"""Package only the shared standard-library lexical analyzer and class materials."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "Ternfold_Lexical_Analyzer_Submission.zip"


def main() -> int:
    OUTPUT.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lexical-package-") as temporary:
        stage = Path(temporary)
        support = ROOT / "submission" / "lexical"
        for name in ("README.md", "analyzer.py", "run_lexer.bat", "run_lexer.sh"):
            shutil.copy2(support / name, stage / name)
        for directory in ("examples", "tests", "expected"):
            shutil.copytree(support / directory, stage / directory)
        frontend = stage / "ternfold" / "frontend"
        frontend.mkdir(parents=True)
        source = ROOT / "src" / "ternfold"
        for filename in [
            "__init__.py",
            "source.py",
            "tokens.py",
            "lexer.py",
            "diagnostics.py",
            "render.py",
            "lexical_report.py",
            "classroom_report.py",
        ]:
            shutil.copy2(source / "frontend" / filename, frontend / filename)
        shutil.copy2(source / "lexical_cli.py", stage / "ternfold" / "lexical_cli.py")
        (stage / "ternfold" / "__init__.py").write_text(
            '"""Ternfold standalone lexical analyzer."""\n', encoding="utf-8"
        )
        for filename in ("complete.tfd", "invalid.tfd"):
            generated = subprocess.run(
                [sys.executable, "-B", "-S", "analyzer.py", "examples/" + filename],
                cwd=stage,
                capture_output=True,
                check=False,
                timeout=15,
            )
            expected = 0 if filename == "complete.tfd" else 1
            if generated.returncode != expected:
                raise RuntimeError(generated.stderr.decode("utf-8", "replace"))
            shutil.copy2(stage / "Symbol Table.txt", stage / "expected" / (filename + ".txt"))
        shutil.copy2(stage / "expected" / "complete.tfd.txt", stage / "Symbol Table.txt")
        test_code = (
            "import unittest,json,sys; "
            "suite=unittest.defaultTestLoader.discover('tests'); "
            "r=unittest.TextTestRunner(verbosity=2).run(suite); "
            "print(json.dumps({'tests':r.testsRun,'failures':len(r.failures),"
            "'errors':len(r.errors),'skipped':len(r.skipped)})); "
            "sys.exit(not r.wasSuccessful())"
        )
        tested = subprocess.run(
            [sys.executable, "-B", "-S", "-c", test_code],
            cwd=stage,
            capture_output=True,
            check=False,
            timeout=90,
        )
        print(tested.stderr.decode("utf-8", "replace"))
        if tested.returncode:
            return tested.returncode
        evidence = json.loads(tested.stdout)
        evidence.update(
            {
                "command": "python -S -m unittest discover -s tests -v",
                "python": sys.version.split()[0],
                "platform": sys.platform,
                "scope": "Standalone lexical package; stdlib only, offline",
            }
        )
        (ROOT / "docs/verification/lexical-build-tests-2026-10-28.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        staged_zip = OUTPUT.with_suffix(".tmp")
        with zipfile.ZipFile(staged_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob("*")):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                relative = path.relative_to(stage).as_posix()
                info = zipfile.ZipInfo(relative, (2026, 10, 28, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100755 if path.suffix == ".sh" else 0o100644) << 16
                archive.writestr(info, path.read_bytes())
        staged_zip.replace(OUTPUT)
    print(f"Created {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
