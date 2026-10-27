# Frontend environment recovery — 2026-10-27

The extracted workspace has no `.git` metadata. Git executable availability is
verified separately; branches, diffs and worktrees are unavailable. Existing
source contains the status CLI and scaffold tests, with no imported M01–M06 work.

`python scripts/bootstrap.py` initially failed fetching locked wheels because
the sandbox denied network sockets (Windows error 10013). A permitted network
retry succeeded: Python 3.14.4, all seven pinned development dependencies, and
the editable project installed. The installed uv is 0.12.19; `uv.lock` was used
with `--locked` and was not edited.

`.venv/Scripts/python.exe scripts/check_environment.py --phase frontend --output
docs/verification/environment-2026-10-27.json` passed all frontend checks. GCC
is absent: native C17 verification is **deferred**, not passed, and remains
mandatory at M10/M11. The JSON report contains exact installed versions.

## Baseline repairs

The first canonical gate exposed existing scaffold defects that earlier
dependency-limited sessions could not check:

- Ruff traversed the generated `.uv-cache` because this extraction has no Git
  repository to activate ignore handling. `pyproject.toml` now explicitly excludes
  that download cache and historical `docs/archive` Python. Maintained code
  remains covered by the same lint rules.
- Ruff import/format fixes were applied to `scripts/bootstrap.py`,
  `scripts/check_codex_workspace.py`, `scripts/check_environment.py`,
  `scripts/course_audit.py`, `scripts/dev.py`, `tests/test_agent_workspace.py`,
  `tests/test_course_contract.py`, and `tests/test_quality_controls.py`.
- `tests/test_foundation.py` compared platform-dependent backslash paths against
  a portable manifest. `.as_posix()` now preserves the exact set comparison on
  Windows; the manifest is read explicitly as UTF-8.

After these repairs, `.venv/Scripts/python.exe scripts/dev.py check` passed:
Ruff lint/format, strict mypy (18 files), **21 tests**, static course mapping,
documentation targets (20 tasks), and seven-agent/nine-skill workspace checks.
This baseline is tooling evidence, not evidence that any language program runs.

`python scripts/bootstrap.py --offline` then passed using the populated cache.
`.venv/Scripts/python.exe scripts/dev.py build` built sdist and wheel, and
`.venv/Scripts/python.exe scripts/smoke_wheel.py` installed that wheel offline
and passed module/console entrypoint checks outside the source checkout.

An independent read-only reviewer was requested for these gate repairs; its
result is recorded with the owning implementation task when accepted.
