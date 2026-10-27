"""Canonical M06 types and immutable, concrete output contracts.

Metavariables and Error are phase-local recovery forms. TypePool owns interning
and substitutions for one check; TypedProgram construction rejects either form.
Nominal identity is the accepted M05 TypeId, never a source spelling.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from ternfold.analysis.numeric import Float64
from ternfold.analysis.resolve import ResolvedProgram, SymbolId, TypeId
from ternfold.frontend.ast import NodeId
from ternfold.frontend.source import SourceSpan


class TypeKind(StrEnum):
    INT = "Int"
    FLOAT = "Float"
    BOOL = "Bool"
    TEXT = "Text"
    CHAR = "Char"
    UNIT = "Unit"
    LIST = "List"
    OPTION = "Option"
    DECISION = "Decision"
    RECORD = "Record"
    ENUM = "Enum"
    MACHINE = "Machine"
    FUNCTION = "Function"
    ERROR = "Error"
    META = "Meta"


@dataclass(frozen=True, slots=True)
class Type:
    kind: TypeKind
    arguments: tuple[Type, ...] = ()
    nominal_id: TypeId | None = None
    variable: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", tuple(self.arguments))

    @property
    def concrete(self) -> bool:
        return self.kind not in {TypeKind.ERROR, TypeKind.META} and all(
            argument.concrete for argument in self.arguments
        )

    @property
    def parameters(self) -> tuple[Type, ...]:
        if self.kind is not TypeKind.FUNCTION:
            raise ValueError("only functions have parameters")
        return self.arguments[:-1]

    @property
    def result(self) -> Type:
        if self.kind is not TypeKind.FUNCTION:
            raise ValueError("only functions have results")
        return self.arguments[-1]

    def __str__(self) -> str:
        if self.nominal_id is not None:
            return f"{self.kind}({self.nominal_id.module.path}:{self.nominal_id.declaration_index})"
        if self.kind is TypeKind.FUNCTION:
            return f"fn({', '.join(map(str, self.parameters))})->{self.result}"
        if self.arguments:
            return f"{self.kind}[{', '.join(map(str, self.arguments))}]"
        return str(self.kind)


INT = Type(TypeKind.INT)
FLOAT = Type(TypeKind.FLOAT)
BOOL = Type(TypeKind.BOOL)
TEXT = Type(TypeKind.TEXT)
CHAR = Type(TypeKind.CHAR)
UNIT = Type(TypeKind.UNIT)
ERROR = Type(TypeKind.ERROR)


class TypePool:
    def __init__(self) -> None:
        self._types = {t: t for t in (INT, FLOAT, BOOL, TEXT, CHAR, UNIT, ERROR)}
        self.substitutions: dict[int, Type] = {}
        self._next_variable = 0

    def make(
        self, kind: TypeKind, arguments: tuple[Type, ...] = (), nominal: TypeId | None = None
    ) -> Type:
        value = Type(kind, arguments, nominal)
        return self._types.setdefault(value, value)

    def function(self, parameters: tuple[Type, ...], result: Type) -> Type:
        return self.make(TypeKind.FUNCTION, (*parameters, result))

    def fresh(self) -> Type:
        variable = self._next_variable
        self._next_variable += 1
        return Type(TypeKind.META, variable=variable)

    def prune(self, value: Type) -> Type:
        if value.kind is TypeKind.META and value.variable in self.substitutions:
            assert value.variable is not None
            result = self.prune(self.substitutions[value.variable])
            self.substitutions[value.variable] = result
            return result
        return value

    def freeze(self, value: Type) -> Type:
        value = self.prune(value)
        if value.kind is TypeKind.META:
            return value
        return self.make(
            value.kind, tuple(self.freeze(a) for a in value.arguments), value.nominal_id
        )

    def _occurs(self, variable: int, value: Type) -> bool:
        value = self.prune(value)
        return value.variable == variable or any(self._occurs(variable, a) for a in value.arguments)

    def unify(self, left: Type, right: Type) -> bool:
        left, right = self.prune(left), self.prune(right)
        if left == right or TypeKind.ERROR in {left.kind, right.kind}:
            return True
        if right.kind is TypeKind.META:
            left, right = right, left
        if left.kind is TypeKind.META:
            assert left.variable is not None
            if self._occurs(left.variable, right):
                return False
            self.substitutions[left.variable] = right
            return True
        if (left.kind, left.nominal_id, len(left.arguments)) != (
            right.kind,
            right.nominal_id,
            len(right.arguments),
        ):
            return False
        return all(self.unify(a, b) for a, b in zip(left.arguments, right.arguments, strict=True))


@dataclass(frozen=True, slots=True)
class NominalInfo:
    type: Type
    declaration: SymbolId
    members: tuple[SymbolId, ...]
    input_type: Type | None = None
    output_type: Type | None = None
    rejection_type: Type | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "members", tuple(self.members))


@dataclass(frozen=True, slots=True)
class BuiltinInstance:
    symbol: SymbolId
    signature: Type
    first_class: bool


@dataclass(frozen=True, slots=True)
class Capture:
    symbol: SymbolId
    type: Type


@dataclass(frozen=True, slots=True)
class Constant:
    type: Type
    scalar: int | bool | str | Float64 | None = None
    items: tuple[Constant, ...] = ()
    variant: SymbolId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class TypedProgram:
    resolved: ResolvedProgram
    node_types: Mapping[NodeId, Type]
    symbol_types: Mapping[SymbolId, Type]
    nominals: Mapping[TypeId, NominalInfo]
    selected_members: Mapping[NodeId, SymbolId]
    builtins: Mapping[NodeId, BuiltinInstance]
    captures: Mapping[NodeId, tuple[Capture, ...]]
    constants: Mapping[SymbolId, Constant]
    origins: Mapping[NodeId, SourceSpan]
    float_literals: Mapping[NodeId, Float64] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "node_types",
            "symbol_types",
            "nominals",
            "selected_members",
            "builtins",
            "captures",
            "constants",
            "origins",
            "float_literals",
        ):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))
        object.__setattr__(
            self,
            "captures",
            MappingProxyType({node: tuple(captures) for node, captures in self.captures.items()}),
        )
        if any(not isinstance(value, Float64) for value in self.float_literals.values()):
            raise ValueError("Float literal table must contain only canonical Float64 values")
        values = tuple(self.node_types.values()) + tuple(self.symbol_types.values())
        values += tuple(instance.signature for instance in self.builtins.values())
        values += tuple(c.type for captures in self.captures.values() for c in captures)
        values += tuple(
            type_
            for info in self.nominals.values()
            for type_ in (info.type, info.input_type, info.output_type, info.rejection_type)
            if type_ is not None
        )
        pending = list(self.constants.values())
        while pending:
            constant = pending.pop()
            values += (constant.type,)
            if (constant.type.kind is TypeKind.FLOAT) != isinstance(constant.scalar, Float64):
                raise ValueError("Float constants must contain canonical finite binary64 values")
            pending.extend(constant.items)
        if any(not value.concrete for value in values):
            raise ValueError("successful TypedProgram must contain only concrete types")
