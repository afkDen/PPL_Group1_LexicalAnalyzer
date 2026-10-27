"""M05 identity and scope assertions; deliberately no type checking."""

from collections.abc import Iterator
from dataclasses import fields
from pathlib import Path

import pytest

from ternfold.analysis.resolve import (
    PRELUDE_TYPES,
    PRELUDE_VALUES,
    ReferenceKind,
    ResolvedProgram,
    SymbolKind,
)
from ternfold.driver import resolve_source as check
from ternfold.frontend import ast as A
from ternfold.frontend.diagnostics import ErrorResult, Result, ValidResult
from ternfold.frontend.source import SourceSpan


def resolve_text(tmp_path: Path, text: str) -> Result[ResolvedProgram]:
    entry = tmp_path / "lib.tfd"
    entry.write_text(text, encoding="utf-8")
    return check(entry)


def valid(tmp_path: Path, text: str) -> ResolvedProgram:
    result = resolve_text(tmp_path, text)
    assert isinstance(result, ValidResult), result.diagnostics
    return result.value


def nodes(node: A.Node) -> Iterator[A.Node]:
    yield node
    for item in fields(node):
        value = getattr(node, item.name)
        if isinstance(value, A.Node):
            yield from nodes(value)
        elif isinstance(value, tuple):
            for child in value:
                if isinstance(child, A.Node):
                    yield from nodes(child)


def syntax(program: ResolvedProgram) -> tuple[A.Node, ...]:
    return tuple(n for m in program.graph.modules for n in nodes(m.program))


def test_forward_functions_and_library_without_main(tmp_path: Path) -> None:
    entry = tmp_path / "lib.tfd"
    entry.write_text("fn first()->Int{second()} fn second()->Int{first()}", encoding="utf-8")
    result = check(entry)
    assert isinstance(result, ValidResult)
    assert len(result.value.references) == 4  # two result types, two callees


def test_initializer_sees_outer_and_sequential_lets_get_distinct_ids(tmp_path: Path) -> None:
    program = valid(tmp_path, "fn f(x:Int)->Int{{let x=x+1;let y=x;let _=y;x}}")
    uses = [n for n in syntax(program) if isinstance(n, A.PathExpr)]
    parameters = [n for n in syntax(program) if isinstance(n, A.Parameter)]
    bindings = [n for n in syntax(program) if isinstance(n, A.Binding)]
    param_id = program.bindings[parameters[0].name.node_id]
    inner_id = program.bindings[bindings[0].name.node_id]
    assert param_id != inner_id
    assert [program.references[n.node_id].symbol_id for n in uses] == [
        param_id,
        inner_id,
        program.bindings[bindings[1].name.node_id],
        inner_id,
    ]
    assert bindings[2].name.node_id not in program.bindings


@pytest.mark.parametrize(
    "text",
    [
        "fn f(x:Int,x:Int)->Int{x}",
        "fn f(x:Int)->Int{let x=1;x}",
        "fn f()->Int{let x=1;let x=x;x}",
        "fn f()->Int{let c=fn(x:Int)->Int{let x=1;x};0}",
        "fn f()->Int{0} fn f()->Int{1}",
        "record R{x:Int,x:Int}",
        "enum E{V,V}",
        "record R{} enum R{V}",
        "enum R{V} record R{}",
        "machine M(x:Int)yields Int rejects Text{state x:Int=0;next x=1;}",
        "machine M(x:Int)yields Int rejects Text{state y:Int=0;state y:Int=1;next y=x;}",
    ],
)
def test_same_scope_duplicates_label_use_and_prior(tmp_path: Path, text: str) -> None:
    result = resolve_text(tmp_path, text)
    assert isinstance(result, ErrorResult)
    error = next(d for d in result.diagnostics.diagnostics if d.code == "E202")
    assert len(error.secondary) == 1
    assert error.primary.span.original_bytes == error.secondary[0].span.original_bytes
    assert error.primary.span.start_byte > error.secondary[0].span.start_byte


@pytest.mark.parametrize(
    "text",
    [
        "fn f()->Int{let x=x;x}",
        "fn f()->Int{let _=missing;0}",
        "fn f()->Int{if true{let x=1;x}else{x}}",
        "fn f()->Int{let a=for x in [1]{x};x}",
        "fn f()->Int{match true{x=>{x},_=>{x}}}",
        "fn f()->Int{let a=fn(x:Int)->Int{x};x}",
        "enum E{V} fn f()->E{V}",
        "fn f(x:Missing)->Int{0}",
        "record R{x:Int} fn f()->Int{R::x}",
        "enum E{V} fn f()->E{E::Missing}",
    ],
)
def test_unresolved_scopes_and_paths(tmp_path: Path, text: str) -> None:
    result = resolve_text(tmp_path, text)
    assert isinstance(result, ErrorResult)
    assert "E203" in [d.code for d in result.diagnostics.diagnostics]


@pytest.mark.parametrize("spelling", PRELUDE_TYPES)
def test_type_reservations_do_not_ban_value_binders(tmp_path: Path, spelling: str) -> None:
    program = valid(tmp_path, f"fn f({spelling}:Int)->Int{{{spelling}}}")
    use = next(n for n in syntax(program) if isinstance(n, A.PathExpr))
    assert program.symbols[program.references[use.node_id].symbol_id].kind is SymbolKind.PARAMETER
    result = resolve_text(tmp_path, f"enum {spelling}{{V}}")
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E201"]


@pytest.mark.parametrize("spelling", PRELUDE_VALUES)
def test_callable_reservations_do_not_ban_types_or_qualified_members(
    tmp_path: Path, spelling: str
) -> None:
    valid(tmp_path, f"enum {spelling}{{Int,{spelling}}} fn f()->{spelling}{{{spelling}::Int}}")
    for text in (
        f"fn {spelling}()->Int{{0}}",
        f"record {spelling}{{}}",
        f"fn f({spelling}:Int)->Int{{0}}",
    ):
        result = resolve_text(tmp_path, text)
        assert isinstance(result, ErrorResult)
        assert "E201" in [d.code for d in result.diagnostics.diagnostics]


def test_overlapping_type_value_and_constructor_namespaces(tmp_path: Path) -> None:
    program = valid(
        tmp_path,
        """
        enum len { V, Int, len }
        fn Int()->Int{1}
        fn f(Int:Int)->Int{Int}
        fn g()->Int{let _=len::V;len([len::Int])+Int()}
        enum E{V} fn E()->Int{0} fn h()->E{let _=E();E::V}
        fn p()->Int{match 1{Int=>{Int}}}
    """,
    )
    references = program.references
    uses = [n for n in syntax(program) if isinstance(n, A.PathExpr)]
    ids = {n.span.text: references[n.node_id].symbol_id for n in uses}
    assert program.symbols[ids["len"]].kind is SymbolKind.BUILTIN
    assert program.symbols[ids["len::V"]].kind is SymbolKind.VARIANT
    assert program.symbols[ids["Int"]].kind in {SymbolKind.LOCAL, SymbolKind.FUNCTION}
    assert all(
        references[n.node_id].type_id is not None
        for n in syntax(program)
        if isinstance(n, A.NamedType)
    )


def test_record_machine_constructor_and_nominal_ids(tmp_path: Path) -> None:
    program = valid(
        tmp_path,
        """
        record R{value:Int} enum E{V(R)}
        machine M(x:Int)yields Int rejects Text{state c:Int=0;next c=x;}
        fn make()->M{let r=R(value:1);let _=E::V(r);M()}
    """,
    )
    namespace = program.namespaces[0]
    assert namespace.types["R"] == namespace.values["R"]
    assert namespace.types["M"] == namespace.values["M"]
    assert "E" not in namespace.values
    uses = {
        n.span.text: program.references[n.node_id]
        for n in syntax(program)
        if isinstance(n, A.PathExpr)
    }
    assert uses["E::V"].type_id == program.symbols[namespace.types["E"]].type_id
    assert uses["R"].type_id != uses["M"].type_id
    argument = next(n for n in syntax(program) if isinstance(n, A.Argument) and n.name is not None)
    field = next(s for s in program.symbols.values() if s.kind is SymbolKind.FIELD)
    assert program.member_references[argument.node_id].candidates == (field.symbol_id,)


def test_closures_capture_ids_in_lexical_order_transitively(tmp_path: Path) -> None:
    program = valid(
        tmp_path,
        """
        fn global()->Int{0}
        fn f(a:Int,b:Int)->Int{
            let c=fn(x:Int)->Int{
                let d=fn()->Int{b+a+x+b+global()};0
            };0
        }
    """,
    )
    closures = [n for n in syntax(program) if isinstance(n, A.ClosureExpr)]
    symbols = {s.name: sid for sid, s in program.symbols.items() if s.kind is SymbolKind.PARAMETER}
    assert program.captures[closures[0].node_id] == (symbols["b"], symbols["a"])
    assert program.captures[closures[1].node_id] == (symbols["b"], symbols["a"], symbols["x"])
    with pytest.raises(TypeError):
        program.captures[closures[0].node_id] = ()  # type: ignore[index]


def test_fresh_blocks_arms_comprehensions_and_input_binding_order(tmp_path: Path) -> None:
    program = valid(
        tmp_path,
        """
        pub fn main()->List[Text]{
            input x:Text from stdin;
            let y=for x in [x]{for x in [x]{x}};
            let _=if true{let x="inner";x}else{x};
            let _=match x{x=>{x},_=>{x}};
            output x to stdout; [x]
        }
    """,
    )
    inputs = [sid for sid, s in program.symbols.items() if s.kind is SymbolKind.INPUT]
    assert len(inputs) == 1
    uses = [n for n in syntax(program) if isinstance(n, A.PathExpr) and n.span.text == "x"]
    assert program.references[uses[0].node_id].symbol_id == inputs[0]
    assert program.references[uses[1].node_id].symbol_id != inputs[0]
    assert program.references[uses[-1].node_id].symbol_id == inputs[0]
    result = resolve_text(tmp_path, "pub fn main()->List[Text]{output x;input x:Text;[x]}")
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E203"]


def test_duplicate_pattern_binder_is_e312_and_other_arms_are_independent(tmp_path: Path) -> None:
    result = resolve_text(tmp_path, "enum E{V(Int,Int)} fn f(x:E)->Int{match x{E::V(a,a)=>{a}}}")
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E312"]
    error = result.diagnostics.diagnostics[0]
    assert isinstance(error.primary.span, SourceSpan)
    assert isinstance(error.secondary[0].span, SourceSpan)
    assert error.primary.span.text == error.secondary[0].span.text == "a"
    valid(tmp_path, "enum E{A(Int),B(Int)} fn f(x:E)->Int{match x{E::A(a)=>{a},E::B(a)=>{a}}}")


@pytest.mark.parametrize(
    "signature",
    [
        "pub fn f(x:List[Secret])->Int{0}",
        "pub fn f()->fn(Int)->Option[Secret]{fn(x:Int)->Option[Secret]{Option::None}}",
        "pub record Visible{field:List[Secret]}",
        "pub enum Visible{V(fn(Secret)->Int)}",
        "pub machine M(x:Secret)yields Int rejects Text{state c:Int=0;next c=0;}",
        "pub machine M(x:Int)yields Secret rejects Text{state c:Int=0;next c=0;}",
        "pub machine M(x:Int)yields Int rejects Secret{state c:Int=0;next c=0;}",
        "pub machine M(x:Int)yields Int rejects Text{state c:Secret=Secret();next c=c;}",
    ],
)
def test_public_exposed_positions_reject_nested_private_types(
    tmp_path: Path, signature: str
) -> None:
    result = resolve_text(tmp_path, "record Secret{} " + signature)
    assert isinstance(result, ErrorResult)
    errors = [d for d in result.diagnostics.diagnostics if d.code == "E207"]
    assert len(errors) == 1
    assert isinstance(errors[0].primary.span, SourceSpan)
    assert isinstance(errors[0].secondary[0].span, SourceSpan)
    assert errors[0].primary.span.text == errors[0].secondary[0].span.text == "Secret"


@pytest.mark.parametrize("order", [0, 1])
def test_forward_machine_members_are_predeclared_once_in_state_order(
    tmp_path: Path, order: int
) -> None:
    declarations = [
        "fn read(m:M)->Int{m.cell}",
        "machine M(r:Int)yields Int rejects Text{"
        "state cell:Int=0;state z:Int=1;next cell=r;next z=z;}",
    ]
    program = valid(tmp_path, " ".join(declarations if order == 0 else declarations[::-1]))
    machine = next(s for s in program.symbols.values() if s.kind is SymbolKind.MACHINE)
    assert machine.type_id is not None
    members = program.members[machine.type_id]
    assert len(members) == len(set(members)) == 2
    assert [program.symbols[sid].name for sid in members] == ["cell", "z"]
    projection = next(n for n in syntax(program) if isinstance(n, A.ProjectionExpr))
    assert program.member_references[projection.node_id].candidates == (members[0],)


def test_machine_old_input_candidate_and_writer_ids_remain_distinct(tmp_path: Path) -> None:
    program = valid(
        tmp_path,
        """
        machine M(delta:Int)yields Int rejects Text{
            state a:Int=0; state b:Int=0;
            next b=if false{next.a}else{a}; next a=delta;
            next a=a;
            guard next.b>0 else "no";
            emit b;
        }
    """,
    )
    uses = [
        (n, program.references[n.node_id])
        for n in syntax(program)
        if isinstance(n, (A.PathExpr, A.NextExpr, A.WriterClause))
    ]
    old_a = next(r for n, r in uses if isinstance(n, A.PathExpr) and n.span.text == "a")
    next_a = next(r for n, r in uses if isinstance(n, A.NextExpr) and n.span.text == "next.a")
    assert old_a.symbol_id == next_a.symbol_id
    assert old_a.kind is ReferenceKind.OLD_CELL
    assert next_a.kind is ReferenceKind.CANDIDATE
    assert sum(r.kind is ReferenceKind.WRITER for _, r in uses) == 3
    assert sum(r.kind is ReferenceKind.INPUT for _, r in uses) == 1
    # Dead branch projections and duplicate writers survive for M07 unchanged.
    assert sum(r.kind is ReferenceKind.CANDIDATE for _, r in uses) == 2


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("fn f()->Int{next.a}", "E405"),
        ("machine M(x:Int)yields Int rejects Text{state a:Int=next.a;next a=x;}", "E405"),
        ("machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=next.b;}", "E403"),
        ("machine M(x:Int)yields Int rejects Text{state a:Int=0;next b=x;}", "E403"),
        (
            "machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=(fn()->Int{next.a})();}",
            "E406",
        ),
    ],
)
def test_machine_context_diagnostics_belong_to_resolution(
    tmp_path: Path, text: str, code: str
) -> None:
    result = resolve_text(tmp_path, text)
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == [code]


def test_projection_before_closure_is_ordinary_capture(tmp_path: Path) -> None:
    program = valid(
        tmp_path,
        """
        machine M(x:Int)yields Int rejects Text{
            state a:Int=0;next a={let candidate=next.a;let f=fn()->Int{candidate+a+x};f()};
        }
    """,
    )
    capture = next(iter(program.captures.values()))
    assert [program.symbols[sid].kind for sid in capture] == [
        SymbolKind.LOCAL,
        SymbolKind.CELL,
        SymbolKind.INPUT,
    ]


@pytest.mark.parametrize(
    "text",
    [
        "fn f()->Int{true}",  # M06 body type
        "fn f()->Int{f(1,2)}",  # M06 arity
        "fn f()->Int{9223372036854775808}",  # M06 literal bound
        "fn f()->Int{match true{true=>{1}}}",  # M06 coverage
        "record R{r:R}",  # M06 nominal cycle
        "machine M(x:Int)yields Int rejects Text{state a:Int=1/0;next a=a;}",
        "machine M(x:Int)yields Int rejects Text{state a:Int=x;next a=a;}",
        "machine M(x:Int)yields Int rejects Text{"
        "state a:Int=0;state b:Int=0;next a=next.b;next b=next.a;}",
        "machine M(x:Int)yields Int rejects Text{state a:Int=0;state b:Int=0;next a=a;}",
    ],
)
def test_future_semantics_are_not_silently_pulled_into_m05(tmp_path: Path, text: str) -> None:
    valid(tmp_path, text)


def test_resolution_suppression_still_blocks_handoff(tmp_path: Path) -> None:
    from ternfold.analysis.resolve import resolve

    program = valid(tmp_path, "fn f()->Int{0}")
    # A valid graph remains reusable; resolve with a zero diagnostic budget must
    # still fail on its own bad reference rather than produce a partial program.
    entry = tmp_path / "bad.tfd"
    entry.write_text("fn f()->Int{unknown}", encoding="utf-8")
    from ternfold.analysis.modules import load_modules
    from ternfold.frontend.source import SourceManager

    graph = load_modules(entry, tmp_path, SourceManager().load_path)
    assert isinstance(graph, ValidResult)
    result = resolve(graph.value, max_diagnostics=0)
    assert isinstance(result, ErrorResult)
    assert result.diagnostics.diagnostics == ()
    assert result.diagnostics.suppressed[0].error_count == 1
    assert isinstance(resolve(program.graph), ValidResult)
