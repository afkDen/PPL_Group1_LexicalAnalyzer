# Verification evidence — architecture foundation

Observed on 2026-09-13. The [environment report](environment.json) records actual package/version commands, both CLI entrypoints and a C17 compile/run. It contains sanitized project paths. The [architecture review](architecture-review.md) records independent skill use and corrections.

| Command/check | Observed result | Scope/limit |
|---|---|---|
| `python3 scripts/bootstrap.py` | Passed; locked package installed into isolated environment | First install can download dev dependencies |
| `python3 scripts/bootstrap.py --offline` | Passed; 20 lock packages resolved, 19 installed packages checked | Reuses populated cache; not a fresh air-gapped machine |
| `scripts/check_environment.py` via project Python | All 23 recorded checks passed | Tool/CLI/C17 probe availability, not compiler semantics |
| `scripts/dev.py check` via project Python | Ruff lint/format passed; strict mypy passed on 13 source files; 11 pytest tests passed | Bootstrap + narrow semantic probe |
| `scripts/audit_docs.py` | Passed; 19 task dependencies and local Markdown targets checked | Does not parse Ternfold source or prove grammar consistency |
| `scripts/dev.py build` | Built sdist and wheel | Status CLI package; native runtime not implemented |
| `scripts/smoke_wheel.py` | Wheel installed offline in separate temporary environment; module/console entrypoints passed outside checkout | No source-path dependency for current CLI |
| `coverage run -m pytest`, `coverage report` | 11 passed; production scaffold coverage 78% | Subprocess coverage is not merged; no claim about absent compiler phases |
| Skill Creator validators and project validator | Both skills valid | Metadata/structure, plus independent review use |
| Dependency artifact hosts | pypi.org and files.pythonhosted.org | No private package mirror required |

No Clang, full native language runtime, sanitizers, Codex UI discovery, source execution, or external skill fetch is claimed verified. Native sanitizer/runtime tests begin in M10. No system tool installation or remote publication occurred.


Phase 2 Antigravity capability/configuration research and local verification limits are recorded in [antigravity-phase2.md](antigravity-phase2.md). Historical Codex-discovery limitations above remain evidence about the Phase 1 environment, not active workflow guidance.
The fresh-archive Phase 2 environment probe is preserved as [`environment-phase2.json`](environment-phase2.json); it intentionally records missing pinned Python tooling after bootstrap was blocked by unavailable PyPI DNS, while C17 and repository customization checks pass.
