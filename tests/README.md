# Test overview

The application uses only `src/main.c`, `src/lexer.c`, `src/source.c`, and
`src/report.c`. The fixed name graph is included from `src/name_dfa.inc`.
No file in this test directory is part of the production executable.

Run strict checks with `sh scripts/build.sh check` or
`./scripts/build.ps1 check`. Use `sanitize` instead of `check` for AddressSanitizer
and UndefinedBehaviorSanitizer builds when supported by the compiler.

| Test | What it checks |
|---|---|
| `test_lexer.c` | Tokens, decoded values, spans, invalid recovery, UTF-8, and allocation failures. |
| `test_integration.c` | CLI arguments, extension policy, output publication, and file failures. |
| `test_classroom.c`, `test_demo.c` | Exact report format and coursework demonstrations. |
| `test_dfa.c` | Fixed states, edges, accepting metadata, and identifier boundaries. |
| `test_trace.c` | Actual transition continuity, final decisions, and byte consumption. |
| `test_differential.c` | Current scanner versus the frozen historical scanner. |
| `test_coverage.c` | Vocabulary, boundaries, diagnostics, reports, and frozen corpus evidence. |
| `fixtures/` | Expected reports, diagnostics, byte fixtures, and historical corpus. |

## Historical comparison files

`baseline_lexer.c` and `baseline_main.c` preserve the earlier scanner and CLI for
tests only. That scanner builds its historical name graph at runtime; this is
**not the active implementation**. The current graph is immutable and defined
at compile time in `src/name_dfa.inc`.

The build driver links `baseline_lexer.c` only into the differential test.
`baseline_main.c` preserves the historical CLI for optional baseline reproduction;
the regular coverage test reads a frozen text corpus. Neither baseline source
is linked into `ternfold-lexer`. Comparisons cover tokens, spans,
diagnostics, decoded values, and both report modes. Keeping the baseline frozen
makes accidental recognition changes visible.

Expected reports are test data, not presentation documents. Do not change their
spacing, escaping, line endings, or invalid source bytes for editorial reasons.
See [verification](../VERIFICATION.md) for counts, CI runs, and platform limits.
