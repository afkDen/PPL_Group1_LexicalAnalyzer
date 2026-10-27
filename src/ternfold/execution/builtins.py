"""Checked primitive and non-calling prelude semantics for verified Core."""

from dataclasses import dataclass

from ternfold.analysis.numeric import (
    Float64,
    NumericFault,
    compare,
    float_int,
    float_text,
    int_float,
    negate,
    power,
)
from ternfold.analysis.numeric import (
    binary as float_binary,
)
from ternfold.analysis.types import BOOL, FLOAT, INT, TEXT, Type
from ternfold.execution.values import Value, value_equal


@dataclass(frozen=True, slots=True)
class PrimitiveFault(Exception):
    code: str
    message: str


def checked(value: int) -> int:
    if not -(1 << 63) <= value < 1 << 63:
        raise PrimitiveFault("R001", "Int overflow")
    return value


def integer(operator: str, left: int, right: int) -> int:
    if operator in {"div", "%"}:
        if right == 0:
            raise PrimitiveFault("R002", "division/remainder by zero")
        if left == -(1 << 63) and right == -1:
            raise PrimitiveFault("R001", "Int division/remainder overflow")
        quotient = abs(left) // abs(right)
        if (left < 0) != (right < 0):
            quotient = -quotient
        remainder = left - quotient * right
        return (
            remainder
            if operator == "%"
            else quotient - int(remainder != 0 and (left < 0) != (right < 0))
        )
    if operator == "^":
        if right < 0:
            raise PrimitiveFault("R005", "negative Int exponent")
        result, base, exponent = 1, left, right
        while exponent:
            if exponent & 1:
                result = checked(result * base)
            exponent >>= 1
            if exponent:
                base = checked(base * base)
        return result
    if operator == "+":
        return checked(left + right)
    if operator == "-":
        return checked(left - right)
    if operator == "*":
        return checked(left * right)
    raise ValueError("unverified integer operation")


def unary(operator: str, value: Value) -> Value:
    if operator == "!":
        assert type(value.scalar) is bool
        return Value(BOOL, not value.scalar)
    if isinstance(value.scalar, Float64):
        return Value(FLOAT, negate(value.scalar))
    assert type(value.scalar) is int
    return Value(INT, checked(-value.scalar))


def binary(operator: str, left: Value, right: Value, result: Type) -> Value:
    if operator in {"==", "!="}:
        equal = value_equal(left, right)
        return Value(BOOL, equal if operator == "==" else not equal)
    if operator == "++":
        if left.type == TEXT:
            assert isinstance(left.scalar, str) and isinstance(right.scalar, str)
            return Value(TEXT, left.scalar + right.scalar)
        return Value(result, items=left.items + right.items)
    if isinstance(left.scalar, Float64) or operator == "/":
        assert isinstance(left.scalar, Float64) or type(left.scalar) is int
        a = left.scalar if isinstance(left.scalar, Float64) else int_float(left.scalar)
        if operator == "^":
            assert type(right.scalar) is int
            return Value(FLOAT, power(a, right.scalar))
        assert isinstance(right.scalar, Float64) or type(right.scalar) is int
        b = right.scalar if isinstance(right.scalar, Float64) else int_float(right.scalar)
        if operator in {"<", "<=", ">", ">="}:
            order = compare(a, b)
            return Value(
                BOOL, {"<": order < 0, "<=": order <= 0, ">": order > 0, ">=": order >= 0}[operator]
            )
        return Value(FLOAT, float_binary(operator, a, b))
    assert type(left.scalar) is int and type(right.scalar) is int
    if operator in {"<", "<=", ">", ">="}:
        a_int, b_int = left.scalar, right.scalar
        return Value(
            BOOL,
            {"<": a_int < b_int, "<=": a_int <= b_int, ">": a_int > b_int, ">=": a_int >= b_int}[
                operator
            ],
        )
    return Value(INT, integer(operator, left.scalar, right.scalar))


def _option(type_: Type, value: Value | None) -> Value:
    return Value(type_, items=() if value is None else (value,), tag=1 if value is None else 0)


def primitive(name: str, args: tuple[Value, ...], result: Type) -> Value:
    first = args[0]
    if name == "len":
        return Value(INT, checked(len(first.items)))
    if name == "append":
        checked(len(first.items) + 1)
        return Value(result, items=first.items + (args[1],))
    if name == "at":
        index = args[1].scalar
        assert type(index) is int
        return _option(result, first.items[index] if 0 <= index < len(first.items) else None)
    if name == "range":
        a, b = first.scalar, args[1].scalar
        assert type(a) is int and type(b) is int
        length = max(0, b - a)
        checked(length)
        # Resource exhaustion is defined separately from mathematical overflow.
        if length > 1_000_000:
            raise PrimitiveFault("R003", "interpreter list allocation limit")
        return Value(result, items=tuple(Value(INT, i) for i in range(a, b)))
    if name == "int_text":
        assert type(first.scalar) is int
        return Value(TEXT, str(first.scalar))
    if name == "bool_text":
        return Value(TEXT, "true" if first.scalar is True else "false")
    if name == "int_float":
        assert type(first.scalar) is int
        return Value(FLOAT, int_float(first.scalar))
    if name == "float_int":
        assert isinstance(first.scalar, Float64)
        converted = float_int(first.scalar)
        return _option(result, Value(INT, converted) if converted is not None else None)
    if name == "float_text":
        assert isinstance(first.scalar, Float64)
        return Value(TEXT, float_text(first.scalar))
    assert isinstance(first.scalar, str)
    text = first.scalar
    if name == "parse_int":
        negative = bool(text) and text[0] == "-"
        digits = text[1:] if negative else text
        valid = (
            bool(digits)
            and (digits[0] != "0" or len(digits) == 1)
            and all("0" <= c <= "9" for c in digits)
        )
        limit = "9223372036854775808" if negative else "9223372036854775807"
        if not valid or (len(digits), digits) > (len(limit), limit):
            return _option(result, None)
        value = int(digits)
        return _option(result, Value(INT, -value if negative else value))
    if name == "text_len":
        return Value(INT, checked(len(text)))
    if name == "text_at":
        index = args[1].scalar
        assert type(index) is int
        return _option(result, Value(TEXT, text[index]) if 0 <= index < len(text) else None)
    if name == "text_slice":
        start, end = args[1].scalar, args[2].scalar
        assert type(start) is int and type(end) is int
        return _option(
            result, Value(TEXT, text[start:end]) if 0 <= start <= end <= len(text) else None
        )
    raise ValueError("unknown verified builtin")


FAULTS = (PrimitiveFault, NumericFault)
