# Submitted proposal and subsequent lexical decisions

The group confirmed on29October2026 that the submitted document is
**Group-1_Project_Proposal-1 (1).pdf**,20pages,1609615bytes, SHA256
`d7c6bb63ca5ff4d7d627591375029e2f943cd6e3ce02cc4ada2f54fc7415c827`.
It is preserved unchanged in the private project. It is not replaced by this
companion, and it is not included in the public lexical package. The separately
preserved19-page Revised and21-page Latest PDFs are later local references;
their filenames are not evidence that they were submitted.

The professor's additional DFA presentation expectations and possible penalty
were reported by another student. They are treated as important grading risks;
we do not claim independent professor confirmation of that report or penalty.

This submission implements lexical recognition only. It does not execute the
language, check types or validate imports. The complete compiler is paused by
the user; its implementation is private and is not a dependency of this package.

## Scope of the comparison

[PROPOSAL_LEXICAL_RECONCILIATION.md](PROPOSAL_LEXICAL_RECONCILIATION.md) lists
each spelling, its submitted/later provenance, scanner acceptance, sample
coverage and generated report evidence. Submitted rules take precedence when
describing what the proposal said. Later documented decisions are identified
as later decisions rather than retrospectively attributed to the proposal.

The submitted proposal already contains DFA explanations/diagrams, identifiers,
keywords, reserved names, Char, noise connectors, both comment forms, div and
power. Current accepted lexical vocabulary retains those spellings. Float and
its three conversion/formatting names are later additions. The static transition
table and actual transition tracing are implementation/presentation improvements;
they do not introduce a new keyword or language feature.

## Differences that must be explained honestly

| Subject | Submitted/later distinction | Disposition |
|---|---|---|
| Float vocabulary | Current `Float`, `int_float`, `float_int`, `float_text` extend the earlier reserved inventory | Preserve and demonstrate as post-submission accepted additions; never claim they were printed in the submitted inventory |
| `/` numerical behavior | Earlier integer-quotient wording differs from later real-division/Float rules | Lexer recognizes `/` in either case; execution is outside this deliverable; no runtime change is made here |
| Numeric suffix recovery | Submitted identifier discussion gives `2total` as integer then identifier; later accepted numeric-run rule diagnoses a malformed numeral such as `2total` as one E102 INVALID run | Retain current documented numeric recovery, expose this lexical difference explicitly, and include it in invalid tests; do not silently rewrite the proposal |
| Report labels | Proposal uses descriptive groups such as RESERVED_NAME and OPERATOR; actual stable API/report uses RESERVED_WORD and concrete operator token labels | Explain the mapping in the reconciliation matrix; retain exactly TOKEN TYPE / LEXEME columns and source-order rows |
| Report layout/escaping | Earlier proposal examples may include location columns; later accepted classroom contract has two columns, plain ordinary lexemes and reversible control escaping | Preserve current classroom mode and compatible lossless quoted mode; neither changes token recognition |
| Implementation host | Historical documents discuss other implementation hosts/toolchains | This submission is C17; compile its four C files or use the separately verified native executable package |

No professor approval of a post-submission change is invented. The source and
coverage tests prove what the current scanner does; they do not erase these
historical differences or establish full-language semantic conformance. The
submitted PDF is immutable. Any unresolved proposal conflict remains visible
in the matrix and final verification record.
