# C17 compiler architecture

ADR 0011 replaces the Python-host implementation. All stages and the native
development driver target ISO C17. Only source/lexing/report/CLI exist now.

| Phase | Owned data and boundary | Status |
|---|---|---|
| Source | immutable UTF-8 bytes/indexes; spans borrow stable source | implemented lexer scope |
| Diagnostics | structured code/span; rendering separate from scanning | implemented lexical scope |
| Lexer | ordered tokens borrow source; result owns decoded literals/vectors | implemented |
| Parser/AST | arena-owned immutable nodes, stable node IDs | M04 pending |
| Modules/resolution | source capability, graph, symbols, visibility | M05 pending |
| Types/coverage | canonical type IDs, checked constants, patterns | M06 pending |
| Machine plan | one writer, lexical dependencies, cycles, ASCII schedule | M07 pending |
| Core | typed structured ANF, lifted closures, spans, verifier | M08 pending |
| Interpreter | only verified Core; explicit frames, checked primitives | M09 pending |
| Runtime/backend | explicit ownership ABI; structured C emission | M10/M11 pending |
| Driver | file/process capabilities, stopping phases, diagnostics | lexer only |

Constructors require fresh outputs and leave destroyable failure states. A source
must remain at a stable address while borrowed by tokens/spans. Destroy lexical
results before sources. Allocator context outlives every allocated owner. No
mutable compiler globals. Later phases publish immutable tables; use distinct
integer ID types, checked arithmetic, arena ownership and explicit destruction.
Errors prevent subsequent phases. Core verification must yield a distinct
executable handle. Never execute AST or unverified Core.

Language semantics remain normative in the dedicated specifications. In
particular plans collect next dependencies before optimization; all candidates
finish before ordered guards; emissions remain private until atomic success.
No later phase is implied by lexical acceptance. Runtime reference counting,
closures, numerical execution and fault unwinding require their own milestones.
