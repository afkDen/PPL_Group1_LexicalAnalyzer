# Development environment and reproducibility

Supported initial host: Linux or macOS, Python >=3.12,<3.15; tested here on Linux with Python 3.12.14, uv 0.12.11 and GCC 13.3.0. Clang was not available and was not claimed tested. The compiler package has zero Python runtime dependencies; only development/testing uses third-party packages.

## Canonical setup

```sh
python3 scripts/bootstrap.py
.venv/bin/python scripts/check_environment.py
.venv/bin/python scripts/dev.py check
```

Bootstrap uses an isolated `.venv`, a project-local `.uv-cache`, and `uv sync --locked`. It does not install machine-wide packages, edit shell startup files, create credentials or contact language runtime services. Optional `--install-native` downloads a hash-pinned portable Windows x64 Clang into the same project cache and runs the C17 gate. It fails clearly if Python/uv is missing or a required verification fails. Running it again is safe. Dependencies are exact direct pins in pyproject.toml, transitive resolution and artifact hashes in uv.lock. To intentionally update them, change the manifest, run `UV_CACHE_DIR=.uv-cache uv lock`, inspect the lock diff and run all gates; never hand-edit the lock.

On this Windows host, native setup is now verified with Clang 23.1.4 from the
official LLVM-MinGW 20261020 UCRT x64 archive. Use
`python scripts/bootstrap.py --install-native` for a fresh project-local setup,
or add `--offline` after the archive/install is cached. `--native` requires a
working compiler without downloading one; `--cc PATH` selects an explicit
executable. Environment checks automatically discover the cached Clang before
PATH GCC/Clang. No administrator or persistent PATH change was required. See
[setup evidence](verification/native-bootstrap-2026-10-27.md). Runtime/backend
milestones and sanitizer gates remain pending.

Verified direct tools: pytest 9.1.1, Ruff 0.16.7, mypy 2.3.1, Hypothesis 6.168.0, coverage 7.16.0, build 1.6.1, setuptools 84.0.0. Ruff combines lint/format; mypy checks strict types; Hypothesis targets source/graph/execution invariants; coverage locates untested paths. No general fuzzing framework is needed at foundation; bounded Hypothesis strategies and subprocess harnesses cover the first valuable cases.

## Missing prerequisite installation

Use the official [Python download/setup documentation](https://www.python.org/downloads/) for a supported interpreter. For uv, the official [installation guide](https://docs.astral.sh/uv/getting-started/installation/) supports pip installation; this project's reproducible command is `python3 -m pip install --user uv==0.12.11` in an environment whose package policy permits it. Bootstrap deliberately reports missing uv instead of changing your machine globally.

Native code requires GCC >=12 or Clang >=16 with C17 and exact int64_t. See [GCC installation documentation](https://gcc.gnu.org/install/) and [Clang getting started](https://clang.llvm.org/get_started.html). On Debian/Ubuntu, an administrator can install the distribution's `build-essential` package (`sudo apt-get update`, then `sudo apt-get install build-essential`); on macOS, Apple's Command Line Tools are installed through `xcode-select --install`. These system installation commands were **not run** here because GCC was already present. Verify the version, then compile/run the actual C17 probe through `check_environment.py --cc gcc` or `--cc clang`; a version string alone is insufficient.


## Codex / ChatGPT development control validation

Codex is a development assistant, not a Ternfold build/runtime dependency. Project instructions live in `AGENTS.md` and `MASTER_IMPLEMENTATION.md`, custom Codex agents in `.codex/agents/`, and project skills in `.agents/skills/`. Validate repository configuration with:

```sh
python scripts/check_codex_workspace.py
```

The checker uses standard-library `tomllib`, verifies role/skill/task references, and reports whether the optional `codex` executable is available; use `--require-cli` only when you specifically expect to use Codex CLI. Static validation **does not prove** live agents/spawns or ChatGPT Work access. In a Codex session explicitly verify custom agent/skill discovery; absent native delegation use sequential work and disclose it. See `docs/codex-handoff.md`.

## Offline use

After a successful initial bootstrap:

```sh
python3 scripts/bootstrap.py --offline
.venv/bin/python scripts/dev.py check
.venv/bin/python scripts/dev.py build
.venv/bin/python scripts/smoke_wheel.py
```

The build command uses `python -m build --no-isolation` against pinned installed setuptools. No dependency resolution occurs during language compilation or execution. An entirely fresh offline machine requires a previously populated uv cache or an independently prepared wheelhouse for its Python/platform. The deliverable source archive intentionally excludes third-party binary caches and virtual environments; it is reproducible source, not an air-gapped binary SDK. Native executables will not require Python after M11.

## What verification establishes

`check_environment.py` invokes pytest, Ruff, mypy, coverage and build version commands, checks direct package versions, imports the package, exercises both module/console CLI entrypoints, validates skill structure, and compiles/runs a real C17 signed-division probe. It fails if any check fails. This proves tool availability and basic native compilation; **it does not prove the future C runtime/backend is implemented or memory-safe**.

`dev.py check` adds actual formatting/lint/type checks and tests; `dev.py build` builds sdist/wheel. The handoff evidence also includes an installed-wheel status command in a separate temporary environment. Native sanitizers are specified for M10; the initial probe is not a sanitizer/runtime conformance claim. See `docs/verification/` for observed results and limitations.

## Research-backed configuration

Configuration was checked against [Ruff configuration](https://docs.astral.sh/ruff/configuration/), [mypy configuration](https://mypy.readthedocs.io/en/stable/config_file.html), [Hypothesis documentation](https://hypothesis.readthedocs.io/en/latest/), [uv lock/sync](https://docs.astral.sh/uv/concepts/projects/sync/) and [Python venv](https://docs.python.org/3/library/venv.html). Those documents inform tooling setup, not Ternfold semantics.


## Course restart: Windows and staged C17 verification (2026-10-15)

The **Python/frontend phases M01–M09 do not require GCC/Clang**. Use `python scripts/bootstrap.py` (or `python scripts/bootstrap.py --offline` after packages are cached); it detects a Windows user-level `uv.exe` in `~/.local/bin`, `~/.cargo/bin` or `%APPDATA%/Python/PythonXY/Scripts` if the executable is not on PATH. After sync it runs `check_environment.py --phase frontend`: a missing native C compiler is reported as **DEFERRED**, not as passed or a blocker to Python work. Native phases M10–M11 and release checks must pass `python scripts/bootstrap.py --native` or `.venv\Scripts\python.exe scripts/check_environment.py --phase native` on Windows (POSIX uses `.venv/bin/python`). The native probe compiles and runs a C17 executable, including `probe.exe` on Windows.

`python scripts/dev.py check` includes static course-requirements and documentation/workspace integrity audits in addition to Ruff/mypy/pytest. Course audit is only a consistency/mapping gate; true runtime features need M03–M14 tests. Python >=3.12,<3.15, uv 0.12.11 and locked dev wheels remain prerequisites; first-time download requires package access. No external AI API is needed to build/run the compiler.
