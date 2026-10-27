# C17 implementation target (ADR0011)

# Ternfold 0.2 course-aligned language specification

Status: **implementation target, revision 2 (course alignment, 2026-10-15)**. The earlier 0.1 core is retained; the new syntax and boundary behavior below are normative. See ADR 0009 and `docs/course-requirements.md`. The repository implements the lexical source/span/diagnostic subset; broader M01–M03 phase acceptance, parsing and execution remain tracked separately. `docs/progress.md` is the implementation status authority. This document owns surface semantics; grammar, type rules, module rules, and runtime representation have focused companion documents. If they disagree, stop the affected feature, resolve the contradiction in these documents, and add a regression case; do not silently choose an implementation behavior.

## Identity and purpose

Ternfold (`.tfd`) makes a change of state an inspectable value: **propose together, validate in order, publish together**. A program can retain an old machine, try several inputs independently, inspect a rejection, and replay a sequence without undo code. Intended uses are local simulations, rule-driven workflows, interactive application models, parsers with explicit domain state, and deterministic event processors. The working name evokes a three-part transition folded over a sequence; it is provisional, not a claim of trademark or package-name clearance.

Three signature interactions define it:

1. Immutable nominal machine values contain snapshots; `step` never mutates its argument.
2. Every state cell has exactly one proposed update, with explicit `next.cell` dependencies checked for cycles and scheduled by the compiler.
3. Typed guards and delayed emissions give rejection a specified value-level meaning. The compiler makes old-state reads, candidate-state reads, validation order, and the acceptance boundary visible.

This combines precedents from synchronous languages, pure update functions, and transactional validation. It does not invent those concepts individually. There is no automatic ticking, shared-memory transaction manager, retry, hidden event loop, durability guarantee, or concurrency in 0.1.

Non-goals: operating-system programming, hard real-time guarantees, distributed execution, transparent persistence, ambient I/O inside pure functions/machines (entrypoint snapshot input and staged output are explicitly allowed), FFI, inheritance, macros, async, user-defined operators, general effect handlers, subtyping, higher-kinded types, user generics, nonfinite numeric values, and dependent types. Pure computation may diverge or fault: purity is not totality. A checked guard is a runtime condition, not a theorem proved by the compiler.

## Source and lexical contract

Source is valid UTF-8 without a BOM. Invalid encoding is E001; a BOM is E002. LF and CRLF are accepted; a lone CR is E003. Original bytes are retained. Whitespace is space, tab, LF, or CRLF, with no layout significance. Semicolons terminate bindings and machine clauses. Newlines never insert semicolons. `//` comments extend to the next newline or EOF. `/* ... */` is a non-nesting block comment (EOF before `*/` is E104). Line and block comments are discarded trivia but are preserved as report rows with source spans in the course symbol-table export. String interpolation does not exist. `//` is never integer division.

Identifiers match ASCII `[A-Za-z_][A-Za-z0-9_]*`, except the standalone `_` is a discard/pattern wildcard, not a referable name. Names are case sensitive. Leading or trailing underscores carry no visibility meaning. Keywords are exactly:

`as div else emit enum false fn for from guard if import in input let machine match next output pub record rejects state stdout stdin to true yields`

`Int Float Bool Text Char Unit List Option Decision` and prelude callable names are reserved in their applicable declaration namespace (E201 on redeclaration). `main` is a conventional entry point. `next` is always a keyword, never an identifier. Tokens use longest match: `:: -> => == != <= >= && || ++ /* */ //` before their single-character prefixes. Unsupported punctuation is E101. No integer bases, digit separators or raw strings exist; decimal Float syntax is defined below. `^` is an exponentiation operator. `div` is a keyword-operator for floor integer division. The quote pair for a `Char` scalar literal is single quotes (`'a'`); see below.

Decimal integer tokens are `0` or a nonzero digit followed by digits. Leading zeros are E102. Tokens hold an unsigned magnitude; the type checker validates signed 64-bit range. The contiguous expression `-9223372036854775808` is the only permitted positive-magnitude exception, recognized as unary minus on that literal. Parenthesizing the magnitude does not grant the exception. Every other positive literal above 9223372036854775807 is E301. Negating the minimum value at runtime faults R001.

Float literals have lexical form
`(0|[1-9][0-9]*)(\.[0-9]+([eE][+-]?[0-9]+)?|[eE][+-]?[0-9]+)`.
Their signs remain separate tokens. Float is finite IEEE 754 binary64 with
nearest/ties-even rounding, gradual underflow and normalized positive zero.
Convert well-formed literals once, preserving original lexemes/spans; a
nonfinite result is E301, while finite underflow is accepted. No NaN/Infinity
literal or value exists. A fractional dot is consumed only if followed by a
digit; `.5` and `1.` are not Float literals. Numeric e/E attempts an exponent
with at most one optional sign and required digits. A missing exponent digit,
identifier suffix, repeated exponent, or second dot followed by a digit is
E102. Invalid runs extend through ASCII alphanumeric/underscore and dots only
when followed by a digit; +/- joins only the exponent-sign position. Preserve
other punctuation, whitespace and comments. Thus `1.foo` is INT DOT IDENT,
`1.2.foo` FLOAT DOT IDENT, `1e++2` INVALID(`1e+`) PLUS INT, and `1efoo.bar`
INVALID(`1efoo`) DOT IDENT. Malformed syntax takes precedence over range checks:
`1e999foo` is E102 and well-formed `1e999` is E301. See ADR 0010.

The signed-Int pattern production uses the same range exception: a pattern
`-9223372036854775808` is valid only when the minus and magnitude are contiguous
in the original bytes. A space or comment between them yields E301 for that
otherwise oversized magnitude, just as in expressions. Whitespace between minus
and smaller representable pattern magnitudes is permitted. This clarifies the
shared literal range rule; it does not add grouping syntax to patterns.

Text is delimited by `"`. It contains Unicode scalar values, including non-ASCII directly. Only `\"`, `\\`, `\n`, `\r`, `\t`, and `\u{H...}` are escapes; the latter uses 1–6 hex digits, at most 10FFFF, excluding D800–DFFF. Raw control characters U+0000–001F and U+007F are forbidden, but may be represented with escapes. Unescaped newline, malformed escape, surrogate, or missing closing quote is E103. A `Char` literal contains exactly one Unicode scalar: e.g. `'A'`, `'ñ'`, `'\n'`, or `'\u{1F642}'`. The Text escape repertoire also applies to Char; zero or multiple scalars, bad escapes, unclosed Char, or raw controls are E105. `Char` is a distinct primitive value/type with equality, but no implicit Char/Text conversion. Text equality compares scalar sequences without normalization. The runtime stores UTF-8 plus byte length, preserving embedded NUL.

## Values and declarations

Values are immutable: Int, Float, Bool, Text, Char, Unit `()`, homogeneous `List[T]`, nominal records/enums, machine snapshots, and function closures. There is no null. Collections are finite. Static types do not expose object identity, pointer equality, memory addresses, or reference counts. Structural sharing is invisible.

A file contains imports then `fn`, `record`, `enum`, or `machine` declarations, optionally `pub`. No top-level executable statements or constants. Top-level function and type signatures are visible throughout their module, permitting direct/mutual function recursion. Local bindings are sequential and immutable:

```tfd
fn double(x: Int) -> Int {
    let result = x * 2;
    result
}
```

Function parameters and results require annotations. A local `let` annotation is optional and checks, rather than coerces, its initializer. A block consists of zero or more `let` bindings followed by exactly one final expression; even Unit must be explicit. No reassignment, implicit return, `return`, `break`, `continue`, or mutable variable exists. `let x = e;` is immutable assignment-style initialization, while `next cell = e;` is the sole machine-state writer. A `for` comprehension constructs lists without mutation. Only the root `main` body additionally permits explicit `input` and `output` boundary clauses (defined below). Bindings may shadow names from an outer lexical scope; duplicate names within the same scope are E202. Parameters and the outer function body's bindings share one scope. A binder is visible only after its initializer. `_` evaluates then discards its initializer and never introduces a symbol.

```tfd
record Point { x: Int, y: Int }
enum Direction { Left, Right }
enum Request { Move(Int), Reset }
```

Records have unique, ordered fields and use named construction: `Point(x: 2, y: 4)`. Every field appears exactly once; arguments may be supplied in any order and evaluate in their written order, then map to declaration-order storage. Field projection is `p.x`. There is no record update syntax; construct a new record. Enum constructors are qualified, e.g. `Request::Move(2)` and `Direction::Left` (no parentheses for a zero-payload variant). Enum payloads are positional. A declaration must have at least one enum variant; a record may have zero fields. User nominal data-type definitions must form an acyclic dependency graph, including through containers. Recursive functions are supported; recursive user data types are not in 0.1. Lists provide unbounded finite nesting without recursive declarations.

## Expressions and evaluation

Evaluation is strict, left to right, except specified conditional constructs and the machine scheduler. Callee evaluates before arguments. A call requires exact arity and types. No implicit currying, named function arguments, optional parameters, splats, or general conversions exist. The numeric `/` operator has the explicit conversion rule below. `if condition { ... } else { ... }` is an expression: condition must be Bool; branches must have equal types; only the chosen branch executes. Every `if` has `else`. `else if` must be written as an `if` inside the else block.

Precedence, strongest first:

| Level | Operators/forms | Association |
|---|---|---|
| 11 | calls, `.field` | left |
| 10 | `^` (Int exponent; checked Int or Float base) | right |
| 9 | unary `- !` | right |
| 8 | `* / div %` | left |
| 7 | `+ - ++` | left |
| 6 | `< <= > >=` | non-associative |
| 5 | `== !=` | non-associative |
| 4 | `&&` | left, short circuit |
| 3 | `||` | left, short circuit |
| 1 | `if`, `match`, anonymous `fn`, `for`, block | primary expression forms with delimited bodies |

The final row is a grammar category, not a binary binding power. These forms
are parsed as primaries and may occur as operands. Comparisons cannot chain
within a level (`a < b < c`, `a == b == c` are E111); `(a < b) == true` is
valid. `&&` evaluates its RHS only when the LHS is true, `||` only when false.
The professor's counts require seven arithmetic operations `+ - / * % div ^`
and nine Boolean/relational operations `&& || ! > < == != >= <=` independently;
assignment, concatenation and arrows do not count toward these inventories.

Int is checked signed 64-bit. `+ - *` accept matching Int or matching Float
operands and preserve that type; unary minus preserves its numeric type.
Ordering `< <= > >=` accepts matching Int or matching Float operands. Other
Int/Float mixing, including numeric equality, arguments and bindings, is E302;
use the explicit conversions in standard-library.md. Logical operators require
Bool. `++` concatenates matching Text values or lists of the same element type.

`/` is real division and always returns Float. Each operand may independently
be Int or Float; convert each Int to nearest/ties-even binary64, retain Float
operands, then perform one rounded division. Thus `5/2/2` is Float 1.25.
Large Ints above 2^53 may round before division. This is an explicit
operator-specific conversion, not exact rational arithmetic or general mixing.
Zero denominator is R002. Int minimum `/ -1` returns finite Float 2^63.

`div` and `%` are Int-only. `div` is the mathematical floor quotient (`-7 div 3`
is -3); `%` retains the dividend-sign remainder from the truncating quotient
(`-7 % 3` is -1, `7 % -3` is 1). The mathematical remainder identity uses the
truncating quotient, not `/` or floor `div`. Both reject zero with R002 and
Int minimum with divisor -1 with R001. There is no wrapped result or C UB.

`^` associates rightward and takes an Int exponent. Int bases require a
nonnegative exponent (R005 otherwise) and checked Int results. Float bases
allow negative exponents by taking a checked rounded reciprocal first; zero
base with negative exponent is R002. Exponent zero produces one after normal
operand evaluation, including `0 ^ 0`. Exact operation order: result=one,
factor=base or reciprocal, exponent magnitude held safely even for Int minimum;
while magnitude is nonzero, multiply/check result by factor if odd, halve the
magnitude, and square/check factor only if magnitude remains nonzero. Every
intermediate operation rounds/checks; never use platform `pow` or needlessly
square after the final bit. Float exponent operands are E302.

Float arithmetic uses binary64 nearest/ties-even after every primitive
operation. Nonfinite intermediate/results fault R001 at the original operator;
zero division faults R002; finite underflow/subnormals are permitted and zeros
normalize positive. No fused operations, NaN, infinity or ambient rounding mode
changes are language semantics. Faults remain distinct from typed rejection.
The canonical formatter and conversion rules are in standard-library.md;
ADR 0010 controls this authorized amendment.

Equality requires equal, equality-capable types: Int, Float, Bool, Text, Char, Unit, and recursively lists/records/enums/machines whose contents are equality-capable. Function types and any aggregate containing a function are not comparable (E305). Machine equality requires the same declaration identity and equal state cells. It does not compare transition code. Ordering is not automatically derived for aggregates. User-defined equality does not exist.

Indexing syntax `xs[i]` does not exist; `at(xs, i)` returns `Option[T]`, with negative or out-of-range index yielding `Option::None`. `len` counts list elements. Text operations are separately named in the prelude, avoiding implicit UTF-8 byte/scalar confusion. Iteration is explicit recursion or `fold`/`map`; their specified left-to-right traversal is observable through fault order.

Anonymous functions have full signatures: `fn (x: Int) -> Int { x + 1 }`. Closures capture free immutable values by value, with representation sharing allowed; captures remain valid after the creating call returns. Local recursive bindings are absent. Top-level mutually recursive functions use global function identities rather than cyclic captured environments. Functions cannot inspect their own identity.

## Pattern matching and expected failure

```tfd
match request {
    Request::Move(amount) => { amount },
    Request::Reset => { 0 }
}
```

Patterns are `_`, a binding, Bool/Int/Float/Text/Char/Unit literal, or qualified enum constructor with recursive payload patterns. No record/list destructuring, guards on arms, OR patterns, ranges, or repeated binders. Patterns select the first matching arm, bind only within that arm, and evaluate only its block. All arms have the same type. Matches must be exhaustive (E310). Provably useless arms are E311 errors. Finite enum/Bool/Unit domains are checked with a pattern matrix; open Int/Float/Text/Char domains require a binding/wildcard residual case. A record, list, function, or machine scrutinee can only be bound or ignored as a whole. Empty matches are invalid. An exhaustive match can still fault in its chosen body.

Expected failure is explicit data (`Option`, user enums, or `Decision`); no exceptions, `try`, propagation operator, or automatic conversion exists. Runtime faults abort evaluation and are not machine rejections. Programs cannot catch runtime faults in 0.2.

## Machines: the central abstraction

```tfd
enum Limit { BelowZero, AboveCapacity }

machine Bin(delta: Int) yields Int rejects Limit {
    state count: Int = 0;
    state doubled: Int = 0;
    next doubled = next.count * 2;
    next count = count + delta;
    guard next.count >= 0 else Limit::BelowZero;
    guard next.count <= 10 else Limit::AboveCapacity;
    emit next.doubled;
}
```

A machine declaration creates a nominal type and a zero-argument constructor `Bin()`. The header parameter is the **step input**, not a constructor parameter. Machines are not generic. Machine cell types must be data-only (no functions anywhere); referenced nominal types must obey the data dependency restrictions. State cells are publicly readable with `value.cell` when the machine type is public, but cannot be constructed or modified outside its generated constructor/step. Snapshot cloning needs no special operation: using the same immutable value twice is sufficient.

A machine body has four ordered sections: one or more `state` declarations, one or more `next` equations, zero or more guards, then zero or more emissions. There are no machine-level `let` declarations; use expression blocks or pure helper functions. Each state cell has exactly one unconditional syntactic next writer; retaining a cell is `next count = count;`. Conditional changes occur inside the writer expression. Missing, duplicate, or unknown writers are E401/E402/E403. The input and cell names must be distinct. Cell names shadow outer module names in machine expressions; use an import alias for disambiguation.

Initializers are closed constant expressions: scalar literals, lists, record/enum construction, unary and binary operators, and parentheses over those forms. They cannot reference bindings, input, cells, `next`, functions, machine constructors, closures, blocks, matches, or conditionals. Constant faults are E306. Initializers evaluate in cell declaration order when constructing a machine. All initial values are type checked. Transition guards do **not** constrain initialization; the programmer must choose a suitable initial state. Constructor values may be precomputed only when this preserves fault behavior.

Inside a next equation, guard, error expression, or emission:

- A bare cell name reads the old snapshot, throughout the entire step.
- `next.cell` reads the candidate value from that cell's writer.
- The header input name reads the single step input.
- `next` is not itself a value, cannot be aliased or passed, and cannot appear outside these contexts.
- `next.cell` beneath an anonymous function is E406. Compute the projection first with a block-local `let`, then capture that ordinary value if needed. Capture is by value, so this is safe and dependency extraction sees the read.
- Pure helper calls are permitted. Helpers receive candidate projections as ordinary arguments; helper bodies cannot access a caller's `next` context.

For each writer `b`, collect every lexical `next.a` in its expression, including dead conditional branches. Add dependency edge `a -> b`. All referenced cells need writers. Reject self edges and strongly connected components (E404), even if a runtime branch would avoid them. This intentionally conservative rule keeps the dependency plan independent of input values and optimization. A graph of old-state references is irrelevant to cycles: swapping two cells is legal. Schedule with Kahn's algorithm: repeatedly select the lexicographically smallest ready cell name using ASCII byte order. **This exact stable schedule determines candidate fault order**, including independent writers. Permuting writer declarations alone does not change results or which fault occurs. Renaming cells may change fault order and is a semantic change if faults are reachable.

### Step semantics

For machine declaration M with input I, output O, and rejection E:

`step : (M, I) -> Decision[M, O, E]`

`Decision::Accept(M, List[O])` and `Decision::Reject(M, E)` are the two variants. The variant type parameters are inferred from expected type/arguments; a local annotation resolves ambiguity. All parameters must be determined, or E304. There is no subtype conversion between machine types with matching layouts.

Operational order is exact:

1. Evaluate the step's machine argument, then input, as ordinary call arguments. Read the immutable old snapshot S.
2. Evaluate **all** candidate writers once, in compiler schedule order, creating private C. Reads of old state always read S; candidate projections read already computed entries of C. Any fault aborts with no decision.
3. Evaluate guard predicates in written order. On the first false guard, evaluate only its error expression and return `Reject(S, error)`. Later guards and every emission are skipped. A fault in a predicate/error expression aborts with no decision.
4. Once every guard succeeds, evaluate emissions in written order into a private list. A fault here also produces no decision; there is no visible partial output.
5. Return `Accept(M(C), emissions)`. The old value remains usable. Publication is the return of this complete value, not allocation of C.

There is no rollback machinery because nothing mutated. There is no guarantee about transitions involving multiple separately stepped machines being jointly accepted: composition must inspect inner decisions and explicitly decide its outer update. `step` may be used in any pure expression, including an outer machine writer. An inner accepted value/emission list has no external side effect and may be discarded if the outer transition rejects.

A rejected result contains exactly the original snapshot by value; emissions are structurally absent from Reject. Guards may mention old and proposed state, making transition relationships expressible. Guard order intentionally remains source order: the earliest domain reason wins. Candidate computations happen before guards, so a guard cannot prevent a fault in a candidate writer. Protect the risky expression with `if` **inside the writer** or model validation in the input type.

## Program boundary

Executable roots expose `pub fn main() -> List[Text]`. There is exactly one such root entry. Imported `main` declarations do not become entries. `check` may check library roots without main; `run` and `build` require it. The host driver evaluates main completely, then writes each returned Text in order followed by one LF, preserving any embedded newlines/NUL bytes. A runtime fault before the return writes no program stdout. OS output failures are host errors; byte writes cannot be rolled back after main returns. Only the root main boundary has explicit captured stdin and staged output clauses as specified below. No ambient clocks, randomness, environment, filesystem, processes, sockets, remote APIs or general stdin primitives exist. The CLI itself reads explicitly named source files and writes explicitly selected build outputs.

## Stability and evolution

This specification defines the complete Ternfold 0.2 target, including ADRs 0009–0010. Milestones may implement a documented subset, but must reject unsupported constructs explicitly; they must not reinterpret them. New effects, recursive data types, generics, memory management changes visible to programs, and alternative transition scheduling require an ADR. Experimental directions are listed separately in the roadmap and are not grammar extensions until specified.

## Course-aligned source model and input/output boundary (revision 2)

**Character set Sigma.** Outside Text/Char/comment contents, source syntax uses ASCII letters `ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`, digits `0123456789`, underscore `_`, quote marks `"` and `'`, operator/punctuation glyphs `+ - * / % ^ < > = ! & | . , ; : ( ) [ ] { }`, backslash `\` only for quoted escapes, plus whitespace SP, TAB, LF, CRLF. Source is UTF-8; string and character literal contents may contain any Unicode scalar allowed by the literal escape/control rules. The lexer must diagnose other source punctuation, not silently skip it. Source layout is **free-field**: spaces/tabs/newlines never implicitly terminate statements.

**Reserved identifiers and noise words.** Besides lexical keywords, the built-in names `Int`, `Float`, `Bool`, `Text`, `Char`, `Unit`, `List`, `Option`, `Decision`, `step`, `len`, `at`, `append`, `map`, `fold`, `range`, `int_text`, `float_text`, `int_float`, `float_int`, `bool_text`, `parse_int`, `text_len`, `text_at`, and `text_slice` are reserved in their documented namespaces. `from` and `to` are *lexically reserved readability connectors* (noise words): the phrases `from stdin` and `to stdout` are optionally permitted only after the matching entrypoint clauses; omitting a whole phrase changes neither type nor execution. `stdin` and `stdout` are reserved sink/source names, not general identifiers. A noise token alone is not a statement and is an error out of context.

**Character constants.** Int (`17`), Float (`1.5`), Bool (`true`), Text (`"hi"`), Char (`'q'`), and Unit (`()`) are distinct source-level literal types. Unit is recognized by the parser from `(` `)` and remains two separate delimiter rows in the educational token report. Thus five lexical literal families (INT, FLOAT, BOOL, STRING, CHAR) exist independently of Unit. The rubric requires at least four.

**Pure iteration.** `for item in list_expression { ... final_expression }` is a list-producing expression: evaluate the iterable once, require `List[T]`, traverse from first to last, bind each immutable `item: T` in a fresh iteration scope, evaluate the body with normal fault order, collect one body result per item into `List[U]`. No `break`, `continue`, mutable index, implicit printing, or side-effecting loop body exists. Nested `for` expressions naturally produce `List[List[U]]`. Empty input yields the empty list without evaluating the body. `for` is not allowed as a machine writer replacement; it is an expression inside any permitted expression position.

**Entrypoint-only input/output clauses.** `main` retains return type `List[Text]` and its zero-argument source signature. Its **outermost block only** additionally permits ordered `input name: Text;` and `output expression;` clauses before its final List[Text] expression. An optional readability phrase is `input name: Text from stdin;` or `output expression to stdout;`. The `input` clause creates an immutable Text binding by consuming the next entry from a **pre-captured, immutable vector of stdin lines**. No other input type is allowed; parse/convert with explicit pure builtins. Too few input lines is R006; extra lines are ignored. Capture has no language-visible side effects. Each `output` expression must have type Text and appends an immutable candidate to a private output buffer in written evaluation order. Only after the whole entrypoint evaluates successfully does the host write that buffer **followed by** the List[Text] returned by main. All other functions, machines, closures, and nested blocks forbid input/output clauses (E208). Both interpreter and C backend execute an equivalent hidden entrypoint adapter parameterized by input snapshot; re-running with the same captured inputs is deterministic. Host I/O errors are host failures, not typed rejections. If main evaluation faults, no program output is written. `emit` in a machine is unchanged (published only on accepted transitions).

**Educational lexer report.** The standalone analyzer writes an actual UTF-8/LF
file named exactly `Symbol Table.txt`, with exactly two tab-separated principal
columns `TOKEN TYPE` and `LEXEME`, source order, comments and INVALID rows.
Lexeme cells use reversible quoted escaping so multiline/control/Unicode text
stays exact in one row. Whitespace/EOF are omitted; Unit is two real paren tokens.
Examples include KEYWORD, RESERVED_WORD, NOISE_WORD, IDENTIFIER, INT_LITERAL,
FLOAT_LITERAL, BOOL_LITERAL, TEXT_LITERAL, CHAR_LITERAL, LINE_COMMENT,
BLOCK_COMMENT, ASSIGN, SEMICOLON and distinct operator/bracket token kinds.
The shared lexer retains structured tokens/spans/diagnostics. The compiler's
older rich TSV/API remains an internal inspection view, not the two-column
classroom adapter. Lexical errors never masquerade as valid AST nodes. All
source launchers reject non-`.tfd` inputs before reading. No regex tokenizer,
premade lexical analyzer, whole-input-word matcher or completed-identifier
keyword/reserved lookup is permitted: per-character DFA transitions and terminal
metadata drive name recognition. A source snapshot error yields a header-only
classroom report plus an original-byte diagnostic.


**Course examples:**
```tfd
fn grid(n: Int) -> List[List[Int]] {
    for row in range(0, n) {
        for col in range(0, 3) { row * 10 + col }
    }
}

pub fn main() -> List[Text] {
    input username: Text from stdin;
    let squared = 3 ^ 2;
    let quotient = -7 div 3;
    let greeting: Text = "Hello, " ++ username;
    output greeting to stdout;
    [int_text(squared), int_text(quotient)]
}
```

ADR 0009 adds syntax; ADR 0010 intentionally changes earlier `/` programs to real Float division. Integer-intent examples must explicitly use `div`, and fractional results use `float_text` or explicit conversion. The old `main` output model, scheduler, guard ordering, old-state/candidate semantics, and checked ownership contract remain unchanged. See the exact grammar in `docs/grammar.md` and recorded tradeoffs in ADRs 0009–0010.

## Approved I/O-bearing main reference boundary

A root public `main` with any outer input/output clause is host-entry-only.
Source references to its resolved symbol are E208 (calls, function values,
recursion, closure/machine references); the generated adapter is not nameable.
A main without I/O remains callable. Apply the rule by identity, preserving
shadowed/unrelated names. Human-approved clarification is recorded in ADR 0009;
C entry-boundary regressions are required in the owning implementation milestone.
