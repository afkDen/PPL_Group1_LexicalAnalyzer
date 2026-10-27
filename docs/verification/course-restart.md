# 2026-10-15 course-aligned restart verification

This report covers **specification/bootstrap** checks only, not a functioning Ternfold compiler.

- Source archive: original Antigravity Phase-2 foundation, rather than partial later M01–M06 workspace from a different session.
- Formal design revision: Ternfold 0.2, ADR 0009, with retained immutable machine/scheduling/guard semantics.
- Proposal: `docs/proposal/Ternfold_Proposal_Revised.pdf` has original 11 pages unchanged and eight illustrated amendment pages. Original PDF page stream equality was checked programmatically.
- `python scripts/course_audit.py`: PASS (25 requirements mapped and initially marked **specified**, not executable).
- `python scripts/audit_docs.py`: PASS (20 task briefs/dependency graph and active documentation links).
- `python scripts/check_antigravity_workspace.py`: PASS static setup (5 agent definitions, 4 skills); Antigravity app/subagent live invocation not tested in this environment.
- `python scripts/validate_skills.py`: PASS (4 skills).
- `python -m compileall -q src scripts tests experiments`: PASS.
- `PYTHONPATH=src:. python -m pytest tests/test_course_contract.py tests/test_agent_workspace.py tests/test_foundation.py -q`: 10 passed.
- `git diff --check`: PASS.
- `python scripts/bootstrap.py --offline`: FAILED because the fresh source archive contains no cached pinned coverage wheel, and this environment has no PyPI network access. Fresh online bootstrap and full pinned Ruff/mypy/Hypothesis/pytest/build checks are **not verified here**. The installed uv executable in this container is 0.10.0; pinned 0.12.11 must be installed in a connected host for full reproducibility.
- Native C17 execution is a distinct requirement from Python frontend development; new `--phase frontend|native` environment check distinguishes deferred native tools from passed native checks. This contract was statically inspected but **not tested on a Windows host**.
- No lexer/parser/type/interpreter/native backend from milestones M01–M14 was claimed implemented. M01 remains next.

When the supervisor begins on its actual host: (1) run `python scripts/bootstrap.py`, (2) run the venv Python's `scripts/dev.py check`, (3) record actual results and errors in `docs/progress.md`, (4) implement M01 and proceed through roadmap, (5) update `docs/course-acceptance.json` only with real test evidence.
