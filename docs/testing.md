# Testing and conformance architecture

Current tests validate source snapshots, diagnostics, the full lexer/parser, module resolution, types, constants and pattern coverage through M06. M07 machine planning is verified under the historical numerical contract; C01 Float frontend/constants are verified; M08 Core is verified; M09 interpretation is active. Core, interpreter and native language semantics remain pending. The small independent transition model is supplementary evidence; production compiler tests must establish each owning milestone. Deadlines in examples/manifest.json are contractual once those milestones complete.

## Test layers and observations

| Layer | What to test | Strong assertion |
|---|---|---|
| Source/spans | UTF-8, CRLF, EOF, invalid ranges, tab display | Original bytes and scalar/source coordinates round-trip correctly |
| Lexer | Every token/escape, invalid Unicode, longest match | Token kinds/payloads/spans, bounded progress |
| Parser/AST | Every grammar form, precedence, recovery | Structural AST plus selected dump goldens; no hangs/cascade explosion |
| Resolution | Scopes, nominal identity, module graph | Resolved IDs and precise multi-span diagnostics |
| Types/coverage | Expected/actual types, inference holes, missing/useless patterns | Concrete typed nodes; valid missing-pattern witnesses |
| Machine plan | Writer completeness, old/next distinction, graph | Exact schedule/read sets/cycle witness independent of hash iteration |
| Lowering/Core | Short circuits, pattern trees, guards/closures | No surface-only op; verifier dominance/type/tag proofs |
| Interpreter | Checked operations, values, limits, calls | Hand-derived results and logical-fault origins |
| Native runtime | Ownership, primitives, UTF-8, allocations | C unit assertions, sanitizers, fault-injection cleanup |
| C emission/build | Statement order, strings, paths, owned slots | Warning-clean C, correct binary result, failure preserves output |
| Differential | Source interpreted versus native | stdout bytes, exit, R001/R002 code and original span |
| CLI/REPL | Entry contracts, session commit, help/error paths | Captured process bytes/status, no tracebacks for user errors |
| Packaging | Installed compiler away from checkout | Imports, CLI, examples and native runtime discoverable offline |

## Feature completion matrix

Every new feature adds applicable rows/cases here or in its task brief. This baseline prevents happy-path-only completion.

| Feature | Valid case | Invalid case / diagnostic | Boundary | Execution/lowering evidence |
|---|---|---|---|---|
| Int | sign-correct integer arithmetic | oversized literal E301 | minimum literal; min div/% -1 R001; zero divisor R002 | Interpreter and C agree on first fault |
| Float | real / and matching Float arithmetic | malformed E102/nonfinite literal E301/mixed E302 | subnormal, zero, ties, max finite, negative power | Bit/result/fault-span and canonical text parity |
| Text | UTF-8 scalar string | malformed escape E103 | embedded NUL, composed/decomposed text, empty | Byte-exact output; scalar indexing |
| Bool/control | conditional and short circuit | Int condition E302 | untaken faulting RHS | Core If, no eager RHS |
| Bindings | captured immutable value | same-scope duplicate E202 | inner shadowing; initializer sees outer binding | Returned closure outlives creating frame |
| Lists/builtins | map/fold/at | heterogeneous list E302, empty inference E304 | negative index; empty map/fold; length overflow | Ordered traversal, builtin wrappers |
| Records | out-of-order named arguments | missing/extra/duplicate fields E303 | zero-field record | Written evaluation order, declaration storage order |
| Enums/match | nested Option[Bool] exhaustive | missing E310/useless E311/wrong pattern E312 | open Int/Text domain wildcard | Scrutinee once; tagged projection proof |
| Functions | mutual recursion and closure calls | wrong arity E303 | call-depth budget R003 | Explicit interpreter stack, native guarded depth |
| Modules | alias-qualified private/public usage | import cycle E205/private E206/escape E204 | same module via two aliases | Stable identity; one source snapshot |
| Machines | multiple states and inputs | data-only violation E407 | no guards/no emissions; keep writer | Ordinary generated step function |
| Snapshot reads | swap | unknown old name E203 | branch twice from same snapshot | Original state unchanged |
| Candidate reads | transitive DAG | duplicate E402/missing E401/cycle E404 | dead branch cycle; self edge | Exact stable plan and instruction order |
| Closure projection | bind candidate then capture value | direct next under closure E406 | immediately called lambda still illegal | Lexical edge before closure lifting |
| Guards | typed expected rejection | non-Bool E302 | multiple false guards; error expression faults | First false wins, later work skipped |
| Emissions | accepted values in source order | wrong emission type E302 | fault in second emission | No partial decision/stdout |
| Decision | acceptance/rejection matched | invalid generic parameters E307 | manually constructed result is ordinary data | No proof/authenticity claim |

## Property tests with concrete payoff

Use Hypothesis, bounded strategies and shrinking. Source-coordinate round trips generate valid Unicode scalar strings with LF/CRLF. Lexer/parser fuzzing generates malformed token neighborhoods as well as arbitrary byte strings. Catch only documented user errors: an unexpected assertion/exception is a bug. Enforce maximum input size and time/step budgets outside the language.

Machine properties: (a) rejected state's value equals original; (b) old snapshot stays unchanged after success; (c) writer-declaration permutations preserve scheduled candidate semantics; (d) adding an old-read cycle is legal while adding a next-read cycle rejects; (e) guard failure prevents all later predicates/error expressions/emissions; (f) two steps from one snapshot do not interfere. The experiment validates a narrow version of these principles; production tests must run source through the real pipeline.

Native differential generators produce well-typed terminating programs from small typed constructors: bounded expressions, explicit if/match, finite lists/folds, and acyclic machine graphs. Track expected type and symbol environment during generation; do not rely on rejecting 99% random text. Keep safe-result strategies separate from deliberately faulting strategies. Include signed extrema, negative remainder and evaluation-order counterexamples. Use explicit seeds for CI/repro and retain minimized failures as readable `.tfd` cases. Generated Core verifier tests separately create bad dominance/type/tag facts.

Two executors share lowering, so equality alone can miss a shared compiler bug. Keep hand-derived expected transcripts, structure assertions on Core, and independent mathematical/oracle properties. Do not build a second full AST interpreter solely to obtain independence; the maintenance burden would dilute correctness work.

## Goldens and fixtures

Golden directories group minimal source, diagnostic JSON/text, AST/plan/Core dump, expected stdout bytes and exit status. Spans/codes and program output are contractual; prose wording can improve with reviewed snapshot updates. Dumps use root-relative paths and deterministic IDs. Never normalize arithmetic fault codes, source spans, program whitespace, or guard reasons out of comparisons. Normalize only documented nondeterministic host metadata when it is outside language behavior.

The example manifest is JSON schema version 1: `path`, `ready_after`, `mode` (`run`/`check`), optional exact `stdout`, optional `diagnostic`. A check fixture without diagnostic must succeed. Run R-codes require exit 3 and its stdout expectation; E-codes require exit 1. Valid run fixtures require exit 0. By M12 all manifest entries must be active and pass; a fixture becoming ready earlier is encouraged.

## Native and resource tests

M10 adds `scripts/test_native.py`: build a private test directory, run C harnesses with argv, timeouts and exact status checks; probe ASan/UBSan support and expose unavailable support as a visible gate result. Native tests create adversarial text and output paths as **data**, never shell commands. Inject allocation failure at each successful-allocation index in a small constructor/call case; confirm all owned roots release and no partial result returns. Test deep release chains without recursive destructors. Resource R003 limits are executor-specific and are not compared for exact coincidence.

For build safety, a fake compiler executable that exits nonzero is a test fixture; verify previously existing output remains byte-identical. Paths with spaces and shell metacharacters must not create extra processes/files. Do not run arbitrary external binaries fetched from test inputs.

## Gates and commands

```sh
.venv/bin/python scripts/dev.py check
.venv/bin/python scripts/audit_docs.py
.venv/bin/python -m coverage run -m pytest
.venv/bin/python -m coverage report
.venv/bin/python scripts/dev.py build
.venv/bin/python scripts/smoke_wheel.py
```

After M10 add `.venv/bin/python scripts/test_native.py`; after M11 run `tests/test_differential.py`; after M13 include scripted REPL sessions. Unit tests belong next to their phase by filename until volume warrants subdirectories. Mark native/property/slow tests with configured pytest markers. Regular check runs bounded properties; extended fuzzing has explicit duration/seed and does not block every trivial edit. Coverage identifies untested branches, but do not substitute a percentage target for semantic assertions. Optional stress expansion stops when the concrete risk/gate is adequately verified.

## Revision 2 course-grade acceptance tests

At lexer milestone: exhaustive examples for the full Sigma inventory, identifiers and keyword-vs-reserved overlay, at least four distinct lexical literal kinds (Int/Bool/Text/Char), Unit composite, comments both kinds (unterminated and nonnesting), noise connectors inside/outside their context, exponent/floor lexing and longest-match with `/` and `//`/`/*`, invalid lexemes, `.tfd` rejection, deterministic `Symbol Table.txt` output including comment/invalid spans. Validate the automata specification with table-driven or property-based transitions. At parser milestone: precedence/associativity, entrypoint clauses, `for` and nested `for`, noise phrase omissions, and E208 boundaries. At types/runtime milestones: Char, floor vs truncation on negative numbers, exponent overflow/negative power, staged output atomicity, input exhaustion, 0 and nested loops, and interpreter/C differential tests. Milestone M14 must run an explicit `scripts/course_audit.py` requirements manifest check and execute a classroom demonstration matrix; source docs alone never count as passing execution requirements.

## C01 numerical amendment evidence

All seven arithmetic and nine logical/relational spellings need independent
fixed inventories, maximal munch and exact report spans; the eleven-item audit
must be tied to runnable .tfd examples and actual Symbol Table.txt publication.
Float tests cover decimal/exponent DFA recovery, correctly rounded finite bits,
open patterns and rounded duplicate literals, exact signatures/conversions,
checked constants, fractional division, each sign pairing of div/%, powers,
subnormals and overflow. Use independent integer/Fraction oracles for rounding
and canonical 17-digit text; parser/formatter round trips alone are insufficient.

M08 verifies Float Core signatures/constants; M09 and M10/M11 implement primitive
checks and compare actual finite results, output bytes, faults and original
spans. Preserve short-circuit nonexecution and main output atomicity. Schema-2
ledger states separate specification/code/tests/review/final verification/blocked
reason; metadata never proves execution. Record platform and actual commands.
