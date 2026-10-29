# Submitted proposal and subsequent lexical decisions

The submitted reference is `Group-1_Project_Proposal-1 (1).pdf`: 20 pages,
1,609,615 bytes, SHA-256
`d7c6bb63ca5ff4d7d627591375029e2f943cd6e3ce02cc4ada2f54fc7415c827`.
The PDF remains unchanged and is not redistributed in this lexical package.

This submission recognizes tokens and generates a Symbol Table. It does not
parse programs, validate imports, check types or execute Ternfold.

## Submitted vocabulary and current recognition

The proposal lists 28 keyword spellings and 21 reserved names. All remain
recognized. The current reserved inventory has 25 spellings: `Float`,
`int_float`, `float_int` and `float_text` were accepted afterward.
The proposal also describes identifiers, Char literals, contextual noise words,
both comment forms, `div` and power.

[PROPOSAL_LEXICAL_RECONCILIATION.md](PROPOSAL_LEXICAL_RECONCILIATION.md) retains
the full spelling matrix, proposal page references, accepting states, source
lines, report rows and boundary-test evidence. Words inside comments and Text
literals do not count as demonstrations of keyword recognition.

The immutable transition table and actual-transition trace are implementation
and presentation improvements. They add no keyword or reserved spelling.

## Material differences

| Subject | Submitted reference | Current lexical analyzer |
|---|---|---|
| Float vocabulary | The reserved inventory does not list `Float` or the three associated conversion/formatting names | Recognizes all four as later reserved additions |
| `/` and `div` | The proposal describes an integer quotient for `/` | Recognizes distinct SLASH and DIV tokens. Later numerical rules distinguish real `/` from integer `div`; this analyzer does not evaluate either operation |
| Numeric suffix recovery | Page 6 gives `2total` as an integer followed by an identifier | Reports one E102 INVALID run under the later numeric-recovery rule; invalid tests preserve this difference |
| Token labels | Descriptive groups include RESERVED_NAME, OPERATOR and DELIMITER | Uses RESERVED_WORD and concrete operator/delimiter labels; the detailed matrix gives the mapping |
| Report columns and escaping | Page 18 specifies location columns | Classroom mode writes exactly TOKEN TYPE and LEXEME, with ordinary lexemes shown plainly and row-breaking characters escaped. The default lossless mode quotes cells |
| Literal and source validation | Escape lists and source-error details are incomplete | Documents precise UTF-8, control-character, Unicode-escape and recovery rules as later elaborations |
| Implementation | The proposal discusses other implementation hosts and toolchains | Uses four C17 implementation files and a directly included fixed-state table |

The current rules are documented as subsequent decisions, without attributing
them retrospectively to the submitted PDF or claiming instructor approval.
Coverage tests establish the scanner's current behavior; they do not establish
full-language semantic conformance. See [INVALID_CASES.md](INVALID_CASES.md) for
recovery examples and [VERIFICATION.md](VERIFICATION.md) for reproducible checks.
