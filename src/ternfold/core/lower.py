"""One-way typed syntax/plan lowering into independently verified structured Core.

This module is a compiler, never an executor. Source identities are replaced
with function/value IDs; the resulting artifact contains no AST or planner.
"""

from __future__ import annotations

from collections.abc import Callable

from ternfold.analysis.constants import contiguous_minimum
from ternfold.analysis.machines import PlannedProgram
from ternfold.analysis.numeric import Float64, negate
from ternfold.analysis.resolve import SymbolId, SymbolKind, TypeId
from ternfold.analysis.types import BOOL, INT, TEXT, UNIT, Constant, Type, TypeKind
from ternfold.core import nodes as C
from ternfold.core.verify import list_type, require_verified, variant_layout
from ternfold.frontend import ast as A
from ternfold.frontend.source import SourceSpan
from ternfold.frontend.tokens import DecimalMagnitude, FloatSpelling
from ternfold.frontend.tokens import TokenKind as K

_OPERATORS = {
    K.PLUS: "+",
    K.MINUS: "-",
    K.STAR: "*",
    K.SLASH: "/",
    K.DIV: "div",
    K.PERCENT: "%",
    K.CARET: "^",
    K.BANG: "!",
    K.EQUAL_EQUAL: "==",
    K.BANG_EQUAL: "!=",
    K.LESS: "<",
    K.LESS_EQUAL: "<=",
    K.GREATER: ">",
    K.GREATER_EQUAL: ">=",
    K.PLUS_PLUS: "++",
}


class _Builder:
    def __init__(
        self,
        owner: _Lowerer,
        origin: C.Origin,
        counter: list[int] | None = None,
        environment: dict[SymbolId, C.ValueId] | None = None,
    ) -> None:
        self.owner = owner
        self.origin = origin
        self.counter = counter if counter is not None else [0]
        self.environment = dict(environment or {})
        self.candidates: dict[SymbolId, C.ValueId] = {}
        self.projections: dict[tuple[C.ValueId, int, int], C.ValueId] = {}
        self.possible: dict[C.ValueId, frozenset[int]] = {}
        self.bindings: list[C.Let] = []

    def fresh(self) -> C.ValueId:
        value = C.ValueId(self.counter[0])
        self.counter[0] += 1
        return value

    def emit(
        self, type_: Type, operation: C.Operation, origin: C.Origin | None = None
    ) -> C.ValueId:
        value = self.fresh()
        self.bindings.append(C.Let(value, type_, operation, origin or self.origin))
        return value

    def child(self) -> _Builder:
        builder = _Builder(self.owner, self.origin, self.counter, self.environment)
        builder.candidates = dict(self.candidates)
        builder.projections = dict(self.projections)
        builder.possible = dict(self.possible)
        return builder

    def branch(
        self,
        build: Callable[[_Builder], C.ValueId],
        facts: dict[C.ValueId, frozenset[int]] | None = None,
    ) -> C.Block:
        nested = self.child()
        nested.possible.update(facts or {})
        if any(not tags for tags in nested.possible.values()):
            return C.Block((), C.Unreachable())
        value = build(nested)
        return C.Block(tuple(nested.bindings), C.Yield(value))

    def scalar(
        self, type_: Type, scalar: int | bool | str | Float64 | None, origin: C.Origin | None = None
    ) -> C.ValueId:
        bits = scalar.bits if isinstance(scalar, Float64) else None
        constant = C.Constant(type_, None if isinstance(scalar, Float64) else scalar, bits)
        index = self.owner.intern(constant)
        return self.emit(type_, C.Const(index), origin)


class _Lowerer:
    def __init__(self, planned: PlannedProgram) -> None:
        self.typed = planned.typed
        self.resolved = self.typed.resolved
        self.plans = planned.plans
        self.constants: list[C.Constant] = []
        self.functions: dict[C.FunctionId, C.Function] = {}
        self.next_function = 0
        self.named: dict[SymbolId, C.FunctionId] = {}
        self.constructors: dict[TypeId, C.FunctionId] = {}
        self.steps: dict[TypeId, C.FunctionId] = {}
        self.wrappers: dict[tuple[str, Type], C.FunctionId] = {}
        self.syntax: dict[A.NodeId, A.Node] = {}
        self.nominals: dict[TypeId, C.Nominal] = {}
        self.entry: C.FunctionId | None = None
        self.io_main: SymbolId | None = None
        self.declarations: list[tuple[SymbolId, A.Declaration]] = []
        for module in self.resolved.graph.modules:
            for index, declaration in enumerate(module.program.declarations):
                sid = SymbolId(module.module_id, index)
                self.declarations.append((sid, declaration))
                if isinstance(declaration, A.FunctionDecl):
                    io = any(
                        isinstance(s, (A.InputClause, A.OutputClause))
                        for s in declaration.body.statements
                    )
                    if (
                        module.module_id == self.resolved.graph.entry
                        and declaration.public
                        and declaration.name.spelling == "main"
                        and io
                    ):
                        self.io_main = sid
                    else:
                        self.named[sid] = self.function_id()
                elif isinstance(declaration, A.MachineDecl):
                    tid = TypeId(sid.module, sid.declaration_index)
                    self.constructors[tid] = self.function_id()
                    self.steps[tid] = self.function_id()
        for tid, info in self.typed.nominals.items():
            if info.type.kind is TypeKind.ENUM:
                variants = tuple(
                    self.typed.symbol_types[sid].parameters
                    if self.typed.symbol_types[sid].kind is TypeKind.FUNCTION
                    else ()
                    for sid in info.members
                )
                self.nominals[tid] = C.Nominal(
                    info.type,
                    variants=variants,
                    names=tuple(self.resolved.symbols[s].name for s in info.members),
                )
            else:
                self.nominals[tid] = C.Nominal(
                    info.type,
                    tuple(self.typed.symbol_types[s] for s in info.members),
                    names=tuple(self.resolved.symbols[s].name for s in info.members),
                    input_type=info.input_type,
                    output_type=info.output_type,
                    rejection_type=info.rejection_type,
                )

    def function_id(self) -> C.FunctionId:
        result = C.FunctionId(self.next_function)
        self.next_function += 1
        return result

    def origin(self, node: A.Node, kind: str = "user", span: SourceSpan | None = None) -> C.Origin:
        return C.Origin(node.node_id, span or node.span, kind)

    def intern(self, constant: C.Constant) -> int:
        # Type is part of the key, so Python Bool/Int equality cannot alias values.
        try:
            return self.constants.index(constant)
        except ValueError:
            self.constants.append(constant)
            return len(self.constants) - 1

    def constant(self, constant: Constant) -> int:
        children = tuple(self.constant(c) for c in constant.items)
        scalar = constant.scalar
        tag = None
        if constant.variant is not None:
            sid = constant.variant
            if constant.type.kind in {TypeKind.OPTION, TypeKind.DECISION}:
                tag = 0 if self.resolved.symbols[sid].name in {"Some", "Accept"} else 1
            else:
                assert constant.type.nominal_id is not None
                tag = self.typed.nominals[constant.type.nominal_id].members.index(sid)
        return self.intern(
            C.Constant(
                constant.type,
                None if isinstance(scalar, Float64) else scalar,
                scalar.bits if isinstance(scalar, Float64) else None,
                children,
                tag,
            )
        )

    def parameters(
        self, builder: _Builder, parameters: tuple[A.Parameter, ...]
    ) -> tuple[C.Parameter, ...]:
        result: list[C.Parameter] = []
        for parameter in parameters:
            sid = self.resolved.bindings[parameter.name.node_id]
            value = builder.fresh()
            builder.environment[sid] = value
            result.append(C.Parameter(value, self.typed.symbol_types[sid], parameter.name.spelling))
        return tuple(result)

    def source_block(self, node: A.BlockExpr, builder: _Builder) -> C.ValueId:
        previous = dict(builder.environment)
        for statement in node.statements:
            if not isinstance(statement, A.Binding):
                raise ValueError("I/O is lowered only by the host entry adapter")
            value = self.expression(statement.value, builder)
            sid = self.resolved.bindings.get(statement.name.node_id)
            if sid is not None:
                builder.environment[sid] = value
        result = self.expression(node.result, builder)
        builder.environment = previous
        return result

    def variant_tag(self, sid: SymbolId, type_: Type) -> int:
        if type_.kind in {TypeKind.OPTION, TypeKind.DECISION}:
            return 0 if self.resolved.symbols[sid].name in {"Some", "Accept"} else 1
        assert type_.nominal_id is not None
        return self.typed.nominals[type_.nominal_id].members.index(sid)

    def wrapper(self, name: str, signature: Type, node: A.Node) -> C.FunctionId:
        key = name, signature
        if key in self.wrappers:
            return self.wrappers[key]
        fid = self.function_id()
        self.wrappers[key] = fid
        builder = _Builder(self, self.origin(node, "builtin-wrapper"))
        parameters = tuple(
            C.Parameter(builder.fresh(), t, f"arg{i}") for i, t in enumerate(signature.parameters)
        )
        arguments = tuple(p.value for p in parameters)
        if name == "step":
            tid = signature.parameters[0].nominal_id
            assert tid is not None
            operation: C.Operation = C.Call(self.steps[tid], arguments)
        else:
            operation = C.Builtin(name, signature, arguments)
        value = builder.emit(signature.result, operation)
        self.functions[fid] = C.Function(
            fid,
            f"builtin:{name}",
            parameters,
            (),
            signature.result,
            C.Block(tuple(builder.bindings), C.Yield(value)),
            builder.origin,
            "builtin-wrapper",
        )
        return fid

    def expression(self, node: A.Expr, builder: _Builder) -> C.ValueId:
        type_ = self.typed.node_types[node.node_id]
        kind = (
            builder.origin.kind
            if builder.origin.kind in {"machine-writer", "guard", "emission"}
            else "user"
        )
        origin = self.origin(node, kind)
        if isinstance(node, A.LiteralExpr):
            if isinstance(node.value, DecimalMagnitude):
                scalar: int | bool | str | Float64 | None = int(node.value.digits)
            elif isinstance(node.value, FloatSpelling):
                scalar = self.typed.float_literals[node.node_id]
            else:
                assert isinstance(node.value, (bool, str))
                scalar = node.value
            return builder.scalar(type_, scalar, origin)
        if isinstance(node, A.UnitExpr):
            return builder.scalar(UNIT, None, origin)
        if isinstance(node, A.GroupExpr):
            return self.expression(node.expression, builder)
        if isinstance(node, A.NextExpr):
            return builder.candidates[self.resolved.references[node.node_id].symbol_id]
        if isinstance(node, A.PathExpr):
            sid = self.resolved.references[node.node_id].symbol_id
            if sid in builder.environment:
                return builder.environment[sid]
            symbol = self.resolved.symbols[sid]
            if symbol.kind is SymbolKind.FUNCTION:
                return builder.emit(type_, C.Closure(self.named[sid], ()), origin)
            if symbol.kind is SymbolKind.BUILTIN:
                instance = self.typed.builtins[node.node_id]
                return builder.emit(
                    type_,
                    C.Closure(self.wrapper(symbol.name, instance.signature, node), ()),
                    origin,
                )
            if symbol.kind is SymbolKind.VARIANT:
                return builder.emit(
                    type_, C.Variant(type_, self.variant_tag(sid, type_), ()), origin
                )
            raise ValueError("unlowered value identity")
        if isinstance(node, A.UnaryExpr):
            if contiguous_minimum(node):
                return builder.scalar(INT, -(1 << 63), origin)
            operand = self.expression(node.operand, builder)
            return builder.emit(
                type_,
                C.Unary(_OPERATORS[node.operator], operand),
                self.origin(node, kind, span=node.operator_span),
            )
        if isinstance(node, A.BinaryExpr):
            left = self.expression(node.left, builder)
            if node.operator in {K.AND_AND, K.OR_OR}:

                def right(child: _Builder) -> C.ValueId:
                    return self.expression(node.right, child)

                def fixed(child: _Builder) -> C.ValueId:
                    return child.scalar(BOOL, node.operator is K.OR_OR, origin)

                then, otherwise = (right, fixed) if node.operator is K.AND_AND else (fixed, right)
                return builder.emit(
                    BOOL, C.If(left, builder.branch(then), builder.branch(otherwise)), origin
                )
            right_value = self.expression(node.right, builder)
            return builder.emit(
                type_,
                C.Binary(_OPERATORS[node.operator], left, right_value),
                self.origin(node, kind, span=node.operator_span),
            )
        if isinstance(node, A.BlockExpr):
            return self.source_block(node, builder)
        if isinstance(node, A.IfExpr):
            condition = self.expression(node.condition, builder)
            then_block = builder.branch(lambda b: self.source_block(node.then_block, b))
            else_block = builder.branch(lambda b: self.source_block(node.else_block, b))
            return builder.emit(type_, C.If(condition, then_block, else_block), origin)
        if isinstance(node, A.ListExpr):
            return builder.emit(
                type_,
                C.ListValue(
                    type_.arguments[0], tuple(self.expression(e, builder) for e in node.elements)
                ),
                origin,
            )
        if isinstance(node, A.ProjectionExpr):
            receiver = self.expression(node.value, builder)
            sid = self.typed.selected_members[node.node_id]
            receiver_type = self.typed.node_types[node.value.node_id]
            assert receiver_type.nominal_id is not None
            index = self.typed.nominals[receiver_type.nominal_id].members.index(sid)
            return builder.emit(type_, C.Project(receiver, index), origin)
        if isinstance(node, A.CallExpr):
            return self.call(node, builder)
        if isinstance(node, A.ClosureExpr):
            fid = self.function_id()
            lifted = _Builder(self, self.origin(node, "closure-lift"))
            parameters = self.parameters(lifted, node.parameters)
            ordered = sorted(self.typed.captures[node.node_id], key=lambda capture: capture.symbol)
            captures: list[C.Parameter] = []
            values: list[C.ValueId] = []
            for capture in ordered:
                value = lifted.fresh()
                lifted.environment[capture.symbol] = value
                captures.append(
                    C.Parameter(value, capture.type, self.resolved.symbols[capture.symbol].name)
                )
                values.append(builder.environment[capture.symbol])
            result = self.source_block(node.body, lifted)
            self.functions[fid] = C.Function(
                fid,
                "closure",
                parameters,
                tuple(captures),
                type_.result,
                C.Block(tuple(lifted.bindings), C.Yield(result)),
                lifted.origin,
                "closure",
            )
            return builder.emit(type_, C.Closure(fid, tuple(values)), origin)
        if isinstance(node, A.ForExpr):
            iterable = self.expression(node.iterable, builder)
            child = builder.child()
            sid = self.resolved.bindings[node.binder.node_id]
            parameter = C.Parameter(
                child.fresh(), self.typed.symbol_types[sid], node.binder.spelling
            )
            child.environment[sid] = parameter.value
            result = self.source_block(node.body, child)
            return builder.emit(
                type_,
                C.ListMap(iterable, parameter, C.Block(tuple(child.bindings), C.Yield(result))),
                origin,
            )
        if isinstance(node, A.MatchExpr):
            value = self.expression(node.value, builder)
            scrutinee_type = self.typed.node_types[node.value.node_id]

            def arm(index: int, child: _Builder) -> C.ValueId:
                selected = node.arms[index]

                def fail(nested: _Builder) -> C.ValueId:
                    return arm(index + 1, nested)

                return self.pattern(
                    selected.pattern,
                    value,
                    scrutinee_type,
                    child,
                    lambda nested: self.source_block(selected.body, nested),
                    fail,
                    type_,
                    index == len(node.arms) - 1,
                )

            return arm(0, builder)
        raise ValueError("lowering requires successful checked syntax")

    def call(self, node: A.CallExpr, builder: _Builder) -> C.ValueId:
        type_ = self.typed.node_types[node.node_id]
        kind = (
            builder.origin.kind
            if builder.origin.kind in {"machine-writer", "guard", "emission"}
            else "user"
        )
        origin = self.origin(node, kind)
        direct = node.callee
        # Parenthesized function expressions are ordinary values, while direct
        # constructors remain syntactically constrained by the type checker.
        if isinstance(direct, A.PathExpr):
            sid = self.resolved.references[direct.node_id].symbol_id
            symbol = self.resolved.symbols[sid]
            if symbol.kind in {
                SymbolKind.RECORD,
                SymbolKind.MACHINE,
                SymbolKind.VARIANT,
                SymbolKind.BUILTIN,
                SymbolKind.FUNCTION,
            }:
                values = tuple(self.expression(a.value, builder) for a in node.arguments)
                if symbol.kind is SymbolKind.FUNCTION:
                    operation: C.Operation = C.Call(self.named[sid], values)
                elif symbol.kind is SymbolKind.MACHINE:
                    assert type_.nominal_id is not None
                    operation = C.Call(self.constructors[type_.nominal_id], values)
                elif symbol.kind is SymbolKind.RECORD:
                    assert type_.nominal_id is not None
                    fields = {
                        self.typed.selected_members[a.node_id]: v
                        for a, v in zip(node.arguments, values, strict=True)
                    }
                    operation = C.Record(
                        type_.nominal_id,
                        tuple(fields[s] for s in self.typed.nominals[type_.nominal_id].members),
                    )
                elif symbol.kind is SymbolKind.VARIANT:
                    operation = C.Variant(type_, self.variant_tag(sid, type_), values)
                else:
                    instance = self.typed.builtins[direct.node_id]
                    if symbol.name == "step":
                        tid = instance.signature.parameters[0].nominal_id
                        assert tid is not None
                        operation = C.Call(self.steps[tid], values)
                    else:
                        operation = C.Builtin(symbol.name, instance.signature, values)
                return builder.emit(type_, operation, origin)
        callee = self.expression(node.callee, builder)
        values = tuple(self.expression(a.value, builder) for a in node.arguments)
        return builder.emit(type_, C.CallClosure(callee, values), origin)

    def pattern(
        self,
        node: A.Pattern,
        value: C.ValueId,
        type_: Type,
        builder: _Builder,
        success: Callable[[_Builder], C.ValueId],
        failure: Callable[[_Builder], C.ValueId],
        result_type: Type,
        final: bool,
    ) -> C.ValueId:
        if isinstance(node, A.WildcardPattern):
            return success(builder)
        if isinstance(node, A.BindingPattern):
            builder.environment[self.resolved.bindings[node.name.node_id]] = value
            return success(builder)
        if isinstance(node, (A.LiteralPattern, A.UnitPattern)):
            # The checked final arm covers the residual domain. It need not
            # retest a literal; payload extraction still requires tag proofs.
            if final or isinstance(node, A.UnitPattern):
                return success(builder)
            if isinstance(node.value, DecimalMagnitude):
                scalar: int | bool | str | Float64 | None = int(node.value.digits)
                if node.minus_span is not None:
                    assert isinstance(scalar, int)
                    scalar = -scalar
            elif isinstance(node.value, FloatSpelling):
                scalar = self.typed.float_literals[node.node_id]
                if node.minus_span is not None:
                    scalar = negate(scalar)
            else:
                assert isinstance(node.value, (bool, str))
                scalar = node.value
            if type_ == BOOL:
                available = builder.possible.get(value, frozenset({0, 1}))
                true_branch = success if scalar is True else failure
                false_branch = failure if scalar is True else success
                return builder.emit(
                    result_type,
                    C.If(
                        value,
                        builder.branch(true_branch, {value: available & {1}}),
                        builder.branch(false_branch, {value: available & {0}}),
                    ),
                    self.origin(node, "pattern-test"),
                )
            literal = builder.scalar(type_, scalar, self.origin(node, "pattern-test"))
            test = builder.emit(
                BOOL, C.Binary("==", value, literal), self.origin(node, "pattern-test")
            )
            return builder.emit(
                result_type,
                C.If(test, builder.branch(success), builder.branch(failure)),
                self.origin(node, "pattern-test"),
            )
        if isinstance(node, A.VariantPattern):
            sid = self.resolved.references[node.node_id].symbol_id
            tag = self.variant_tag(sid, type_)
            layout = variant_layout(type_, self.nominals)[tag]

            def selected(child: _Builder) -> C.ValueId:
                def payload(index: int, current: _Builder) -> C.ValueId:
                    if index == len(node.arguments):
                        return success(current)
                    key = value, tag, index
                    projected = current.projections.get(key)
                    if projected is None:
                        projected = current.emit(
                            layout[index],
                            C.Payload(value, tag, index),
                            self.origin(node, "pattern-test"),
                        )
                        current.projections[key] = projected
                    return self.pattern(
                        node.arguments[index],
                        projected,
                        layout[index],
                        current,
                        lambda nested: payload(index + 1, nested),
                        failure,
                        result_type,
                        final,
                    )

                return payload(0, child)

            available = builder.possible.get(
                value, frozenset(range(len(variant_layout(type_, self.nominals))))
            )
            default = (
                C.Block((), C.Unreachable())
                if final
                else builder.branch(failure, {value: available - {tag}})
            )
            return builder.emit(
                result_type,
                C.SwitchTag(
                    value,
                    (C.TagCase(tag, builder.branch(selected, {value: available & {tag}})),),
                    default,
                ),
                self.origin(node, "pattern-test"),
            )
        raise ValueError("invalid checked pattern")

    def machine(self, sid: SymbolId, node: A.MachineDecl) -> None:
        tid = TypeId(sid.module, sid.declaration_index)
        info = self.typed.nominals[tid]
        plan = self.plans[tid]
        constructor = _Builder(self, self.origin(node, "machine-constructor"))
        cells = tuple(
            constructor.emit(
                self.typed.symbol_types[cell], C.Const(self.constant(self.typed.constants[cell]))
            )
            for cell in plan.cells
        )
        snapshot = constructor.emit(info.type, C.MachineValue(tid, cells))
        self.functions[self.constructors[tid]] = C.Function(
            self.constructors[tid],
            f"construct:{node.name.spelling}",
            (),
            (),
            info.type,
            C.Block(tuple(constructor.bindings), C.Yield(snapshot)),
            constructor.origin,
            "constructor",
        )
        builder = _Builder(self, self.origin(node, "machine-writer"))
        assert (
            info.input_type is not None
            and info.output_type is not None
            and info.rejection_type is not None
        )
        old = C.Parameter(builder.fresh(), info.type, "old")
        input_ = C.Parameter(builder.fresh(), info.input_type, node.parameters[0].name.spelling)
        builder.environment[plan.input] = input_.value
        for index, cell in enumerate(plan.cells):
            builder.environment[cell] = builder.emit(
                self.typed.symbol_types[cell], C.Project(old.value, index)
            )
        clauses = {
            self.resolved.references[c.node_id].symbol_id: c
            for c in node.clauses
            if isinstance(c, A.WriterClause)
        }
        for cell in plan.schedule:
            builder.candidates[cell] = self.expression(clauses[cell].value, builder)
        guards = tuple(c for c in node.clauses if isinstance(c, A.GuardClause))
        emissions = tuple(c for c in node.clauses if isinstance(c, A.EmitClause))
        decision = Type(TypeKind.DECISION, (info.type, info.output_type, info.rejection_type))
        output_type = info.output_type

        def continuation(index: int, current: _Builder) -> C.ValueId:
            if index == len(guards):
                values_list: list[C.ValueId] = []
                for emission in emissions:
                    current.origin = self.origin(emission, "emission")
                    values_list.append(self.expression(emission.value, current))
                values = tuple(values_list)
                output = current.emit(list_type(output_type), C.ListValue(output_type, values))
                new = current.emit(
                    info.type,
                    C.MachineValue(tid, tuple(current.candidates[cell] for cell in plan.cells)),
                )
                return current.emit(decision, C.Variant(decision, 0, (new, output)))
            guard = guards[index]
            current.origin = self.origin(guard, "guard")
            test = self.expression(guard.condition, current)

            def reject(child: _Builder) -> C.ValueId:
                reason = self.expression(guard.error, child)
                return child.emit(
                    decision,
                    C.Variant(decision, 1, (old.value, reason)),
                    self.origin(guard, "guard"),
                )

            return current.emit(
                decision,
                C.If(
                    test,
                    current.branch(lambda child: continuation(index + 1, child)),
                    current.branch(reject),
                ),
                self.origin(guard, "guard"),
            )

        result = continuation(0, builder)
        self.functions[self.steps[tid]] = C.Function(
            self.steps[tid],
            f"step:{node.name.spelling}",
            (old, input_),
            (),
            decision,
            C.Block(tuple(builder.bindings), C.Yield(result)),
            builder.origin,
            "step",
        )

    def host_entry(self, sid: SymbolId, node: A.FunctionDecl) -> None:
        fid = self.function_id()
        self.entry = fid
        builder = _Builder(self, self.origin(node, "host-entry"))
        snapshot = C.Parameter(builder.fresh(), list_type(TEXT), "input-snapshot")
        if sid != self.io_main:
            result = builder.emit(list_type(TEXT), C.Call(self.named[sid], ()))
        else:
            staged: list[C.ValueId] = []
            input_index = 0
            for statement in node.body.statements:
                if isinstance(statement, A.Binding):
                    value = self.expression(statement.value, builder)
                    bound = self.resolved.bindings.get(statement.name.node_id)
                    if bound is not None:
                        builder.environment[bound] = value
                elif isinstance(statement, A.InputClause):
                    value = builder.emit(
                        TEXT, C.InputAt(snapshot.value, input_index), self.origin(statement)
                    )
                    builder.environment[self.resolved.bindings[statement.name.node_id]] = value
                    input_index += 1
                elif isinstance(statement, A.OutputClause):
                    staged.append(self.expression(statement.value, builder))
            returned = self.expression(node.body.result, builder)
            output = builder.emit(list_type(TEXT), C.ListValue(TEXT, tuple(staged)))
            result = builder.emit(list_type(TEXT), C.Binary("++", output, returned))
        self.functions[fid] = C.Function(
            fid,
            "host-entry",
            (snapshot,),
            (),
            list_type(TEXT),
            C.Block(tuple(builder.bindings), C.Yield(result)),
            builder.origin,
            "entry",
        )

    def run(self) -> C.VerifiedCore:
        for sid, node in self.declarations:
            if isinstance(node, A.FunctionDecl) and sid != self.io_main:
                builder = _Builder(self, self.origin(node))
                parameters = self.parameters(builder, node.parameters)
                result = self.source_block(node.body, builder)
                self.functions[self.named[sid]] = C.Function(
                    self.named[sid],
                    node.name.spelling,
                    parameters,
                    (),
                    self.typed.symbol_types[sid].result,
                    C.Block(tuple(builder.bindings), C.Yield(result)),
                    builder.origin,
                )
            elif isinstance(node, A.MachineDecl):
                self.machine(sid, node)
        for sid, node in self.declarations:
            if (
                isinstance(node, A.FunctionDecl)
                and sid.module == self.resolved.graph.entry
                and node.public
                and node.name.spelling == "main"
                and not node.parameters
                and self.typed.symbol_types[sid].result == list_type(TEXT)
            ):
                self.host_entry(sid, node)
        return require_verified(
            C.CoreProgram(
                tuple(self.nominals.values()),
                tuple(self.constants),
                tuple(fn for _, fn in sorted(self.functions.items())),
                self.entry,
            )
        )


def lower(planned: PlannedProgram) -> C.VerifiedCore:
    """Lower a fully checked library/program and verify before publication."""
    return _Lowerer(planned).run()
