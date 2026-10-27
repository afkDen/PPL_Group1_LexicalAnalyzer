"""ADR 0010 finite binary64 from exact integer ratios, without host FP semantics.

Values store canonical bits. Every primitive rounds once, nearest/ties-even;
formatting rounds the exact binary value to 17 decimal digits before trimming.
No source evaluation, locale conversion, printf/repr formatting or platform pow.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NumericFault(Exception):
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class Float64:
    bits: int

    def __post_init__(self) -> None:
        if type(self.bits) is not int or not 0 <= self.bits < 1 << 64:
            raise ValueError("Float bits must be unsigned 64-bit")
        if (self.bits >> 52) & 2047 == 2047:
            raise ValueError("Float must be finite")
        if self.bits & ((1 << 63) - 1) == 0:
            object.__setattr__(self, "bits", 0)

    def ratio(self) -> tuple[int, int]:
        exponent = (self.bits >> 52) & 2047
        significand = self.bits & ((1 << 52) - 1)
        shift = -1074
        if exponent:
            significand |= 1 << 52
            shift = exponent - 1023 - 52
        if self.bits >> 63:
            significand = -significand
        return (significand << shift, 1) if shift >= 0 else (significand, 1 << -shift)


def _round_quotient(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    twice = remainder * 2
    return quotient + (twice > denominator or (twice == denominator and quotient % 2 == 1))


def from_ratio(numerator: int, denominator: int = 1) -> Float64:
    if denominator == 0:
        raise NumericFault("R002", "Float division by zero")
    negative = (numerator < 0) != (denominator < 0)
    numerator, denominator = abs(numerator), abs(denominator)
    if numerator == 0:
        return Float64(0)
    exponent = numerator.bit_length() - denominator.bit_length()
    if (
        (numerator < denominator << exponent)
        if exponent >= 0
        else (numerator << -exponent < denominator)
    ):
        exponent -= 1
    if exponent > 1023:
        raise NumericFault("R001", "nonfinite Float result")
    shift = max(52 - exponent, 0) if exponent >= -1022 else 1074
    if exponent > 52:
        significand = _round_quotient(numerator, denominator << (exponent - 52))
    else:
        significand = _round_quotient(numerator << shift, denominator)
    if exponent < -1022:
        bits = significand
    else:
        if significand == 1 << 53:
            significand >>= 1
            exponent += 1
        if exponent > 1023:
            raise NumericFault("R001", "nonfinite Float result")
        bits = ((exponent + 1023) << 52) | (significand - (1 << 52))
    return Float64(bits | ((1 << 63) if negative and bits else 0))


def decimal_float(spelling: str) -> Float64:
    """Convert a validated unsigned decimal spelling without host digit limits.

    Exponent parsing saturates beyond the significand length: huge exponents
    classify as overflow/underflow before constructing a power of ten.
    """
    mantissa, marker, exponent_text = spelling.lower().partition("e")
    whole, dot, fraction = mantissa.partition(".")
    digits = (whole + fraction).lstrip("0")
    if not digits:
        return Float64(0)
    exponent = 0
    if marker:
        negative = exponent_text.startswith("-")
        raw = exponent_text.lstrip("+-").lstrip("0") or "0"
        bound = len(spelling) + 2000
        exponent = bound if len(raw) > len(str(bound)) else min(int(raw), bound)
        if negative:
            exponent = -exponent
    exponent -= len(fraction) if dot else 0
    adjusted = len(digits) + exponent - 1
    if adjusted > 309:
        raise NumericFault("R001", "nonfinite Float literal")
    if adjusted < -325:
        return Float64(0)
    stripped = digits.rstrip("0")
    exponent += len(digits) - len(stripped)
    coefficient = 0
    # CPython permits a decimal conversion limit as low as 640 digits. Keep
    # each conversion below that supported minimum without changing the host.
    for offset in range(0, len(stripped), 600):
        chunk = stripped[offset : offset + 600]
        coefficient = coefficient * 10 ** len(chunk) + int(chunk)
    return (
        from_ratio(coefficient * 10**exponent)
        if exponent >= 0
        else from_ratio(coefficient, 10**-exponent)
    )


def int_float(value: int) -> Float64:
    return from_ratio(value)


def float_int(value: Float64) -> int | None:
    numerator, denominator = value.ratio()
    integer = abs(numerator) // denominator
    if numerator < 0:
        integer = -integer
    return integer if -(1 << 63) <= integer < 1 << 63 else None


def negate(value: Float64) -> Float64:
    return Float64(value.bits ^ (1 << 63))


def binary(operator: str, left: Float64, right: Float64) -> Float64:
    a, b = left.ratio()
    c, d = right.ratio()
    if operator == "+":
        return from_ratio(a * d + c * b, b * d)
    if operator == "-":
        return from_ratio(a * d - c * b, b * d)
    if operator == "*":
        return from_ratio(a * c, b * d)
    if operator == "/":
        return from_ratio(a * d, b * c)
    raise ValueError("unsupported Float operation")


def power(base: Float64, exponent: int) -> Float64:
    one = from_ratio(1)
    factor = binary("/", one, base) if exponent < 0 else base
    magnitude = abs(exponent)
    result = one
    while magnitude:
        if magnitude & 1:
            result = binary("*", result, factor)
        magnitude >>= 1
        if magnitude:
            factor = binary("*", factor, factor)
    return result


def compare(left: Float64, right: Float64) -> int:
    a, b = left.ratio()
    c, d = right.ratio()
    difference = a * d - c * b
    return (difference > 0) - (difference < 0)


def float_text(value: Float64) -> str:
    numerator, denominator = value.ratio()
    if numerator == 0:
        return "0.0e0"
    sign = "-" if numerator < 0 else ""
    numerator = abs(numerator)
    # Finite binary64 ratios have at most 1075 decimal digits; exact comparisons
    # avoid logarithm rounding at decimal powers and subnormal boundaries.
    exponent = len(str(numerator)) - len(str(denominator))
    if (
        (numerator < denominator * 10**exponent)
        if exponent >= 0
        else (numerator * 10**-exponent < denominator)
    ):
        exponent -= 1
    shift = 16 - exponent
    digits = (
        _round_quotient(numerator * 10**shift, denominator)
        if shift >= 0
        else _round_quotient(numerator, denominator * 10**-shift)
    )
    if digits == 10**17:
        digits //= 10
        exponent += 1
    decimal = str(digits).zfill(17)
    fraction = decimal[1:].rstrip("0") or "0"
    return f"{sign}{decimal[0]}.{fraction}e{exponent}"
