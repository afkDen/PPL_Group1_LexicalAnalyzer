# Phase 2 Antigravity capability verification — 2026-09-15

This records the implementation-environment research used to migrate active orchestration from Codex to Antigravity without changing Ternfold semantics.

## Primary-source findings

- Antigravity 2.0 overview and subagents: <https://antigravity.google/docs/overview>, <https://antigravity.google/docs/subagents>.
- Workspace/root rules and AGENTS.md behavior: <https://antigravity.google/docs/cli/best-practices/>.
- Workspace skills and progressive disclosure: <https://antigravity.google/docs/ide/skills/>. The workspace path is consistently `.agents/skills/`; current global-path documentation differs by Antigravity surface/migration page, so this repository does not depend on global skills.
- Workflow deprecation/migration to skills by 2026-11-01: <https://antigravity.google/docs/migration/workflows-to-skills>.
- Gemini 3.8 Flash model/thinking levels: <https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash>, <https://ai.google.dev/gemini-api/docs/thinking>.
- Antigravity model/effort selection and CLI `--effort`: <https://antigravity.google/docs/models>, <https://antigravity.google/docs/cli/headless/>.
- Custom-agent location/frontmatter/tools and asynchronous subagent workspace isolation: <https://antigravity.google/docs/subagents>.
- Official Google skill repositories considered: <https://github.com/google/skills>, <https://github.com/google-gemini/gemini-skills>.

## Decisions

Use Gemini 3.8 Flash High for the primary supervisor; repository custom agents use `model: inherit`. Keep Low/Medium/High as a routing policy because the current Markdown agent schema exposes model tier but not an explicit effort key. Use project skills instead of new legacy workflows. Keep the agent team small and compiler-specific. Do not install Google Cloud/Gemini API skill plugins because they solve a different problem and would add no value to the offline compiler.

## Local evidence and limitation

The Phase 2 container has no `agy` or Antigravity executable, so installed-version detection, `/agents` UI discovery, skill selector discovery, and live asynchronous delegation cannot be run here. `scripts/check_antigravity_workspace.py` instead validates supported repository paths, frontmatter, agent tool names, skill references, task-routing metadata, and stale active Codex references. The first real Antigravity session must confirm UI discovery; this is a development-control-plane check, not a compiler build dependency.

## Phase 2 repository verification

Observed in this preparation container after the migration:

- `python3 scripts/check_antigravity_workspace.py`: passed; 5 agents, 4 skills, task routing and active controls validated; `agy` absent, so static mode only.
- `python3 scripts/validate_skills.py`: passed; 4 workspace skills validated.
- `python3 scripts/audit_docs.py`: passed; active documentation links and all 19 task dependencies/routing references validated.
- `python3 -m compileall -q scripts tests src`: passed.
- `git diff --check`: passed.
- `PYTHONPATH=src python3 -m pytest -q --ignore=tests/test_transition_probe.py`: 7 passed, including the new Antigravity workspace tests. The property probe was excluded only because Hypothesis is unavailable in the container's system Python.
- `python3 scripts/bootstrap.py`: attempted and failed while resolving the pinned development environment because this container cannot resolve `files.pythonhosted.org`; the failure occurred before project dependencies were installed.
- `python3 scripts/bootstrap.py --offline`: also cannot complete because the uploaded source archive intentionally excludes its populated uv cache.
- `.venv/bin/python scripts/check_environment.py`: correctly reports the missing pinned Python tools/package after the failed bootstrap while still passing Python, uv, GCC/C17, skill validation and Antigravity static workspace validation.

This is an environment/network limitation, not a waived quality gate. On a machine with normal package access, run the canonical bootstrap and full checks before M01.
