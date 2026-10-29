# Static-DFA lexical submission verification

This source snapshot implements the existing28keyword/25reserved vocabulary
with an immutable215state prefix graph. The four-file C17 application includes
src/name_dfa.inc directly; it never builds word transitions at runtime.
Optional --trace-dfa records actual scanner state updates on stderr.

## Observed Windows candidate gates

LLVM-MinGW Clang23.1.4,Windowsx64,ISO C17 with strict warnings as errors.
Current integrated check passed117201lexer,31CLIcases/12604checks,
684classroom,78sample,58087graph,994trace,13464314differential comparisons
across3010cases,289723independentcoverage checks over618frozenoldcases,
and84repositoryauditchecks. One local unprivilegedsymlink capability probe is
unavailable. ASan/UBSan integrated gates also passed the same counts (12608CLIchecks).
Optimized -O2 integrated gates passed the same counts. Independent final audit and actual target-host source/ZIP evidence remain release gates. No unsupportedplatform success is inferred.

The primary/support examples were read-only parser checked with zero diagnostics
using the preserved accepted M04 parser API; they are not name/type/runtime
validated. Vocabulary and trace examples are lexical streams, not executable
program claims. The original invalid.tfd remains unchanged. Expanded invalid
examples and separate byte fixtures are documented in INVALID_CASES.md.

## Independent review and historical behavior

A frozen test-only scanner snapshot preserves accepted source7cc9044; its
original source SHA256 is e8c38747cb811a1828fc6fdef2d755238e2a6755bc423caf145675c98ac0be30.
The only baseline adjustments rename test symbols/include paths. It is not
linked into the production application. Differential tests compare statuses,
metadata,source spans,decoded payloads,diagnostics and both report modes.
A second independent frozen text corpus covers618boundary/invalid cases.
Expected reports changed only for intentionally expanded demo inputs; the
recognizer change is required to preserve prior lexical behavior.

Proposal review used user-confirmed Group-1_Project_Proposal-1 (1).pdf,
20pages,SHA256d7c6bb63ca5ff4d7d627591375029e2f943cd6e3ce02cc4ada2f54fc7415c827.
It remains unchanged and is not redistributed. The companion and per-spelling
matrix distinguish later Float/numeric recovery/report decisions. Full-proposal
semantic equivalence is expressly not claimed. Student-reported new grading
expectations/penalty are not independently confirmed professor statements.

## Packaging and platform boundaries

SOURCE_FILES.txt is the explicit source-only file allowlist. Manifests and
archive hashes remain outside the archive to avoid self-reference. Recommended
source and separate all-in-one binaries must be built from this same accepted
lexical revision; release notes identify their hashes and actual native runs.
Historical2026-10-29releases remain preserved and must not supply binaries for
this revised source. No toolchain/IDE is bundled in source. Direct Dev-C++/Xcode
GUI execution remains unverified; their manual configuration and equivalent
four-file compiler commands are documented.

The full compiler is paused by user and excluded from all public source/binary
packages. Its M01–M04 acceptance is preserved; partial M05 is unaccepted and
will not resume after lexical finalization without explicit authorization.

Integration corrections: initial expanded-demo golden mismatch was resolved only by copying the separately generated reports for the intentionally changed input. The old invalid demo and frozen618case oracle remain unchanged. A Windows-reserved NUL fixture name was replaced by embedded-nul.tfd without changing input bytes/classification. One premature sanitizer build hit the shared tfdev file lock while check was still running; sequential check/sanitize/release reruns passed. These failed integration attempts are retained as evidence, not hidden.

Final trace-review corrections removed zero-length/stale-state escape events and overlapping invalid-scalar consumption. The994check trace suite now asserts continuity and exactly-once byte consumption. Native reviewer Volta independently passed strict/sanitized994checks plus3455privatechecks covering35OOMpositions and35latewritefailures, with no remainingP1/P2. Frozen lexerSHA25647d63444ef7268895376475e30b53774a8c9826587a9d7e237184be255e70c8d. Clangstaticanalysisclean. A case-insensitive documentation map was corrected to ordinal case-sensitive keys; table IDs now match actual accepting states.
