# Core: one typed, structured, administrative-normal-form IR

Core is justified by removing machine scheduling/guards and pattern matching exactly once. Both interpreter and C backend execute its simpler ordered semantics. It is not a textual substitution layer, a bytecode, or LLVM clone. It retains structured conditionals to generate inspectable C without requiring CFG reconstruction.

## Schema and invariants

A CoreProgram contains a type table, immutable constant pool, ordered CoreFunctions and metadata. Each function has FunctionId, named typed parameters, an explicit capture parameter tuple, result type, and a Block. A Block contains ordered `Let(ValueId, Type, Operation, Origin)` bindings and exactly one terminator: `Yield(ValueId)` or `Unreachable`. Unreachable is permitted only in a branch whose accumulated verified tag facts have an empty possible-tag set; it has no ValueId and does not impose a result type. All reachable branches must yield the enclosing operation's declared result type. A normal function entry cannot be unreachable. IDs are function-unique. Operands must be earlier definitions, parameters/captures, or enclosing-block definitions. A nested block cannot leak its private IDs. Branch results are bound by the enclosing operation; no phi nodes are necessary. Blocks are not source expression statements.

Operations and required checks:

| Operation | Semantics / verifier obligation |
|---|---|
| `Const(constant_id)` | Exact declared type; literal is representable, Float bits finite/zero canonical |
| `Unary(op,v)` / `Binary(op,a,b)` | Only non-short-circuit primitive operators with exact operand/result types, including ADR 0010 numeric rules |
| `Record(type_id, field_values)` | Declaration-order fields, exactly one per field |
| `Variant(type_id, tag, payloads)` | Correct instantiated enum/Option/Decision layout and arity |
| `List(element_type, values)` | Homogeneous element types |
| `Project(v, field_index)` | Record or machine field; valid index and result type |
| `Tag(v)` | Enum-like value to an internal tag type, never a source Int |
| `Payload(v, tag, index)` | Dominated by a proof that v has tag; checked payload type |
| `If(test, then_block, else_block)` | Bool test, only selected block runs, equal branch result types; direct Bool branch facts refine that same ValueId |
| `SwitchTag(v, cases, default)` | Distinct valid tags; exhaustive or explicit unreachable default; branch results same type |
| `Call(function_id, args)` | Exact known signature; arguments are already evaluated values |
| `Closure(function_id, captures)` | Closed lifted code with ordered capture types |
| `CallClosure(callee, args)` | Exact function type; no host callable/source evaluation |
| `Builtin(id, type_args, args)` | One of the finite prelude operations, all type args concrete |
| `MachineValue(type_id, cells)` | Internal-only nominal snapshot construction, data-only cells |
| `Unreachable` terminator | Only a branch proved to have no possible tag by verifier facts; no result binding or Yield; never replaces a possible fault |

There are no unresolved names, user pattern objects, `next` projections, implicit mutation, generic metavariables, AST error nodes, or machine-step opcodes in Core. `step` lowers to a static call to the appropriate generated step function because the machine type is known. Closure calls remain dynamic. Constructor invariants and tags are validated by the Core verifier, which must reject maliciously constructed in-memory IR in tests.

Verifier tracks lexical scope/dominance and tag facts through SwitchTag branches. A Payload is legal only in a branch proving the exact source ValueId tag. If a variable is copied, proofs do not magically transfer unless an explicit alias rule is implemented and tested. A SwitchTag default is omitted only when its case tags cover every possible tag. An explicit Unreachable default is legal only under that same coverage proof. Missing Option::None with an Unreachable default is invalid Core. Literal comparisons do not establish empty source tag sets by themselves. Direct If on a Bool ValueId refines its possible false/true values in the two branches; repeated tests of that same ValueId can prove an empty Boolean branch. This does not transfer facts through arbitrary equality operations or copied values. Nested pattern matching lowers to nested switches; literal patterns lower to equality tests and If. Evaluation of scrutinees happens once.

## Lowering rules

- Bind source expression operands in their specified evaluation order before constructing an op. A callee is evaluated before arguments; record fields evaluate in written order but Record stores declaration order.
- `a && b` becomes `If(a, block(lower b), block(false))`; `||` analogously. Never use eager Binary for these.
- Blocks become ordered lets plus a yield; source bindings resolve to the resulting ID rather than inserting redundant Core values.
- A match becomes an ordered decision tree from the checked pattern matrix; no body or scrutinee is evaluated speculatively. A plain exhaustive enum match can use SwitchTag. Overlapping patterns retain source priority.
- A first-class prelude callable with a concrete expected function type lowers to a capture-free generated wrapper FunctionId, interned by builtin identity and concrete signature. Its body performs the typed Builtin call; a first-class step wrapper instead calls the generated step function for the concrete machine type. Record/machine/enum constructor function values are not supported: constructor syntax is usable only in direct construction, except nullary enum variants which are ordinary values. No executor-specific host builtin callable representation exists.
- Closures are lifted to uniquely identified functions; captures are explicit immutable values ordered by SymbolId. Recursion refers to top-level FunctionIds and does not create self-referential captures.
- A machine constructor builds its checked constants and MachineValue. Each declaration gets an internal step function taking old snapshot and input. Entry code projects old cells first; candidate writers lower in MachinePlan order. Candidate references become already-defined candidate ValueIds.
- After candidates, nested guard If nodes select either a Reject construction from the old snapshot or the continuation. A false branch evaluates only that guard's error expression. At the final continuation, lower emissions left to right, build their list and the candidate MachineValue, then build Accept. No partially built Accept escapes.

For the Bin example, schematic Core (notation is a dump design, not source grammar):

```text
step Bin(%old: Bin, %delta: Int) -> Decision[Bin,Int,Limit]
  %count = project %old .count
  %n_count = checked_add %count %delta
  %n_doubled = checked_mul %n_count 2
  %ok_low = ge %n_count 0
  %result = if %ok_low {
    %ok_high = le %n_count 10
    %high_result = if %ok_high {
      %out = list[Int] [%n_doubled]
      %new = machine Bin [count=%n_count, doubled=%n_doubled]
      %accepted = Decision.Accept(%new, %out)
      yield %accepted
    } else {
      %reason = Limit.AboveCapacity
      %rejected = Decision.Reject(%old, %reason)
      yield %rejected
    }
    yield %high_result
  } else {
    %reason = Limit.BelowZero
    %rejected = Decision.Reject(%old, %reason)
    yield %rejected
  }
  yield %result
```

The multiplication may fault before either guard: that follows the language. The graph is checked before folding any branches. Pure does not mean freely reorderable: arithmetic, allocation and calls may fault. Initial optimization is **off**. An optional constant-folding pass must preserve first language fault and may fold only proven safe operations; no hoisting across guards, short circuits, or branch boundaries. Resource-failure equivalence is excluded, but this is not permission to change deterministic language faults.

## Reference execution

Interpreter stores explicit tagged value classes (Python bool is not a Ternfold Int), an environment indexed by ValueId, and an explicit control/call frame stack to prevent Python RecursionError from becoming language behavior. Dispatch Core operations with exact Int bounds and integer quotient/remainder implemented without floating approximation. Real `/` uses ADR 0010 binary64 rules. Track step budget and language call depth; limit failures are R003. Frame contexts retain current source origin. Interpreter cannot consult TypedAST or reschedule a machine.

## Revision 2 lowering contract

Add Char literal/constant representation, checked power `^` and floor `div` operators to verified primitive typing. `for` lowers to a structural list iteration plan or a tail-recursive compiled helper with strict element order; final Core must remain structured, inspectable and type-verified (no AST interpreter shortcut). Main's surface input/output clauses lower into a generated hidden entrypoint adapter taking explicit immutable `List[Text]` input and producing a fully staged `List[Text]` result; the normal function `main` source still returns `List[Text]`. The output buffer is never written by Core; host I/O is after evaluation. No machine scheduler changes. The verifier must reject `input`/`output` operations reachable from pure function/machine Core. Backend and interpreter run the same verified Core. See ADR 0009 for language-evolution authority.

## Float Core amendment (ADR 0010, required before executor work)

Core represents concrete Float types and canonical finite constant bits. The
verifier checks arithmetic signatures independently: matching Int/Float for
`+ - *`, either numeric pair returning Float for `/`, Int-only `div`/`%`, and
Int exponent with Int or Float base for `^`. Bool short-circuits remain If;
numeric conversions/formatting are finite typed Builtin operations. Folded
constants must preserve specified rounding, fault order and source origin.

Float patterns lower through exact numeric equality and existing ordered If
branches, retaining wildcard residuals; Float is never a finite tag universe.
Machine cell layout and dependency scheduling are unchanged. Both executors
consume verified Core only, use the same operation order and fault spans, and
must implement rounding/finite/zero checks and exact canonical formatting.
Native constants use bit payloads, not reparsed source decimals. M08 verifies
these invariants with malformed hand-built Core; M09/M11 establish execution
and native parity. No successful Core admits NaN/infinity or noncanonical zero.

## Approved I/O-bearing main reference boundary

A root public `main` with any outer input/output clause is host-entry-only.
Source references to its resolved symbol are E208 (calls, function values,
recursion, closure/machine references); the generated adapter is not nameable.
A main without I/O remains callable. Apply the rule by identity, preserving
shadowed/unrelated names. Human-approved clarification is recorded in ADR 0009;
`tests/test_entry_boundary.py` supplies positive/negative regressions.

## Implemented M08 representation (verification active)

Frozen slotted records in core/nodes.py normalize all owned sequences into tuple
snapshots, including nested nominal payload rows. CoreProgram stores independent
nominal layouts, constants, functions and optional hidden entry ID; no AST,
TypedProgram or MachinePlan is available to executors. Debug Origin retains only
source NodeId/span/kind metadata. ValueIds are function-local; branch IDs are
unique but cannot escape lexical scope.

The allowed structural comprehension choice is ListMap(iterable, element, body),
which evaluates its iterable once, visits elements in order and creates a new
list. InputAt(snapshot,index) exists only in the hidden entry adapter; output
clauses lower into evaluated Text values and a final staged list concatenation,
never a printing primitive. Adapter calls/references are rejected by the verifier.
Source references to I/O-bearing main are rejected before lowering per the
approved boundary. Pure main remains callable through an ordinary user function.

verify returns structured invariant Issues with optional original Origin.
require_verified raises VerificationError on any issue and otherwise creates a
sealed VerifiedCore handle. A verifier failure in the CLI is internal exit70,
not a source error or host exit2. Direct handle construction and dataclass replace
cannot bypass verification. The verifier independently checks nominal cycles/
layouts/headers, finite canonical constants, exact signatures, dominance, payload
proofs and entry restrictions. The JSON dump uses schema_version1, root-relative
origins and deterministic function/value IDs. It remains data, not execution.
