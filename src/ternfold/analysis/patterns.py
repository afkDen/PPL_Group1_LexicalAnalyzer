"""Typed recursive pattern matrices, with ordered usefulness and witnesses.

Finite domains are Bool, Unit, enums, Option and Decision. Int/Text/Char remain
open; records/lists/machines/functions are opaque and only bindable as a whole.
The checker owns AST pattern typing. This module never guesses from spellings.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ternfold.analysis.modules import ModuleId
from ternfold.analysis.numeric import Float64
from ternfold.analysis.resolve import (
    PRELUDE_TYPE_IDS,
    ResolvedProgram,
    SymbolId,
    SymbolKind,
    TypeId,
)
from ternfold.analysis.types import BOOL, UNIT, NominalInfo, Type, TypeKind


@dataclass(frozen=True, slots=True)
class Constructor:
    tag: str
    payload: tuple[Type, ...] = ()
    symbol: SymbolId | None = None
    literal: int | bool | str | Float64 | None = None
    display: str = ""


@dataclass(frozen=True, slots=True)
class Pattern:
    constructor: Constructor | None = None
    arguments: tuple[Pattern, ...] = ()

    def render(self) -> str:
        if self.constructor is None:
            return "_"
        display = self.constructor.display
        if display == "_":
            return "_"
        return display + (
            "(" + ", ".join(p.render() for p in self.arguments) + ")" if self.arguments else ""
        )


WILDCARD = Pattern()
type Row = tuple[Pattern, ...]
type Matrix = tuple[Row, ...]


class Coverage:
    def __init__(
        self,
        resolved: ResolvedProgram,
        symbol_types: Mapping[SymbolId, Type],
        nominals: Mapping[TypeId, NominalInfo],
        module: ModuleId | None = None,
    ) -> None:
        self.resolved = resolved
        self.symbol_types = symbol_types
        self.nominals = nominals
        self.module = module or resolved.graph.entry

    def qualifier(self, declaration: SymbolId) -> str | None:
        owner = self.resolved.symbols[declaration]
        if declaration.module == self.module:
            return owner.name
        namespace = next(ns for ns in self.resolved.namespaces if ns.module_id == self.module)
        for sid in namespace.types.values():
            alias = self.resolved.symbols[sid]
            if alias.kind is SymbolKind.IMPORT and alias.target_module == declaration.module:
                return alias.name + "::" + owner.name
        return None

    def constructors(self, type_: Type) -> tuple[Constructor, ...] | None:
        if type_ == BOOL:
            return (
                Constructor("Bool", literal=False, display="false"),
                Constructor("Bool", literal=True, display="true"),
            )
        if type_ == UNIT:
            return (Constructor("Unit", display="()"),)
        if type_.kind is TypeKind.ENUM:
            assert type_.nominal_id is not None
            info = self.nominals[type_.nominal_id]
            result: list[Constructor] = []
            qualifier = self.qualifier(info.declaration)
            for sid in info.members:
                signature = self.symbol_types[sid]
                payload = signature.parameters if signature.kind is TypeKind.FUNCTION else ()
                result.append(
                    Constructor(
                        "variant",
                        payload,
                        sid,
                        display=qualifier + "::" + self.resolved.symbols[sid].name
                        if qualifier
                        else "_",
                    )
                )
            return tuple(result)
        if type_.kind in {TypeKind.OPTION, TypeKind.DECISION}:
            name = "Option" if type_.kind is TypeKind.OPTION else "Decision"
            variants = sorted(
                (
                    symbol
                    for symbol in self.resolved.symbols.values()
                    if symbol.kind is SymbolKind.VARIANT
                    and symbol.owner is not None
                    and symbol.owner.module.path == "<prelude>"
                    and symbol.owner == PRELUDE_TYPE_IDS[name]
                ),
                key=lambda s: s.symbol_id,
            )
            payloads: tuple[tuple[Type, ...], ...]
            if name == "Option":
                payloads = ((type_.arguments[0],), ())
            else:
                machine, output, error = type_.arguments
                payloads = ((machine, Type(TypeKind.LIST, (output,))), (machine, error))
            return tuple(
                Constructor("variant", payload, symbol.symbol_id, display=name + "::" + symbol.name)
                for symbol, payload in zip(variants, payloads, strict=True)
            )
        return None

    @staticmethod
    def specialize(matrix: Matrix, constructor: Constructor) -> Matrix:
        rows: list[Row] = []
        for row in matrix:
            head, *tail = row
            if head.constructor is None:
                rows.append((WILDCARD,) * len(constructor.payload) + tuple(tail))
            elif head.constructor == constructor:
                rows.append(head.arguments + tuple(tail))
        return tuple(rows)

    def useful(self, matrix: Matrix, row: Row, types: tuple[Type, ...]) -> Row | None:
        """Return a symbolic witness in row's domain not covered by matrix."""
        # A wildcard vector subsumes every query at this specialization. Do not
        # enumerate the Cartesian product of its finite payload domains.
        if any(all(pattern.constructor is None for pattern in covered) for covered in matrix):
            return None
        if not matrix:
            return self.uncovered_witness(row, types)
        if not row:
            return None
        head, tail = row[0], row[1:]
        if head.constructor is None and all(covered[0].constructor is None for covered in matrix):
            # This column cannot distinguish any covering row from the query.
            # Branching over its finite constructors would repeat the same tail
            # problem once per inhabitant, exponentially across wide payloads.
            witness = self.useful(tuple(covered[1:] for covered in matrix), tail, types[1:])
            if witness is None:
                return None
            return self.uncovered_witness((head,), types[:1]) + witness
        if head.constructor is not None:
            constructor = head.constructor
            witness = self.useful(
                self.specialize(matrix, constructor),
                head.arguments + tail,
                constructor.payload + types[1:],
            )
            if witness is None:
                return None
            count = len(constructor.payload)
            return (Pattern(constructor, witness[:count]),) + witness[count:]
        domain = self.constructors(types[0])
        if domain is not None:
            for constructor in domain:
                witness = self.useful(
                    self.specialize(matrix, constructor),
                    (WILDCARD,) * len(constructor.payload) + tail,
                    constructor.payload + types[1:],
                )
                if witness is not None:
                    count = len(constructor.payload)
                    return (Pattern(constructor, witness[:count]),) + witness[count:]
            return None
        default = tuple(row[1:] for row in matrix if row[0].constructor is None)
        witness = self.useful(default, tail, types[1:])
        return None if witness is None else (WILDCARD,) + witness

    def uncovered_witness(self, row: Row, types: tuple[Type, ...]) -> Row:
        """Choose one inhabitant per column, without exploring combinations.

        Nominal cycles were rejected before coverage. Finite wildcard domains
        choose their first constructor, preserving deterministic witness order;
        open/opaque domains retain a symbolic residual wildcard.
        """
        witness: list[Pattern] = []
        for pattern, type_ in zip(row, types, strict=True):
            constructor = pattern.constructor
            arguments = pattern.arguments
            if constructor is None:
                domain = self.constructors(type_)
                if domain is None:
                    witness.append(WILDCARD)
                    continue
                constructor = domain[0]
                arguments = (WILDCARD,) * len(constructor.payload)
            witness.append(
                Pattern(constructor, self.uncovered_witness(arguments, constructor.payload))
            )
        return tuple(witness)
