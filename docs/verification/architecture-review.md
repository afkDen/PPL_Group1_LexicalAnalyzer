# Architecture and skill review evidence

Date: 2026-09-13. Two bounded independent review passes used the repository's actual project skills against raw documents and fixtures.

## Feature skill review

The reviewer found reserved keyword `machine` used as a pattern binder in three positive fixtures. Renamed the binders/references to `snapshot`, preserving expected output. The reviewer also found Core's unreachable/default block contract underspecified: made Unreachable a proof-restricted terminator, with reachable-branch result typing and a required invalid-IR counterexample. Finally, defined typed capture-free wrappers for first-class builtins, including step, and explicitly excluded first-class nominal constructors. These changes resolve preimplementation contract defects.

## Differential skill review

A second pass applied ternfold-differential to testing.md, M09–M14 task briefs, the example manifest and actual tests/probe. It identified no additional concrete blockers. It confirmed that independent expectations, fault locations, ownership/resource tests, installed-wheel native testing and milestone fixture activation are required, and that bootstrap/probe limitations are accurately stated.

## Limits

Review does not prove the specification complete or the unimplemented compiler correct. No Ternfold lexer/parser/executor was run. Both skill directories passed the supplied system validator and portable project validator. Actual Codex selector discovery remains untested because the Codex CLI is unavailable in this container; explicit reading/invocation of the skill instructions was exercised.
