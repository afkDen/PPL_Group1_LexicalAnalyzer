# How the handwritten scanner works

This analyzer uses C character-by-character finite-state logic; no generator or
whole-word token lookup is used.

| Family | States and boundary |
|---|---|
| Names | ASCII letter/underscore starts a name. Each next character advances a trie edge; a missing edge enters the generic identifier state. Letters/digits/underscore continue. Classification uses terminal metadata only at the boundary. `letx` and `Intensity` remain identifiers. |
| Keywords/reserved | The same name trie recognizes the documented keywords and reserved type/builtin names. An inventory builds transitions; input words are never compared against completed spellings. |
| Numbers | Start/zero/integer/fraction/exponent/sign/digits states distinguish Int and Float. Leading zeros and malformed suffix/exponent runs become INVALID with recovery. Signs remain separate operators; signed range checks belong to the later compiler. |
| Text/Char | Opening quote, content, escape, Unicode-escape and closing quote states preserve source lexemes. Escape decoding validates Unicode scalars; Char must decode to one scalar. |
| Comments | `/` branches to line-comment, block-comment or slash. Line comments stop at newline/EOF. Block comments stop at the first `*/`; nesting is not recognized. |
| Operators | Maximal munch accepts two-character operators before their prefixes, including `&&`, `||`, comparisons and arrows. `div` follows the name trie. |
| Invalid input | Unsupported symbols and malformed literal/comment states produce INVALID rows and structured diagnostics. Every scan path consumes input or reaches EOF. |

Example name transition: start → `l` → `e` → `t` → boundary accepts KEYWORD;
continuing with `x` enters the identifier path and accepts IDENTIFIER.

The primary `complete.tfd` is a coherent example containing the grading categories.
`vocabulary.tfd` is an explicitly lexical-only inventory/boundary fixture, not an
executable program. `invalid.tfd` demonstrates recovery and expected failure.

The report is a presentation of these same tokens, not a second scanner.
Classroom mode prints ordinary lexemes plainly and reversibly escapes row-breaking
characters; compatible lossless mode uses JSON-quoted cells. Both include comment
and invalid rows in original source order, omitting whitespace/EOF.
