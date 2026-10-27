# C17 specialist orchestration

Supervisor owns integration, task choice, interfaces, evidence and progress.
frontend-engineer owns source/diagnostics/DFA/parser/AST; semantics-core-engineer
owns resolution/types/plans/Core/interpreter; backend-runtime-engineer owns C17
runtime/backend/ABI; quality-engineer owns native fixtures/fuzz/build portability.
reviewer, semantic-auditor and native-safety-auditor are independent read-only roles.
Max three workers, no pinned model. High effort for ownership/ABI/semantics/review;
Medium for bounded ordinary work. Parallel writers require isolated worktrees and
disjoint contracts. A staged disjoint single writer may work alongside read-only
reviewers; supervisor must not edit its files before a frozen handoff.

Delegation includes task ID, objective, owned files/interfaces, norms, invariants,
non-goals, required tests, requested effort and exact handoff requirements. Review
actual code and rerun tests before accepting. Missing facilities are reported,
not simulated. After interruptions inspect work before starting another worker.
No approval-gated plan; pause only for genuine permission or semantic ambiguity.
