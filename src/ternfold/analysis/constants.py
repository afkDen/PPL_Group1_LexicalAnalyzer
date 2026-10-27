"""Closed initializer validation/evaluation only; never a program interpreter."""

from collections.abc import Mapping
from dataclasses import dataclass

from ternfold.analysis.numeric import (
    Float64,
    NumericFault,
    binary,
    compare,
    int_float,
    negate,
    power,
)
from ternfold.analysis.resolve import ResolvedProgram, SymbolId, SymbolKind
from ternfold.analysis.types import Constant, Type, TypeKind
from ternfold.frontend import ast as A
from ternfold.frontend.source import SourceSpan
from ternfold.frontend.tokens import DecimalMagnitude
from ternfold.frontend.tokens import TokenKind as K

INT_MIN = -(1 << 63)
INT_MAX = (1 << 63) - 1


@dataclass(frozen=True, slots=True)
class ConstantError(Exception):
    message: str
    span: SourceSpan


def literal_int(magnitude: DecimalMagnitude, *, minimum_exception: bool = False) -> int | None:
    limit = "9223372036854775808" if minimum_exception else "9223372036854775807"
    digits = magnitude.digits
    if (len(digits), digits) > (len(limit), limit):
        return None
    return int(digits)


def contiguous_minimum(expression: A.UnaryExpr) -> bool:
    operand = expression.operand
    return (
        expression.operator is K.MINUS
        and isinstance(operand, A.LiteralExpr)
        and isinstance(operand.value, DecimalMagnitude)
        and operand.value.digits == "9223372036854775808"
        and expression.operator_span.end_byte == operand.literal_span.start_byte
    )


def checked_int(value: int, span: SourceSpan) -> int:
    if not INT_MIN <= value <= INT_MAX:
        raise ConstantError("constant Int overflow", span)
    return value


def integer_binary(operator: K, left: int, right: int, span: SourceSpan) -> int:
    if operator in {K.DIV, K.PERCENT}:
        if right == 0:
            raise ConstantError("constant division/remainder by zero", span)
        if left == INT_MIN and right == -1:
            raise ConstantError("constant Int division/remainder overflow", span)
        quotient = abs(left) // abs(right)
        if (left < 0) != (right < 0):
            quotient = -quotient
        remainder = left - quotient * right
        if operator is K.PERCENT:
            return remainder
        if operator is K.DIV and remainder != 0 and (left < 0) != (right < 0):
            quotient -= 1
        return quotient
    if operator is K.CARET:
        if right < 0:
            raise ConstantError("constant negative exponent", span)
        result, base, exponent = 1, left, right
        while exponent:
            if exponent & 1:
                result = checked_int(result * base, span)
            exponent >>= 1
            if exponent:
                base = checked_int(base * base, span)
        return result
    if operator is K.PLUS:
        return checked_int(left + right, span)
    if operator is K.MINUS:
        return checked_int(left - right, span)
    if operator is K.STAR:
        return checked_int(left * right, span)
    raise ValueError("not an Int arithmetic operator")


def evaluate_initializer(
    expression: A.Expr,
    resolved: ResolvedProgram,
    types: Mapping[A.NodeId, Type],
    selected: Mapping[A.NodeId, SymbolId],
    float_literals: Mapping[A.NodeId, Float64],
) -> Constant:
    """Called only after successful typing. Reject forbidden syntax before evaluation."""

    def constructor(node: A.Expr) -> SymbolId | None:
        if not isinstance(node, A.PathExpr):
            return None
        sid = resolved.references[node.node_id].symbol_id
        if resolved.symbols[sid].kind in {SymbolKind.RECORD, SymbolKind.VARIANT}:
            return sid
        return None

    def validate(node: A.Expr) -> None:
        if isinstance(node, (A.LiteralExpr, A.UnitExpr)):
            return
        if isinstance(node, A.GroupExpr):
            validate(node.expression)
        elif isinstance(node, A.ListExpr):
            for element in node.elements:
                validate(element)
        elif isinstance(node, A.UnaryExpr):
            validate(node.operand)
        elif isinstance(node, A.BinaryExpr):
            validate(node.left)
            validate(node.right)
        elif isinstance(node, A.CallExpr) and constructor(node.callee) is not None:
            for argument in node.arguments:
                validate(argument.value)
        elif isinstance(node, A.PathExpr) and constructor(node) is not None:
            return
        else:
            raise ConstantError("initializer requires a closed constant expression", node.span)

    def scalar_equal(left: Constant, right: Constant) -> bool:
        return (
            left.type == right.type
            and left.scalar == right.scalar
            and left.variant == right.variant
            and len(left.items) == len(right.items)
            and all(scalar_equal(a, b) for a, b in zip(left.items, right.items, strict=True))
        )

    def evaluate(node: A.Expr) -> Constant:
        type_ = types[node.node_id]
        if isinstance(node, A.UnitExpr):
            return Constant(type_)
        if isinstance(node, A.LiteralExpr):
            if node.kind is K.FLOAT:
                return Constant(type_, float_literals[node.node_id])
            if isinstance(node.value, DecimalMagnitude):
                return Constant(type_, int(node.value.digits))
            assert isinstance(node.value, (bool, str))
            return Constant(type_, node.value)
        if isinstance(node, A.GroupExpr):
            return evaluate(node.expression)
        if isinstance(node, A.ListExpr):
            return Constant(type_, items=tuple(evaluate(e) for e in node.elements))
        if isinstance(node, A.PathExpr):
            return Constant(type_, variant=resolved.references[node.node_id].symbol_id)
        if isinstance(node, A.CallExpr):
            sid = constructor(node.callee)
            assert sid is not None
            values = [(argument, evaluate(argument.value)) for argument in node.arguments]
            symbol = resolved.symbols[sid]
            if symbol.kind is SymbolKind.RECORD:
                assert symbol.type_id is not None
                fields = {selected[arg.node_id]: value for arg, value in values}
                return Constant(
                    type_, items=tuple(fields[s] for s in resolved.members[symbol.type_id])
                )
            return Constant(type_, items=tuple(value for _, value in values), variant=sid)
        if isinstance(node, A.UnaryExpr):
            if contiguous_minimum(node):
                return Constant(type_, INT_MIN)
            operand = evaluate(node.operand)
            if node.operator is K.BANG:
                assert isinstance(operand.scalar, bool)
                return Constant(type_, not operand.scalar)
            if isinstance(operand.scalar, Float64):
                return Constant(type_, negate(operand.scalar))
            assert type(operand.scalar) is int
            return Constant(type_, checked_int(-operand.scalar, node.operator_span))
        if isinstance(node, A.BinaryExpr):
            left = evaluate(node.left)
            if node.operator is K.AND_AND and left.scalar is False:
                return Constant(type_, False)
            if node.operator is K.OR_OR and left.scalar is True:
                return Constant(type_, True)
            right = evaluate(node.right)
            op = node.operator
            if op in {K.EQUAL_EQUAL, K.BANG_EQUAL}:
                equal = scalar_equal(left, right)
                return Constant(type_, equal if op is K.EQUAL_EQUAL else not equal)
            if op in {K.AND_AND, K.OR_OR}:
                assert isinstance(right.scalar, bool)
                return Constant(type_, right.scalar)
            if op is K.PLUS_PLUS:
                if type_.kind is TypeKind.TEXT:
                    assert isinstance(left.scalar, str) and isinstance(right.scalar, str)
                    return Constant(type_, left.scalar + right.scalar)
                return Constant(type_, items=left.items + right.items)
            if op is K.SLASH or isinstance(left.scalar, Float64):
                assert isinstance(left.scalar, Float64) or type(left.scalar) is int
                left_value = (
                    left.scalar if isinstance(left.scalar, Float64) else int_float(left.scalar)
                )
                if op is K.CARET:
                    assert type(right.scalar) is int
                    try:
                        return Constant(type_, power(left_value, right.scalar))
                    except NumericFault as error:
                        raise ConstantError(error.message, node.operator_span) from error
                assert isinstance(right.scalar, Float64) or type(right.scalar) is int
                right_value = (
                    right.scalar if isinstance(right.scalar, Float64) else int_float(right.scalar)
                )
                if op in {K.LESS, K.LESS_EQUAL, K.GREATER, K.GREATER_EQUAL}:
                    order = compare(left_value, right_value)
                    return Constant(
                        type_,
                        {
                            K.LESS: order < 0,
                            K.LESS_EQUAL: order <= 0,
                            K.GREATER: order > 0,
                            K.GREATER_EQUAL: order >= 0,
                        }[op],
                    )
                try:
                    return Constant(
                        type_,
                        binary(
                            {K.PLUS: "+", K.MINUS: "-", K.STAR: "*", K.SLASH: "/"}[op],
                            left_value,
                            right_value,
                        ),
                    )
                except NumericFault as error:
                    raise ConstantError(error.message, node.operator_span) from error
            assert type(left.scalar) is int and type(right.scalar) is int
            a, b = left.scalar, right.scalar
            if op in {K.LESS, K.LESS_EQUAL, K.GREATER, K.GREATER_EQUAL}:
                return Constant(
                    type_,
                    {
                        K.LESS: a < b,
                        K.LESS_EQUAL: a <= b,
                        K.GREATER: a > b,
                        K.GREATER_EQUAL: a >= b,
                    }[op],
                )
            return Constant(type_, integer_binary(op, a, b, node.operator_span))
        raise AssertionError("validated constant form was not evaluated")

    validate(expression)
    return evaluate(expression)
