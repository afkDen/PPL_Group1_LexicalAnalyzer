# Codex / ChatGPT Work migration evidence — 2026-10-15

This is a **development-control-plane conversion** of the Ternfold 0.2 restart scaffold, not implementation of a compiler milestone. Verified source normative specs, grammar, type model, Core, runtime, ADR 0009, course requirements/acceptance ledger, revised proposal PDF, and `uv.lock` were all **byte-identical** to the incoming course ZIP. No M01–M06 implementation was imported. `docs/tasks.json` keeps M00 and C00 complete and M01 pending.

## Official Codex conventions used

- Repository instruction discovery: <https://developers.openai.com/codex/guides/agents-md> (`AGENTS.md`).
- Project-scoped custom agents: <https://developers.openai.com/codex/multi-agent> (`.codex/agents/*.toml`).
- Project skills: <https://developers.openai.com/codex/skills> (`.agents/skills/*/SKILL.md`).
- Project local config: <https://developers.openai.com/codex/config-advanced> (`.codex/config.toml`).

No model is hard-coded. Agent roles are bounded and reviewer is read-only. `max_concurrent_threads_per_session = 3`. These are **static configuration facts**, not proof the user's selected Codex/ChatGPT surface has live subagent tools enabled. ChatGPT conversation alone has no automatic local repository access; use Codex or repository-capable Work for actual builds/tests.

## Checks actually executed in this container

- `python scripts/check_codex_workspace.py`: **PASS**, 5 project agents / 4 project skills / task-routing controls; `codex` CLI not installed (static validation only).
- `python scripts/validate_skills.py`: **PASS**, 4 checked-in skills.
- `python scripts/audit_docs.py`: **PASS**, 20 tasks and relative local links.
- `python scripts/course_audit.py`: **PASS**, static 0.2 specification crosswalk only (no language runtime evidence).
- `python -m compileall -q scripts src tests`: **PASS**.
- `PYTHONPATH=src python -m pytest -q --ignore=tests/test_transition_probe.py`: **10 passed** (Hypothesis-dependent probe intentionally unavailable in system Python; not counted as full suite).
- `python scripts/bootstrap.py --offline`: **FAIL**, missing `coverage==7.16.0` wheel in this container's uv cache, network disabled. No claim of full pinned Ruff/mypy/Hypothesis/build success. A connected machine must run normal bootstrap and full `scripts/dev.py check`.

## What remains unverified

Live Codex/ChatGPT agent discovery, subagent delegation, cloud workspace integration, and full locked environment verification were not possible in this container. Actual Ternfold tokens/parser/type/run/native build and course pass remain pending respective implementation milestones. Missing C17 toolchain is a native-only blocker if not installed; frontend phases may proceed with explicit deferred status.

## Recheck in this ChatGPT environment (October 15, 2026)

- `python scripts/check_codex_workspace.py`: **PASS** (5 TOML agents / 4 skills); no installed Codex CLI in this container, so native agent discovery/delegation is not live-verified.
- `python scripts/validate_skills.py`: **PASS**.
- `python scripts/course_audit.py`: **PASS** (static crosswalk only).
- `python scripts/audit_docs.py`: **PASS** (20 tasks).
- `python -m compileall -q src scripts tests`: **PASS**.
- `PYTHONPATH=src python -m pytest -q tests/test_agent_workspace.py tests/test_foundation.py tests/test_course_contract.py`: **10 passed**.
- Full test run including `tests/test_transition_probe.py`: **BLOCKED** because Hypothesis is absent.
- `uv sync --locked --offline`: **BLOCKED** because the local uv is 0.10.0 with no cached managed Python 3.12/development wheels. No successful full pinned bootstrap/Ruff/mypy/build/native verification is claimed.
- `.codex/config.toml` keys and `.codex/agents` schema were cross-checked against current official Codex config and Subagents reference. Live Codex and ChatGPT Work environment tests remain for the receiving machine/session.
- `docs/what-codex-builds.md` now explicitly separates available scaffold from planned M01–M14/advanced implementation.
