# Compiler architecture

The production implementation uses Python 3.12–3.14, with **zero third-party runtime Python dependencies**. Dev dependencies are pinned in pyproject.toml and transitively locked in uv.lock. C17 is required only for native builds and native differential tests. Language execution never depends on a hosted service.

## Phase boundaries

| Component / intended modules | Input → output | Responsibility and dependency rules |
|---|---|---|
| `frontend/source.py` | path/bytes → SourceFile | Immutable byte snapshot, UTF-8 validation, newline index, IDs. Imports only stdlib. |
| `frontend/diagnostics.py`, `render.py` | data → text/JSON | Structured errors and separate rendering; depends on source only. |
| `frontend/tokens.py`, `lexer.py` | SourceFile → LexResult | Token kinds/literal payloads/spans; no semantic name lookup. |
| `frontend/ast.py`, `parser.py` | tokens → ParseResult | Immutable surface AST and recovery; no runtime values. |
| `analysis/modules.py`, `resolve.py` | module ASTs → ResolvedProgram | Load graph, IDs, scopes, export rules. Driver supplies source loading capability. |
| `analysis/types.py`, `check.py`, `patterns.py` | resolved program → TypedProgram | Canonical types, local checking, constants, coverage. |
| `analysis/machines.py` | typed machine → MachinePlan | Exactly-one-writer checks, lexical dependencies, cycle witnesses, stable schedule. |
| `core/nodes.py`, `lower.py`, `verify.py`, `dump.py` | typed program + plans → CoreProgram | Sole executable IR. Structured ANF, lifted closures, transition desugaring, verifier. |
| `execution/values.py`, `builtins.py`, `interpreter.py` | verified Core + entry → ExecutionResult | Reference semantics, explicit frame stack, checked primitives, no C/backend import. |
| `backend/c_nodes.py`, `c_emit.py`, `build.py` | verified Core → authored C AST → C text → executable | Structural emission, ABI calls, secure compiler invocation. No interpreter import. |
| `driver.py`, `cli.py`, `repl.py` | user request → pipeline result | Orchestrate, choose stop phase, render diagnostics, own filesystem/process I/O. |
| `runtime/` | C ABI calls → native values | Independent C17 runtime with no Python dependency. |

A directory currently containing a README is an explicitly allocated work boundary, not a completed layer. Add actual modules only in the owning task. Do not fill every directory with empty classes.

## Shared data contracts

Prefer frozen `@dataclass(slots=True)` records and enums/tagged unions. Use tuple collections in published IR/AST and mutable local builders within passes. IDs are distinct small wrappers (`SourceId`, `NodeId`, `SymbolId`, `TypeId`, `CellId`, `FunctionId`, `ValueId`); never mix source spelling with identity. A phase result contains either a valid value and diagnostics, or no value and diagnostics. If any error exists, do not invoke later phases. Warnings are structured but cannot mask errors.

Conceptual interfaces (not promised Python field ordering):

```python
lex(source: SourceFile) -> LexResult
parse(tokens: tuple[Token, ...]) -> ParseResult
resolve(modules: ModuleGraph) -> Result[ResolvedProgram]
check(program: ResolvedProgram) -> Result[TypedProgram]
plan_machine(machine: TypedMachine) -> Result[MachinePlan]
lower(program: TypedProgram, plans: Mapping[TypeId, MachinePlan]) -> Result[CoreProgram]
verify(program: CoreProgram) -> tuple[Issue, ...]
interpret(program: VerifiedCore, entry: FunctionId, limits: Limits) -> ExecutionResult
emit_c(program: VerifiedCore) -> CTranslationUnit
```

Use a lightweight immutable wrapper `VerifiedCore` constructible only by successful verification. Python cannot enforce this against malicious callers; it expresses a project invariant and simplifies interfaces. No globals that accumulate state between compilations. Stable dump ordering is required regardless of process hash randomization. Source buffers outlive all spans in a compilation session.

## Diagnostics

SourceFile retains filename/display name, source ID, original UTF-8 bytes, decoded scalar text and byte line-starts. SourceSpan is a half-open `[start_byte,end_byte)` pair tied to a SourceId, validated at creation. EOF is legal. SourceLocation is computed lazily as one-based line and Unicode-scalar column; CRLF is one line ending. Tabs count as one source column; human snippets expand to four-column tab stops with a separate display mapping. JSON spans always carry byte offsets and scalar coordinates; future LSP conversion to UTF-16 belongs to an adapter.

The M01 source API retains the owning immutable `SourceFile` in each span and
computes locations on request. Span endpoints must be UTF-8 scalar boundaries;
joins require the same snapshot. `scalar_index` and `byte_offset_for_scalar`
map between byte boundaries and scalar indices; `location` and `byte_offset`
map between bytes and one-based line/column coordinates. CR and LF in a CRLF
pair retain distinct scalar positions on the preceding line, and the next line
starts after LF. This preserves invertible original-byte coordinates without
normalizing the single line ending. EOF after a final LF is column 1 of the
following empty line. Display columns use four-column tab stops, with each
other scalar occupying one display column.

`SourceManager.add_bytes` creates a fresh identity per explicit byte load;
`load_path` caches canonical `Path.resolve()` paths, including rejected source
snapshots, for the session. A new manager is needed to observe edits on disk.
The driver retains responsibility for allowed roots, `.tfd` extensions, and
filesystem exceptions. Source validation returns `SourceLoadResult` with either
a valid source or immutable `SourceError` data (E001/E002/E003). Rejected bytes
cannot have a valid `SourceSpan`, so source errors carry their raw byte range
and original bytes directly. Direct `SourceFile` construction raises
`SourceValidationError` containing the same data. Validation checks encoding,
then a leading BOM, then the first lone CR.

Diagnostic carries stable code, severity, message, primary label, zero or more secondary labels, notes/help, and optional machine-applicable edits (span + replacement). Labels may span files. Renderer owns color policy (`--color auto|always|never`), snippets and multiline clipping. Compiler phases must not print. Runtime faults carry an original operation span and ordered call frames; desugared guards/projections retain origins. C generated filenames must never replace user spans in ordinary diagnostics. JSON uses a versioned schema and no color. Deterministic sorting is by root-relative filename, primary start byte, code; multiple runtime frames preserve call order.

M02 implements diagnostic data in `frontend/diagnostics.py` and pure string
renderers in `frontend/render.py`. `ValidResult[T]` carries a value and an
error-free `DiagnosticReport`; `ErrorResult` requires an error and carries no
value. `DiagnosticBag` retains up to 100 diagnostics per primary source identity
by default, plus one suppression record per affected source. Suppressed errors
still make the report fail, even if all retained diagnostics were warnings.
Published reports/labels/notes/edits are immutable; insertion order controls
retention and rendering sorts retained diagnostics separately.

Schema-v1 JSON has `schema_version`, `has_errors`, `diagnostics` and `suppressed`
fields. Each diagnostic contains code/severity/message, primary/secondary
labels, notes/help and edits. Label spans include file, source ordinal,
`source_valid`, and start/end objects with `byte`, `line`, `column`. Rejected
source errors adapt to `RawSourceSpan`: byte offsets stay exact, `source_valid`
is false, and scalar line/column fields are null. No replacement-decoded fake
snapshot is introduced. Text displays these rejected ranges as bounded hex-byte
excerpts. Machine-applicable edits require valid source spans.

Rendering receives explicit `RenderContext` rather than consulting a terminal
or printing. Its optional root must be absolute so filename formatting cannot
depend on the process working directory. Automatic color requires an explicitly supplied TTY context;
JSON never contains renderer color sequences. Text escapes terminal controls,
expands tabs, clips long lines and multiline excerpts, and shows separate
snippets for overlapping or cross-file labels. Runtime call-frame collection
remains an execution-phase responsibility; M02 does not implement runtime faults.

## Lexical inspection API (M03)

`frontend/tokens.py` defines immutable token/trivia records and exact keyword,
operator and reserved-name inventories. `DecimalMagnitude.digits` stores a
canonical unsigned decimal spelling, avoiding host integer-conversion limits.
M06 owns signed bounds and the contiguous minimum-Int exception. Bool literals
use TRUE/FALSE token kinds with Boolean payloads; Text and Char carry decoded
scalar strings. Reserved type/prelude spellings remain IDENT tokens.

`frontend/lexer.py` explicitly scans Unicode scalars while constructing spans
from original byte boundaries. `LexResult` retains genuine tokens (including
INVALID recovery tokens and EOF), whitespace/comment trivia, and diagnostics.
Only `for_parser()` yields a successful token stream: any lexical error,
including one hidden by the retention cap, yields `ErrorResult`. Recovery and
course inspection therefore cannot feed invalid tokens into parsing.

`frontend/lexical_report.py` renders schema-v1 token JSON and a TSV educational
report over the same records. Token JSON stores every Int value as
`{"decimal": "digits"}` and includes kind, exact lexeme, decoded value,
error code, and original byte/scalar spans. The course report keeps genuine
parenthesis rows and adds explicitly marked Unit-shaped composite rows, even
across trivia, except after recognizable callee/parameter-ending tokens. This
is a lexical view rather than proof that the parser accepts a Unit expression.

Report `RESERVED_NAME` is a spelling overlay; declaration namespace checks remain
M05 work. `NOISE_WORD` applies to FROM/TO in an INPUT/OUTPUT-led lexical segment
followed by the appropriate STDIN/STDOUT and semicolon. Nested brace contexts
preserve an outer output segment. This does not prove main scope or valid
expressions; other FROM/TO occurrences remain KEYWORD. Comment/INVALID rows
retain exact spans, including errors suppressed from the diagnostic display.

The CLI owns `.tfd` and root validation, UTF-8/LF publication, diagnostic/color
context and filesystem exceptions. Explicit symbol-table output is written to a
temporary sibling then replaced; it cannot alias the source file. Output writes
flush inside the handled host-error path; a failed pipe is quieted before
process shutdown so host failures retain exit 2.

## Surface syntax API (M04)

`frontend/ast.py` holds frozen slotted syntax records with per-parse `NodeId`
ordinals paired with source identity. Groups, operator/literal/name spans,
written argument/arm/machine-clause order and original decimal magnitudes remain
explicit. It contains no resolved symbols, inferred types, schedules or executable
operations. Error nodes and `MissingToken` records are recovery data.

`parse(tokens, root_module=True, max_diagnostics=100)` consumes an ordered,
single-source, lexically successful EOF-terminated token stream. Imports must
later be parsed with `root_module=False`. Recursive descent owns declarations,
types, patterns and blocks; Pratt parsing owns operators/postfix forms. Root
public zero-argument main may contain outer input/output clauses; nested or
imported contexts diagnose E208. Executable return-type suitability and expression
types remain later-phase work. A bare Text input annotation is checked as a
grammar form, and mixed named/positional call arguments diagnose E112 without
guessing constructor identity.

`ParseResult` exposes an inspectable recovery `program`, diagnostics and inserted
zero-width `missing_tokens`; `for_resolution()` returns a valid result only when
no error exists, including suppressed errors. The parser preserves following
declarations during depth-aware synchronization and never raises the Python
recursion limit. `ParserResourceError` represents host nesting capacity, not a
fabricated source syntax error.

`ast_dump` returns schema-v1 JSON with file, `has_errors`, program and missing
tokens. Every syntax record uses `node_type` as its class discriminator, separate
from token/literal `kind` fields; IDs are deterministic ordinals. Original
byte/scalar spans and decimal-string payloads remain explicit. Recovery ASTs
may be dumped by the CLI but cannot pass the resolution gate. Dump recursion
capacity failures also remain host errors. ASTs are not an execution substrate.

## Resolution API (M05)

The driver owns a fresh compilation `SourceManager` and supplies its loading
capability to `analysis/modules.py`. Canonical root-relative paths form
`ModuleId`; imports are validated before normalization and resolved containment
checks. Published module records retain source snapshots, SHA-256 of those
original bytes, successfully parsed programs and import edges. The graph uses
dependency order and an iterative import traversal; aliases to the same path
share one module identity and one cached read. Import cycles retain their path
chain and original import labels. Entry filesystem/configuration failures remain
host errors; malformed/missing/escaping imports yield source diagnostics.

`analysis/resolve.py` publishes a `ResolvedProgram` retaining syntax plus immutable
ID tables for symbols, declaration bindings, references, nominal members,
type-dependent member references and closure captures. `TypeId` is a module and
declaration index; `SymbolId` adds a local/member ordinal. Type and value
namespaces are separate; records/machines also reserve constructor values,
while enum variants remain qualified. Prelude type and callable reservations
apply only to their declared namespaces. Public signature privacy follows
nested type syntax without checking expression types.

References distinguish types, values, old cells, inputs, candidate projections
and writer targets. Projections and named fields whose receiver requires M06
type information retain candidate member IDs and receiver NodeId, avoiding a
second spelling lookup after type selection. Machine cell members are
predeclared so forward uses do not depend on body traversal order. Lexical
captures retain free-local IDs in first-reference order; lowering must place
explicit captures in the Core contract's SymbolId order. Global functions are
not closure-environment captures.

`driver.resolve_source(entry, root=...)` returns a valid resolved program or structured
error result. Through M05 it performs no inference, body type/arity validation,
coverage, constant evaluation, nominal cycle checks, writer coverage or machine
scheduling. Libraries need no main. M05 CLI check was quiet and resolution-only; the explicit
API remains available independently as CLI check advances through later phases.
Successful resolution does not establish type correctness or executability.

## Type and constant API (M06)

`analysis/types.py` defines concrete structural types with preserved nominal
TypeIds, immutable nominal/builtin/capture/constant records and `TypedProgram`.
The checker owns a per-compilation TypePool; inference variables and Error forms
are internal recovery data. Successful output validates all node/symbol/builtin/
capture types, nominal signatures and nested constant children, then publishes
immutable mapping snapshots. No successful typed artifact may retain unresolved
metavariables or ErrorType.

`analysis/check.py` checks every reachable module declaration using resolved
IDs. Bidirectional contexts and finite fresh builtin schemes determine exact
types without user polymorphism. Member candidates select by receiver nominal
identity; nominal/signature cycles, data-only state and equality capabilities
are checked structurally. Machine writer/guard/rejection/emission types are
checked while duplicate writers, dead branches and candidate edges remain for
M07. Public-signature visibility remains the M05 responsibility.

`analysis/patterns.py` performs recursive ordered usefulness/exhaustiveness over
typed patterns. Finite constructor domains include Bool/Unit/enums/Option/
Decision; Int/Text/Char remain open and require residual wildcards/binders.
Witness constructor spellings must be reachable from the caller module, using
an import alias when needed. Invalid payload patterns retain safe recovery
types and cannot publish a successful TypedProgram.

`analysis/constants.py` validates the closed initializer form before evaluating
its pure constant subset. It does not interpret general programs. Literal
magnitude checks precede host integer conversion; contiguous-minus minimum-Int
origins remain explicit in expressions and signed patterns. Constant arithmetic
uses checked Int64 integer operations and the ADR 0010 real-division/Float
contract, with bounded checked exponentiation by squaring. Constant faults yield E306 at their original
operation spans; untaken short-circuit operands do not execute, but forbidden
syntax still invalidates an initializer.

`driver.type_source` resolves then type-checks, preserving `resolve_source` as an
independent phase API. At M06 acceptance CLI check stopped at types. M07 advances
`driver.check` through machine planning; the earlier phase APIs remain available.

## Machine plan API (M07)

`analysis/machines.py` consumes concrete `TypedProgram` and publishes immutable
`PlannedProgram(typed, plans)`. Plans are keyed by nominal TypeId; cell/input
identities remain resolved SymbolIds. `MachinePlan.cells` preserves declaration
order for snapshot storage, `writers` preserves written clauses, `schedule`
contains ASCII-minimum ready cells, and dependencies sort by source/target name.
Writer and ordered guard/error/emission records retain their original NodeIds
and spans for later lowering. No values are evaluated or guards proved.

Read sets distinguish old cells, candidate cells and the input, using resolved
identity. Unique sets sort by name; occurrence lists retain lexical traversal
order and original spans. Traversal includes all lexical branches/comprehension
bodies and does not enter helper declarations. Repeated projections create one
graph edge with every occurrence retained. Only writer candidate reads create
edges. Exact writers are validated before graph construction. Iterative SCC and
cycle-witness traversal excludes downstream blocked cells; Kahn uses a priority
queue and admits newly ready cells before each next selection.

`driver.check` returns a complete frontend `PlannedProgram` without requiring
main. Earlier phase failures stop before planning. `plan_dump` emits schema-v1
JSON: entry path, machine identities, cell order, writer origins/read sets,
dependency projections, exact schedule, ordered guard condition/error reads and
emissions. Filenames are root-relative and JSON escapes controls. The dump
explicitly states that guards are runtime checks and emissions publish only on
success. This artifact is explanatory and does not authorize execution; Core
lowering and verification remain the only future executor boundary.

## Numerical amendment (C01, verified frontend)

ADR 0010 adds finite binary64 Float without changing phase boundaries or machine
scheduling. Lexer/AST preserve decimal lexemes and original spans; the typed Float literal
map stores unsigned token bits, with negative-expression/pattern signs retained
separately for lowering to apply once; resolution
reserves the primitive/conversions using canonical prelude identities; types
and constants check exact domains and finite values. Numeric helpers implement
specified primitive arithmetic and exact canonical decimal formatting, not
general source evaluation. Float patterns remain open-domain equality cases.
M08 Core carries finite constant bits and concrete types; both later executors
consume verified Core and preserve operation/fault order. C17 representation,
rounding and subnormal behavior require actual capability probes and parity.

## Security and process control

Driver reads only the chosen source root. `build.py` invokes a resolved compiler executable via an argv list, `shell=False`, and a temporary directory. `--cc` accepts a single executable path/name, never a flag-containing command string. Extra compiler flags, if later supported, are repeated structured CLI values and explicitly documented. Do not interpolate source paths into shell commands or C identifiers. Escape every generated string literal by bytes; use numeric ID-based mangling. A build may replace only an explicitly requested output; write a temporary sibling and atomically replace it after successful compilation. A nonzero compiler exit preserves the existing output and reports captured, size-capped diagnostics. Runtime execution has a configurable timeout at the tool/driver boundary; generated programs have no sandbox escape APIs, but this compiler is not a security sandbox for arbitrary native binaries.

## Refactoring boundaries

Agents may reorganize private helpers, builders, serialization utilities and internal data layouts when all callers/tests are updated. Changes to accepted syntax, observable fault order, visibility, builtins, ownership ABI, or phase ownership require specification/ADR review. Interpreter and backend must not share the experiment module: it is independent evidence, not executable production truth.

## M08 publication boundary (active verification)

`driver.compile_source` preserves check/typing/resolution APIs, then lowers and
independently verifies Core. Successful library roots need no main; an executable
entry is optional metadata until run/build require it. `core` dumps only this
verified artifact. Malformed compiler IR yields structured internal Issues and
CLI exit70; ordinary source/host errors retain their previous distinctions.
Nominal layouts and builtin signatures are checked without consulting the typed
source. Owned containers snapshot to tuples and the verified handle cannot be
forged by ordinary construction/replacement. No source execution is implemented.
