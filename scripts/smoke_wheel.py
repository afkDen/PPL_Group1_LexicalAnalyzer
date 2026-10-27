"""Install the built wheel offline in isolation and exercise its real entry point."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    wheels = sorted((root / "dist").glob("ternfold_lang-*.whl"))
    if len(wheels) != 1:
        print("Build exactly one current wheel with scripts/dev.py build first.")
        return 1
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["UV_CACHE_DIR"] = str(root / ".uv-cache")
    with tempfile.TemporaryDirectory(prefix="ternfold-wheel-") as directory:
        temporary = Path(directory)
        env["TMPDIR"] = directory
        virtual = temporary / "environment"
        subprocess.run(
            ["uv", "venv", "--offline", "--python", sys.executable, str(virtual)],
            cwd=temporary,
            env=env,
            check=True,
        )
        python = virtual / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--offline",
                "--no-deps",
                "--python",
                str(python),
                str(wheels[0]),
            ],
            cwd=temporary,
            env=env,
            check=True,
        )
        result = subprocess.run(
            [str(python), "-I", "-m", "ternfold", "status"],
            cwd=temporary,
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        status = json.loads(result.stdout)
        if status["language_execution"] is not False:
            raise AssertionError(
                "Update wheel smoke contract when language execution is implemented"
            )
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                "import sys, ternfold; from pathlib import Path; "
                "origin = Path(ternfold.__file__).resolve(); "
                "assert origin.is_relative_to(Path(sys.prefix).resolve())",
            ],
            cwd=temporary,
            env=env,
            check=True,
            timeout=10,
        )
        executable = python.parent / ("ternfold.exe" if os.name == "nt" else "ternfold")
        subprocess.run(
            [str(executable), "--version"], cwd=temporary, env=env, check=True, timeout=10
        )
        source = temporary / "sample.tfd"
        source.write_text(
            "pub fn main() -> List[Text] { let c: Char = 'ñ'; [\"hé\"] }\n",
            encoding="utf-8",
        )
        report = temporary / "Symbol Table.txt"
        inspected = subprocess.run(
            [
                str(python),
                "-I",
                "-m",
                "ternfold",
                "tokens",
                str(source),
                "--symbol-table",
                str(report),
            ],
            cwd=temporary,
            env=env,
            capture_output=True,
            check=True,
            timeout=10,
        )
        tokens = json.loads(inspected.stdout)["tokens"]
        assert tokens[-1]["kind"] == "EOF"
        assert any(token["kind"] == "CHAR" and token["value"] == "ñ" for token in tokens)
        assert any(token["kind"] == "TEXT" and token["value"] == "hé" for token in tokens)
        assert "CHAR_LITERAL" in report.read_text(encoding="utf-8")
        parsed = subprocess.run(
            [str(python), "-I", "-m", "ternfold", "ast", str(source)],
            cwd=temporary,
            env=env,
            capture_output=True,
            check=True,
            timeout=10,
        )
        tree = json.loads(parsed.stdout)
        assert tree["has_errors"] is False
        assert tree["program"]["declarations"][0]["node_type"] == "FunctionDecl"
        source.write_bytes(b"fn broken()->Int {}")
        recovered = subprocess.run(
            [str(executable), "ast", str(source), "--diagnostic-format", "json"],
            cwd=temporary,
            env=env,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert recovered.returncode == 1
        assert json.loads(recovered.stdout)["has_errors"] is True
        assert json.loads(recovered.stderr)["diagnostics"][0]["code"] == "E110"
        library = temporary / "library.tfd"
        library.write_text("pub record Item {} fn hidden()->Int{0}", encoding="utf-8")
        source.write_text(
            'import "library.tfd" as lib; fn f()->Int{let item=lib::Item();0}',
            encoding="utf-8",
        )
        resolved = subprocess.run(
            [str(python), "-I", "-m", "ternfold", "check", str(source)],
            cwd=temporary,
            env=env,
            capture_output=True,
            check=True,
            timeout=10,
        )
        # Library roots need no main even after check advances through M06 typing.
        assert resolved.stdout == resolved.stderr == b""
        source.write_text("fn f()->Int{true}", encoding="utf-8")
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                "import sys; from ternfold.driver import resolve_source; "
                "from ternfold.frontend.diagnostics import ValidResult; "
                "assert isinstance(resolve_source(sys.argv[1]), ValidResult)",
                str(source),
            ],
            cwd=temporary,
            env=env,
            check=True,
            timeout=10,
        )
        mismatch = subprocess.run(
            [str(executable), "check", str(source), "--diagnostic-format", "json"],
            cwd=temporary,
            env=env,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert mismatch.returncode == 1 and mismatch.stdout == b""
        assert json.loads(mismatch.stderr)["diagnostics"][0]["code"] == "E302"
        source.write_text(
            "machine Real(request:Float)yields Float rejects Text{"
            "state value:Float=7/2;next value=value/request;emit next.value;}"
            "fn f()->Text{float_text(1.25e1)}",
            encoding="utf-8",
        )
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                "import sys; from ternfold.driver import type_source; "
                "from ternfold.frontend.diagnostics import ValidResult; "
                "from ternfold.analysis.numeric import Float64, float_text; "
                "r=type_source(sys.argv[1]); assert isinstance(r, ValidResult); "
                "c=next(iter(r.value.constants.values())); "
                "assert isinstance(c.scalar, Float64) and c.scalar.bits==0x400c000000000000; "
                "assert float_text(c.scalar)=='3.5e0'",
                str(source),
            ],
            cwd=temporary,
            env=env,
            check=True,
            timeout=10,
        )
        real = subprocess.run(
            [str(executable), "check", str(source)],
            cwd=temporary,
            env=env,
            capture_output=True,
            check=True,
            timeout=10,
        )
        assert real.stdout == real.stderr == b""
        source.write_text("fn f()->Float{1e999}", encoding="utf-8")
        overflow = subprocess.run(
            [str(executable), "check", str(source), "--diagnostic-format", "json"],
            cwd=temporary,
            env=env,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert overflow.returncode == 1 and overflow.stdout == b""
        assert json.loads(overflow.stderr)["diagnostics"][0]["code"] == "E301"
        source.write_text(
            "machine M(request:Int)yields Int rejects Text{"
            "state a:Int=0;state b:Int=0;"
            "next a=next.b+1;next b=request;"
            'guard next.a>0 else "negative";emit next.a;}',
            encoding="utf-8",
        )
        planned = subprocess.run(
            [str(executable), "plan", str(source)],
            cwd=temporary,
            env=env,
            capture_output=True,
            check=True,
            timeout=10,
        )
        plan = json.loads(planned.stdout)
        assert plan["schema_version"] == 1 and plan["language_execution"] is False
        machine = plan["machines"][0]
        assert [cell["name"] for cell in machine["schedule"]] == ["b", "a"]
        assert machine["dependencies"][0]["source"]["name"] == "b"
        assert len(machine["guards"]) == len(machine["emissions"]) == 1
        assert machine["origin"]["span"]["file"] == "sample.tfd"
        assert planned.stderr == b"" and b"\r\n" not in planned.stdout
        lowered = subprocess.run(
            [str(executable), "core", str(source)],
            cwd=temporary,
            env=env,
            capture_output=True,
            check=True,
            timeout=10,
        )
        verified = json.loads(lowered.stdout)
        assert verified["phase"] == "verified-core" and verified["language_execution"] is False
        functions = verified["program"]["functions"]
        assert any(fn["kind"] == "step" for fn in functions)
        assert all(fn["origin"]["span"]["file"] == "sample.tfd" for fn in functions)
        assert lowered.stderr == b"" and b"\r\n" not in lowered.stdout
        source.write_text(
            "machine M(request:Int)yields Int rejects Text{"
            "state a:Int=0;state b:Int=0;next a=request;}",
            encoding="utf-8",
        )
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                "import sys; from ternfold.driver import type_source; "
                "from ternfold.frontend.diagnostics import ValidResult; "
                "assert isinstance(type_source(sys.argv[1]), ValidResult)",
                str(source),
            ],
            cwd=temporary,
            env=env,
            check=True,
            timeout=10,
        )
        for command in ("check", "plan"):
            missing = subprocess.run(
                [str(executable), command, str(source), "--diagnostic-format", "json"],
                cwd=temporary,
                env=env,
                capture_output=True,
                check=False,
                timeout=10,
            )
            assert missing.returncode == 1 and missing.stdout == b""
            assert json.loads(missing.stderr)["diagnostics"][0]["code"] == "E401"
        source.write_text(
            'import "library.tfd" as lib; fn f()->Int{lib::hidden()}', encoding="utf-8"
        )
        private = subprocess.run(
            [str(executable), "check", str(source), "--diagnostic-format", "json"],
            cwd=temporary,
            env=env,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert private.returncode == 1 and private.stdout == b""
        assert json.loads(private.stderr)["diagnostics"][0]["code"] == "E206"
        source.write_bytes(b"@")
        rejected = subprocess.run(
            [str(executable), "tokens", str(source), "--diagnostic-format", "json"],
            cwd=temporary,
            env=env,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert rejected.returncode == 1
        assert json.loads(rejected.stderr)["diagnostics"][0]["code"] == "E101"
    print(
        "Installed-wheel entrypoints, reports, AST, phase APIs, plans and diagnostics "
        "passed outside checkout"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
