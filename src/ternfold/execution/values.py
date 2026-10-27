"""Tagged immutable language values; host Bool/Int and callables never alias.

Core supplies nominal layouts. This module supplies finite scalar validation,
immutable child ownership and iterative equality without recursive host stacks.
"""

from __future__ import annotations

from dataclasses import dataclass

from ternfold.analysis.numeric import Float64
from ternfold.analysis.types import Type, TypeKind
from ternfold.core.nodes import FunctionId, Origin


@dataclass(frozen=True, slots=True)
class Value:
    type: Type
    scalar: int | bool | str | Float64 | None = None
    items: tuple[Value, ...] = ()
    tag: int | None = None
    function: FunctionId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        if not isinstance(self.type, Type) or not self.type.concrete:
            raise ValueError("runtime values require a concrete source type")
        if any(not isinstance(item, Value) for item in self.items):
            raise ValueError("runtime children must be language values")
        kind = self.type.kind
        scalar = self.scalar
        scalar_kind = kind in {
            TypeKind.INT,
            TypeKind.BOOL,
            TypeKind.FLOAT,
            TypeKind.TEXT,
            TypeKind.CHAR,
            TypeKind.UNIT,
        }
        if scalar_kind and (self.items or self.tag is not None or self.function is not None):
            raise ValueError("scalar values cannot contain children, tags or code")
        if kind is TypeKind.INT:
            valid = type(scalar) is int and -(1 << 63) <= scalar < 1 << 63
        elif kind is TypeKind.BOOL:
            valid = type(scalar) is bool
        elif kind is TypeKind.FLOAT:
            valid = isinstance(scalar, Float64)
        elif kind in {TypeKind.TEXT, TypeKind.CHAR}:
            valid = isinstance(scalar, str)
            if valid:
                assert isinstance(scalar, str)
                try:
                    scalar.encode("utf-8", "strict")
                except UnicodeError:
                    valid = False
                if kind is TypeKind.CHAR:
                    valid = valid and len(scalar) == 1
        elif kind is TypeKind.UNIT:
            valid = scalar is None
        elif kind is TypeKind.FUNCTION:
            valid = (
                scalar is None
                and self.tag is None
                and isinstance(self.function, FunctionId)
                and type(self.function.value) is int
                and self.function.value >= 0
            )
        else:
            valid = scalar is None and self.function is None
            if kind is TypeKind.LIST:
                valid = (
                    valid
                    and self.tag is None
                    and len(self.type.arguments) == 1
                    and all(item.type == self.type.arguments[0] for item in self.items)
                )
            elif kind in {TypeKind.RECORD, TypeKind.MACHINE}:
                valid = valid and self.type.nominal_id is not None and self.tag is None
            elif kind in {TypeKind.ENUM, TypeKind.OPTION, TypeKind.DECISION}:
                valid = valid and type(self.tag) is int and self.tag >= 0
            else:
                valid = False
        if not valid:
            raise ValueError("invalid tagged runtime value")


def value_equal(left: Value, right: Value) -> bool:
    """Structural equality with an explicit stack; never Python pointer equality."""
    pending = [(left, right)]
    while pending:
        a, b = pending.pop()
        if a.function is not None or b.function is not None:
            raise ValueError("functions are not equality-capable")
        if (
            a.type != b.type
            or a.scalar != b.scalar
            or a.tag != b.tag
            or len(a.items) != len(b.items)
        ):
            return False
        pending.extend(zip(a.items, b.items, strict=True))
    return True


@dataclass(frozen=True, slots=True)
class Limits:
    max_steps: int = 10_000_000
    max_depth: int = 1_024

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in (self.max_steps, self.max_depth)):
            raise ValueError("execution limits require positive exact integers")


@dataclass(frozen=True, slots=True)
class Fault:
    code: str
    origin: Origin
    message: str
    frames: tuple[Origin, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "frames", tuple(self.frames))
        if self.code not in {"R001", "R002", "R003", "R004", "R005", "R006"}:
            raise ValueError("unknown language fault")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    value: Value | None = None
    fault: Fault | None = None

    def __post_init__(self) -> None:
        if (self.value is None) == (self.fault is None):
            raise ValueError("execution produces exactly one value or fault")
