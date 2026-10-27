"""M05 identity resolution, separate namespaces and lexical capture analysis.

No expression types, constructor arities, constants, pattern coverage or machine
plans are computed here. Syntax is retained with immutable ID side tables. A
type-dependent field selector carries candidate member IDs; M06 selects by the
receiver's nominal TypeId, rather than performing spelling lookup again.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from ternfold.analysis.modules import Module, ModuleGraph, ModuleId
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
from ternfold.frontend.source import SourceSpan
from ternfold.frontend.tokens import KEYWORDS

PRELUDE_TYPES = ("Int", "Bool", "Text", "Char", "Unit", "List", "Option", "Decision", "Float")
PRELUDE_VALUES = (
    "step",
    "len",
    "at",
    "append",
    "map",
    "fold",
    "range",
    "int_text",
    "bool_text",
    "parse_int",
    "text_len",
    "text_at",
    "text_slice",
    "int_float",
    "float_int",
    "float_text",
)
_PRELUDE = ModuleId("<prelude>")


@dataclass(frozen=True, slots=True, order=True)
class SymbolId:
    module: ModuleId
    declaration_index: int
    ordinal: int = 0


@dataclass(frozen=True, slots=True, order=True)
class TypeId:
    module: ModuleId
    declaration_index: int


# Explicit catalog preserves all previously accepted prelude identities when
# adding a primitive. Consumers compare IDs from this metadata, never ordinals.
PRELUDE_TYPE_IDS = MappingProxyType(
    {name: TypeId(_PRELUDE, index if index < 8 else 21) for index, name in enumerate(PRELUDE_TYPES)}
)
PRELUDE_VALUE_IDS = MappingProxyType(
    {
        name: SymbolId(_PRELUDE, index + 8 if index < 13 else index + 9)
        for index, name in enumerate(PRELUDE_VALUES)
    }
)


class SymbolKind(StrEnum):
    TYPE = "prelude-type"
    BUILTIN = "builtin"
    FUNCTION = "function"
    RECORD = "record"
    ENUM = "enum"
    MACHINE = "machine"
    VARIANT = "variant"
    FIELD = "field"
    CELL = "old-cell"
    IMPORT = "import"
    PARAMETER = "parameter"
    INPUT = "input"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class Symbol:
    symbol_id: SymbolId
    name: str
    kind: SymbolKind
    span: SourceSpan | None
    public: bool = False
    type_id: TypeId | None = None
    owner: TypeId | None = None
    target_module: ModuleId | None = None


class ReferenceKind(StrEnum):
    TYPE = "type"
    VALUE = "value"
    OLD_CELL = "old-cell"
    INPUT = "input"
    CANDIDATE = "candidate"
    WRITER = "writer"


@dataclass(frozen=True, slots=True)
class Reference:
    symbol_id: SymbolId
    kind: ReferenceKind
    type_id: TypeId | None
    path: tuple[SymbolId, ...]


@dataclass(frozen=True, slots=True)
class MemberReference:
    """M06-dependent selection. Empty candidates are not a lexical name error."""

    receiver: A.NodeId
    candidates: tuple[SymbolId, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ModuleNamespace:
    module_id: ModuleId
    types: Mapping[str, SymbolId]
    values: Mapping[str, SymbolId]


@dataclass(frozen=True, slots=True)
class ResolvedProgram:
    graph: ModuleGraph
    symbols: Mapping[SymbolId, Symbol]
    namespaces: tuple[ModuleNamespace, ...]
    bindings: Mapping[A.NodeId, SymbolId]
    references: Mapping[A.NodeId, Reference]
    members: Mapping[TypeId, tuple[SymbolId, ...]]
    member_references: Mapping[A.NodeId, MemberReference]
    captures: Mapping[A.NodeId, tuple[SymbolId, ...]]


@dataclass(slots=True)
class _Scope:
    parent: _Scope | None = None
    values: dict[str, SymbolId] = field(default_factory=dict)

    def find(self, spelling: str) -> SymbolId | None:
        scope: _Scope | None = self
        while scope is not None:
            if spelling in scope.values:
                return scope.values[spelling]
            scope = scope.parent
        return None


@dataclass(slots=True)
class _Namespace:
    types: dict[str, SymbolId] = field(default_factory=dict)
    values: dict[str, SymbolId] = field(default_factory=dict)


class _Resolver:
    def __init__(self, graph: ModuleGraph, cap: int) -> None:
        self.graph = graph
        self.bag = DiagnosticBag(cap)
        self.symbols: dict[SymbolId, Symbol] = {}
        self.namespaces = {module.module_id: _Namespace() for module in graph.modules}
        self.bindings: dict[A.NodeId, SymbolId] = {}
        self.references: dict[A.NodeId, Reference] = {}
        self.entry_only: set[SymbolId] = {
            SymbolId(module.module_id, index)
            for module in graph.modules
            if module.module_id == graph.entry
            for index, declaration in enumerate(module.program.declarations)
            if isinstance(declaration, A.FunctionDecl)
            and declaration.public
            and declaration.name.spelling == "main"
            and any(
                isinstance(s, (A.InputClause, A.OutputClause)) for s in declaration.body.statements
            )
        }
        self.members: dict[TypeId, list[SymbolId]] = {}
        self.member_references: dict[A.NodeId, MemberReference] = {}
        self.captures: dict[A.NodeId, tuple[SymbolId, ...]] = {}
        self.prelude = _Namespace()
        self.module_id = graph.entry
        self.declaration_index = 0
        # Each closure collects free locals in first lexical reference order.
        self.closures: list[dict[SymbolId, None]] = []
        self.local_depth: dict[SymbolId, int] = {}
        self.cells: dict[str, SymbolId] = {}
        self.transition = False
        self._prelude()

    def error(self, code: str, message: str, span: SourceSpan, prior: Symbol | None = None) -> None:
        self.bag.add(
            Diagnostic(
                code,
                Severity.ERROR,
                message,
                Label(span),
                (Label(prior.span, "declared here"),) if prior and prior.span is not None else (),
            )
        )

    def _prelude(self) -> None:
        for index, spelling in enumerate(PRELUDE_TYPES + PRELUDE_VALUES):
            is_type = index < len(PRELUDE_TYPES)
            type_id = PRELUDE_TYPE_IDS[spelling] if is_type else None
            symbol_id = (
                SymbolId(_PRELUDE, type_id.declaration_index)
                if type_id
                else PRELUDE_VALUE_IDS[spelling]
            )
            symbol = Symbol(
                symbol_id,
                spelling,
                SymbolKind.TYPE if is_type else SymbolKind.BUILTIN,
                None,
                True,
                type_id,
            )
            self.symbols[symbol.symbol_id] = symbol
            (self.prelude.types if is_type else self.prelude.values)[spelling] = symbol.symbol_id
        for type_name, variants in (
            ("Option", ("Some", "None")),
            ("Decision", ("Accept", "Reject")),
        ):
            owner = self.symbols[self.prelude.types[type_name]]
            assert owner.type_id is not None
            self.members[owner.type_id] = []
            for ordinal, spelling in enumerate(variants, 1):
                symbol = Symbol(
                    SymbolId(_PRELUDE, owner.symbol_id.declaration_index, ordinal),
                    spelling,
                    SymbolKind.VARIANT,
                    None,
                    True,
                    owner=owner.type_id,
                )
                self.symbols[symbol.symbol_id] = symbol
                self.members[owner.type_id].append(symbol.symbol_id)

    def reserve(
        self,
        name: A.Name,
        symbol: Symbol,
        tables: tuple[dict[str, SymbolId], ...],
        *,
        type_space: bool = False,
        value_space: bool = False,
        pattern: bool = False,
    ) -> bool:
        spelling = name.spelling
        if spelling == "_":
            return False
        if (
            spelling in KEYWORDS
            or (type_space and spelling in self.prelude.types)
            or (value_space and spelling in self.prelude.values)
        ):
            self.error("E201", f"reserved declaration name {spelling!r}", name.span)
            return False
        for table in tables:
            if spelling in table:
                self.error(
                    "E312" if pattern else "E202",
                    f"duplicate binding {spelling!r}",
                    name.span,
                    self.symbols[table[spelling]],
                )
                return False
        self.symbols[symbol.symbol_id] = symbol
        self.bindings[name.node_id] = symbol.symbol_id
        for table in tables:
            table[spelling] = symbol.symbol_id
        return True

    def local(
        self,
        name: A.Name,
        scope: _Scope,
        kind: SymbolKind = SymbolKind.LOCAL,
        *,
        owner: TypeId | None = None,
        pattern: bool = False,
    ) -> SymbolId | None:
        symbol = Symbol(
            SymbolId(self.module_id, self.declaration_index, name.node_id.value + 1),
            name.spelling,
            kind,
            name.span,
            owner=owner,
        )
        if not self.reserve(name, symbol, (scope.values,), value_space=True, pattern=pattern):
            return None
        self.local_depth[symbol.symbol_id] = len(self.closures)
        return symbol.symbol_id

    def predeclare(self, module: Module) -> None:
        namespace = self.namespaces[module.module_id]
        for index, edge in enumerate(module.imports):
            name = edge.declaration.alias
            symbol = Symbol(
                SymbolId(module.module_id, -1, index),
                name.spelling,
                SymbolKind.IMPORT,
                name.span,
                target_module=edge.target,
            )
            self.reserve(
                name, symbol, (namespace.types, namespace.values), type_space=True, value_space=True
            )
        for index, declaration in enumerate(module.program.declarations):
            if isinstance(declaration, A.ErrorDecl):
                raise ValueError("resolution requires a successful parser handoff")
            assert isinstance(
                declaration, (A.FunctionDecl, A.RecordDecl, A.EnumDecl, A.MachineDecl)
            )
            nominal = not isinstance(declaration, A.FunctionDecl)
            kind = (
                SymbolKind.FUNCTION
                if isinstance(declaration, A.FunctionDecl)
                else SymbolKind.RECORD
                if isinstance(declaration, A.RecordDecl)
                else SymbolKind.ENUM
                if isinstance(declaration, A.EnumDecl)
                else SymbolKind.MACHINE
            )
            symbol = Symbol(
                SymbolId(module.module_id, index),
                declaration.name.spelling,
                kind,
                declaration.name.span,
                declaration.public,
                TypeId(module.module_id, index) if nominal else None,
            )
            tables = (
                (namespace.types,)
                if kind is SymbolKind.ENUM
                else (namespace.types, namespace.values)
                if nominal
                else (namespace.values,)
            )
            self.reserve(
                declaration.name,
                symbol,
                tables,
                type_space=nominal,
                value_space=kind is not SymbolKind.ENUM,
            )
            # Members have nominal owners even when a declaration has an error;
            # failed phase results never publish these recovery identities.
            if nominal:
                assert symbol.type_id is not None
                self.members[symbol.type_id] = []
                member_names: dict[str, SymbolId] = {}
                children = (
                    declaration.fields
                    if isinstance(declaration, A.RecordDecl)
                    else declaration.variants
                    if isinstance(declaration, A.EnumDecl)
                    else tuple(c for c in declaration.clauses if isinstance(c, A.StateClause))
                    if isinstance(declaration, A.MachineDecl)
                    else ()
                )
                for child in children:
                    member = Symbol(
                        SymbolId(module.module_id, index, child.name.node_id.value + 1),
                        child.name.spelling,
                        SymbolKind.VARIANT
                        if isinstance(child, A.EnumVariant)
                        else SymbolKind.CELL
                        if isinstance(child, A.StateClause)
                        else SymbolKind.FIELD,
                        child.name.span,
                        declaration.public,
                        owner=symbol.type_id,
                    )
                    if self.reserve(child.name, member, (member_names,)):
                        self.members[symbol.type_id].append(member.symbol_id)

    def reference(
        self,
        node: A.Node,
        symbol_id: SymbolId,
        kind: ReferenceKind,
        path: tuple[SymbolId, ...] | None = None,
    ) -> None:
        symbol = self.symbols[symbol_id]
        self.references[node.node_id] = Reference(
            symbol_id, kind, symbol.type_id or symbol.owner, path or (symbol_id,)
        )
        depth = self.local_depth.get(symbol_id)
        if depth is not None:
            for closure in self.closures[depth:]:
                closure[symbol_id] = None

    def lookup_path(
        self, path: A.Path, scope: _Scope, *, type_space: bool
    ) -> tuple[SymbolId, ...] | None:
        parts = path.parts
        namespace = self.namespaces[self.module_id]
        spelling = parts[0].spelling
        if type_space or len(parts) > 1:
            found = namespace.types.get(spelling, self.prelude.types.get(spelling))
        else:
            found = scope.find(spelling)
        if found is None:
            self.error(
                "E203", f"unresolved {'type' if type_space else 'name'} {spelling!r}", parts[0].span
            )
            return None
        ids = [found]
        symbol = self.symbols[found]
        position = 1
        if symbol.kind is SymbolKind.IMPORT:
            if len(parts) == 1:
                self.error("E203", "import alias requires a qualified member", path.span, symbol)
                return None
            assert symbol.target_module is not None
            imported = self.namespaces[symbol.target_module]
            # An intermediate qualifier denotes an enum type, the final one a
            # value or type in its own namespace. Imported aliases never re-export.
            table = imported.types if type_space or len(parts) > 2 else imported.values
            found = table.get(parts[position].spelling)
            if found is None:
                self.error("E203", "unresolved imported member", parts[position].span, symbol)
                return None
            symbol = self.symbols[found]
            if symbol.kind is SymbolKind.IMPORT or not symbol.public:
                self.error("E206", "imported member is private", parts[position].span, symbol)
                return None
            ids.append(found)
            position += 1
        if position < len(parts):
            if type_space or position + 1 != len(parts) or symbol.type_id not in self.members:
                self.error("E203", "invalid qualified path", parts[position].span, symbol)
                return None
            # Only enum/prelude variants are qualified values; record fields and
            # machine cells use projections, never Type::field paths.
            variants = self.members[symbol.type_id]
            found = next(
                (
                    sid
                    for sid in variants
                    if self.symbols[sid].name == parts[position].spelling
                    and self.symbols[sid].kind is SymbolKind.VARIANT
                ),
                None,
            )
            if found is None:
                self.error("E203", "unresolved enum variant", parts[position].span, symbol)
                return None
            ids.append(found)
        elif type_space and symbol.type_id is None:
            self.error("E203", "name does not denote a type", path.span, symbol)
            return None
        elif not type_space and symbol.kind in {SymbolKind.ENUM, SymbolKind.TYPE}:
            self.error("E203", "type requires a qualified variant", path.span, symbol)
            return None
        return tuple(ids)

    def annotation(self, syntax: A.TypeSyntax, scope: _Scope, *, exposed: bool = False) -> None:
        if isinstance(syntax, A.NamedType):
            path = self.lookup_path(syntax.path, scope, type_space=True)
            if path is not None:
                self.reference(syntax, path[-1], ReferenceKind.TYPE, path)
                symbol = self.symbols[path[-1]]
                if exposed and not symbol.public:
                    self.error(
                        "E207", "public signature exposes a private type", syntax.path.span, symbol
                    )
            for argument in syntax.arguments:
                self.annotation(argument, scope, exposed=exposed)
        elif isinstance(syntax, A.FunctionType):
            for parameter in syntax.parameters:
                self.annotation(parameter, scope, exposed=exposed)
            self.annotation(syntax.result, scope, exposed=exposed)
        else:
            raise ValueError("resolution requires valid type syntax")

    def scope(self) -> _Scope:
        namespace = self.namespaces[self.module_id]
        return _Scope(values={**self.prelude.values, **namespace.values})

    def signatures(self, module: Module) -> None:
        self.module_id = module.module_id
        scope = self.scope()
        for declaration in module.program.declarations:
            if isinstance(declaration, (A.FunctionDecl, A.MachineDecl)):
                for parameter in declaration.parameters:
                    self.annotation(parameter.annotation, scope, exposed=declaration.public)
                if isinstance(declaration, A.FunctionDecl):
                    self.annotation(declaration.return_type, scope, exposed=declaration.public)
                else:
                    self.annotation(declaration.output_type, scope, exposed=declaration.public)
                    self.annotation(declaration.rejection_type, scope, exposed=declaration.public)
                    for clause in declaration.clauses:
                        if isinstance(clause, A.StateClause):
                            self.annotation(clause.annotation, scope, exposed=declaration.public)
            elif isinstance(declaration, A.RecordDecl):
                for member in declaration.fields:
                    self.annotation(member.annotation, scope, exposed=declaration.public)
            elif isinstance(declaration, A.EnumDecl):
                for variant in declaration.variants:
                    for payload in variant.payload:
                        self.annotation(payload, scope, exposed=declaration.public)

    def block(self, block: A.BlockExpr, scope: _Scope, *, fresh: bool = True) -> None:
        if fresh:
            scope = _Scope(scope)
        for statement in block.statements:
            if isinstance(statement, A.Binding):
                if statement.annotation is not None:
                    self.annotation(statement.annotation, scope)
                self.expression(statement.value, scope)
                self.local(statement.name, scope)
            elif isinstance(statement, A.InputClause):
                self.annotation(statement.annotation, scope)
                self.local(statement.name, scope, SymbolKind.INPUT)
            elif isinstance(statement, A.OutputClause):
                self.expression(statement.value, scope)
            else:
                raise ValueError("resolution requires valid statements")
        self.expression(block.result, scope)

    def pattern(self, pattern: A.Pattern, scope: _Scope) -> None:
        if isinstance(pattern, A.BindingPattern):
            self.local(pattern.name, scope, pattern=True)
        elif isinstance(pattern, A.VariantPattern):
            path = self.lookup_path(pattern.path, scope, type_space=False)
            if path is not None:
                self.reference(pattern, path[-1], ReferenceKind.VALUE, path)
            for argument in pattern.arguments:
                self.pattern(argument, scope)
        elif not isinstance(pattern, (A.WildcardPattern, A.UnitPattern, A.LiteralPattern)):
            raise ValueError("resolution requires valid patterns")

    def member_reference(self, node: A.Node, receiver: A.Expr, name: A.Name) -> None:
        candidates = tuple(
            sorted(
                sid
                for sid, symbol in self.symbols.items()
                if symbol.name == name.spelling
                and symbol.kind in {SymbolKind.FIELD, SymbolKind.CELL}
                and (symbol.public or sid.module == self.module_id)
            )
        )
        self.member_references[node.node_id] = MemberReference(
            receiver.node_id, candidates, name.span
        )

    def expression(self, expression: A.Expr, scope: _Scope) -> None:
        if isinstance(expression, (A.UnitExpr, A.LiteralExpr)):
            return
        if isinstance(expression, A.PathExpr):
            path = self.lookup_path(expression.path, scope, type_space=False)
            if path is not None:
                symbol = self.symbols[path[-1]]
                if path[-1] in self.entry_only:
                    self.error(
                        "E208",
                        "main with input/output clauses is host-entry-only",
                        expression.span,
                    )
                kind = (
                    ReferenceKind.OLD_CELL
                    if symbol.kind is SymbolKind.CELL
                    else ReferenceKind.INPUT
                    if symbol.kind is SymbolKind.INPUT
                    else ReferenceKind.VALUE
                )
                self.reference(expression, path[-1], kind, path)
        elif isinstance(expression, A.NextExpr):
            if self.closures:
                self.error("E406", "candidate projection underneath a closure", expression.span)
            elif not self.transition:
                self.error(
                    "E405", "candidate projection outside a machine transition", expression.span
                )
            elif expression.cell.spelling not in self.cells:
                self.error("E403", "unknown candidate cell", expression.cell.span)
            else:
                self.reference(
                    expression, self.cells[expression.cell.spelling], ReferenceKind.CANDIDATE
                )
        elif isinstance(expression, A.GroupExpr):
            self.expression(expression.expression, scope)
        elif isinstance(expression, A.UnaryExpr):
            self.expression(expression.operand, scope)
        elif isinstance(expression, A.BinaryExpr):
            self.expression(expression.left, scope)
            self.expression(expression.right, scope)
        elif isinstance(expression, A.CallExpr):
            self.expression(expression.callee, scope)
            for argument in expression.arguments:
                if argument.name is not None:
                    self.member_reference(argument, expression.callee, argument.name)
                self.expression(argument.value, scope)
        elif isinstance(expression, A.ProjectionExpr):
            self.expression(expression.value, scope)
            self.member_reference(expression, expression.value, expression.field)
        elif isinstance(expression, A.ListExpr):
            for element in expression.elements:
                self.expression(element, scope)
        elif isinstance(expression, A.BlockExpr):
            self.block(expression, scope)
        elif isinstance(expression, A.IfExpr):
            self.expression(expression.condition, scope)
            self.block(expression.then_block, scope)
            self.block(expression.else_block, scope)
        elif isinstance(expression, A.MatchExpr):
            self.expression(expression.value, scope)
            for arm in expression.arms:
                arm_scope = _Scope(scope)
                self.pattern(arm.pattern, arm_scope)
                self.block(arm.body, arm_scope)
        elif isinstance(expression, A.ForExpr):
            self.expression(expression.iterable, scope)
            iteration = _Scope(scope)
            self.local(expression.binder, iteration)
            self.block(expression.body, iteration)
        elif isinstance(expression, A.ClosureExpr):
            closure_scope = _Scope(scope)
            self.closures.append({})
            for parameter in expression.parameters:
                self.annotation(parameter.annotation, scope)
                self.local(parameter.name, closure_scope, SymbolKind.PARAMETER)
            self.annotation(expression.return_type, scope)
            self.block(expression.body, closure_scope, fresh=False)
            self.captures[expression.node_id] = tuple(self.closures.pop())
        else:
            raise ValueError("resolution requires valid expressions")

    def bodies(self, module: Module) -> None:
        self.module_id = module.module_id
        for index, declaration in enumerate(module.program.declarations):
            self.declaration_index = index
            scope = _Scope(self.scope())
            if isinstance(declaration, A.FunctionDecl):
                for parameter in declaration.parameters:
                    self.local(parameter.name, scope, SymbolKind.PARAMETER)
                self.block(declaration.body, scope, fresh=False)
            elif isinstance(declaration, A.MachineDecl):
                owner = TypeId(self.module_id, index)
                for parameter in declaration.parameters:
                    self.local(parameter.name, scope, SymbolKind.INPUT)
                self.cells = {}
                for clause in declaration.clauses:
                    if isinstance(clause, A.StateClause):
                        sid = self.local(clause.name, scope, SymbolKind.CELL, owner=owner)
                        if sid is not None:
                            self.cells[clause.name.spelling] = sid
                            symbol = self.symbols[sid]
                            self.symbols[sid] = Symbol(
                                sid,
                                symbol.name,
                                symbol.kind,
                                symbol.span,
                                declaration.public,
                                owner=owner,
                            )
                for clause in declaration.clauses:
                    self.transition = not isinstance(clause, A.StateClause)
                    if isinstance(clause, A.StateClause):
                        self.expression(clause.value, scope)
                    elif isinstance(clause, A.WriterClause):
                        sid = self.cells.get(clause.name.spelling)
                        if sid is None:
                            self.error("E403", "unknown writer cell", clause.name.span)
                        else:
                            self.reference(clause, sid, ReferenceKind.WRITER)
                        self.expression(clause.value, scope)
                    elif isinstance(clause, A.GuardClause):
                        self.expression(clause.condition, scope)
                        self.expression(clause.error, scope)
                    elif isinstance(clause, A.EmitClause):
                        self.expression(clause.value, scope)
                self.transition = False
                self.cells = {}

    def run(self) -> Result[ResolvedProgram]:
        for module in self.graph.modules:
            self.predeclare(module)
        for module in self.graph.modules:
            self.signatures(module)
        for module in self.graph.modules:
            self.bodies(module)
        report = self.bag.report()
        if report.has_errors:
            return ErrorResult(report)
        return ValidResult(
            ResolvedProgram(
                self.graph,
                MappingProxyType(self.symbols),
                tuple(
                    ModuleNamespace(mid, MappingProxyType(ns.types), MappingProxyType(ns.values))
                    for mid, ns in self.namespaces.items()
                ),
                MappingProxyType(self.bindings),
                MappingProxyType(self.references),
                MappingProxyType({tid: tuple(members) for tid, members in self.members.items()}),
                MappingProxyType(self.member_references),
                MappingProxyType(self.captures),
            ),
            report,
        )


def resolve(graph: ModuleGraph, *, max_diagnostics: int = 100) -> Result[ResolvedProgram]:
    """Resolve a successfully loaded graph; error results contain no program."""
    return _Resolver(graph, max_diagnostics).run()
