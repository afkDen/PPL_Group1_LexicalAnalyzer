"""Immutable structured Core data; no syntax, resolution tables or planner access.

The verifier is the only constructor of the executor-facing VerifiedCore handle.
Core retains source identities solely as debug origins. Values are function-local.
"""

from __future__ import annotations

from dataclasses import dataclass

from ternfold.analysis.resolve import TypeId
from ternfold.analysis.types import Type
from ternfold.frontend.ast import NodeId
from ternfold.frontend.source import SourceSpan


def _tuples(record: object, *names: str) -> None:
    for name in names:
        object.__setattr__(record, name, tuple(getattr(record, name)))


@dataclass(frozen=True, slots=True, order=True)
class FunctionId:
    value: int


@dataclass(frozen=True, slots=True, order=True)
class ValueId:
    value: int


@dataclass(frozen=True, slots=True)
class Origin:
    node: NodeId
    span: SourceSpan
    kind: str = "user"


@dataclass(frozen=True, slots=True)
class TagType:
    subject: Type


type CoreType = Type | TagType


@dataclass(frozen=True, slots=True)
class Parameter:
    value: ValueId
    type: Type
    name: str = ""


@dataclass(frozen=True, slots=True)
class Constant:
    type: Type
    scalar: int | bool | str | None = None
    float_bits: int | None = None
    children: tuple[int, ...] = ()
    tag: int | None = None

    def __post_init__(self) -> None:
        _tuples(self, "children")


@dataclass(frozen=True, slots=True)
class Nominal:
    type: Type
    fields: tuple[Type, ...] = ()
    variants: tuple[tuple[Type, ...], ...] = ()
    names: tuple[str, ...] = ()
    input_type: Type | None = None
    output_type: Type | None = None
    rejection_type: Type | None = None

    def __post_init__(self) -> None:
        _tuples(self, "fields", "variants", "names")
        object.__setattr__(self, "variants", tuple(tuple(row) for row in self.variants))


@dataclass(frozen=True, slots=True)
class Const:
    constant: int


@dataclass(frozen=True, slots=True)
class Unary:
    operator: str
    operand: ValueId


@dataclass(frozen=True, slots=True)
class Binary:
    operator: str
    left: ValueId
    right: ValueId


@dataclass(frozen=True, slots=True)
class Record:
    nominal: TypeId
    values: tuple[ValueId, ...]

    def __post_init__(self) -> None:
        _tuples(self, "values")


@dataclass(frozen=True, slots=True)
class Variant:
    type: Type
    tag: int
    values: tuple[ValueId, ...]

    def __post_init__(self) -> None:
        _tuples(self, "values")


@dataclass(frozen=True, slots=True)
class ListValue:
    element: Type
    values: tuple[ValueId, ...]

    def __post_init__(self) -> None:
        _tuples(self, "values")


@dataclass(frozen=True, slots=True)
class Project:
    value: ValueId
    index: int


@dataclass(frozen=True, slots=True)
class Tag:
    value: ValueId


@dataclass(frozen=True, slots=True)
class Payload:
    value: ValueId
    tag: int
    index: int


@dataclass(frozen=True, slots=True)
class If:
    condition: ValueId
    then: Block
    otherwise: Block


@dataclass(frozen=True, slots=True)
class TagCase:
    tag: int
    body: Block


@dataclass(frozen=True, slots=True)
class SwitchTag:
    value: ValueId
    cases: tuple[TagCase, ...]
    default: Block | None

    def __post_init__(self) -> None:
        _tuples(self, "cases")


@dataclass(frozen=True, slots=True)
class Call:
    function: FunctionId
    arguments: tuple[ValueId, ...]

    def __post_init__(self) -> None:
        _tuples(self, "arguments")


@dataclass(frozen=True, slots=True)
class Closure:
    function: FunctionId
    captures: tuple[ValueId, ...]

    def __post_init__(self) -> None:
        _tuples(self, "captures")


@dataclass(frozen=True, slots=True)
class CallClosure:
    callee: ValueId
    arguments: tuple[ValueId, ...]

    def __post_init__(self) -> None:
        _tuples(self, "arguments")


@dataclass(frozen=True, slots=True)
class Builtin:
    name: str
    signature: Type
    arguments: tuple[ValueId, ...]

    def __post_init__(self) -> None:
        _tuples(self, "arguments")


@dataclass(frozen=True, slots=True)
class MachineValue:
    nominal: TypeId
    cells: tuple[ValueId, ...]

    def __post_init__(self) -> None:
        _tuples(self, "cells")


@dataclass(frozen=True, slots=True)
class ListMap:
    """Evaluate iterable once; bind element and execute body in source order."""

    iterable: ValueId
    element: Parameter
    body: Block


@dataclass(frozen=True, slots=True)
class InputAt:
    """Hidden entry adapter only; missing captured line is R006."""

    snapshot: ValueId
    index: int


type Operation = (
    Const
    | Unary
    | Binary
    | Record
    | Variant
    | ListValue
    | Project
    | Tag
    | Payload
    | If
    | SwitchTag
    | Call
    | Closure
    | CallClosure
    | Builtin
    | MachineValue
    | ListMap
    | InputAt
)


@dataclass(frozen=True, slots=True)
class Let:
    value: ValueId
    type: CoreType
    operation: Operation
    origin: Origin


@dataclass(frozen=True, slots=True)
class Yield:
    value: ValueId


@dataclass(frozen=True, slots=True)
class Unreachable:
    pass


@dataclass(frozen=True, slots=True)
class Block:
    bindings: tuple[Let, ...]
    terminator: Yield | Unreachable

    def __post_init__(self) -> None:
        _tuples(self, "bindings")


@dataclass(frozen=True, slots=True)
class Function:
    function: FunctionId
    name: str
    parameters: tuple[Parameter, ...]
    captures: tuple[Parameter, ...]
    result: Type
    body: Block
    origin: Origin
    kind: str = "user"

    def __post_init__(self) -> None:
        _tuples(self, "parameters", "captures")


@dataclass(frozen=True, slots=True)
class CoreProgram:
    nominals: tuple[Nominal, ...]
    constants: tuple[Constant, ...]
    functions: tuple[Function, ...]
    entry: FunctionId | None = None

    def __post_init__(self) -> None:
        _tuples(self, "nominals", "constants", "functions")


@dataclass(frozen=True, slots=True, init=False)
class VerifiedCore:
    """Handle returned only after structural/type verification succeeds."""

    program: CoreProgram

    def __init__(self, program: CoreProgram, token: object) -> None:
        if token is not _VERIFIED_TOKEN:
            raise ValueError("use require_verified to construct VerifiedCore")
        object.__setattr__(self, "program", program)


_VERIFIED_TOKEN = object()
