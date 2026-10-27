> Design research history: language candidates remain useful; implementation selection is superseded by ADR0011.

# Design exploration and selection

Research performed 2026-09-13. This is a decision record, not a survey of every language. Examples for rejected candidates are exploratory sketches and are **not Ternfold syntax**. Assessments and scores are the project's design judgment, not measured benchmarks. No exhaustive originality or naming search is claimed.

## Problems worth addressing

Mutable application state often spreads a single conceptual change across sequential assignments. Readers must reconstruct which values are old, which are already changed, what happens on validation failure, and whether an output escaped before the change finished. Pure update functions solve much of this, but large record reconstruction still makes simultaneous versus dependent updates implicit. A language can expose these relationships and make the compiler verify their structure.

Other substantial opportunities are also real: effectful code hides capabilities; incremental computations duplicate work; protocol misuse is discovered too late; numerical code loses dimensions; and provenance disappears during data transformations. The task is choosing one coherent center rather than accumulating all six.

## Targeted precedent and influence

| Primary source | Relevant established idea | Lesson for this project |
|---|---|---|
| [Verimag: Lustre](https://www-verimag.imag.fr/The-Lustre-Programming-Language-and.html) | Synchronous dataflow and tooling for reactive systems | Dependency analysis is meaningful compiler work. Ternfold uses explicit calls and rejectable snapshots, not implicit clocks or real-time claims. |
| [Elm architecture guide](https://guide.elm-lang.org/architecture/) | A model updated in response to messages, with a pure application structure | Immutable state transitions can form a practical programming model. Explicit candidate reads/guards are Ternfold's additional language contract. |
| [Clojure refs and transactions](https://clojure.org/reference/refs) | Coordinated transactional state with validation under concurrency | Adopt all-or-nothing value publication; avoid importing STM's coordination/retry machinery into a single-threaded value language. |
| [Koka language book](https://koka-lang.github.io/koka/doc/book.html) | Typed effects, handlers, and a functional core | Explicit effects are powerful but would shift this project's difficulty into effect polymorphism and handler semantics. |
| [Differential Dataflow book](https://timelydataflow.github.io/differential-dataflow/) | Incremental computation over changing inputs | A change-centric language could be compelling, but correct retractions/iteration require substantially more runtime machinery. |
| [Idris 2 linear resources](https://idris2.readthedocs.io/en/latest/app/linear.html) | Linear usage can enforce resource protocols | Protocol safety is deep but asks beginners to reason about consumption across branches. |
| [F# units of measure](https://learn.microsoft.com/en-us/dotnet/fsharp/language-reference/units-of-measure) | Dimensions can be carried statically in numeric programs | Strong value per runtime cost, but too narrow as the only identity unless scientific computing is the explicit domain. |
| [Rust ownership chapter](https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html) | Ownership makes memory responsibilities explicit | Do not add a borrow checker to a language whose semantic center is immutable snapshots. |
| [LLVM frontend tutorial](https://llvm.org/docs/tutorial/MyFirstLanguageFrontend/index.html) | Explicit frontend stages and downstream native code generation | Learn phase boundaries; do not copy its tutorial language or make LLVM a prerequisite. |
| [WebAssembly core specification](https://webassembly.github.io/spec/core/) | A portable validated execution target with an explicit machine model | Useful future target, but source value representation, host integration, and debugging remain our responsibility. |

These are influences, not claims of equivalence. In particular, Ternfold is not a real-time synchronous language or a concurrent transaction implementation. Rejectable pure values alone are possible as libraries elsewhere. Its claimed design contribution is a coherent language integration of explicit old/proposed reads, statically scheduled writers, ordered rejection, and delayed emissions, with introspection as part of the toolchain.

## Candidate A — Ternfold: guarded transition values (selected)

**Philosophy:** make a state change inspectable before it becomes a new value. Style: pure functions plus nominal machine snapshots. Uses: simulations, local workflows, rule engines, replayable application models.

```tfd
machine Counter(delta: Int) yields Int rejects Text {
    state n: Int = 0;
    next n = n + delta;
    guard next.n >= 0 else "below zero";
    emit next.n;
}
```

Rules: old reads remain old; every cell has one writer; proposed reads form a DAG; guards are ordered; rejected transitions preserve old state and emit nothing. Distinctiveness comes from compiler-visible candidate dependencies interacting with value-level rejection.

Advantages: state semantics can be explained with one concrete example; useful static cycle and missing-writer diagnostics; immutable values enable replay/branching; easy-to-observe cross-backend invariants. Disadvantages: some applications need mutable I/O services; prevalidation does not suppress candidate faults; conservative lexical dependencies reject some safe conditional cycles. Learnability: moderate, primarily the old/next distinction. Compiler: medium, graph analysis and ordinary typed lowering. Runtime: low-to-medium, immutable aggregate values and RC in C. Risk: medium, especially fault order and ownership. Testing: algebraic rejection/replay properties, scheduler permutation tests, differential interpreter/C tests. Extensibility: composite machines, trace exploration, static relationships. Showcase: capacity-constrained inventory with paired cells, a rejected update, and two branches from the same snapshot.

## Candidate B — Undertone: capabilities as part of function composition

**Philosophy:** a function says what the world must provide. Style: functional computations with typed algebraic effects. Uses: testable applications, command-line tools, deterministic simulations of I/O.

```text
fn fetch_label(id: Id) -> Text ! {Store, Missing} {
    Store.read(id) otherwise Missing.raise(id)
}
with Store = memory_store, Missing = recover_label { fetch_label(key) }
```

Rules: effect rows propagate; handlers discharge operations; higher-order functions preserve effect variables; scoped resumptions cannot escape. Distinctiveness would come from capability-aware composition and inspectable handling, not from claiming to invent effects. Advantages: test doubles become language-level handlers, ambient authority shrinks. Disadvantages: effect errors can overwhelm users; multi-shot versus one-shot resumptions radically alter implementation. Learnability: high initial burden. Compiler: high (row unification, handler typing, continuation lowering). Runtime: high if resumable handlers; medium for limited abortive ones. Risk: high. Testing: handler nesting, captured continuations, effect inference, exception equivalence. Extensibility: concurrency and structured resources. Showcase: same business computation under real/replay/simulation handlers. Rejected because its strongest version spends the complexity budget before the compiler's basic usability is established.

## Candidate C — Delta Loom: values defined by changes

**Philosophy:** recompute only the consequences of an input change. Style: persistent relations and incremental queries. Uses: live reports, dependency analysis, incremental local indexes.

```text
relation Edge(from: Node, to: Node)
view Reach = fix R { Edge union join(R, Edge) }
apply { +Edge(a,b); -Edge(c,d) } => changes Reach
```

Rules: input updates form batches; derived views maintain deltas; retractions and recursive fixpoints have formal semantics; transactions expose stable query results. Distinctiveness: change propagation is the primary evaluation model. Advantages: excellent live demonstrations, useful optimization and provenance work. Disadvantages: bag/set semantics, negative updates, iteration, and memory reclamation are difficult interactions. Learnability: medium for queries, high for recursion/deltas. Compiler: high relational lowering and plan analysis. Runtime: very high. Risk: high. Testing: incremental/full-recompute equivalence, retraction cancellation, batch-order invariants. Extensibility: query planning and distributed dataflow. Showcase: update one edge and explain changed reachability. Rejected because reliable incremental semantics would dominate the project and constrain general programming.

## Candidate D — Relayglass: protocol-indexed values

**Philosophy:** only legal next actions should type-check. Style: linear resources with state-indexed transitions. Uses: parsers, staged builders, local service protocols.

```text
protocol Session { Closed --open--> Ready; Ready --send(Text)--> Ready }
fn greet(s: Session[Closed]) -> Session[Ready] {
    let ready = open(move s)
    send(move ready, "hello")
}
```

Rules: resource values used once; branches consume matching resources; transitions change static state; closure capture and containers preserve linear usage. Advantages: meaningful compiler safety, crisp invalid examples. Disadvantages: resource splitting, loops, and joins burden everyday code; recovering from errors complicates signatures. Learnability: high. Compiler: high control-flow/resource analysis. Runtime: low once checked. Risk: high at closure and error interactions. Testing: negative linearity corpus, branch-consumption matrices, protocol state reachability. Extensibility: session types and protocol visualization. Showcase: impossible out-of-order request rejected with a state path. Rejected because it approaches a second ownership language without a sufficiently distinct implementation advantage.

## Candidate E — Measureline: dimensioned computation with tolerances

**Philosophy:** numbers should retain the meaning that makes their operations valid. Style: numeric expressions with dimensions and explicit uncertainty. Uses: engineering notebooks, simulation configuration, unit-aware data pipelines.

```text
let distance = 24 @ metre ± 0.1
let duration = 6 @ second ± 0.02
let speed: metre/second = distance / duration
```

Rules: units normalize symbolically; affine units distinguish points from deltas; interval arithmetic is outward rounded; invalid dimension combinations are static errors. Advantages: low runtime overhead for erased units, visually persuasive diagnostics. Disadvantages: uncertainty propagation and floating-point rounding are subtle; units alone are established in other languages. Learnability: moderate domain knowledge. Compiler: medium-to-high dimension solving. Runtime: medium numerical correctness. Risk: high if intervals are promised, low for units alone. Testing: dimension identities, scale conversions, containment of exact rational results. Extensibility: vector spaces, symbolic expressions. Showcase: reject adding temperature points and demonstrate safe conversions. Rejected because a reliable uncertainty model is a substantial separate numerical project; removing it weakens the identity.

## Candidate F — Witnessleaf: explainable data transformations

**Philosophy:** computed data should carry an inspectable explanation. Style: typed transformations with compositional provenance. Uses: configuration explainers, local rule evaluation, audit-oriented data processing.

```text
let price = source("catalog", item.price)
let eligible = explain { price < limit && member.active }
why eligible
```

Rules: provenance nodes follow computations; selection records reasons; explanations have stable IDs; programmer can bound or redact origins. Advantages: immediate usefulness and rich compiler tooling. Disadvantages: explanation size explodes, control-flow provenance can reveal sensitive values, and optimizing without changing explanations requires a precise observational model. Learnability: low for basics, high for cost model. Compiler: medium. Runtime: high tracking/storage overhead. Risk: medium-to-high. Testing: evaluation erasure equivalence, explanation stability, bounded graph growth. Extensibility: interactive traces and query systems. Showcase: a compact decision graph explaining an outcome. Rejected as the central runtime model; bounded opt-in transition tracing is retained as an advanced Ternfold tool without automatic data provenance.

## Comparison and decision

Scores 1–5, higher is better. Delivery is the chance of reaching a polished complete language with the proposed host/backend. These are qualitative estimates; weighting favors semantic identity plus realizability.

| Candidate | Identity (30%) | User value (25%) | Delivery (25%) | Analysis/demo (20%) | Weighted |
|---|---:|---:|---:|---:|---:|
| A Ternfold | 5 | 4 | 5 | 5 | 4.75 |
| B Undertone | 4 | 5 | 2 | 5 | 3.95 |
| C Delta Loom | 5 | 4 | 2 | 5 | 4.00 |
| D Relayglass | 4 | 4 | 2 | 5 | 3.70 |
| E Measureline | 3 | 4 | 3 | 4 | 3.45 |
| F Witnessleaf | 4 | 4 | 3 | 5 | 3.95 |

Choose A. The decisive advantage is a small semantic center that creates real compiler responsibilities while permitting a transparent reference implementation. Static typing catches malformed transitions before execution; an explicit step call avoids a hidden scheduler; C provides native artifacts without delegating language semantics to the host. No subjective tie requires a user decision.

## Host and backend alternatives

| Host | Advantages | Costs | Decision |
|---|---|---|---|
| Python | Small explicit passes, fast iteration, strong test tools, inspectable data | Runtime slower; must implement Int/Bool semantics explicitly | Historical choice, superseded by accepted C17-only ADR0011 |
| Rust | Strong implementation invariants and efficient runtime | Lifetime/ownership implementation overhead competes with language design | Revisit only for measured frontend bottlenecks |
| OCaml | Natural ASTs and pattern matching | Adds less familiar packaging/toolchain to the handoff | Good alternative, no decisive delivery gain |
| TypeScript | Familiar tooling and JSON diagnostics | Numeric model and JS host behavior require care; no project-specific benefit | Reject for this project |

| Target | Semantics/control | Dependency/complexity | Portability/debugging | Decision |
|---|---|---|---|---|
| C17 | Explicit checked runtime and deterministic evaluation | Moderate backend; ordinary C compiler | Broad native reach; generated C and sanitizers inspectable | Select, whole-program, no C optimizer until semantics pass |
| Bytecode + VM | Full control; clean portable artifact | Moderate custom verifier/VM; duplicates executor work | Portable with VM; native executable less direct | Strong runner-up; not an additional 0.1 layer |
| WebAssembly | Explicit machine, portable embedding | Memory ABI and host integration still required | Good later browser demo, more tools today | Defer |
| LLVM | Strong optimization and tooling ecosystem | Heavy bindings/version/IR/runtime surface | Excellent native potential, more debugging layers | Defer until measured need |

Parser choice: recursive descent plus Pratt; grammar is expression-oriented and has no indentation ambiguity. IR choice: one structured ANF Core after a typed AST; machines lower away using a separately inspectable dependency plan. An AST interpreter would duplicate special machine semantics in both execution paths. A CFG/SSA optimizer is unnecessary for the initial structured C backend.

## Remaining risks and how they are bounded

1. **Originality:** the integration must be demonstrated, not marketed as unprecedented. Preserve explicit attribution above.
2. **Proposal fault order:** lexical scheduling is part of semantics. Do not let a hash map, source order, or optimization choose it accidentally.
3. **C ownership:** boxed immutable values need correct retains/releases across early exits. Verify with sanitizers and differential tests before optimization.
4. **Expressiveness:** monomorphic user declarations and data-only cells may be limiting. Validate the showcase and M12 applications before proposing extensions.
5. **Resources:** deterministic values do not imply identical out-of-memory behavior across executors. Resource failures are separately classified.
6. **Names:** Veyra was rejected after search found an existing language. Ternfold had no clear language match in this targeted search; do not infer legal clearance.
7. **No static invariant proof:** guards validate transitions dynamically. The compiler proves graph/typing/coverage properties only.
