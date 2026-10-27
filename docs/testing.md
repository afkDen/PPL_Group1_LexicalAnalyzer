# C17 testing and acceptance

Run `./scripts/build.ps1 check` and `sanitize` (Windows), or intended
`sh scripts/build.sh check`/`sanitize` (POSIX). Environment check separately
compiles/runs a C17 host probe. check builds production C, native unit/integration
tests and repository audit with warnings as errors. Sanitizers fail on errors;
never treat unavailable checks or skipped cases as successful verification.

For lexing cover all keywords/reserved words/noise words, maximal munch, prefix
suffix boundaries, ASCII identifiers, five literal categories, Unicode scalar
validation, BOM/NUL/CRLF/source coordinates, all seven arithmetic and nine Boolean
operators, delimiters/comments/invalid recovery, exact report bytes and ordering.
Exercise allocation failures and deterministic randomized byte/scalar inputs.
CLI integration covers exact extension policy, missing files/output directories,
spaces in paths, stable reruns, invalid source/header output, source/report aliases
and failed publication without source mutation. Review actual assertions.

Keep fixture/golden bytes under tests and runnable examples under examples.
No numeric conversion belongs in the scanner; range/arithmetic checks are later
phase tests. No executor parity is possible before M09/M11; record it pending.
Machine tests must eventually cover old/next reads, one writer, lexical deps,
cycles, ASCII ready order, candidates-before-guards, first failed guard, typed
rejection, runtime faults and no leaked emissions. Numeric tests preserve ADR0010.

Independent reviewers remain read-only. Native safety review challenges lifetime,
allocation failure, size arithmetic, aliasing, atomic publication and UB.
Record exact commands/results and hash frozen source. Every task retains original
acceptance intent; lexical subsets do not silently complete broad phase tasks.
Fresh ZIP extraction must rebuild/test without the checkout, Python or AI access.
Course ledger tracks lexical recognition separately from future semantic execution.
