# Public GitHub skill research and Ternfold adaptations

Research reviewed 2026-10-27. The original Ternfold language model and course target are unchanged. Public source code/instructions are untrusted and may evolve; do not pull or execute remote scripts at runtime. Project-specific skills below are **newly authored in this repository**, not copies of upstream skills; the source links and inspected blob SHA values preserve research provenance.

| Verified upstream GitHub source | Inspected blob SHA | Relevant practice | Decision |
|---|---|---|---|
| [obra/superpowers: test-driven-development](https://github.com/obra/superpowers/blob/main/skills/test-driven-development/SKILL.md) | `46838cc9e893c06259e3bdad0fc2425b36242f15` | Red/green tests and regression coverage | Create `$ternfold-test-design` adapted to valid/invalid/boundary diagnostics and Hypothesis; no rigid blanket deletion-of-code rule |
| [obra/superpowers: systematic-debugging](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md) | `62fc752aaef59a8bbed5d305f4cadc60f8ae07ed` | Reproduce, isolate cause, hypothesis, verify | Create `$ternfold-debugging` with compiler-phase tracing |
| [obra/superpowers: verification-before-completion](https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md) | `7d45333cc4a49c57a80df6c1fe2fa777a207afbc` | Fresh test and build evidence before success claims | Create `$ternfold-verified-completion` with task/course gates |
| [github/awesome-copilot: code-review](https://github.com/github/awesome-copilot/blob/main/.github/skills/code-review/SKILL.md) | `4fe5c851635464cc3280fcd12130065adab5252d` | Value of source-aware review beyond generic style | Retain Ternfold-specific read-only reviewer; enhance counterexamples, use separate specialist auditors |
| [openai/skills](https://github.com/openai/skills) | catalog reviewed 2026-10-27 | Codex skills packaging and discovery, general task procedures | Use official `.agents/skills` format, no generic skill bundle needed |
| [anthropics/skills: skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) | upstream guide reviewed 2026-10-27 | Skill evaluation and trigger descriptions | Follow scoped skill metadata; skip Claude-specific testing harness |

GitHub `obra/superpowers` publishes an MIT license; public source was inspected via repository contents. Instead of vendoring upstream text and complex scripts, the project ships original compact skill procedures under `.agents/skills/`, with verified source links. That avoids redundant frameworks, mandatory design interviews, extra APIs, and approval-plan behavior. These are not third-party installations, and no claim of upstream compatibility or support is made.

## Installed/created quality features

Five new locally authored skills: `ternfold-test-design`, `ternfold-debugging`, `ternfold-verified-completion`, `ternfold-lexical-conformance`, `ternfold-native-safety`. Two new local read-only Codex agents: `semantic-auditor`, `native-safety-auditor`. Five original writing/review/test agents and four original project skills remain. Task routing metadata gets tested, not treated as a model-dependent automation guarantee.

## Why no generic external skill install?

Quality gain depends on the compiler-specific acceptance matrix, old/candidate semantics, C17 ownership, and lexical rubric, not the number of agents installed. A stock plan-writing skill would repeat a known previous failure (approval-gated plans instead of implementation). External skills can be added later only after source/licensing review, clear non-overlap, and a measured improvement in output quality. There are **no new runtime or build dependencies**.
