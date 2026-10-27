# Codex implementation orchestration

Codex project config: `.codex/config.toml`; seven specialist/auditor definitions: `.codex/agents/*.toml`; reusable skills: `.agents/skills/*/SKILL.md`. Official capability references: <https://developers.openai.com/codex/multi-agent>, <https://developers.openai.com/codex/skills>, <https://developers.openai.com/codex/guides/agents-md>. Codex clients may offer different agent controls; verify in actual session. No CLI/API credentials or hard-coded model names are stored.

## Supervisor

Use the currently selected capable Codex model, with high reasoning for cross-phase/machine/type/backend work. First reconcile actual worktree and `docs/tasks.json` before task selection. No approval-plan stop. Task briefs authorize implementation. Supervisor owns integration, review, completion evidence, conflict resolution and progression.

## Specialist routing

| Agent | Typical ownership | Normal effort |
|---|---|---|
| `frontend-engineer` | M01–M04 source, lex/parse, diagnostic/AST | Medium; High on grammar ambiguity |
| `semantics-core-engineer` | M05–M09 modules/types/machines/Core/interpreter | High |
| `backend-runtime-engineer` | M10–M11 C runtime/backend, M16 optimization | High |
| `quality-engineer` | Tests, fuzz/property, fixtures, differential/packaging | Medium |
| `reviewer` | Independent read-only review and specification compliance | Medium; High for semantic milestones |

Give every worker a bounded delegation: task ID, objective, normative references, owned files/interfaces, invariants, prohibited redesign, acceptance cases, tests, commands and requested effort. Ask for explicit handoff with actual files/commands/results/risks. Supervisor must review actual implementation, not blindly accept the handoff. Do not run simultaneous writers on shared contracts. Prefer max 2–3 concurrent specialists, and isolated worktrees when writing in parallel.

Use `$ternfold-orchestration` for nontrivial routing, `$ternfold-feature` for language feature work, `$ternfold-spec-audit` when semantics/contract changes, `$ternfold-differential` once M09+M11 are runnable. Skills are procedures, not a replacement for tools, tests, or normative docs.

## Product capability fallbacks

When a Codex client does not expose native subagents, implement sequentially, perform an explicit independent review pass and record its limits. For ordinary ChatGPT without repository filesystem, the same instructions can guide analysis of uploaded files, but completion claims require a code-capable workspace (Codex/Work) and test evidence. Do not pretend ChatGPT text chat is automatically synced to the user's local repo.

## Retry, quota recovery and milestone closure

Inspect partial diffs, worktrees, running/dead workers, command failures and progress before resuming. Do not duplicate work. Initial attempt → focused diagnosis → targeted retry → high reasoning/escalation → independent reviewer → user only if permissions, destructive changes, or irresolvable high-impact semantic choices. Formal High milestone reviews after M04, M07, M09, M11, M14. Only after gates pass update `docs/tasks.json`, `docs/progress.md`, briefs and course acceptance evidence. Do not execute M06 typing inside unfinished M05 resolution merely to satisfy tests.

## Targeted quality assurance extensions

- **test-first, evidence-heavy feature work:** `$ternfold-test-design`; own work stays with the original compiler specialist.
- **root-cause debugging:** `$ternfold-debugging`, isolate first divergent phase and preserve a regression.
- **lexical DFA and classroom outputs:** `$ternfold-lexical-conformance`; run with frontend-engineer/quality-engineer.
- **native ABI and ownership:** `$ternfold-native-safety`; mandatory read-only `native-safety-auditor` before M10/M11 acceptance.
- **completion signoff:** `$ternfold-verified-completion`; no status mutation without fresh results.
- **adversarial semantics:** `semantic-auditor` is a read-only peer of the reviewer, not another implementer. For M05–M09 use at major/semantic gates as appropriate. The reviewer still owns general diff quality.

Delegations must explicitly name requested effort and skill(s). Choose High for ambiguous semantic/ownership issues, Medium for clear engineering, Low for mechanical work. Run at most 3 subagents; prefer parallel *read-only* audit to competing writers. Do not mark task/acceptance complete without supervisor integration and evidence. If subagents are unavailable on a ChatGPT surface, state the limitation and run sequential review; do not invent subagent events.

Per-agent High reasoning defaults are configured for semantic/backend specialists and reviewers/auditors through supported `model_reasoning_effort` keys, with explicit task-level effort taking precedence where Codex exposes it. No model ID is hard-pinned.
