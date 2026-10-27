# Codex / ChatGPT handoff — Ternfold 0.2 implementation

## Purpose and state

This is **the active implementation handoff**. Ternfold `.tfd` is a pure statically typed language whose immutable machines **propose together, validate in order, publish together**. Frozen Ternfold 0.2 contracts: `docs/language-spec.md`, `docs/grammar.md`, `docs/type-system.md`, `docs/core-ir.md`, `docs/runtime.md`, `docs/decisions/0009.md` and `docs/course-requirements.md`. First 0.1 proposal is historical; its course amendment is appended in `docs/proposal/Ternfold_Proposal_Revised.pdf`.

**M00 + C00, M01–M07 and C01 frontend amendments are accepted; M08 is active.**
The CLI supports tokens, ast, full-frontend check and machine plan JSON, with
finite Float/real division frontend and closed constants. C01 final gate passed
1,155 tests, Ruff, mypy56/all audits and corrected isolated offline wheel checks.
All16 lexical report and eleven-item evidence audit exist; historical milestones
remain regression gates. Core/source execution/native parity are not yet present.

## Numerical and recovery context

Accepted ADR 0010 controls seven arithmetic `+ - / * % div ^` and nine
logical/relational `&& || ! > < == != >= <=` required counts. Real `/` returns
finite binary64 Float for any numeric pair; other mixing is strict, Float^Int is
explicit. Read exact literal/recovery/conversion/rounding/fault/formatter rules.
C01 is verified frontend/constants only; future M09–M11 own actual executor
parity. Literal map holds unsigned canonical Float64 values with separate signs;
constructors reject forged foreign/nonfinite payloads. Decimal conversion uses
600-digit chunks and works under supported PYTHONINTMAXSTRDIGITS=640.

The context refresh on 2026-10-28 removed owner Kant and semantic auditor
Chandrasekhar (confirmed not_found). Their files/handoffs/reviews are preserved.
Replacement spawn failed agent thread limit, not an invented review. Meitner
remains active read-only and independently closed the final bounded fixes.
Supervisor is now sole code writer; reconcile capabilities before delegation.
No Git metadata exists; do not create/invent history/worktrees or restart phases.

Schema-2 course ledger distinguishes specified/implemented/tested/reviewed/
verified/blocked, validates nested stage evidence, and keeps runtime parity
specified separately. Sidechat read-only lexical audit is complete with no
further assignment. Windows Python3.14.4 is the only tested host; cached Clang
C17 probe passes but no Ternfold native executor exists.

## Stage 1 requirements — delivered (2026-10-28)

Completed human-authorized Stage 1 temporarily superseded M08 to produce verified
Ternfold_Lexical_Analyzer_Submission.zip and update supplied repository
https://github.com/afkDen/PPL_Group1_LexicalAnalyzer.git when access permits.
Preserve all full-project source/history/config; resume M08 afterward. Core
nodes.py/verify.py/lower.py and tests/test_core.py are correct partial work,
not accepted; lower.py has seven mypy issues and no execution path. No competing
writer is active; reviewer Meitner is read-only. Do not restart or discard work.

New mandatory professor restrictions: actual character DFA/trie transitions for
identifiers AND keywords/reserved/noise, no regex tokenization/generator or
completed-word KEYWORDS.get/spelling-set matching. Existing lexer/report paths
need a targeted correction. Reuse one scanner. Classroom Symbol Table.txt must
have exactly two principal columns TOKEN TYPE and LEXEME, comments/invalid rows
in source order; preserve rich internal APIs separately. Stage1 must run offline
with Python stdlib, independent of analysis/Core/native/AI/dev dependencies.
Package minimal source/support/launchers/README/valid-invalid examples/expected
report/runnable tests/DFA+eleven-item evidence. Exclude orchestration/config,
full-compiler docs/caches/venv/toolchains from submission only. Preserve notices
and truthful limitations; no invented authorship/identity.

Inspect latest printed proposal and normative inventories. Verify all11 items,
all7+9 operators, boundaries/errors/report bytes, strict recognition audit.
Extract ZIP fresh outside checkout, follow README, generate NEW exact report and
run included tests before claiming readiness. Inspect target GitHub files/history
before changes, no forcepush/reset, preserve compiler repository and report any
actual access blocker. Final delivery needs ZIP link, commands/tests/review,
11-item matrix, GitHub status and reminder for physical INDEX CARD/latest proposal.

## Latest packaging scope clarification

Human explicitly excludes unnecessary class/checklist/evidence documents from
both ZIP and lexical GitHub repository. Bundle only runnable source/local modules,
launchers, concise technical README, representative valid/invalid examples,
actual Symbol Table.txt, expected test reports and executable tests/config.
Keep all mandatory audits/review/evidence/course tracking in this development
repository. No compliance/DFA/proposal-crosswalk/review-report documents or
TEST_RESULTS metadata in the submission; explain DFA briefly in README/code.
Preserve actual legal notices, without inventing license/attribution. Rebuild,
re-extract and review the final minimal content before publishing.

## Stage 1 completed; resume Stage 2

S01 accepted/delivered/published. Final ZIP output/Ternfold_Lexical_Analyzer_Submission.zip
is33828bytes/20files, SHA256b2ec3219c83340f5edceed4f4a0c54078618f2dccf6ad9af208de16bd8f78131.
Strict trie/numeric DFA, actual two-column report and minimal stdlib slice pass
fresh extraction/newreport/11tests/Windowslauncher plus independent Meitner review.
GitHub main389030efe8e852b319fe87ea2fd243d58cac1859 has exactly20matchingblobhashes.
No extras/checklists/class reports in ZIP or remote; evidence stays mainrepo.
M08 active again. Earlier priority paragraphs are recovery history, not unfinished
Stage1. PartialCore nodes/verify/lower and28tests preserved; lowerer's mypy issues
fixed but complete lowering still unverified. Supervisor solewriter, Meitner
read-only. I/Omainentry-only was explicitly approved by human and implemented
with12regressions (resolutionplusentry92pass). Full1195tests/Ruff/mypy65/audits
passed; this doesnotacceptM08. Next run all validexamples through lower, fix
real defects, completeCoreCLI/dumps/verifiernegativecases andindependentreview.

## Latest Stage 2 state — M09 active

M08 accepted after1244full/77focused tests, Ruff/mypy68/audits, independent
Highreview closure, installedCorewheel andexactarchivebytes. All16validfixtures
lowerverified; Core hasnoAST/planner runtimeaccess. Allreviewfindingsclosed,
see M08verification+hashes. CurrentCLI nexttaskM09; check/plan/compile_source/core
are available, runisnot. Preserve reviewedlexicalZIP/remote20files unchanged.

M09 coherentpartial: execution/values.py immutabletaggedvalues,limits,faults,
executionresult anditerativeequality;tests/test_values.py15pass+mypy2pass. No
interpreter orruncommand yet. Supervisorsolewriter, Meitnerread-only; replacements
previouslyhittoolthreadlimit. Reconcilecapabilities beforedelegating. NextreadM09/
runtime/std/Core, implementprimitivebuiltins+explicitcontrol/callstackdispatcher,
thenmainIOatomicity/faultspans/limits/sourceexamplesandindependentreview.
Do notmarkM09completefromvaluerecordtests orCoreverification.

## Start/resume

1. Read `MASTER_IMPLEMENTATION.md`, `AGENTS.md`, this handoff, `docs/progress.md` and `docs/tasks.json`.
2. Inspect git/worktrees (when a Git checkout exists), current files, active task and actual test evidence before trusting old descriptions. The source ZIP excludes `.git`, so do not claim an existing history or worktrees in a fresh extraction.
3. Read the owning `docs/tasks/Mxx.md`, relevant normative specs/ADRs; run `python scripts/bootstrap.py` when needed. Use Python from `.venv/Scripts/python.exe` (Windows) or `.venv/bin/python` (POSIX).
4. Run `<venv-python> scripts/check_codex_workspace.py` and `<venv-python> scripts/dev.py check`; use `check_environment.py --phase frontend`, upgrading to `--phase native` at native milestones.
5. **Implement, not approval-plan**. Delegate bounded substantial work to `.codex/agents/` when supported, use `$ternfold-*` project skills where helpful, review independently, test and update progress.

## Architecture and task gates

Pipeline: Source snapshots → lexing → surface AST → module resolution → type/pattern checker → dependency scheduler → verified structured Core → reference interpreter or C17 runtime/backend. Main output is staged; faults cannot leak any published output. Python is the compiler host; output executable uses C17 runtime/ABI. `docs/implementation-plan.md` and individual task briefs define real acceptance, phases and dependencies. `M03` owns lexical DFAs, four lexical constant kinds and `Symbol Table.txt`; `M04` owns new syntax; `M06–M09` handle types/execution; `M10–M11` native parity; `M14` final course ledger conformance.

The native C compiler may be absent for M01–M09 (record **deferred**, not pass). It becomes mandatory for M10–M11 and final project verification. Course audit only validates static requirements mapping; no language feature is complete until executable tests and review support it.

## Agents, skills and effort

Codex project custom-agent TOML: `.codex/agents/` (seven roles). Project skills: `.agents/skills/` (nine). Native multi-agent support and per-spawn effort are product-dependent: use supported tools where available; otherwise implement/review serially and disclose the fallback. Do not pin a model unavailable to the user's account. Low is mechanical; Medium bounded code; High type/machine/Core/backend/milestone correctness. Reviewer is read-only. Avoid overlapping implementation of a shared compiler semantic contract.

## Interruptions, permission and quality

On 2026-10-27 the human user explicitly authorized necessary project dependency
and build-tool setup, including installing a supported native C17 compiler
(GCC/Clang) and suitable bootstrap integration. Proceed autonomously within that
scope; do not ask again for routine dependency installation. Actual sandbox or
administrator requirements still apply and must be reported if unavoidable.
This authorization persists across milestones and interrupted sessions.
Native setup is now verified: project-local LLVM-MinGW Clang23.1.4, real C17
compile/run, and offline bootstrap --install-native passed. See
[native setup evidence](verification/native-bootstrap-2026-10-27.md).
Earlier missing-GCC notes are historical; cached Clang is auto-discovered.

No separate user approval required for ordinary roadmap implementation. If interrupted, inspect git/partial files/worktrees/delegations, last test output and remaining task acceptance criteria; preserve correct work and resume, do not redo or mark prematurely complete. Never do unsafe/destructive operations without approval, fabricate tests/reviews, or silently change semantic design. New observable language behavior requires normative docs/tests and ADR procedure. Progress and acceptance ledger are persistent memory.

**Current next action:** resume M09 from the coherent values slice above,
without restarting M08 or touching delivered Stage1. No source executor exists
until the explicit-stack Core interpreter is implemented and verified. Preserve
real division/Float rules, immutable snapshots, scheduler faultorder, guards and
atomic staged output. Use exact result/fault/stdout observations and independent
hand-derived fixtures. Native differential work remains M10/M11. Supervisor
implements; reviewer stays read-only, no invented delegation.

## Quality-control additions (2026-10-27)

The repository now provides **7 custom Codex agents** and **9 focused project skills**. Two new read-only auditor agents (`semantic-auditor`, `native-safety-auditor`) check semantics and C ABI ownership separately from implementers. Five new repo-local skills improve test design, debugging, fresh completion evidence, lexical course conformance and native memory safety. Public GitHub inspiration and decisions are documented in `docs/github-skills-research.md`. This updates agent procedures and task routing only; the source-of-truth language design, output artifacts, dependency graph and starting M01 remain unchanged. Full environment quality gates still require installed pinned dev packages; static configuration checks alone never count as compiler evidence.
