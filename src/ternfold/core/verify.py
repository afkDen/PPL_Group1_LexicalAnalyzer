"""Independent Core dominance, layout, signature and tag-proof verification."""

from __future__ import annotations

from dataclasses import dataclass

from ternfold.analysis.modules import ModuleId
from ternfold.analysis.numeric import Float64
from ternfold.analysis.resolve import TypeId
from ternfold.analysis.types import BOOL, FLOAT, INT, TEXT, UNIT, Type, TypeKind
from ternfold.core import nodes as C


@dataclass(frozen=True, slots=True)
class Issue:
    message: str
    origin: C.Origin | None = None


class VerificationError(ValueError):
    def __init__(self, issues: tuple[Issue, ...]) -> None:
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))


def function_type(parameters: tuple[Type, ...], result: Type) -> Type:
    return Type(TypeKind.FUNCTION, parameters + (result,))


def list_type(element: Type) -> Type:
    return Type(TypeKind.LIST, (element,))


def _value_id(value: object) -> bool:
    return isinstance(value, C.ValueId) and type(value.value) is int and value.value >= 0


def _function_id(value: object) -> bool:
    return isinstance(value, C.FunctionId) and type(value.value) is int and value.value >= 0


def _nominal_id(value: object) -> bool:
    return (
        isinstance(value, TypeId)
        and isinstance(value.module, ModuleId)
        and type(value.declaration_index) is int
        and value.declaration_index >= 0
        and isinstance(value.module.path, str)
        and bool(value.module.path)
    )


def variant_layout(type_: Type, nominals: dict[TypeId, C.Nominal]) -> tuple[tuple[Type, ...], ...]:
    if type_.kind is TypeKind.OPTION and len(type_.arguments) == 1:
        return ((type_.arguments[0],), ())  # Some, None
    if type_.kind is TypeKind.DECISION and len(type_.arguments) == 3:
        machine, output, rejection = type_.arguments
        return ((machine, list_type(output)), (machine, rejection))  # Accept, Reject
    if type_.kind is TypeKind.ENUM and type_.nominal_id in nominals:
        return nominals[type_.nominal_id].variants
    return ()


def builtin_signature(name: str, signature: Type) -> bool:
    if signature.kind is not TypeKind.FUNCTION or not signature.arguments:
        return False
    args, result = signature.parameters, signature.result
    fixed = {
        "range": ((INT, INT), list_type(INT)),
        "int_text": ((INT,), TEXT),
        "bool_text": ((BOOL,), TEXT),
        "parse_int": ((TEXT,), Type(TypeKind.OPTION, (INT,))),
        "text_len": ((TEXT,), INT),
        "text_at": ((TEXT, INT), Type(TypeKind.OPTION, (TEXT,))),
        "text_slice": ((TEXT, INT, INT), Type(TypeKind.OPTION, (TEXT,))),
        "int_float": ((INT,), FLOAT),
        "float_int": ((FLOAT,), Type(TypeKind.OPTION, (INT,))),
        "float_text": ((FLOAT,), TEXT),
    }
    if name in fixed:
        return (args, result) == fixed[name]
    if not args or args[0].kind is not TypeKind.LIST or len(args[0].arguments) != 1:
        return False
    element = args[0].arguments[0]
    if name == "len":
        return len(args) == 1 and result == INT
    if name == "at":
        return args == (list_type(element), INT) and result == Type(TypeKind.OPTION, (element,))
    if name == "append":
        return args == (list_type(element), element) and result == args[0]
    if name == "map":
        return (
            len(args) == 2
            and result.kind is TypeKind.LIST
            and len(result.arguments) == 1
            and args[1] == function_type((element,), result.arguments[0])
        )
    if name == "fold":
        return (
            len(args) == 3
            and args[1] == result
            and args[2] == function_type((result, element), result)
        )
    return False


class _Verifier:
    def __init__(self, program: C.CoreProgram) -> None:
        self.program = program
        self.nominals = {
            n.type.nominal_id: n for n in program.nominals if n.type.nominal_id is not None
        }
        self.functions = {f.function: f for f in program.functions}
        self.issues: list[Issue] = []
        self.origin: C.Origin | None = None
        self.seen: set[C.ValueId] = set()
        self.current: C.Function | None = None

    def error(self, message: str) -> None:
        self.issues.append(Issue(message, self.origin))

    def type_valid(self, type_: C.CoreType) -> bool:
        if isinstance(type_, C.TagType):
            return (
                isinstance(type_.subject, Type)
                and self.type_valid(type_.subject)
                and bool(variant_layout(type_.subject, self.nominals))
            )
        if not isinstance(type_, Type) or not isinstance(type_.kind, TypeKind):
            return False
        if not all(isinstance(t, Type) and self.type_valid(t) for t in type_.arguments):
            return False
        if type_.kind in {TypeKind.RECORD, TypeKind.ENUM, TypeKind.MACHINE}:
            if not _nominal_id(type_.nominal_id):
                return False
            info = self.nominals.get(type_.nominal_id) if type_.nominal_id is not None else None
            return info is not None and info.type == type_ and not type_.arguments
        if type_.nominal_id is not None or type_.variable is not None:
            return False
        if type_.kind in {TypeKind.LIST, TypeKind.OPTION}:
            return len(type_.arguments) == 1
        if type_.kind is TypeKind.DECISION:
            if len(type_.arguments) != 3:
                return False
            machine, output, rejection = type_.arguments
            info = self.nominals.get(machine.nominal_id) if machine.nominal_id is not None else None
            return (
                machine.kind is TypeKind.MACHINE
                and info is not None
                and (info.output_type, info.rejection_type) == (output, rejection)
            )
        if type_.kind is TypeKind.FUNCTION:
            return bool(type_.arguments)
        return (
            type_.kind
            in {
                TypeKind.INT,
                TypeKind.FLOAT,
                TypeKind.BOOL,
                TypeKind.CHAR,
                TypeKind.TEXT,
                TypeKind.UNIT,
            }
            and not type_.arguments
        )

    def data_only(self, type_: Type, seen: frozenset[TypeId] = frozenset()) -> bool:
        if not isinstance(type_, Type):
            return False
        if type_.kind is TypeKind.FUNCTION:
            return False
        if not all(self.data_only(t, seen) for t in type_.arguments):
            return False
        tid = type_.nominal_id
        if tid is not None and tid not in seen and tid in self.nominals:
            info = self.nominals[tid]
            return all(self.data_only(t, seen | {tid}) for t in info.fields) and all(
                self.data_only(t, seen | {tid}) for row in info.variants for t in row
            )
        return True

    def constant(self, index: int) -> None:
        c = self.program.constants[index]
        if not isinstance(c.type, Type) or not self.type_valid(c.type):
            self.error("constant has invalid type")
            return
        if any(type(child) is not int or not 0 <= child < index for child in c.children):
            self.error("constant children must precede their parent")
            return
        children = tuple(self.program.constants[i].type for i in c.children)
        kind = c.type.kind
        valid = False
        if kind is TypeKind.FLOAT:
            try:
                valid = c.float_bits is not None and Float64(c.float_bits).bits == c.float_bits
            except (ValueError, TypeError):
                pass
            valid = valid and c.scalar is None and not c.children and c.tag is None
        elif c.float_bits is not None:
            valid = False
        elif kind is TypeKind.INT:
            valid = type(c.scalar) is int and -(1 << 63) <= c.scalar < 1 << 63
        elif kind is TypeKind.BOOL:
            valid = type(c.scalar) is bool
        elif kind in {TypeKind.CHAR, TypeKind.TEXT}:
            valid = isinstance(c.scalar, str)
            if valid:
                assert isinstance(c.scalar, str)
                try:
                    c.scalar.encode("utf-8", "strict")
                except UnicodeError:
                    valid = False
                if kind is TypeKind.CHAR:
                    valid = valid and len(c.scalar) == 1
        elif kind is TypeKind.UNIT:
            valid = c.scalar is None and not c.children and c.tag is None
        elif kind is TypeKind.LIST:
            valid = (
                all(t == c.type.arguments[0] for t in children)
                and c.scalar is None
                and c.tag is None
            )
        elif kind in {TypeKind.RECORD, TypeKind.MACHINE}:
            info = self.nominals[c.type.nominal_id]  # type: ignore[index]
            valid = children == info.fields and c.scalar is None and c.tag is None
        else:
            layout = variant_layout(c.type, self.nominals)
            valid = (
                type(c.tag) is int
                and 0 <= c.tag < len(layout)
                and children == layout[c.tag]
                and c.scalar is None
            )
        if kind in {TypeKind.INT, TypeKind.BOOL, TypeKind.CHAR, TypeKind.TEXT}:
            valid = valid and not c.children and c.tag is None
        if not valid:
            self.error("invalid constant payload/layout")

    def define(self, parameter: C.Parameter, environment: dict[C.ValueId, C.CoreType]) -> None:
        if not _value_id(parameter.value) or parameter.value in self.seen:
            self.error("duplicate or invalid function-local value ID")
        self.seen.add(parameter.value)
        environment[parameter.value] = parameter.type
        if not isinstance(parameter.type, Type) or not self.type_valid(parameter.type):
            self.error("invalid binding type")

    def layouts(self) -> None:
        graph: dict[TypeId, set[TypeId]] = {tid: set() for tid in self.nominals}
        for tid, info in self.nominals.items():
            headers = (info.input_type, info.output_type, info.rejection_type)
            valid_names = all(isinstance(name, str) and name for name in info.names) and len(
                set(info.names)
            ) == len(info.names)
            if not valid_names:
                self.error("invalid nominal member names")
            if info.type.kind is TypeKind.ENUM:
                if (
                    info.fields
                    or not info.variants
                    or len(info.names) != len(info.variants)
                    or any(t is not None for t in headers)
                ):
                    self.error("invalid enum layout")
            elif info.type.kind in {TypeKind.RECORD, TypeKind.MACHINE}:
                if info.variants or len(info.names) != len(info.fields):
                    self.error("invalid record/machine layout")
                if info.type.kind is TypeKind.MACHINE:
                    if not info.fields or any(
                        not isinstance(t, Type) or not self.type_valid(t) for t in headers
                    ):
                        self.error(
                            "machine requires concrete input/output/rejection types and state"
                        )
                elif any(t is not None for t in headers):
                    self.error("record cannot contain machine headers")
            else:
                self.error("nominal table requires record/enum/machine types")
            pending = list(info.fields) + [t for row in info.variants for t in row]
            pending += [t for t in headers if isinstance(t, Type)]
            while pending:
                type_ = pending.pop()
                if not isinstance(type_, Type):
                    self.error("nominal layout contains a non-source type")
                    continue
                if type_.nominal_id in graph:
                    assert type_.nominal_id is not None
                    graph[tid].add(type_.nominal_id)
                pending.extend(type_.arguments)
        finished: set[TypeId] = set()
        for start in graph:
            if start in finished:
                continue
            active = {start}
            stack = [(start, iter(graph[start]))]
            while stack:
                node, edges = stack[-1]
                target = next(edges, None)
                if target is None:
                    stack.pop()
                    active.remove(node)
                    finished.add(node)
                elif target in active:
                    self.error("recursive nominal layout/signature graph")
                elif target not in finished:
                    active.add(target)
                    stack.append((target, iter(graph[target])))

    def block(
        self,
        block: C.Block,
        inherited: dict[C.ValueId, C.CoreType],
        facts: dict[C.ValueId, frozenset[int]],
        impossible: bool = False,
    ) -> Type | None:
        environment = dict(inherited)
        for binding in block.bindings:
            self.origin = binding.origin
            actual = self.operation(binding.operation, environment, facts, impossible)
            if actual != binding.type:
                self.error("operation result differs from binding type")
            # Tag values are internal and can never be function arguments/results.
            if not _value_id(binding.value) or binding.value in self.seen:
                self.error("duplicate or invalid function-local value ID")
            self.seen.add(binding.value)
            environment[binding.value] = binding.type
            if not self.type_valid(binding.type):
                self.error("invalid binding type")
        if isinstance(block.terminator, C.Unreachable):
            if not impossible:
                self.error("Unreachable without an empty verified tag set")
            return None
        if not _value_id(block.terminator.value):
            self.error("invalid yielded value ID")
            return None
        result = environment.get(block.terminator.value)
        if result is None or isinstance(result, C.TagType):
            self.error("yield must name a dominating source-typed value")
            return None
        return result

    def operation(
        self,
        op: C.Operation,
        env: dict[C.ValueId, C.CoreType],
        facts: dict[C.ValueId, frozenset[int]],
        impossible: bool,
    ) -> C.CoreType | None:
        def value(vid: C.ValueId) -> Type:
            if not _value_id(vid):
                self.error("invalid operand value ID")
                return UNIT
            type_ = env.get(vid)
            if not isinstance(type_, Type):
                self.error("operand lacks a dominating source-typed definition")
                return UNIT
            return type_

        def arguments(ids: tuple[C.ValueId, ...]) -> tuple[Type, ...]:
            return tuple(value(v) for v in ids)

        if isinstance(op, C.Const):
            if type(op.constant) is int and 0 <= op.constant < len(self.program.constants):
                return self.program.constants[op.constant].type
            self.error("unknown constant ID")
        elif isinstance(op, C.Unary):
            operand = value(op.operand)
            if (op.operator == "!" and operand == BOOL) or (
                op.operator == "-" and operand in {INT, FLOAT}
            ):
                return operand
            self.error("invalid unary signature")
        elif isinstance(op, C.Binary):
            a, b = value(op.left), value(op.right)
            if op.operator in {"+", "-", "*"} and a == b and a in {INT, FLOAT}:
                return a
            if op.operator == "/" and a in {INT, FLOAT} and b in {INT, FLOAT}:
                return FLOAT
            if op.operator in {"div", "%"} and a == b == INT:
                return INT
            if op.operator == "^" and a in {INT, FLOAT} and b == INT:
                return a
            if op.operator in {"<", "<=", ">", ">="} and a == b and a in {INT, FLOAT}:
                return BOOL
            if op.operator in {"==", "!="} and a == b and self.data_only(a):
                return BOOL
            if op.operator == "++" and a == b and (a == TEXT or a.kind is TypeKind.LIST):
                return a
            self.error("invalid binary signature or eager short-circuit operation")
        elif isinstance(op, (C.Record, C.MachineValue)):
            if not _nominal_id(op.nominal):
                self.error("invalid referenced nominal ID")
                return None
            info = self.nominals.get(op.nominal)
            values = op.values if isinstance(op, C.Record) else op.cells
            expected = TypeKind.RECORD if isinstance(op, C.Record) else TypeKind.MACHINE
            if info is not None and info.type.kind is expected and arguments(values) == info.fields:
                if expected is TypeKind.MACHINE and not self.data_only(info.type):
                    self.error("machine contains function state")
                return info.type
            self.error("invalid nominal construction")
        elif isinstance(op, C.Variant):
            if not isinstance(op.type, Type) or not self.type_valid(op.type):
                self.error("invalid variant operation type")
                return None
            layout = variant_layout(op.type, self.nominals)
            if (
                type(op.tag) is int
                and 0 <= op.tag < len(layout)
                and arguments(op.values) == layout[op.tag]
            ):
                return op.type
            self.error("invalid variant tag/payload layout")
        elif isinstance(op, C.ListValue):
            if not isinstance(op.element, Type) or not self.type_valid(op.element):
                self.error("invalid list operation element type")
                return None
            if arguments(op.values) == (op.element,) * len(op.values):
                return list_type(op.element)
            self.error("heterogeneous list")
        elif isinstance(op, C.Project):
            subject = value(op.value)
            info = self.nominals.get(subject.nominal_id) if subject.nominal_id is not None else None
            if (
                info is not None
                and subject.kind in {TypeKind.RECORD, TypeKind.MACHINE}
                and type(op.index) is int
                and 0 <= op.index < len(info.fields)
            ):
                return info.fields[op.index]
            self.error("invalid field projection")
        elif isinstance(op, (C.Tag, C.Payload, C.SwitchTag)):
            subject = value(op.value)
            layout = variant_layout(subject, self.nominals)
            if not layout:
                self.error("tag operation requires enum-like value")
                return None
            possible = facts.get(op.value, frozenset(range(len(layout))))
            if isinstance(op, C.Tag):
                return C.TagType(subject)
            if isinstance(op, C.Payload):
                if (
                    type(op.tag) is int
                    and 0 <= op.tag < len(layout)
                    and type(op.index) is int
                    and 0 <= op.index < len(layout[op.tag])
                    and possible == frozenset({op.tag})
                ):
                    return layout[op.tag][op.index]
                self.error("payload projection lacks exact dominating tag proof")
                return None
            tags = [case.tag for case in op.cases]
            if len(set(tags)) != len(tags) or any(
                type(t) is not int or not 0 <= t < len(layout) for t in tags
            ):
                self.error("invalid/duplicate switch tag")
                return None
            results: list[Type] = []
            for case in op.cases:
                narrowed = possible & {case.tag}
                branch = self.block(
                    case.body, env, {**facts, op.value: narrowed}, impossible or not narrowed
                )
                if branch is not None:
                    results.append(branch)
            remaining = possible - set(tags)
            if op.default is None:
                if remaining:
                    self.error("non-exhaustive switch lacks default")
            else:
                branch = self.block(
                    op.default, env, {**facts, op.value: remaining}, impossible or not remaining
                )
                if branch is not None:
                    results.append(branch)
            if results and any(t != results[0] for t in results):
                self.error("switch branch result mismatch")
            return results[0] if results else None
        elif isinstance(op, C.If):
            if value(op.condition) != BOOL:
                self.error("if requires Bool")
            possible_bool = facts.get(op.condition, frozenset({0, 1}))
            true_facts = {**facts, op.condition: possible_bool & {1}}
            false_facts = {**facts, op.condition: possible_bool & {0}}
            then_type = self.block(
                op.then, env, true_facts, impossible or not true_facts[op.condition]
            )
            else_type = self.block(
                op.otherwise, env, false_facts, impossible or not false_facts[op.condition]
            )
            if then_type is not None and else_type is not None and then_type != else_type:
                self.error("if branch result mismatch")
            return then_type if then_type is not None else else_type
        elif isinstance(op, (C.Call, C.Closure)):
            if not _function_id(op.function):
                self.error("invalid referenced function ID")
                return None
            fn = self.functions.get(op.function)
            if fn is None:
                self.error("unknown function ID")
                return None
            if fn.kind == "entry":
                self.error("hidden entry adapter is not callable or capturable")
            if isinstance(op, C.Call):
                if fn.captures or arguments(op.arguments) != tuple(p.type for p in fn.parameters):
                    self.error("direct call signature/capture mismatch")
                return fn.result
            if arguments(op.captures) != tuple(p.type for p in fn.captures):
                self.error("closure capture signature/order mismatch")
            return function_type(tuple(p.type for p in fn.parameters), fn.result)
        elif isinstance(op, C.CallClosure):
            callee = value(op.callee)
            if callee.kind is TypeKind.FUNCTION and callee.arguments:
                if arguments(op.arguments) != callee.parameters:
                    self.error("closure call argument mismatch")
                return callee.result
            self.error("closure call requires function")
        elif isinstance(op, C.Builtin):
            if not isinstance(op.signature, Type) or not self.type_valid(op.signature):
                self.error("invalid builtin operation signature type")
                return None
            if not builtin_signature(op.name, op.signature):
                self.error("unknown builtin or invalid concrete builtin signature")
                return None
            if arguments(op.arguments) != op.signature.parameters:
                self.error("builtin argument mismatch")
            return op.signature.result
        elif isinstance(op, C.ListMap):
            if not isinstance(op.element.type, Type) or not self.type_valid(op.element.type):
                self.error("invalid iteration element type")
                return None
            iterable = value(op.iterable)
            if iterable != list_type(op.element.type):
                self.error("iteration element type mismatch")
            nested = dict(env)
            self.define(op.element, nested)
            result = self.block(op.body, nested, dict(facts), impossible)
            return list_type(result) if result is not None else None
        elif isinstance(op, C.InputAt):
            if (
                self.current is None
                or self.current.kind != "entry"
                or self.program.entry != self.current.function
            ):
                self.error("input reachable outside hidden host entry adapter")
            if value(op.snapshot) != list_type(TEXT) or type(op.index) is not int or op.index < 0:
                self.error("invalid input snapshot/index")
            return TEXT
        return None

    def run(self) -> tuple[Issue, ...]:
        if len(self.functions) != len(self.program.functions):
            self.error("duplicate function ID")
        if len(self.nominals) != len(self.program.nominals):
            self.error("missing/duplicate nominal identity")
        self.layouts()
        for nominal in self.program.nominals:
            if (
                not self.type_valid(nominal.type)
                or any(not self.type_valid(t) for t in nominal.fields)
                or any(not self.type_valid(t) for row in nominal.variants for t in row)
            ):
                self.error("invalid nominal layout/type")
            if nominal.type.kind is TypeKind.MACHINE and not self.data_only(nominal.type):
                self.error("machine state must be data-only")
        for index in range(len(self.program.constants)):
            self.constant(index)
        for fn in self.program.functions:
            self.current = fn
            self.origin = fn.origin
            self.seen = set()
            env: dict[C.ValueId, C.CoreType] = {}
            if (
                not _function_id(fn.function)
                or not isinstance(fn.result, Type)
                or not self.type_valid(fn.result)
            ):
                self.error("invalid function ID/result type")
            for parameter in fn.parameters + fn.captures:
                self.define(parameter, env)
            result = self.block(fn.body, env, {})
            if result != fn.result:
                self.error("function body does not yield declared result")
            if fn.kind == "entry" and (
                len(fn.parameters) != 1 or fn.parameters[0].type != list_type(TEXT)
            ):
                self.error("entry adapter must take one captured input vector")
        if self.program.entry is not None:
            if not _function_id(self.program.entry):
                self.error("invalid selected entry ID")
                return tuple(self.issues)
            entry = self.functions.get(self.program.entry)
            if (
                entry is None
                or entry.kind != "entry"
                or entry.result != list_type(TEXT)
                or entry.captures
            ):
                self.error("invalid host entry function")
        return tuple(self.issues)


def verify(program: C.CoreProgram) -> tuple[Issue, ...]:
    """Return every discovered invariant issue; never execute Core."""
    return _Verifier(program).run()


def require_verified(program: C.CoreProgram) -> C.VerifiedCore:
    issues = verify(program)
    if issues:
        raise VerificationError(issues)
    return C.VerifiedCore(program, C._VERIFIED_TOKEN)
