"""Explicit Core call/control stacks; no AST, name resolution or machine planner.

Every frame completes into a private destination. Main output is ordinary data
until the host receives a fully successful result. Internal callbacks are control
continuations, never representations of source functions or builtin callables.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ternfold.analysis.numeric import Float64, NumericFault
from ternfold.analysis.types import TEXT, Type, TypeKind
from ternfold.core import nodes as C
from ternfold.core.verify import function_type
from ternfold.execution import builtins as B
from ternfold.execution.values import ExecutionResult, Fault, Limits, Value


@dataclass(slots=True)
class _Block:
    block: C.Block
    environment: dict[C.ValueId, Value]
    done: Callable[[Value], None]
    depth: int
    calls: tuple[C.Origin, ...]
    index: int = 0
    tags: dict[C.ValueId, int] = field(default_factory=dict)


@dataclass(slots=True)
class _Traversal:
    items: tuple[Value, ...]
    result_type: Type
    done: Callable[[Value], None]
    origin: C.Origin
    depth: int
    calls: tuple[C.Origin, ...]
    closure: Value | None = None
    operation: C.ListMap | None = None
    environment: dict[C.ValueId, Value] = field(default_factory=dict)
    accumulator: Value | None = None
    index: int = 0
    collected: list[Value] = field(default_factory=list)


class _Interpreter:
    def __init__(self, core: C.VerifiedCore, limits: Limits) -> None:
        if not isinstance(core, C.VerifiedCore):
            raise TypeError("execution requires VerifiedCore")
        self.program = core.program
        self.functions = {f.function: f for f in self.program.functions}
        self.limits = limits
        self.steps = 0
        self.stack: list[_Block | _Traversal] = []
        self.result: Value | None = None
        self.constants: list[Value] = []
        self.origin = self.program.functions[0].origin if self.program.functions else None
        self.calls: tuple[C.Origin, ...] = ()
        for constant in self.program.constants:
            self.constants.append(
                Value(
                    constant.type,
                    Float64(constant.float_bits)
                    if constant.float_bits is not None
                    else constant.scalar,
                    tuple(self.constants[i] for i in constant.children),
                    constant.tag,
                )
            )

    def invoke(
        self,
        function: C.FunctionId,
        arguments: tuple[Value, ...],
        captures: tuple[Value, ...],
        done: Callable[[Value], None],
        depth: int,
        calls: tuple[C.Origin, ...],
    ) -> None:
        if depth > self.limits.max_depth:
            raise B.PrimitiveFault("R003", "language call depth limit")
        fn = self.functions[function]
        if tuple(v.type for v in arguments) != tuple(p.type for p in fn.parameters) or tuple(
            v.type for v in captures
        ) != tuple(p.type for p in fn.captures):
            raise ValueError("execution argument/capture type mismatch")
        env = {
            p.value: v
            for p, v in zip(fn.parameters + fn.captures, arguments + captures, strict=True)
        }
        self.stack.append(_Block(fn.body, env, done, depth, calls))

    def store(self, value: Value) -> None:
        self.result = value

    def run(self, function: C.FunctionId, arguments: tuple[Value, ...]) -> ExecutionResult:
        try:
            self.invoke(function, arguments, (), self.store, 1, ())
            while self.stack:
                frame = self.stack[-1]
                self.calls = frame.calls
                self.steps += 1
                if self.steps > self.limits.max_steps:
                    raise B.PrimitiveFault("R003", "Core instruction budget exhausted")
                if isinstance(frame, _Traversal):
                    self.origin = frame.origin
                    self.traverse(frame)
                    continue
                if frame.index == len(frame.block.bindings):
                    if not isinstance(frame.block.terminator, C.Yield):
                        raise B.PrimitiveFault("R004", "verified unreachable branch executed")
                    value = frame.environment[frame.block.terminator.value]
                    self.stack.pop()
                    frame.done(value)
                    continue
                binding = frame.block.bindings[frame.index]
                frame.index += 1
                self.origin = binding.origin

                def done(
                    value: Value,
                    env: dict[C.ValueId, Value] = frame.environment,
                    target: C.ValueId = binding.value,
                ) -> None:
                    env[target] = value

                self.operation(binding, frame, done)
            assert self.result is not None
            return ExecutionResult(value=self.result)
        except (B.PrimitiveFault, NumericFault) as error:
            assert self.origin is not None
            return ExecutionResult(fault=Fault(error.code, self.origin, error.message, self.calls))
        except MemoryError:
            assert self.origin is not None
            return ExecutionResult(
                fault=Fault("R003", self.origin, "host allocation failed", self.calls)
            )

    def operation(self, binding: C.Let, frame: _Block, done: Callable[[Value], None]) -> None:
        op, env = binding.operation, frame.environment
        result_type = binding.type

        def values(ids: tuple[C.ValueId, ...]) -> tuple[Value, ...]:
            return tuple(env[i] for i in ids)

        if isinstance(op, C.Const):
            done(self.constants[op.constant])
        elif isinstance(op, C.Unary):
            done(B.unary(op.operator, env[op.operand]))
        elif isinstance(op, C.Binary):
            assert isinstance(result_type, Type)
            done(B.binary(op.operator, env[op.left], env[op.right], result_type))
        elif isinstance(op, C.Record):
            assert isinstance(result_type, Type)
            done(Value(result_type, items=values(op.values)))
        elif isinstance(op, C.MachineValue):
            assert isinstance(result_type, Type)
            done(Value(result_type, items=values(op.cells)))
        elif isinstance(op, C.Variant):
            done(Value(op.type, items=values(op.values), tag=op.tag))
        elif isinstance(op, C.ListValue):
            assert isinstance(result_type, Type)
            done(Value(result_type, items=values(op.values)))
        elif isinstance(op, C.Project):
            done(env[op.value].items[op.index])
        elif isinstance(op, C.Payload):
            subject = env[op.value]
            if subject.tag != op.tag:
                raise B.PrimitiveFault("R004", "invalid verified payload tag")
            done(subject.items[op.index])
        elif isinstance(op, C.Tag):
            tag = env[op.value].tag
            assert tag is not None
            frame.tags[binding.value] = tag
        elif isinstance(op, C.If):
            condition = env[op.condition]
            assert type(condition.scalar) is bool
            selected = op.then if condition.scalar else op.otherwise
            self.stack.append(_Block(selected, dict(env), done, frame.depth, frame.calls))
        elif isinstance(op, C.SwitchTag):
            selected_case = next(
                (case.body for case in op.cases if case.tag == env[op.value].tag), op.default
            )
            if selected_case is None:
                raise B.PrimitiveFault("R004", "nonexhaustive verified switch")
            self.stack.append(_Block(selected_case, dict(env), done, frame.depth, frame.calls))
        elif isinstance(op, C.Closure):
            fn = self.functions[op.function]
            done(
                Value(
                    function_type(tuple(p.type for p in fn.parameters), fn.result),
                    items=values(op.captures),
                    function=op.function,
                )
            )
        elif isinstance(op, C.Call):
            self.invoke(
                op.function,
                values(op.arguments),
                (),
                done,
                frame.depth + 1,
                frame.calls + (binding.origin,),
            )
        elif isinstance(op, C.CallClosure):
            closure = env[op.callee]
            assert closure.function is not None
            self.invoke(
                closure.function,
                values(op.arguments),
                closure.items,
                done,
                frame.depth + 1,
                frame.calls + (binding.origin,),
            )
        elif isinstance(op, C.Builtin):
            args = values(op.arguments)
            if op.name in {"map", "fold"}:
                self.stack.append(
                    _Traversal(
                        args[0].items,
                        op.signature.result,
                        done,
                        binding.origin,
                        frame.depth,
                        frame.calls,
                        closure=args[-1],
                        accumulator=args[1] if op.name == "fold" else None,
                    )
                )
            else:
                done(B.primitive(op.name, args, op.signature.result))
        elif isinstance(op, C.ListMap):
            assert isinstance(result_type, Type)
            self.stack.append(
                _Traversal(
                    env[op.iterable].items,
                    result_type,
                    done,
                    binding.origin,
                    frame.depth,
                    frame.calls,
                    operation=op,
                    environment=dict(env),
                )
            )
        elif isinstance(op, C.InputAt):
            items = env[op.snapshot].items
            if op.index >= len(items):
                raise B.PrimitiveFault("R006", "insufficient captured input")
            done(items[op.index])
        else:
            raise B.PrimitiveFault("R004", "unknown verified operation")

    def traverse(self, frame: _Traversal) -> None:
        if frame.index == len(frame.items):
            self.stack.pop()
            frame.done(
                frame.accumulator
                if frame.accumulator is not None
                else Value(frame.result_type, items=tuple(frame.collected))
            )
            return
        item = frame.items[frame.index]
        frame.index += 1

        def done(value: Value) -> None:
            if frame.accumulator is not None:
                frame.accumulator = value
            else:
                frame.collected.append(value)

        if frame.operation is not None:
            env = dict(frame.environment)
            env[frame.operation.element.value] = item
            self.stack.append(_Block(frame.operation.body, env, done, frame.depth, frame.calls))
        else:
            assert frame.closure is not None and frame.closure.function is not None
            arguments = (item,) if frame.accumulator is None else (frame.accumulator, item)
            self.invoke(
                frame.closure.function,
                arguments,
                frame.closure.items,
                done,
                frame.depth + 1,
                frame.calls + (frame.origin,),
            )


_DEFAULT_LIMITS = Limits()


def interpret(
    core: C.VerifiedCore,
    function: C.FunctionId,
    arguments: tuple[Value, ...] = (),
    *,
    limits: Limits = _DEFAULT_LIMITS,
) -> ExecutionResult:
    return _Interpreter(core, limits).run(function, arguments)


def execute_main(
    core: C.VerifiedCore, inputs: tuple[str, ...] = (), *, limits: Limits = _DEFAULT_LIMITS
) -> ExecutionResult:
    if core.program.entry is None:
        raise ValueError("execution requires pub fn main() -> List[Text]")
    snapshot = Value(
        Type(TypeKind.LIST, (TEXT,)), items=tuple(Value(TEXT, text) for text in inputs)
    )
    return interpret(core, core.program.entry, (snapshot,), limits=limits)
