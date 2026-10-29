# How the handwritten scanner works

The analyzer recognizes tokens character by character in handwritten C17.
Production name recognition uses fixed transitions and terminal metadata; it
does not use a lexer generator, regular-expression tokenizer or completed-word
lookup.

## Recognition rules

| Family | States and boundary |
|---|---|
| Names | An ASCII letter or underscore starts a name. Each character follows an immutable prefix-state edge; a missing edge enters the generic identifier fallback. Letters, digits and underscores continue the name. Classification uses terminal metadata only at the maximal identifier boundary. `letx` and `Intensity` remain identifiers. |
| Keywords and reserved names | The `static const name_states[]` table in `src/name_dfa.inc` contains 215 fixed states, including start state 0, with character edges and terminal metadata. The application never constructs this graph at runtime. The absorbing identifier fallback is represented separately by `SIZE_MAX`. |
| Numbers | Start, zero, integer, fraction, exponent, sign and exponent-digit states distinguish Int and Float spellings. Leading zeros and malformed suffix or exponent runs produce INVALID tokens with recovery. Signs outside exponents remain separate operators; numeric range checking is outside lexical analysis. |
| Text and Char | Opening-quote, content, escape, Unicode-escape and closing-quote states preserve source lexemes. Decoding validates Unicode scalars; Char must decode to exactly one scalar. |
| Comments | `/` branches to a line comment, block comment or SLASH token. Line comments stop at newline or EOF. Block comments stop at the first `*/`; comments do not nest. |
| Operators | Maximal munch accepts valid two-character operators before their one-character prefixes, including `&&`, `\|\|`, comparisons and arrows. The word `div` follows the name DFA. |
| Invalid input | Unsupported symbols and malformed literals or comments produce INVALID tokens and diagnostics. Every scan path consumes input or reaches EOF. Source-validation errors prevent tokenization. |

For `let`, the path is state 0 → 43 (`l`) → 44 (`e`) → 45 (`t`).
At a name boundary, state 45 selects LET. If an adjacent `x` follows, the
scanner continues into the identifier fallback and classifies the whole
`letx` lexeme as IDENT. Reaching a keyword terminal does not end a name early.

The fixed name table covers names, keyword spellings, reserved spellings and
the standalone `_` token. Numbers, quoted literals, comments and symbolic
operators use separate handwritten state and switch logic in `src/lexer.c`.

## Production source and historical test baseline

The executable compiles four files: `src/main.c`, `src/lexer.c`,
`src/source.c` and `src/report.c`. The scanner directly includes
`src/name_dfa.inc`; this include is not a fifth compilation unit.

The frozen `tests/baseline_lexer.c` scanner and `tests/baseline_main.c`
entry point are used only for differential tests. Their historical runtime
graph construction is not part of the production executable.
`tests/test_dfa.c` checks fixed edges, targets, reachability, outgoing-label
uniqueness, terminal metadata and identifier fallback.

## Demonstrations and reports

`examples/lexical/complete.tfd` demonstrates all 28 current keyword spellings,
25 reserved names and the full operator/delimiter inventory as actual tokens.
`support.tfd` supplies its companion source example. Successful tokenization
does not establish grammatical correctness, type correctness or execution.
`vocabulary.tfd` is a lexical inventory and boundary fixture;
`invalid.tfd` demonstrates diagnostics and recovery.

The report presents these same tokens. Classroom mode writes exactly TOKEN TYPE
and LEXEME, shows ordinary lexemes plainly and reversibly escapes row-breaking
characters. Default lossless mode uses JSON-quoted cells. Both retain comments
and invalid tokens in source order and omit whitespace and EOF.

[DFA_LIVE_DEMO.md](DFA_LIVE_DEMO.md) gives exact state paths and the
`--trace-dfa` procedure. The trace records actual scanner state updates;
it uses no separate teaching recognizer. [RUBRIC.md](RUBRIC.md) and
[DEMO_ROWS.md](DEMO_ROWS.md) map the demonstrations to report evidence.
