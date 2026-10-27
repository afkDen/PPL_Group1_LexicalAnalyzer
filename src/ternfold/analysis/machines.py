"""M07 lexical machine plans: writer coverage, SCC witnesses and stable Kahn order.

This pass consumes concrete TypedProgram data and preserves source expression
identities; it never evaluates, folds, lowers, or follows helper function bodies.
Read occurrences retain every original span while graph edges deduplicate pairs.
Graph traversal and syntax walking are iterative, independent of graph depth.
"""

from __future__ import annotations

import heapq
import json
from collections.abc import Mapping
from dataclasses import dataclass, fields
from types import MappingProxyType

from ternfold.analysis.resolve import ReferenceKind, SymbolId, TypeId
from ternfold.analysis.types import TypedProgram
from ternfold.frontend import ast as A
from ternfold.frontend.diagnostics import (
    Diagnostic,
    DiagnosticBag,
    ErrorResult,
    Label,
    Result,
    Severity,
    ValidResult,
)
from ternfold.frontend.render import RenderContext
from ternfold.frontend.source import SourceSpan


@dataclass(frozen=True, slots=True)
class Read:
    symbol: SymbolId
    kind: ReferenceKind
    node_id: A.NodeId
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class Reads:
    old_cells: tuple[SymbolId, ...]
    candidate_cells: tuple[SymbolId, ...]
    inputs: tuple[SymbolId, ...]
    occurrences: tuple[Read, ...]

    def __post_init__(self) -> None:
        for name in ("old_cells", "candidate_cells", "inputs", "occurrences"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class WriterPlan:
    cell: SymbolId
    node_id: A.NodeId
    span: SourceSpan
    expression: A.NodeId
    reads: Reads


@dataclass(frozen=True, slots=True)
class Dependency:
    source: SymbolId
    target: SymbolId
    projections: tuple[Read, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "projections", tuple(self.projections))


@dataclass(frozen=True, slots=True)
class GuardPlan:
    node_id: A.NodeId
    span: SourceSpan
    condition: A.NodeId
    error: A.NodeId
    condition_reads: Reads
    error_reads: Reads


@dataclass(frozen=True, slots=True)
class EmissionPlan:
    node_id: A.NodeId
    span: SourceSpan
    expression: A.NodeId
    reads: Reads


@dataclass(frozen=True, slots=True)
class MachinePlan:
    type_id: TypeId
    symbol: SymbolId
    node_id: A.NodeId
    span: SourceSpan
    input: SymbolId
    cells: tuple[SymbolId, ...]
    writers: tuple[WriterPlan, ...]
    dependencies: tuple[Dependency, ...]
    schedule: tuple[SymbolId, ...]
    guards: tuple[GuardPlan, ...]
    emissions: tuple[EmissionPlan, ...]

    def __post_init__(self) -> None:
        for name in ("cells", "writers", "dependencies", "schedule", "guards", "emissions"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class PlannedProgram:
    typed: TypedProgram
    plans: Mapping[TypeId, MachinePlan]

    def __post_init__(self) -> None:
        object.__setattr__(self, "plans", MappingProxyType(dict(self.plans)))


class _Planner:
    def __init__(self, typed: TypedProgram, cap: int) -> None:
        self.typed = typed
        self.resolved = typed.resolved
        self.bag = DiagnosticBag(cap)

    def name(self, symbol: SymbolId) -> str:
        return self.resolved.symbols[symbol].name

    def reads(self, expression: A.Expr, cells: frozenset[SymbolId]) -> Reads:
        occurrences: list[Read] = []
        stack: list[tuple[A.Node, bool]] = [(expression, False)]
        while stack:
            node, closure = stack.pop()
            if isinstance(node, (A.PathExpr, A.NextExpr)):
                reference = self.resolved.references[node.node_id]
                if isinstance(node, A.NextExpr):
                    if closure:
                        self.bag.add(
                            Diagnostic(
                                "E406",
                                Severity.ERROR,
                                "candidate projection underneath a closure",
                                Label(node.span),
                            )
                        )
                    elif reference.symbol_id not in cells:
                        self.bag.add(
                            Diagnostic(
                                "E403", Severity.ERROR, "unknown candidate cell", Label(node.span)
                            )
                        )
                if reference.kind in {
                    ReferenceKind.OLD_CELL,
                    ReferenceKind.CANDIDATE,
                    ReferenceKind.INPUT,
                }:
                    occurrences.append(
                        Read(reference.symbol_id, reference.kind, node.node_id, node.span)
                    )
            children: list[A.Node] = []
            for field in fields(node):
                value = getattr(node, field.name)
                if isinstance(value, A.Node):
                    children.append(value)
                elif isinstance(value, tuple):
                    children.extend(child for child in value if isinstance(child, A.Node))
            stack.extend(
                (child, closure or isinstance(node, A.ClosureExpr)) for child in reversed(children)
            )

        def symbols(kind: ReferenceKind) -> tuple[SymbolId, ...]:
            return tuple(
                sorted({read.symbol for read in occurrences if read.kind is kind}, key=self.name)
            )

        return Reads(
            symbols(ReferenceKind.OLD_CELL),
            symbols(ReferenceKind.CANDIDATE),
            symbols(ReferenceKind.INPUT),
            tuple(occurrences),
        )

    def components(
        self,
        cells: tuple[SymbolId, ...],
        adjacent: Mapping[SymbolId, tuple[SymbolId, ...]],
    ) -> tuple[tuple[SymbolId, ...], ...]:
        """Iterative Kosaraju; blocked acyclic descendants are not cycle members."""
        seen: set[SymbolId] = set()
        finished: list[SymbolId] = []
        for start in sorted(cells, key=self.name):
            if start in seen:
                continue
            seen.add(start)
            stack = [(start, 0)]
            while stack:
                cell, index = stack[-1]
                if index == len(adjacent[cell]):
                    finished.append(cell)
                    stack.pop()
                    continue
                child = adjacent[cell][index]
                stack[-1] = cell, index + 1
                if child not in seen:
                    seen.add(child)
                    stack.append((child, 0))
        reverse: dict[SymbolId, list[SymbolId]] = {cell: [] for cell in cells}
        for cell, children in adjacent.items():
            for child in children:
                reverse[child].append(cell)
        seen.clear()
        result: list[tuple[SymbolId, ...]] = []
        for start in reversed(finished):
            if start in seen:
                continue
            seen.add(start)
            members: list[SymbolId] = []
            pending = [start]
            while pending:
                cell = pending.pop()
                members.append(cell)
                for child in reverse[cell]:
                    if child not in seen:
                        seen.add(child)
                        pending.append(child)
            result.append(tuple(sorted(members, key=self.name)))
        return tuple(sorted(result, key=lambda component: tuple(map(self.name, component))))

    def cycle_witness(
        self,
        component: tuple[SymbolId, ...],
        adjacent: Mapping[SymbolId, tuple[SymbolId, ...]],
    ) -> tuple[SymbolId, ...]:
        allowed = frozenset(component)
        seen = {component[0]}
        active = {component[0]: 0}
        stack = [(component[0], 0)]
        while stack:
            cell, index = stack[-1]
            if index == len(adjacent[cell]):
                stack.pop()
                del active[cell]
                continue
            child = adjacent[cell][index]
            stack[-1] = cell, index + 1
            if child not in allowed:
                continue
            if child in active:
                return tuple(frame[0] for frame in stack[active[child] :]) + (child,)
            if child not in seen:
                seen.add(child)
                active[child] = len(stack)
                stack.append((child, 0))
        raise AssertionError("cyclic component has no cycle witness")

    def machine(self, declaration: A.MachineDecl, tid: TypeId) -> MachinePlan | None:
        cells = self.typed.nominals[tid].members
        cell_set = frozenset(cells)
        coverage: dict[SymbolId, A.WriterClause] = {}
        valid = True
        # Exactly-one-writer checks precede any graph construction.
        for clause in declaration.clauses:
            if not isinstance(clause, A.WriterClause):
                continue
            target = self.resolved.references[clause.node_id].symbol_id
            if target not in cell_set:
                self.bag.add(
                    Diagnostic(
                        "E403", Severity.ERROR, "unknown writer cell", Label(clause.name.span)
                    )
                )
                valid = False
            elif target in coverage:
                self.bag.add(
                    Diagnostic(
                        "E402",
                        Severity.ERROR,
                        f"duplicate writer for {self.name(target)!r}",
                        Label(clause.name.span),
                        (Label(coverage[target].name.span, "first writer is here"),),
                    )
                )
                valid = False
            else:
                coverage[target] = clause
        for cell in cells:
            if cell not in coverage:
                span = self.resolved.symbols[cell].span
                assert span is not None
                self.bag.add(
                    Diagnostic(
                        "E401",
                        Severity.ERROR,
                        f"missing writer for {self.name(cell)!r}",
                        Label(span),
                        help=(
                            f"retain old state with next {self.name(cell)} = {self.name(cell)};",
                        ),
                    )
                )
                valid = False
        if not valid:
            return None
        writers: list[WriterPlan] = []
        guards: list[GuardPlan] = []
        emissions: list[EmissionPlan] = []
        projections: dict[tuple[SymbolId, SymbolId], list[Read]] = {}
        for clause in declaration.clauses:
            if isinstance(clause, A.WriterClause):
                cell = self.resolved.references[clause.node_id].symbol_id
                reads = self.reads(clause.value, cell_set)
                writers.append(
                    WriterPlan(cell, clause.node_id, clause.span, clause.value.node_id, reads)
                )
                for read in reads.occurrences:
                    if read.kind is ReferenceKind.CANDIDATE:
                        projections.setdefault((read.symbol, cell), []).append(read)
            elif isinstance(clause, A.GuardClause):
                guards.append(
                    GuardPlan(
                        clause.node_id,
                        clause.span,
                        clause.condition.node_id,
                        clause.error.node_id,
                        self.reads(clause.condition, cell_set),
                        self.reads(clause.error, cell_set),
                    )
                )
            elif isinstance(clause, A.EmitClause):
                emissions.append(
                    EmissionPlan(
                        clause.node_id,
                        clause.span,
                        clause.value.node_id,
                        self.reads(clause.value, cell_set),
                    )
                )
        edges = tuple(
            Dependency(source, target, tuple(reads))
            for (source, target), reads in sorted(
                projections.items(), key=lambda pair: (self.name(pair[0][0]), self.name(pair[0][1]))
            )
        )
        adjacent_lists: dict[SymbolId, list[SymbolId]] = {cell: [] for cell in cells}
        indegrees: dict[SymbolId, int] = {cell: 0 for cell in cells}
        for edge in edges:
            adjacent_lists[edge.source].append(edge.target)
            indegrees[edge.target] += 1
        adjacent = {
            cell: tuple(sorted(children, key=self.name))
            for cell, children in adjacent_lists.items()
        }
        cyclic = False
        for component in self.components(cells, adjacent):
            if len(component) == 1 and component[0] not in adjacent[component[0]]:
                continue
            cyclic = True
            witness = self.cycle_witness(component, adjacent)
            labels = tuple(
                Label(read.span, f"{self.name(target)} depends on candidate {self.name(source)}")
                for source, target in zip(witness, witness[1:], strict=False)
                for read in projections[(source, target)]
            )
            self.bag.add(
                Diagnostic(
                    "E404",
                    Severity.ERROR,
                    "proposed-state dependency cycle: " + " -> ".join(map(self.name, witness)),
                    labels[0],
                    labels[1:],
                    help=(
                        "bare cell names read old state; next.cell reads a candidate "
                        "and creates a dependency",
                    ),
                )
            )
        if cyclic:
            return None
        ready = [(self.name(cell), cell) for cell in cells if indegrees[cell] == 0]
        heapq.heapify(ready)
        schedule: list[SymbolId] = []
        while ready:
            _, cell = heapq.heappop(ready)
            schedule.append(cell)
            for dependent in adjacent[cell]:
                indegrees[dependent] -= 1
                if indegrees[dependent] == 0:
                    heapq.heappush(ready, (self.name(dependent), dependent))
        assert len(schedule) == len(cells)
        return MachinePlan(
            tid,
            self.typed.nominals[tid].declaration,
            declaration.node_id,
            declaration.span,
            self.resolved.bindings[declaration.parameters[0].name.node_id],
            cells,
            tuple(writers),
            edges,
            tuple(schedule),
            tuple(guards),
            tuple(emissions),
        )

    def run(self) -> Result[PlannedProgram]:
        plans: dict[TypeId, MachinePlan] = {}
        for module in self.resolved.graph.modules:
            for index, declaration in enumerate(module.program.declarations):
                if isinstance(declaration, A.MachineDecl):
                    tid = TypeId(module.module_id, index)
                    plan = self.machine(declaration, tid)
                    if plan is not None:
                        plans[tid] = plan
        report = self.bag.report()
        return (
            ErrorResult(report)
            if report.has_errors
            else ValidResult(PlannedProgram(self.typed, plans), report)
        )


def plan_machines(program: TypedProgram, *, max_diagnostics: int = 100) -> Result[PlannedProgram]:
    """Plan all loaded machines, including unused imports; never require main."""
    return _Planner(program, max_diagnostics).run()


def plan_dump(program: PlannedProgram, context: RenderContext | None = None) -> str:
    """Deterministic schema-v1 JSON over static plans, without copying syntax."""
    context = context or RenderContext(root=program.typed.resolved.graph.root)
    symbols = program.typed.resolved.symbols

    def symbol_data(sid: SymbolId) -> dict[str, object]:
        return {
            "module": sid.module.path,
            "declaration_index": sid.declaration_index,
            "ordinal": sid.ordinal,
            "name": symbols[sid].name,
        }

    def span_data(span: SourceSpan) -> dict[str, object]:
        return {
            "file": context.filename(span.source.display_name),
            "start": {
                "byte": span.start_byte,
                "line": span.start.line,
                "column": span.start.column,
            },
            "end": {"byte": span.end_byte, "line": span.end.line, "column": span.end.column},
        }

    def origin(nid: A.NodeId, span: SourceSpan | None = None) -> dict[str, object]:
        return {"node_id": nid.value, "span": span_data(span or program.typed.origins[nid])}

    def read_data(read: Read) -> dict[str, object]:
        return {
            "symbol": symbol_data(read.symbol),
            "kind": str(read.kind),
            "origin": origin(read.node_id, read.span),
        }

    def reads_data(reads: Reads) -> dict[str, object]:
        return {
            "old_cells": [symbol_data(s) for s in reads.old_cells],
            "candidate_cells": [symbol_data(s) for s in reads.candidate_cells],
            "inputs": [symbol_data(s) for s in reads.inputs],
            "occurrences": [read_data(r) for r in reads.occurrences],
        }

    def cell_data(sid: SymbolId) -> dict[str, object]:
        span = symbols[sid].span
        assert span is not None
        return {"symbol": symbol_data(sid), "span": span_data(span)}

    def machine_data(plan: MachinePlan) -> dict[str, object]:
        return {
            "type_id": {
                "module": plan.type_id.module.path,
                "declaration_index": plan.type_id.declaration_index,
            },
            "symbol": symbol_data(plan.symbol),
            "origin": origin(plan.node_id, plan.span),
            "input": symbol_data(plan.input),
            "cells": [cell_data(s) for s in plan.cells],
            "writers": [
                {
                    "target": symbol_data(w.cell),
                    "origin": origin(w.node_id, w.span),
                    "expression": origin(w.expression),
                    "reads": reads_data(w.reads),
                }
                for w in plan.writers
            ],
            "dependencies": [
                {
                    "source": symbol_data(e.source),
                    "target": symbol_data(e.target),
                    "projections": [read_data(r) for r in e.projections],
                }
                for e in plan.dependencies
            ],
            "schedule": [symbol_data(s) for s in plan.schedule],
            "guards": [
                {
                    "origin": origin(g.node_id, g.span),
                    "condition": origin(g.condition),
                    "error": origin(g.error),
                    "condition_reads": reads_data(g.condition_reads),
                    "error_reads": reads_data(g.error_reads),
                }
                for g in plan.guards
            ],
            "emissions": [
                {
                    "origin": origin(e.node_id, e.span),
                    "expression": origin(e.expression),
                    "reads": reads_data(e.reads),
                }
                for e in plan.emissions
            ],
        }

    return (
        json.dumps(
            {
                "schema_version": 1,
                "phase": "machine-plan",
                "language_execution": False,
                "entry": program.typed.resolved.graph.entry.path,
                "notes": [
                    "Guards are runtime checks; this static plan does not prove they succeed.",
                    "All candidates precede ordered guards; "
                    "the first failed guard selects rejection.",
                    "Emissions publish only on success; runtime faults are not typed rejections.",
                ],
                "machines": [machine_data(plan) for _, plan in sorted(program.plans.items())],
            },
            ensure_ascii=True,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
