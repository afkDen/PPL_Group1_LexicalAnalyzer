# How the handwritten scanner works

This analyzer uses C character-by-character finite-state logic; no generator or
whole-word token lookup is used.

| Family | States and boundary |
|---|---|
| Names | ASCII letter/underscore starts a name. Each next character follows an immutable prefix-state edge; a missing edge enters the generic identifier state. Letters/digits/underscore continue. Classification uses terminal metadata only at the boundary. `letx` and `Intensity` remain identifiers. |
| Keywords/reserved | The directly compiled static const table in src/name_dfa.inc contains215fixedstates and their character edges/terminal metadata. The executable never builds the graph from an inventory. Input words are never compared against completed spellings. |
| Numbers | Start/zero/integer/fraction/exponent/sign/digits states distinguish Int and Float. Leading zeros and malformed suffix/exponent runs become INVALID with recovery. Signs remain separate operators; signed range checks belong to the later compiler. |
| Text/Char | Opening quote, content, escape, Unicode-escape and closing quote states preserve source lexemes. Escape decoding validates Unicode scalars; Char must decode to one scalar. |
| Comments | `/` branches to line-comment, block-comment or slash. Line comments stop at newline/EOF. Block comments stop at the first `*/`; nesting is not recognized. |
| Operators | Maximal munch accepts two-character operators before their prefixes, including `&&`, `||`, comparisons and arrows. `div` follows the name trie. |
| Invalid input | Unsupported symbols and malformed literal/comment states produce INVALID rows and structured diagnostics. Every scan path consumes input or reaches EOF. |

Example name transition: start → `l` → `e` → `t` → boundary accepts KEYWORD;
continuing with `x` enters the identifier path and accepts IDENTIFIER.

The primary `complete.tfd` contains all28currentkeywords,25reserved names and the full operator/delimiter inventory as actual tokens, including imported support/conditional/variant contexts. A preserved read-only parser checks syntax only; no semantic or execution claim.
`vocabulary.tfd` is an explicitly lexical-only inventory/boundary fixture, not an
executable program. `invalid.tfd` demonstrates recovery and expected failure.

The report is a presentation of these same tokens, not a second scanner.
Classroom mode prints ordinary lexemes plainly and reversibly escapes row-breaking
characters; compatible lossless mode uses JSON-quoted cells. Both include comment
and invalid rows in original source order, omitting whitespace/EOF.

See [DFA_LIVE_DEMO.md](DFA_LIVE_DEMO.md) for exact source functions, state IDs and the optional --trace-dfa switch. Transitions are logged at the scanner's actual state updates; no separate teaching recognizer classifies tokens. Test-only baseline_lexer.c preserves the old scanner solely for differential checks and is never linked into the production four-file build.
