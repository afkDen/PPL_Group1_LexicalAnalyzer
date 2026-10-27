# Ternfold 0.2 — C17 implementation control

## Execution policy

Read AGENTS.md, docs/codex-handoff.md, docs/progress.md, docs/tasks.json,
docs/implementation-plan.md and the earliest eligible task brief. Reconcile Git,
source, tests and active worker handoffs before restarting anything. Continue
ordinary authorized work autonomously; do not introduce another approval plan.
The authoritative C17 migration directive supersedes the former Python workflow.

## Target and delivery order

ISO C17 owns the complete frontend, semantics, Core, interpreter, backend,
runtime and native developer tools. First deliver an independently buildable
C lexical analyzer. Then resume the canonical compiler roadmap. Preserve all
M00–M17/X01 identities, responsibilities, dependencies and acceptance intent,
plus C00/C01/S01. C-MIGRATION-01 is a narrow migration/delivery task, not a
replacement roadmap. M15–M17/X01 remain optional after M14 and never block class.
Historical Python passes do not complete C milestones. ADR 0011 records the change.

## Canonical gates

Windows: `./scripts/build.ps1 environment`, `./scripts/build.ps1 check`,
`./scripts/build.ps1 sanitize`. POSIX intended equivalents use
`sh scripts/build.sh environment|check|sanitize`. Verify actual toolchain/platform
support before claiming it. Compiler/interpreter commands must remain explicitly
unavailable until implemented. No Python packaging, virtualenv or hosted API is
an active build dependency. Packaging uses scripts/package.ps1 and verification
uses scripts/verify-archives.ps1; run clean extracted builds before acceptance.

## Semantics and quality

Normative language/specification documents and ADRs define behavior; migration
changes implementation only. Preserve source spans, diagnostics, static typing,
old versus candidate reads, dependency collection, ASCII ready ordering,
all candidates before ordered guards, first failure, typed rejection and atomic
publication with private delayed emissions. Execute only verified Core once it
exists. I/O-bearing root main is entry-only (E208); pure main remains callable.
ADR 0010 defines finite binary64 real division and checked Int arithmetic.

Use project orchestration/feature/test-design skills. Delegate bounded substantial
work to configured specialists when available. Keep one writer per shared
contract; parallel writers require disjoint worktrees. Independent reviewer is
read-only. Native ownership and UB require native-safety review; semantic changes
require spec audit; dual executors require differential tests when runnable.
Run strict warnings, native tests, failure injection, repository/course audits,
sanitisers and independent review. Record actual commands, outcomes and limits.
Do not mark a task complete from a happy path or static metadata alone.

## Recovery and safety

Inspect existing partial work after quota interruptions; never restart accepted
work. Preserve historical branches, proposals and useful behavioral fixtures.
Never invent Git identity, force-push, hide failures or publish without authority.
The user authorized this C17 foundation's publication to the existing repository;
inspect remote changes and preserve history first. No credentials in artifacts.
Progress, task graph, verification records and handoff must permit offline resumption.
