---
name: ternfold-orchestration
description: Route Ternfold roadmap work between direct implementation and Codex subagents, choose reasoning effort, parallelism, skills, and review. Use at task selection, delegation, retry, or milestone boundaries.
---

# Ternfold orchestration

Read `MASTER_IMPLEMENTATION.md`, `docs/progress.md`, `docs/tasks.json`, and the candidate task brief. Do not redesign language semantics while routing work.

1. Reconcile actual repository evidence with task status. Pick the earliest eligible incomplete task unless a recorded blocker makes an independent task preferable.
2. Classify the work: mechanical/low consequence -> Low; bounded engineering with stable contracts -> Medium; semantic, architectural, cross-phase, ambiguous, difficult to verify, or expensive to repair -> High. Prefer High when uncertain on important compiler work.
3. Decide direct versus delegated execution. Delegate only when the task is bounded, specialization helps, review independence matters, or parallel work is genuinely disjoint. Keep one owner for shared syntax, type, Core, ABI, module, or source contracts.
4. For delegated work, include: task ID; objective; requested reasoning; owning documents/ADRs; files/interfaces; invariants; prohibited redesign; required tests; acceptance criteria; verification commands; and handoff format. Require the worker to report files changed, tests added, commands/results, unresolved issues, and architectural concerns.
5. Prefer `inherit` workspace for read-only research/review and single-owner implementation. Use an isolated branch/worktree for parallel write tasks, then let the supervisor review and integrate. Never let two agents edit the same semantic contract concurrently.
6. Require an independent reviewer for semantic or architecture-sensitive tasks and at milestone gates. Use `ternfold-spec-audit` when cross-layer consistency matters and `ternfold-differential` once executable parity or C ownership is in scope.
7. On failure: diagnose once, retry only if the approach remains sound, increase reasoning, route to a specialist/reviewer, then escalate to the High-thinking supervisor. Ask the user only for authorization or a genuinely unresolved high-impact choice.
8. Accept work only after the owning task's checks pass and `docs/progress.md` plus `docs/tasks.json` reflect real evidence.

Do not spawn agents merely to increase concurrency. The compiler is the project; orchestration stays small.
