# Invalid input: documented rules, expected rows and recovery

Run with `--classroom --output-dir build`. Each run replaces the table in build;
rerun complete.tfd afterward. Diagnostics use stderr and original byte spans.
The original concise `examples/lexical/invalid.tfd` is preserved. The expanded
`examples/lexical/invalid-comprehensive.tfd` exercises independent rule families.
The trace fixture is intentionally invalid in places and is not a valid program.

| Rule / representative input | Expected code / report | Recovery / evidence |
|---|---|---|
| Unsupported `@`, `$`, backtick, backslash, Unicode Ω outside quotes/comments | E101; INVALID for each unsupported scalar | Subsequent tokens retained; expanded demo and test_coverage invalid_rules |
| A single `&` or `\|` | E101; INVALID | `&&` and `\|\|` are valid compounds; operator boundaries tested |
| Decimal leading zeros `00`, `09` | E102; one INVALID run | Separator starts next token; signs are separate operators |
| Missing exponent digits `1e`, `1e+`, `1e-` | E102; INVALID | `1e++2` recovers as INVALID(1e+), PLUS, INT(2) |
| Numeric suffix / extra fraction `1efoo`, `1_0`, `1.2.3`, `2e3e4` | E102; one malformed run | `1efoo.bar` preserves DOT/IDENT after INVALID(1efoo); `1.foo` is INT/DOT/IDENT |
| `2total` | E102 INVALID under the later accepted recovery rule | Explicit difference from submitted p.6; not concealed as historical compliance |
| Unknown Text escape `"bad\q"` | E103; INVALID literal | Closing quote or line boundary controls recovery |
| Empty/too-long/invalid Unicode escape, surrogate or above10FFFF | E103 for Text, E105 for Char; INVALID | Expanded example and independent explicit negative cases |
| Unterminated Text before newline | E103; INVALID to recovery boundary | `let recovered_text = 3;` still tokenizes on following line |
| Empty/multiple-scalar Char `''`, `'ab'`, bad escape or unclosed Char | E105; INVALID | Following `let recovered_char = 4;` survives newline recovery |
| Raw control inside literal | E103 or E105 | C tests supply actual control bytes; escaped `\n` is a different valid input |
| `/*` without closing `*/` | E104; final INVALID block run | No later token exists outside the unfinished comment; do not promise recovery past EOF |
| Embedded NUL outside a literal | E101 INVALID, surrounding identifiers retained | Separate binary `tests/fixtures/invalid/embedded-nul.tfd`; NUL is valid UTF-8 but unsupported syntax |
| Malformed UTF-8 / truncated sequence | E001; header-only Symbol Table | `utf8-invalid.tfd`, `utf8-truncated.tfd`; no replacement decoding or invented token coordinates |
| Initial UTF-8 BOM | E002; header-only report | `utf8-bom.tfd`; exact raw range retained |
| Lone CR (not CRLF) | E003; header-only report | `lone-cr.tfd`; LF and CRLF remain supported |
| Unsupported extension `README.md`, missing `.txt`, uppercase `.TFD` | CLI exit1; extension diagnostic; existing report unchanged | Rejected before attempting to open source; CLI tests establish order |

Each binary source fixture is separate: incompatible encoding errors are not
combined into one fake text example. The expanded invalid demo is valid UTF-8,
so its recoverable lexical errors produce actual INVALID rows. Source-invalid
fixtures prevent tokenization and produce only `TOKEN TYPE\tLEXEME` plus newline.

`tests/fixtures/invalid/` contains exact classroom/lossless report and diagnostic
goldens for the expanded examples and byte fixtures. `test_coverage.c` compares
them and independently checks error codes, byte spans and preserved valid tokens.
`old-scanner.baseline.txt` is a frozen pre-refactor behavior oracle, not a sample
to edit when new results differ. `test_differential.c` separately compares the old
test-only scanner with production recognition, payloads, metadata and reports.

These are **not** lexical errors: unmatched brackets, unknown names, misplaced
noise words, wrong argument types, out-of-range Int magnitudes, or well-formed
`1e999`. The lexer can tokenize them; grammar/type/runtime validity belongs to
later phases. In particular, `*/` outside a comment has the existing BLOCK_CLOSE
token but is not a valid standalone source program or an extra arithmetic operator.

All invalid runs exit1 after writing any applicable report. Usage, allocation,
read, trace-output or report-publication failures exit2. No lexical rule is added
solely to manufacture an INVALID example.
