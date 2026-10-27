# Static type model

Normative companion to the language spec. The implementation is nominal, monomorphic for user declarations, and bidirectional locally. This is a deliberate complexity budget: algebraic data, higher-order functions, and machine results provide useful composition without user polymorphism or constraint solving.

## Representation

`Type = Int | Float | Bool | Text | Char | Unit | List(Type) | Option(Type) | Decision(M,O,E) | Record(TypeId) | Enum(TypeId) | Machine(TypeId) | Function(tuple[Type], Type) | ErrorType`.

TypeId is `(ModuleId, declaration index)`, never spelling alone. ErrorType is recovery-only, suppresses cascades, and is forbidden in a successful TypedProgram/Core. `Decision[M,O,E]` is permitted only when M is a machine and O/E are exactly its declared output/rejection types. A machine's input/output/error types may contain function values, but state fields may not. Input/output/error types may not recursively reference that same machine declaration, directly or transitively. These signature edges join the nominal dependency graph to avoid infinitely expanded Decision types. No type aliases or type-variable syntax exist.

A separate type namespace contains records/enums/machines and prelude types; values contain functions, local bindings, and generated record/machine constructor names. A record or machine reserves its spelling in both namespaces. Enum constructors live only under the enum qualifier. Import aliases cannot collide with either local namespace. Public signatures cannot expose private nominal types (E207). All record fields and enum variants of a public type are public; no per-field visibility.

## Judgments and inference

Use `Γ ⊢ e ⇒ T` to synthesize and `Γ ⊢ e ⇐ T` to check. Literals synthesize fixed primitive types; a name synthesizes its resolved symbol type. Annotated binders/parameters/results check. Local nonempty lists synthesize from their first element then check the rest; an empty list requires expected `List[T]`. A context can also supply an expected type for all elements. Missing expected type is E304, not implicit `Any` or Unit.

For calls, resolve the callee then check arguments in written order against parameter types. Function values require exact arity. Record constructors check named fields against declaration types. There is no general implicit conversion or variance (numeric `/` has its explicit operand rule): `List[A]` equals `List[B]` only when A equals B, and function parameter/result types compare exactly.

For `if` without an expected type, synthesize the then block and check the else block against it. With an expected type, check both. A `match` does the same using its first arm. This intentionally means `{ [] }` as the first branch cannot infer from a later `[1]`; annotate the containing binding/result. Function and closure bodies are always checked against their declared result.

Builtin generic call signatures are finite compiler-known schemes (standard-library.md). Instantiate fresh internal metavariables per use, unify constraints from an expected result and all arguments, then require all solved. Do not generalize local bindings. A bare polymorphic builtin as a function value requires a concrete expected function type; otherwise E304. Builtin constructors such as `Option::None` likewise require context. Record/machine/enum constructor names are not first-class function values; they are valid only in direct construction syntax (nullary enum variants are already ordinary values). A first-class builtin lowers to a capture-free typed wrapper function as specified in core-ir.md. Machine constructor calls synthesize a concrete machine type. `step(m,x)` first resolves the machine type, then checks x and synthesizes its exact Decision type.

Equality checks capability structurally; no type class machinery or user-defined capability resolution. Runtime faults do not add an effect to a function type. Every language function is computationally pure; the driver alone has I/O. Tail calls are not guaranteed to use constant stack in 0.1.

## Numerical types (ADR 0010)

Float is finite binary64, data-only and equality-capable. Int/Float literals
synthesize their distinct types; expected Float never silently changes an Int
literal into Float. Matching Int or Float operands are required for `+ - *`,
ordering and numeric equality. Unary minus preserves the numeric type. `/`
accepts either numeric type independently on each side and synthesizes Float,
with explicit nearest-even Int conversion. `div` and `%` require Int and return
Int. `^` requires an Int exponent; result follows Int or Float base. Other mixed
types are E302. `int_float`, `float_int` and `float_text` have fixed monomorphic
signatures; they are reserved value names. Function/record calls and container
unification retain exact types without widening.

Closed constants admit primitive numeric expressions and Float literals under
the same finite arithmetic rules; conversion/formatter builtin calls remain
forbidden by the closed initializer syntax. Nonfinite literals are E301;
constant operation faults are E306 at their original spans. Float patterns have
an open domain with equality after rounding/zero normalization; they need a
wildcard/binder residual, and equal rounded patterns are useless E311. No
successful TypedProgram or nested constant may contain a nonfinite Float,
ErrorType or unresolved metavariable. The Float literal map stores unsigned
token values as canonical Float64 payloads; AST unary-minus/signed-pattern
origins remain separate, and lowering applies each sign exactly once. Manually
constructed typed artifacts must also reject non-Float64 literal-map values.
Prelude family IDs must be constructed
from canonical identities; adding Float cannot shift Option/Decision behavior
through stale numeric indices.

## Machine environment and scheduling

Build all cell symbols and types before checking writer bodies. The contextual environment contains distinct old-cell symbols, an input symbol, and candidate-cell projection nodes; do not lower all three to ordinary name lookup. Projected candidate nodes retain target CellId and projection span. After type checking, extract lexical dependencies without constant folding. Every writer must return its cell's type. Guards check as Bool, rejection expressions as E, and emissions as O. Guards/emissions do not add graph edges between writers; they execute only after the candidate graph completes. Unknown projections and projections under closures have dedicated errors before cycle analysis.

Use Tarjan or DFS coloring for a cycle witness, and stable Kahn scheduling for execution. Report one cycle with all participating projection spans and a help note distinguishing `cell` from `next.cell`; report independent cycles if within diagnostic limits. Missing/duplicate writers are checked before graph construction. A writer assigned with a branch still counts as one writer, regardless of branches.

## Patterns and coverage

Pattern checking receives an expected scrutinee type. Constructor qualifier/type and payload arity must match. Each pattern binder adds a fresh symbol at the known payload type. A nested pattern matrix specializes enum constructors, Bool values, and Unit; literal Int/Text patterns only cover their exact values and never exhaust their open domains. For nondecomposable values only `_`/binder can cover. First compute usefulness in arm order, then compute a missing witness if the full matrix is not exhaustive. Render witnesses with `_` where an infinite payload remains. This catches `Option::Some(true), Option::Some(false), Option::None` without requiring a wildcard.

## Diagnostic contract

Int literal patterns use the same signed range and original-byte adjacency
exception as literal expressions. The minimum-Int pattern is valid only with
contiguous minus/magnitude; other oversized pattern magnitudes are E301. This
range validation precedes coverage, which must never receive an impossible Int
literal witness.

| Code | Meaning |
|---|---|
| E201–E202 | Reserved/duplicate declaration or same-scope binder |
| E203 | Unresolved name/path |
| E204 | Import not found or outside source root |
| E205 | Import cycle |
| E206 | Private export access |
| E207 | Public signature exposes private type |
| E301 | Int literal out of range or nonfinite Float literal |
| E302 | Expected/actual type mismatch, including non-Bool condition |
| E303 | Wrong call/constructor arity or record field set |
| E304 | Insufficient inference context/unresolved builtin metavariable |
| E305 | Equality not supported for this type |
| E306 | Invalid/faulting constant initializer |
| E307 | Recursive nominal type/signature graph or invalid Decision parameters |
| E310–E311 | Non-exhaustive match / useless arm |
| E312 | Invalid pattern type/arity or duplicate pattern binder |
| E401–E403 | Missing writer / duplicate writer / unknown writer or projection |
| E404 | Proposed-state dependency cycle |
| E405 | `next.cell` outside a machine transition context |
| E406 | `next.cell` underneath a closure |
| E407 | Function-containing state cell |

These categories are stable. Diagnostic messages can improve without changing codes. Labels must include the offending span, and a declaration/expected-type span when available.

## Revision 2: course requirements (normative)

Primitive `Char` is one Unicode scalar, equality-capable and distinct from `Text`, including in lists/records/patterns; it has no implicit conversion. `CHAR` literals are typed `Char`; Char patterns cover finite individual values but cannot exhaust the open Char domain without `_`/binder. `div` is Int × Int -> Int; `^` is Int × Int -> Int or Float × Int -> Float, with checked faults as in language-spec.md and ADR 0010. `for x in xs { body }` requires `xs: List[T]`, introduces immutable `x: T`, and infers `List[U]` from body `U`; the empty list and nested-loops cases require contextual typing as with list literals. Entrypoint-only `input` binds a `Text` symbol in source order; `output` requires Text and contributes to the staged main output, not the main final expression type. Disallow these clauses in other scopes (E208). `from` and `to` optional phrases and `stdin`/`stdout` are reserved/lexically recognized and not user nameable. Preserve old nominal/machine typing rules.

## Approved I/O-bearing main reference boundary

A root public `main` with any outer input/output clause is host-entry-only.
Source references to its resolved symbol are E208 (calls, function values,
recursion, closure/machine references); the generated adapter is not nameable.
A main without I/O remains callable. Apply the rule by identity, preserving
shadowed/unrelated names. Human-approved clarification is recorded in ADR 0009;
`tests/test_entry_boundary.py` supplies positive/negative regressions.
