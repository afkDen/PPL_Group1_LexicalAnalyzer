"""M06 bidirectional type checking over resolved IDs, without machine planning."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ternfold.analysis.constants import (
    ConstantError,
    contiguous_minimum,
    evaluate_initializer,
    literal_int,
)
from ternfold.analysis.numeric import Float64, NumericFault, decimal_float, float_text, negate
from ternfold.analysis.patterns import WILDCARD, Constructor, Coverage, Pattern
from ternfold.analysis.resolve import (
    PRELUDE_TYPE_IDS,
    ResolvedProgram,
    SymbolId,
    SymbolKind,
    TypeId,
)
from ternfold.analysis.types import (
    BOOL,
    CHAR,
    ERROR,
    FLOAT,
    INT,
    TEXT,
    UNIT,
    BuiltinInstance,
    Capture,
    Constant,
    NominalInfo,
    Type,
    TypedProgram,
    TypeKind,
    TypePool,
)
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
from ternfold.frontend.tokens import DecimalMagnitude, FloatSpelling
from ternfold.frontend.tokens import TokenKind as K


@dataclass(frozen=True, slots=True)
class _MachineConstraint:
    machine: Type
    output: Type
    rejection: Type
    input: Type | None
    span: SourceSpan
    code: str


class _Checker:
    def __init__(self, program: ResolvedProgram, cap: int) -> None:
        self.resolved = program
        self.pool = TypePool()
        self.bag = DiagnosticBag(cap)
        self.nodes: dict[A.NodeId, Type] = {}
        self.symbols: dict[SymbolId, Type] = {}
        self.nominals: dict[TypeId, NominalInfo] = {}
        self.selected: dict[A.NodeId, SymbolId] = {}
        self.builtins: dict[A.NodeId, BuiltinInstance] = {}
        self.constants: dict[SymbolId, Constant] = {}
        self.float_literals: dict[A.NodeId, Float64] = {}
        self.origins: dict[A.NodeId, SourceSpan] = {}
        self.symbol_origins: dict[SymbolId, SourceSpan] = {}
        self.constraints: list[_MachineConstraint] = []
        self.pending_decisions: list[tuple[Type, SourceSpan]] = []
        self.pending_inference: list[tuple[Type, SourceSpan]] = []
        self.equality_obligations: list[tuple[Type, SourceSpan]] = []
        self.nominal_edges: dict[TypeId, list[tuple[TypeId, SourceSpan]]] = {}
        self.module_id = program.graph.entry

    def error(
        self, code: str, message: str, span: SourceSpan, prior: SourceSpan | None = None
    ) -> None:
        self.bag.add(
            Diagnostic(
                code,
                Severity.ERROR,
                message,
                Label(span),
                (Label(prior, "expected or declared here"),) if prior else (),
            )
        )

    def unify(
        self,
        actual: Type,
        expected: Type,
        span: SourceSpan,
        prior: SourceSpan | None = None,
        *,
        code: str = "E302",
    ) -> None:
        if not self.pool.unify(actual, expected):
            self.error(
                code,
                f"expected {self.pool.freeze(expected)}, got {self.pool.freeze(actual)}",
                span,
                prior,
            )

    def record(self, node: A.Node, type_: Type) -> Type:
        self.nodes[node.node_id] = type_
        self.origins[node.node_id] = node.span
        return type_

    def bind(self, name: A.Name, type_: Type, origin: SourceSpan | None = None) -> None:
        sid = self.resolved.bindings.get(name.node_id)
        if sid is not None:
            self.symbols[sid] = type_
            self.symbol_origins[sid] = origin or name.span

    def annotation(self, syntax: A.TypeSyntax) -> Type:
        if isinstance(syntax, A.FunctionType):
            type_ = self.pool.function(
                tuple(self.annotation(p) for p in syntax.parameters), self.annotation(syntax.result)
            )
        elif isinstance(syntax, A.NamedType):
            reference = self.resolved.references[syntax.node_id]
            symbol = self.resolved.symbols[reference.symbol_id]
            arguments = tuple(self.annotation(a) for a in syntax.arguments)
            if symbol.kind is SymbolKind.TYPE:
                kind = TypeKind(symbol.name)
                arity = {TypeKind.LIST: 1, TypeKind.OPTION: 1, TypeKind.DECISION: 3}.get(kind, 0)
                if len(arguments) != arity:
                    self.error(
                        "E303", f"type {kind} expects {arity} arguments", syntax.span, symbol.span
                    )
                    type_ = ERROR
                else:
                    type_ = self.pool.make(kind, arguments)
            else:
                if arguments:
                    self.error(
                        "E303",
                        "user types are monomorphic and take no arguments",
                        syntax.span,
                        symbol.span,
                    )
                assert reference.type_id is not None
                type_ = self.nominals[reference.type_id].type
            if type_.kind is TypeKind.DECISION:
                self.pending_decisions.append((type_, syntax.span))
        else:
            raise ValueError("typing requires valid resolved type syntax")
        return self.record(syntax, type_)

    def signature(self, parameters: tuple[A.Parameter, ...], result: A.TypeSyntax) -> Type:
        types = tuple(self.annotation(p.annotation) for p in parameters)
        for parameter, type_ in zip(parameters, types, strict=True):
            self.bind(parameter.name, type_, parameter.annotation.span)
            self.record(parameter, type_)
        return self.pool.function(types, self.annotation(result))

    def signatures(self) -> None:
        for symbol in self.resolved.symbols.values():
            if symbol.kind in {SymbolKind.RECORD, SymbolKind.ENUM, SymbolKind.MACHINE}:
                assert symbol.type_id is not None
                kind = {
                    SymbolKind.RECORD: TypeKind.RECORD,
                    SymbolKind.ENUM: TypeKind.ENUM,
                    SymbolKind.MACHINE: TypeKind.MACHINE,
                }[symbol.kind]
                type_ = self.pool.make(kind, nominal=symbol.type_id)
                self.nominals[symbol.type_id] = NominalInfo(
                    type_, symbol.symbol_id, self.resolved.members[symbol.type_id]
                )
        for module in self.resolved.graph.modules:
            for index, declaration in enumerate(module.program.declarations):
                sid = SymbolId(module.module_id, index)
                if isinstance(declaration, A.FunctionDecl):
                    self.symbols[sid] = self.signature(
                        declaration.parameters, declaration.return_type
                    )
                    self.symbol_origins[sid] = declaration.span
                    continue
                tid = TypeId(module.module_id, index)
                info = self.nominals[tid]
                annotations: list[A.TypeSyntax] = []
                if isinstance(declaration, A.RecordDecl):
                    for member in declaration.fields:
                        type_ = self.annotation(member.annotation)
                        self.bind(member.name, type_, member.annotation.span)
                        annotations.append(member.annotation)
                    self.symbols[sid] = self.pool.function(
                        tuple(self.symbols[m] for m in info.members), info.type
                    )
                elif isinstance(declaration, A.EnumDecl):
                    self.symbols[sid] = info.type
                    for variant in declaration.variants:
                        payload = tuple(self.annotation(p) for p in variant.payload)
                        self.bind(
                            variant.name,
                            self.pool.function(payload, info.type) if payload else info.type,
                        )
                        annotations.extend(variant.payload)
                elif isinstance(declaration, A.MachineDecl):
                    parameter = declaration.parameters[0]
                    input_ = self.annotation(parameter.annotation)
                    self.bind(parameter.name, input_, parameter.annotation.span)
                    output = self.annotation(declaration.output_type)
                    rejection = self.annotation(declaration.rejection_type)
                    info = replace(
                        info, input_type=input_, output_type=output, rejection_type=rejection
                    )
                    self.nominals[tid] = info
                    self.symbols[sid] = self.pool.function((), info.type)
                    annotations.extend(
                        (parameter.annotation, declaration.output_type, declaration.rejection_type)
                    )
                    for clause in declaration.clauses:
                        if isinstance(clause, A.StateClause):
                            self.bind(
                                clause.name,
                                self.annotation(clause.annotation),
                                clause.annotation.span,
                            )
                            annotations.append(clause.annotation)
                edges: list[tuple[TypeId, SourceSpan]] = []

                def collect(
                    syntax: A.TypeSyntax, edges: list[tuple[TypeId, SourceSpan]] = edges
                ) -> None:
                    if isinstance(syntax, A.NamedType):
                        reference = self.resolved.references[syntax.node_id]
                        if reference.type_id in self.nominals:
                            assert reference.type_id is not None
                            edges.append((reference.type_id, syntax.span))
                        for argument in syntax.arguments:
                            collect(argument)
                    elif isinstance(syntax, A.FunctionType):
                        for parameter in syntax.parameters:
                            collect(parameter)
                        collect(syntax.result)

                for annotation in annotations:
                    collect(annotation)
                self.nominal_edges[tid] = edges

    def validate_cycles(self) -> None:
        finished: set[TypeId] = set()
        for start in self.nominal_edges:
            if start in finished:
                continue
            active = {start: 0}
            stack: list[tuple[TypeId, int, SourceSpan | None]] = [(start, 0, None)]
            while stack:
                tid, index, incoming = stack[-1]
                edges = self.nominal_edges[tid]
                if index == len(edges):
                    stack.pop()
                    del active[tid]
                    finished.add(tid)
                    continue
                target, span = edges[index]
                stack[-1] = tid, index + 1, incoming
                if target in active:
                    cycle = stack[active[target] :]
                    labels = tuple(
                        Label(frame[2], "signature dependency")
                        for frame in cycle[1:]
                        if frame[2] is not None
                    )
                    chain = " -> ".join(str(self.nominals[t].type) for t, _, _ in cycle)
                    self.bag.add(
                        Diagnostic(
                            "E307",
                            Severity.ERROR,
                            "recursive nominal/signature dependency: " + chain,
                            Label(span),
                            labels,
                        )
                    )
                elif target not in finished:
                    active[target] = len(stack)
                    stack.append((target, 0, span))

    def machine_constraints(self) -> None:
        pending = self.constraints
        self.constraints = []
        for constraint in pending:
            machine = self.pool.prune(constraint.machine)
            if machine.kind is TypeKind.META:
                self.constraints.append(constraint)
                continue
            if machine.kind is TypeKind.ERROR:
                continue
            if machine.kind is not TypeKind.MACHINE:
                self.error(
                    constraint.code, "Decision/step requires a machine type", constraint.span
                )
                continue
            assert machine.nominal_id is not None
            info = self.nominals[machine.nominal_id]
            assert info.output_type is not None and info.rejection_type is not None
            self.unify(constraint.output, info.output_type, constraint.span, code=constraint.code)
            self.unify(
                constraint.rejection, info.rejection_type, constraint.span, code=constraint.code
            )
            if constraint.input is not None:
                assert info.input_type is not None
                self.unify(constraint.input, info.input_type, constraint.span, code=constraint.code)

    def validate_decisions(self) -> None:
        pending = self.pending_decisions
        self.pending_decisions = []
        for decision, span in pending:
            machine, output, rejection = decision.arguments
            self.constraints.append(
                _MachineConstraint(machine, output, rejection, None, span, "E307")
            )
        self.machine_constraints()

    def data_only(self, type_: Type, seen: frozenset[TypeId] = frozenset()) -> bool:
        type_ = self.pool.prune(type_)
        if type_.kind is TypeKind.FUNCTION:
            return False
        if not all(self.data_only(a, seen) for a in type_.arguments):
            return False
        if type_.nominal_id is not None and type_.nominal_id not in seen:
            tid = type_.nominal_id
            for sid in self.nominals[tid].members:
                member = self.symbols[sid]
                if self.resolved.symbols[sid].kind is SymbolKind.VARIANT:
                    payload = member.parameters if member.kind is TypeKind.FUNCTION else ()
                    if not all(self.data_only(p, seen | {tid}) for p in payload):
                        return False
                elif not self.data_only(member, seen | {tid}):
                    return False
        return True

    def scheme(self, sid: SymbolId, span: SourceSpan) -> Type:
        symbol = self.resolved.symbols[sid]

        def list_(type_: Type) -> Type:
            return self.pool.make(TypeKind.LIST, (type_,))

        def option(type_: Type) -> Type:
            return self.pool.make(TypeKind.OPTION, (type_,))

        fn = self.pool.function
        a, b = self.pool.fresh(), self.pool.fresh()
        if symbol.kind is SymbolKind.VARIANT:
            assert symbol.owner is not None
            if symbol.owner == PRELUDE_TYPE_IDS["Option"]:
                return fn((a,), option(a)) if sid.ordinal == 1 else option(a)
            machine, output, rejection = a, b, self.pool.fresh()
            decision = self.pool.make(TypeKind.DECISION, (machine, output, rejection))
            self.constraints.append(
                _MachineConstraint(machine, output, rejection, None, span, "E307")
            )
            return fn(
                (machine, list_(output)) if sid.ordinal == 1 else (machine, rejection), decision
            )
        if symbol.name == "step":
            machine, input_, output, rejection = a, b, self.pool.fresh(), self.pool.fresh()
            self.constraints.append(
                _MachineConstraint(machine, output, rejection, input_, span, "E302")
            )
            return fn(
                (machine, input_), self.pool.make(TypeKind.DECISION, (machine, output, rejection))
            )
        signatures = {
            "len": fn((list_(a),), INT),
            "at": fn((list_(a), INT), option(a)),
            "append": fn((list_(a), a), list_(a)),
            "map": fn((list_(a), fn((a,), b)), list_(b)),
            "fold": fn((list_(a), b, fn((b, a), b)), b),
            "range": fn((INT, INT), list_(INT)),
            "int_text": fn((INT,), TEXT),
            "bool_text": fn((BOOL,), TEXT),
            "parse_int": fn((TEXT,), option(INT)),
            "text_len": fn((TEXT,), INT),
            "text_at": fn((TEXT, INT), option(TEXT)),
            "text_slice": fn((TEXT, INT, INT), option(TEXT)),
            "int_float": fn((INT,), FLOAT),
            "float_int": fn((FLOAT,), option(INT)),
            "float_text": fn((FLOAT,), TEXT),
        }
        return signatures[symbol.name]

    def path(self, expression: A.PathExpr, expected: Type | None, direct: bool) -> Type:
        sid = self.resolved.references[expression.node_id].symbol_id
        symbol = self.resolved.symbols[sid]
        is_prelude = sid.module.path == "<prelude>"
        type_ = self.scheme(sid, expression.span) if is_prelude else self.symbols[sid]
        is_constructor = symbol.kind in {SymbolKind.RECORD, SymbolKind.MACHINE, SymbolKind.VARIANT}
        if is_constructor and type_.kind is TypeKind.FUNCTION and not direct:
            self.error(
                "E303",
                "constructor is only usable in direct construction syntax",
                expression.span,
                symbol.span,
            )
        if is_prelude:
            if not direct and expected is None and not self.pool.freeze(type_).concrete:
                self.error(
                    "E304", "polymorphic value requires a concrete expected type", expression.span
                )
            self.pending_inference.append((type_, expression.span))
            if symbol.kind is SymbolKind.BUILTIN:
                self.builtins[expression.node_id] = BuiltinInstance(sid, type_, not direct)
        return type_

    def member(self, node: A.Node, receiver: Type) -> SymbolId | None:
        reference = self.resolved.member_references[node.node_id]
        receiver = self.pool.prune(receiver)
        for sid in reference.candidates:
            if (
                self.resolved.symbols[sid].owner == receiver.nominal_id
                and receiver.nominal_id is not None
            ):
                self.selected[node.node_id] = sid
                return sid
        if receiver.kind is not TypeKind.ERROR:
            self.error("E302", f"no such field on {receiver}", reference.span)
        return None

    def call(self, expression: A.CallExpr, expected: Type | None) -> Type:
        direct = expression.callee if isinstance(expression.callee, A.PathExpr) else None
        callee = self.expr(expression.callee, direct=direct is not None)
        signature = self.pool.prune(callee)
        if signature.kind is not TypeKind.FUNCTION:
            if signature.kind is not TypeKind.ERROR:
                self.error(
                    "E303",
                    "callee is not callable (nullary variants have no parentheses)",
                    expression.callee.span,
                )
            for argument in expression.arguments:
                self.expr(argument.value)
            return ERROR
        sid = self.resolved.references[direct.node_id].symbol_id if direct else None
        symbol = self.resolved.symbols[sid] if sid is not None else None
        if expected is not None:
            self.unify(signature.result, expected, expression.span)
        if symbol is not None and symbol.kind is SymbolKind.RECORD:
            assert symbol.type_id is not None
            fields = self.nominals[symbol.type_id].members
            supplied: set[SymbolId] = set()
            for argument in expression.arguments:
                target = (
                    self.member(argument, signature.result) if argument.name is not None else None
                )
                if argument.name is None:
                    self.error(
                        "E303",
                        "record construction requires named fields",
                        argument.span,
                        symbol.span,
                    )
                elif target is None:
                    self.error("E303", "unknown record field", argument.name.span, symbol.span)
                elif target in supplied:
                    self.error(
                        "E303",
                        "duplicate record field",
                        argument.name.span,
                        self.resolved.symbols[target].span,
                    )
                if target is not None:
                    supplied.add(target)
                self.expr(
                    argument.value,
                    self.symbols[target] if target is not None else None,
                    self.symbol_origins.get(target) if target else None,
                )
            if supplied != set(fields):
                self.error(
                    "E303",
                    "record construction must provide every field exactly once",
                    expression.span,
                    symbol.span,
                )
        else:
            if len(expression.arguments) != len(signature.parameters):
                self.error(
                    "E303",
                    f"expected {len(signature.parameters)} arguments, "
                    f"got {len(expression.arguments)}",
                    expression.span,
                    symbol.span if symbol else None,
                )
            for index, argument in enumerate(expression.arguments):
                self.machine_constraints()
                if argument.name is not None:
                    self.error(
                        "E303",
                        "only records accept named arguments",
                        argument.name.span,
                        symbol.span if symbol else None,
                    )
                parameter = (
                    signature.parameters[index] if index < len(signature.parameters) else None
                )
                self.expr(argument.value, parameter, symbol.span if symbol else None)
        self.machine_constraints()
        return signature.result

    def block(
        self, block: A.BlockExpr, expected: Type | None, prior: SourceSpan | None = None
    ) -> Type:
        for statement in block.statements:
            if isinstance(statement, A.Binding):
                inference_start = len(self.pending_inference)
                annotation = self.annotation(statement.annotation) if statement.annotation else None
                type_ = self.expr(
                    statement.value,
                    annotation,
                    statement.annotation.span if statement.annotation else None,
                )
                self.machine_constraints()
                for inferred, span in self.pending_inference[inference_start:]:
                    if not self.pool.freeze(inferred).concrete:
                        self.error(
                            "E304", "local binding needs fully determined type arguments", span
                        )
                del self.pending_inference[inference_start:]
                self.bind(statement.name, annotation or type_)
                self.record(statement, annotation or type_)
            elif isinstance(statement, A.InputClause):
                annotation = self.annotation(statement.annotation)
                self.unify(annotation, TEXT, statement.annotation.span)
                self.bind(statement.name, TEXT)
                self.record(statement, UNIT)
            elif isinstance(statement, A.OutputClause):
                self.expr(statement.value, TEXT, statement.span)
                self.record(statement, UNIT)
        return self.record(block, self.expr(block.result, expected, prior))

    def finish_inference(self, start: int) -> None:
        """Seal builtin uses before their consumer can supply downstream constraints.

        Nested builtin arguments with unsettled expected types share the enclosing
        call's solving region. Its expected result and all arguments may constrain
        them; later arms, operands, bindings and function bodies may not.
        """
        self.machine_constraints()
        for type_, span in self.pending_inference[start:]:
            if not self.pool.freeze(type_).concrete:
                self.error("E304", "builtin/constructor type arguments are not determined", span)
        del self.pending_inference[start:]

    def pattern(self, pattern: A.Pattern, expected: Type, coverage: Coverage) -> Pattern:
        self.record(pattern, expected)
        if isinstance(pattern, A.BindingPattern):
            self.bind(pattern.name, expected)
            return WILDCARD
        if isinstance(pattern, A.WildcardPattern):
            return WILDCARD
        if isinstance(pattern, (A.LiteralPattern, A.UnitPattern)):
            if isinstance(pattern, A.UnitPattern):
                actual, constructor = UNIT, Constructor("Unit", display="()")
            else:
                actual = {
                    K.INT: INT,
                    K.FLOAT: FLOAT,
                    K.TEXT: TEXT,
                    K.CHAR: CHAR,
                    K.TRUE: BOOL,
                    K.FALSE: BOOL,
                }[pattern.kind]
                value: DecimalMagnitude | FloatSpelling | Float64 | int | str | bool | None = (
                    pattern.value
                )
                if isinstance(value, DecimalMagnitude):
                    allow = (
                        pattern.minus_span is not None
                        and pattern.minus_span.end_byte == pattern.literal_span.start_byte
                    )
                    magnitude = literal_int(value, minimum_exception=allow)
                    if magnitude is None:
                        self.error(
                            "E301", "Int pattern literal outside signed range", pattern.literal_span
                        )
                        magnitude = 0
                    value = -magnitude if pattern.minus_span is not None else magnitude
                if isinstance(value, FloatSpelling):
                    value = self.float_literal(pattern.node_id, value, pattern.literal_span)
                    if pattern.minus_span is not None:
                        value = negate(value)
                assert isinstance(value, (int, bool, str, Float64))
                display = "true" if value is True else "false" if value is False else str(value)
                if isinstance(value, str):
                    display = repr(value)
                elif isinstance(value, Float64):
                    display = float_text(value)
                constructor = Constructor(str(actual.kind), literal=value, display=display)
            self.unify(actual, expected, pattern.span, code="E312")
            return Pattern(constructor)
        if isinstance(pattern, A.VariantPattern):
            sid = self.resolved.references[pattern.node_id].symbol_id
            domain = coverage.constructors(self.pool.freeze(expected))
            variant = next((c for c in domain or () if c.symbol == sid), None)
            if variant is None:
                self.error(
                    "E312",
                    "pattern constructor does not belong to scrutinee type",
                    pattern.path.span,
                    self.resolved.symbols[sid].span,
                )
                for child in pattern.arguments:
                    self.recover_pattern(child)
                return WILDCARD
            if len(pattern.arguments) != len(variant.payload):
                self.error(
                    "E312",
                    "pattern constructor payload arity mismatch",
                    pattern.span,
                    self.resolved.symbols[sid].span,
                )
            children = tuple(
                self.pattern(child, type_, coverage)
                for child, type_ in zip(pattern.arguments, variant.payload, strict=False)
            )
            for child in pattern.arguments[len(variant.payload) :]:
                self.recover_pattern(child)
            return Pattern(variant, children)
        raise ValueError("typing requires valid resolved patterns")

    def recover_pattern(self, pattern: A.Pattern) -> None:
        self.record(pattern, ERROR)
        if isinstance(pattern, A.BindingPattern):
            self.bind(pattern.name, ERROR)
        elif isinstance(pattern, A.VariantPattern):
            for child in pattern.arguments:
                self.recover_pattern(child)

    def expr(
        self,
        expression: A.Expr,
        expected: Type | None = None,
        prior: SourceSpan | None = None,
        *,
        direct: bool = False,
    ) -> Type:
        start = len(self.pending_inference)
        boundary = not direct and (expected is None or self.pool.freeze(expected).concrete)
        result = self.infer_expr(expression, expected, prior, direct=direct)
        if boundary:
            self.finish_inference(start)
        return result

    def float_literal(self, node: A.NodeId, spelling: FloatSpelling, span: SourceSpan) -> Float64:
        try:
            value = decimal_float(spelling.spelling)
        except NumericFault:
            self.error("E301", "Float literal does not round to a finite binary64 value", span)
            value = Float64(0)
        self.float_literals[node] = value
        return value

    def infer_expr(
        self,
        expression: A.Expr,
        expected: Type | None = None,
        prior: SourceSpan | None = None,
        *,
        direct: bool = False,
    ) -> Type:
        if expected is not None:
            expected = self.pool.prune(expected)
        type_: Type
        if isinstance(expression, A.LiteralExpr):
            type_ = {
                K.INT: INT,
                K.FLOAT: FLOAT,
                K.TEXT: TEXT,
                K.CHAR: CHAR,
                K.TRUE: BOOL,
                K.FALSE: BOOL,
            }[expression.kind]
            if (
                isinstance(expression.value, DecimalMagnitude)
                and literal_int(expression.value) is None
            ):
                self.error("E301", "Int literal outside signed range", expression.literal_span)
            elif isinstance(expression.value, FloatSpelling):
                self.float_literal(expression.node_id, expression.value, expression.literal_span)
        elif isinstance(expression, A.UnitExpr):
            type_ = UNIT
        elif isinstance(expression, A.PathExpr):
            type_ = self.path(expression, expected, direct)
        elif isinstance(expression, A.NextExpr):
            sid = self.resolved.references[expression.node_id].symbol_id
            type_ = self.symbols[sid]
        elif isinstance(expression, A.GroupExpr):
            type_ = self.expr(expression.expression, expected, prior)
        elif isinstance(expression, A.UnaryExpr):
            unary_expected = (
                BOOL
                if expression.operator is K.BANG
                else (expected if expected in {INT, FLOAT} else None)
            )
            type_ = unary_expected or INT
            if contiguous_minimum(expression):
                type_ = INT
                self.record(expression.operand, INT)
            else:
                operand = self.expr(expression.operand, unary_expected, expression.operator_span)
                if unary_expected is None:
                    type_ = operand
                if expression.operator is K.MINUS and self.pool.prune(operand).kind not in {
                    TypeKind.INT,
                    TypeKind.FLOAT,
                    TypeKind.ERROR,
                }:
                    self.error(
                        "E302", "numeric negation requires Int or Float", expression.operator_span
                    )
        elif isinstance(expression, A.BinaryExpr):
            op = expression.operator
            if op in {K.EQUAL_EQUAL, K.BANG_EQUAL}:
                left = self.expr(expression.left)
                self.expr(expression.right, left, expression.left.span)
                self.equality_obligations.append((left, expression.operator_span))
                type_ = BOOL
            elif op is K.PLUS_PLUS:
                context = (
                    expected
                    if expected is not None and expected.kind in {TypeKind.LIST, TypeKind.TEXT}
                    else None
                )
                left = self.expr(expression.left, context)
                self.expr(expression.right, left, expression.left.span)
                concrete = self.pool.prune(left)
                if concrete.kind not in {TypeKind.TEXT, TypeKind.LIST, TypeKind.ERROR}:
                    self.error(
                        "E302",
                        "concatenation requires two Texts or two same-element lists",
                        expression.operator_span,
                    )
                type_ = left
            elif op is K.SLASH:
                for child in (expression.left, expression.right):
                    operand_type = self.pool.prune(self.expr(child))
                    if operand_type.kind not in {TypeKind.INT, TypeKind.FLOAT, TypeKind.ERROR}:
                        self.error(
                            "E302", "real division requires Int or Float operands", child.span
                        )
                type_ = FLOAT
            elif op in {
                K.PLUS,
                K.MINUS,
                K.STAR,
                K.CARET,
                K.LESS,
                K.LESS_EQUAL,
                K.GREATER,
                K.GREATER_EQUAL,
            }:
                arithmetic = op in {K.PLUS, K.MINUS, K.STAR, K.CARET}
                context = expected if arithmetic and expected in {INT, FLOAT} else None
                left = self.expr(expression.left, context)
                numeric = self.pool.prune(left)
                if numeric.kind not in {TypeKind.INT, TypeKind.FLOAT, TypeKind.ERROR}:
                    self.error(
                        "E302", "numeric operator requires Int or Float", expression.left.span
                    )
                self.expr(expression.right, INT if op is K.CARET else left, expression.left.span)
                type_ = left if arithmetic else BOOL
            else:
                boolean = op in {K.AND_AND, K.OR_OR}
                operand = BOOL if boolean else INT
                self.expr(expression.left, operand, expression.operator_span)
                self.expr(expression.right, operand, expression.operator_span)
                type_ = (
                    BOOL
                    if boolean or op in {K.LESS, K.LESS_EQUAL, K.GREATER, K.GREATER_EQUAL}
                    else INT
                )
        elif isinstance(expression, A.CallExpr):
            type_ = self.call(expression, expected)
        elif isinstance(expression, A.ProjectionExpr):
            receiver = self.expr(expression.value)
            member_id = self.member(expression, receiver)
            type_ = self.symbols[member_id] if member_id is not None else ERROR
        elif isinstance(expression, A.ListExpr):
            element = (
                expected.arguments[0]
                if expected is not None and expected.kind is TypeKind.LIST
                else None
            )
            if expected is not None and expected.kind is TypeKind.META:
                # A finite builtin scheme can learn List[T] from this argument,
                # then solve T from later arguments/callback annotations.
                element = self.pool.fresh()
            if element is None and not expression.elements:
                self.error(
                    "E304", "empty list needs an expected List element type", expression.span
                )
                element = ERROR
            for item in expression.elements:
                actual = self.expr(item, element)
                if element is None:
                    element = actual
            assert element is not None
            type_ = self.pool.make(TypeKind.LIST, (element,))
        elif isinstance(expression, A.BlockExpr):
            type_ = self.block(expression, expected, prior)
        elif isinstance(expression, A.IfExpr):
            self.expr(expression.condition, BOOL, expression.condition.span)
            type_ = self.block(expression.then_block, expected, prior)
            self.block(
                expression.else_block, expected or type_, prior or expression.then_block.span
            )
        elif isinstance(expression, A.ClosureExpr):
            type_ = self.signature(expression.parameters, expression.return_type)
            if expected is not None:
                self.unify(type_, expected, expression.span, prior)
            self.block(expression.body, type_.result, expression.return_type.span)
        elif isinstance(expression, A.ForExpr):
            iterable = self.pool.prune(self.expr(expression.iterable))
            if iterable.kind is TypeKind.LIST:
                self.bind(expression.binder, iterable.arguments[0])
            else:
                if iterable.kind is not TypeKind.ERROR:
                    self.error("E302", "for iterable must be a List", expression.iterable.span)
                self.bind(expression.binder, ERROR)
            element = (
                expected.arguments[0]
                if expected is not None and expected.kind is TypeKind.LIST
                else None
            )
            type_ = self.pool.make(TypeKind.LIST, (self.block(expression.body, element, prior),))
        elif isinstance(expression, A.MatchExpr):
            scrutinee = self.pool.freeze(self.expr(expression.value))
            if not scrutinee.concrete:
                self.error(
                    "E304",
                    "match scrutinee type must be determined before its arms",
                    expression.value.span,
                )
            coverage = Coverage(self.resolved, self.symbols, self.nominals, self.module_id)
            matrix: tuple[tuple[Pattern, ...], ...] = ()
            type_ = expected or ERROR
            for index, arm in enumerate(expression.arms):
                before = self.bag.report()
                pattern = self.pattern(arm.pattern, scrutinee, coverage)
                valid_pattern = before == self.bag.report() and scrutinee.concrete
                if valid_pattern:
                    if coverage.useful(matrix, (pattern,), (scrutinee,)) is None:
                        self.error("E311", "match arm is useless", arm.pattern.span)
                    matrix += ((pattern,),)
                result = self.block(arm.body, expected or (type_ if index else None), prior)
                if index == 0 and expected is None:
                    type_ = result
            if scrutinee.concrete:
                witness = coverage.useful(matrix, (WILDCARD,), (scrutinee,))
                if witness is not None:
                    self.error(
                        "E310",
                        "non-exhaustive match; missing " + witness[0].render(),
                        expression.span,
                    )
        else:
            raise ValueError("typing requires a successfully resolved expression")
        if expected is not None:
            self.unify(type_, expected, expression.span, prior)
        return self.record(expression, type_)

    def bodies(self) -> None:
        for module in self.resolved.graph.modules:
            self.module_id = module.module_id
            for index, declaration in enumerate(module.program.declarations):
                sid = SymbolId(module.module_id, index)
                if isinstance(declaration, A.FunctionDecl):
                    self.block(
                        declaration.body, self.symbols[sid].result, declaration.return_type.span
                    )
                elif isinstance(declaration, A.MachineDecl):
                    info = self.nominals[TypeId(module.module_id, index)]
                    assert info.output_type is not None and info.rejection_type is not None
                    for clause in declaration.clauses:
                        if isinstance(clause, A.StateClause):
                            cell = self.resolved.bindings[clause.name.node_id]
                            cell_type = self.symbols[cell]
                            if not self.data_only(cell_type):
                                self.error(
                                    "E407",
                                    "state cells must contain data only",
                                    clause.annotation.span,
                                )
                            self.expr(clause.value, cell_type, clause.annotation.span)
                        elif isinstance(clause, A.WriterClause):
                            target = self.resolved.references[clause.node_id].symbol_id
                            self.expr(
                                clause.value, self.symbols[target], self.symbol_origins.get(target)
                            )
                        elif isinstance(clause, A.GuardClause):
                            self.expr(clause.condition, BOOL, clause.span)
                            self.expr(
                                clause.error, info.rejection_type, declaration.rejection_type.span
                            )
                        elif isinstance(clause, A.EmitClause):
                            self.expr(clause.value, info.output_type, declaration.output_type.span)

    def run(self) -> Result[TypedProgram]:
        self.signatures()
        self.validate_cycles()
        self.validate_decisions()
        if self.bag.has_errors:
            return ErrorResult(self.bag.report())
        self.bodies()
        self.validate_decisions()
        self.machine_constraints()
        self.finish_inference(0)
        for type_, span in self.equality_obligations:
            settled = self.pool.freeze(type_)
            if not settled.concrete:
                self.error("E304", "equality operand type is not determined", span)
            elif not self.data_only(settled):
                self.error("E305", "equality is not supported for function-containing values", span)
        if self.bag.has_errors:
            return ErrorResult(self.bag.report())
        nodes = {nid: self.pool.freeze(t) for nid, t in self.nodes.items()}
        symbols = {sid: self.pool.freeze(t) for sid, t in self.symbols.items()}
        for module in self.resolved.graph.modules:
            for declaration in module.program.declarations:
                if isinstance(declaration, A.MachineDecl):
                    for clause in declaration.clauses:
                        if isinstance(clause, A.StateClause):
                            try:
                                value = evaluate_initializer(
                                    clause.value,
                                    self.resolved,
                                    nodes,
                                    self.selected,
                                    self.float_literals,
                                )
                                self.constants[self.resolved.bindings[clause.name.node_id]] = value
                            except ConstantError as error:
                                self.error(
                                    "E306", error.message, error.span, clause.annotation.span
                                )
        if self.bag.has_errors:
            return ErrorResult(self.bag.report())
        captures = {
            nid: tuple(Capture(sid, symbols[sid]) for sid in sids)
            for nid, sids in self.resolved.captures.items()
        }
        return ValidResult(
            TypedProgram(
                self.resolved,
                nodes,
                symbols,
                self.nominals,
                self.selected,
                {
                    nid: replace(instance, signature=self.pool.freeze(instance.signature))
                    for nid, instance in self.builtins.items()
                },
                captures,
                self.constants,
                self.origins,
                self.float_literals,
            ),
            self.bag.report(),
        )


def check(program: ResolvedProgram, *, max_diagnostics: int = 100) -> Result[TypedProgram]:
    """Type-check every loaded declaration; M07 machine graph checks are deferred."""
    return _Checker(program, max_diagnostics).run()
