"""M07 machine graph and phase boundaries through actual source typing."""

import random
from dataclasses import FrozenInstanceError
from itertools import permutations
from pathlib import Path

import pytest

from ternfold.analysis.machines import MachinePlan, PlannedProgram, plan_machines
from ternfold.analysis.resolve import ReferenceKind, SymbolId
from ternfold.driver import check, resolve_source, type_source
from ternfold.frontend.diagnostics import ErrorResult, Result, ValidResult
from ternfold.frontend.source import SourceSpan


def source(tmp_path: Path, body: str, prefix: str = "") -> Path:
    entry = tmp_path / "machine.tfd"
    entry.write_text(
        prefix + "machine M(x:Int)yields Int rejects Text{" + body + "}", encoding="utf-8"
    )
    return entry


def planned(tmp_path: Path, body: str, prefix: str = "") -> PlannedProgram:
    result = check(source(tmp_path, body, prefix))
    assert isinstance(result, ValidResult), result.diagnostics
    return result.value


def names(program: PlannedProgram, symbols: tuple[SymbolId, ...]) -> list[str]:
    return [program.typed.resolved.symbols[s].name for s in symbols]


def single(program: PlannedProgram) -> MachinePlan:
    assert len(program.plans) == 1
    return next(iter(program.plans.values()))


def test_newly_ready_cell_preempts_already_ready_cell(tmp_path: Path) -> None:
    entry = tmp_path / "machine.tfd"
    entry.write_text(
        "machine M(x:Int)yields Int rejects Text{"
        "state a:Int=0;state b:Int=0;state z:Int=0;"
        "next z=x;next a=next.b;next b=x;}",
        encoding="utf-8",
    )
    result = check(entry)
    assert isinstance(result, ValidResult), result.diagnostics
    plan = next(iter(result.value.plans.values()))
    symbols = result.value.typed.resolved.symbols
    assert [symbols[sid].name for sid in plan.schedule] == ["b", "a", "z"]


def test_snapshot_swap_old_cycles_are_not_dependencies(tmp_path: Path) -> None:
    program = planned(
        tmp_path, "state left:Int=2;state right:Int=9;next right=left;next left=right;"
    )
    plan = single(program)
    assert names(program, plan.cells) == ["left", "right"]
    assert names(program, tuple(w.cell for w in plan.writers)) == ["right", "left"]
    assert names(program, plan.schedule) == ["left", "right"]
    assert plan.dependencies == ()
    assert [names(program, w.reads.old_cells) for w in plan.writers] == [["left"], ["right"]]
    assert all(not w.reads.candidate_cells for w in plan.writers)


def test_repeated_candidate_reads_one_edge_but_all_origins_retained(tmp_path: Path) -> None:
    program = planned(tmp_path, "state a:Int=0;state b:Int=0;next b=next.a+next.a+a;next a=x;")
    plan = single(program)
    assert len(plan.dependencies) == 1
    edge = plan.dependencies[0]
    assert names(program, (edge.source, edge.target)) == ["a", "b"]
    assert [r.span.text for r in edge.projections] == ["next.a", "next.a"]
    assert edge.projections[0].span.start_byte != edge.projections[1].span.start_byte
    assert names(program, plan.schedule) == ["a", "b"]
    assert names(program, plan.writers[0].reads.old_cells) == ["a"]
    assert names(program, plan.writers[0].reads.candidate_cells) == ["a"]
    assert [r.kind for r in plan.writers[0].reads.occurrences] == [
        ReferenceKind.CANDIDATE,
        ReferenceKind.CANDIDATE,
        ReferenceKind.OLD_CELL,
    ]
    assert names(program, plan.writers[1].reads.inputs) == ["x"]


def test_ascii_schedule_and_every_writer_permutation(tmp_path: Path) -> None:
    states = "state a:Int=0;state z:Int=0;state _a:Int=0;state A:Int=0;state b:Int=0;"
    writers = ("next a=next.b;", "next b=x;", "next z=1 div 0;", "next _a=2^-1;", "next A=0;")
    schedules = set()
    for permutation in permutations(writers):
        program = planned(tmp_path, states + "".join(permutation))
        schedules.add(tuple(names(program, single(program).schedule)))
    assert schedules == {("A", "_a", "b", "a", "z")}
    # Faulting body operators are typed syntax; this tests order, not execution.


@pytest.mark.parametrize(
    "expression",
    [
        "if false{next.a}else{0}",
        "if false&&(next.a==0){1}else{0}",
        "match true{true=>{0},false=>{next.a}}",
        "{let _=for y in range(0,0){next.a};0}",
        "{let _=for y in [next.a]{y};0}",
        "helper(next.a)",
        "{let f=if true{fn(y:Int)->Int{y}}else{let _=next.a;fn(y:Int)->Int{y}};f(0)}",
    ],
)
def test_lexical_self_edges_survive_dead_and_empty_paths(tmp_path: Path, expression: str) -> None:
    entry = source(tmp_path, f"state a:Int=0;next a={expression};", "fn helper(y:Int)->Int{y}")
    assert isinstance(type_source(entry), ValidResult)
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E404"]
    error = result.diagnostics.diagnostics[0]
    assert isinstance(error.primary.span, SourceSpan) and error.primary.span.text == "next.a"


def test_comprehension_projection_helper_and_shadowed_reads_use_ids(tmp_path: Path) -> None:
    program = planned(
        tmp_path,
        "state a:R=R(field:0);state b:Int=0;"
        "next b={let a=3;let _=for v in [next.a.field]{helper(v)};a};"
        "next a=R(field:x);",
        "record R{field:Int}fn helper(a:Int)->Int{a}",
    )
    plan = single(program)
    assert names(program, plan.schedule) == ["a", "b"]
    writer = plan.writers[0]
    assert writer.reads.old_cells == ()  # the local a is not the old cell a
    assert names(program, writer.reads.candidate_cells) == ["a"]
    assert [r.span.text for r in plan.dependencies[0].projections] == ["next.a"]


def test_guards_errors_emissions_keep_order_and_never_add_graph_edges(tmp_path: Path) -> None:
    program = planned(
        tmp_path,
        "state a:Int=0;state b:Int=0;next b=x;next a=x;"
        "guard next.b>a else int_text(next.a);"
        "guard next.a>b else int_text(b);emit next.b;emit a;",
    )
    plan = single(program)
    assert plan.dependencies == ()
    assert names(program, plan.schedule) == ["a", "b"]
    assert [names(program, g.condition_reads.candidate_cells) for g in plan.guards] == [
        ["b"],
        ["a"],
    ]
    assert [names(program, g.error_reads.candidate_cells) for g in plan.guards] == [["a"], []]
    assert [names(program, e.reads.candidate_cells) for e in plan.emissions] == [["b"], []]
    assert [names(program, e.reads.old_cells) for e in plan.emissions] == [[], ["a"]]
    clauses = next(m.program.declarations[0] for m in program.typed.resolved.graph.modules)
    from ternfold.frontend import ast as A

    assert isinstance(clauses, A.MachineDecl)
    guards = [c for c in clauses.clauses if isinstance(c, A.GuardClause)]
    assert [g.condition for g in plan.guards] == [g.condition.node_id for g in guards]
    assert [g.error for g in plan.guards] == [g.error.node_id for g in guards]
    emissions = [c for c in clauses.clauses if isinstance(c, A.EmitClause)]
    assert [e.expression for e in plan.emissions] == [e.value.node_id for e in emissions]


def test_bind_candidate_before_closure_is_safe_and_helper_bodies_not_propagated(
    tmp_path: Path,
) -> None:
    program = planned(
        tmp_path,
        "state a:Int=0;state b:Int=0;next b={let v=next.a;"
        "let f=fn()->Int{v+a+x};helper(f())};next a=x;",
        "fn helper(a:Int)->Int{a+a}",
    )
    plan = single(program)
    assert len(plan.dependencies) == 1
    assert names(program, plan.writers[0].reads.old_cells) == ["a"]
    assert len(plan.writers[0].reads.occurrences) == 3
    assert names(program, plan.schedule) == ["a", "b"]


@pytest.mark.parametrize(
    ("body", "codes"),
    [
        ("state a:Int=0;state b:Int=0;next a=a;", ["E401"]),
        ("state a:Int=0;next a=a;next a=x;", ["E402"]),
        ("state a:Int=0;state b:Int=0;next a=next.a;next a=x;", ["E402", "E401"]),
    ],
)
def test_writer_coverage_precedes_graph_with_use_and_prior_spans(
    tmp_path: Path,
    body: str,
    codes: list[str],
) -> None:
    entry = source(tmp_path, body)
    assert isinstance(resolve_source(entry), ValidResult)
    assert isinstance(type_source(entry), ValidResult)
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == codes
    for error in result.diagnostics.diagnostics:
        assert isinstance(error.primary.span, SourceSpan)
        if error.code == "E402":
            assert len(error.secondary) == 1
            assert error.secondary[0].span.start_byte < error.primary.span.start_byte
        else:
            assert error.primary.span.text == "b"


def test_cycles_only_label_real_witness_edges_not_blocked_descendants(tmp_path: Path) -> None:
    result = check(
        source(
            tmp_path,
            "state a:Int=0;state b:Int=0;state c:Int=0;state d:Int=0;"
            "next a=next.b;next b=next.a;next c=next.c;next d=next.a;",
        )
    )
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E404", "E404"]
    first, second = result.diagnostics.diagnostics
    assert "a -> b -> a" in first.message
    assert "c -> c" in second.message
    spans = [label.span for label in (first.primary, *first.secondary)]
    assert all(isinstance(span, SourceSpan) for span in spans)
    assert {span.text for span in spans if isinstance(span, SourceSpan)} == {"next.a", "next.b"}
    assert len(spans) == 2
    assert first.help and "old" in first.help[0]
    assert isinstance(second.primary.span, SourceSpan) and second.primary.span.text == "next.c"


def test_cycle_diagnostic_retains_duplicate_projection_spans(tmp_path: Path) -> None:
    result = check(source(tmp_path, "state a:Int=0;next a=next.a+next.a;"))
    assert isinstance(result, ErrorResult)
    error = result.diagnostics.diagnostics[0]
    assert error.code == "E404" and len(error.secondary) == 1
    assert error.primary.span.start_byte != error.secondary[0].span.start_byte


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ("state a:Int=0;next a=next.unknown;", "E403"),
        ("state a:Int=0;next unknown=a;", "E403"),
        ("state a:Int=next.a;next a=x;", "E405"),
        ("state a:Int=0;next a=(fn()->Int{next.a})();", "E406"),
        ("state a:Int=0;next a=true;", "E302"),
    ],
)
def test_prior_phase_failures_block_planner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: str,
    code: str,
) -> None:
    import ternfold.driver

    def forbidden(*args: object, **kwargs: object) -> Result[PlannedProgram]:
        raise AssertionError("invalid frontend reached machine planning")

    monkeypatch.setattr(ternfold.driver, "plan_machines", forbidden)
    result = check(source(tmp_path, body))
    assert isinstance(result, ErrorResult)
    assert code in [d.code for d in result.diagnostics.diagnostics]


@pytest.mark.parametrize("cap", [0, 2, 100])
@pytest.mark.parametrize("kind", ["missing", "duplicate", "cycles"])
def test_planner_caps_preserve_failure_without_partial_program(
    tmp_path: Path, cap: int, kind: str
) -> None:
    count = 105
    if kind == "duplicate":
        body = "state a:Int=0;next a=x;" + "next a=x;" * count
    else:
        body = "".join(f"state c{i}:Int=0;" for i in range(count + 1))
        body += (
            "next c0=x;"
            if kind == "missing"
            else "".join(f"next c{i}=next.c{i};" for i in range(count + 1))
        )
    typed = type_source(source(tmp_path, body))
    assert isinstance(typed, ValidResult)
    result = plan_machines(typed.value, max_diagnostics=cap)
    assert isinstance(result, ErrorResult)
    expected = count + (kind == "cycles")
    assert len(result.diagnostics.diagnostics) == min(cap, expected)
    assert len(result.diagnostics.suppressed) == 1
    assert result.diagnostics.suppressed[0].error_count == expected - cap


def test_small_graphs_against_exhaustive_topological_permutation_oracle(tmp_path: Path) -> None:
    rng = random.Random(707)
    cell_names = ("A", "_a", "a", "b", "z")
    for _ in range(90):
        count = rng.randrange(1, 6)
        cells = cell_names[:count]
        edges = {(a, b) for a in cells for b in cells if rng.randrange(7) == 0}
        valid_orders = [
            order
            for order in permutations(cells)
            if all(order.index(a) < order.index(b) for a, b in edges)
        ]
        body = "".join(f"state {name}:Int=0;" for name in cells)
        writer_order = list(cells)
        rng.shuffle(writer_order)
        for cell in writer_order:
            reads = ["next." + a for a, b in sorted(edges) if b == cell]
            body += f"next {cell}=" + ("+".join(reads) if reads else "x") + ";"
        result = check(source(tmp_path, body))
        if valid_orders:
            assert isinstance(result, ValidResult), result.diagnostics
            assert tuple(names(result.value, single(result.value).schedule)) == min(valid_orders)
        else:
            assert isinstance(result, ErrorResult)
            assert {d.code for d in result.diagnostics.diagnostics} == {"E404"}


@pytest.mark.parametrize("cycle", [False, True])
def test_deep_machine_graph_uses_iterative_traversal(tmp_path: Path, cycle: bool) -> None:
    count = 1100
    body = "".join(f"state c{i:04}:Int=0;" for i in range(count))
    body += "".join(
        f"next c{i:04}="
        + (f"next.c{i - 1:04}" if i else f"next.c{count - 1:04}" if cycle else "x")
        + ";"
        for i in range(count)
    )
    result = check(source(tmp_path, body))
    if cycle:
        assert isinstance(result, ErrorResult)
        assert [d.code for d in result.diagnostics.diagnostics] == ["E404"]
        assert len(result.diagnostics.diagnostics[0].secondary) == count - 1
    else:
        assert isinstance(result, ValidResult)
        assert len(single(result.value).schedule) == count


def test_plan_records_and_map_are_immutable(tmp_path: Path) -> None:
    program = planned(tmp_path, "state a:Int=0;next a=x;")
    plan = single(program)
    with pytest.raises(TypeError):
        program.plans[plan.type_id] = plan  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        plan.schedule = ()  # type: ignore[misc]


@pytest.mark.parametrize("cap", [0, 1, 100])
def test_diagnostic_caps_are_separate_for_each_imported_source(tmp_path: Path, cap: int) -> None:
    entry = tmp_path / "entry.tfd"
    entry.write_text('import "a.tfd" as a;import "b.tfd" as b;', encoding="utf-8")
    for name in ("a", "b"):
        (tmp_path / f"{name}.tfd").write_text(
            "machine M(x:Int)yields Int rejects Text{state a:Int=0;state b:Int=0;"
            "state c:Int=0;next a=next.a;next b=next.b;next c=next.c;}",
            encoding="utf-8",
        )
    typed = type_source(entry)
    assert isinstance(typed, ValidResult)
    result = plan_machines(typed.value, max_diagnostics=cap)
    assert isinstance(result, ErrorResult)
    assert len(result.diagnostics.diagnostics) == 2 * min(cap, 3)
    if cap < 3:
        assert len(result.diagnostics.suppressed) == 2
        assert len({s.source_id for s in result.diagnostics.suppressed}) == 2
        assert all(s.error_count == 3 - cap for s in result.diagnostics.suppressed)
    else:
        assert result.diagnostics.suppressed == ()
