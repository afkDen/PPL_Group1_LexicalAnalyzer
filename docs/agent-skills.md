# C17 agent and skill configuration

Seven stable specialist names live in .codex/agents/*.toml. Agent files require
name, description and developer_instructions; optional model_reasoning_effort
routes risk. Project .codex/config.toml enables agents with max three concurrent
threads. No hard-coded model, credential, sandbox override or runtime dependency.
Schema source checked during migration:
https://learn.chatgpt.com/docs/agent-configuration/subagents

Nine original project skills live in .agents/skills/*/SKILL.md. Each has YAML
name/description metadata and offline procedural instructions. Use orchestration
at task selection; feature + test-design for implementation; lexical-conformance
for DFA/report; debugging for failures; spec-audit for cross-phase consistency;
native-safety for C lifetime/UB; differential once executors exist;
verified-completion before any acceptance. All refer to native C gates.

Native repository audit checks inventory/required fields and workflow references.
This is metadata validation, not a claim to exhaustively validate the Codex parser.
Agent availability depends on the running client; never pretend delegation ran.
