"""C01 exact binary64 and formatting helper boundaries."""

import os
import random
import struct
import subprocess
import sys
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from ternfold.analysis.numeric import (
    Float64,
    NumericFault,
    binary,
    compare,
    decimal_float,
    float_int,
    float_text,
    from_ratio,
    int_float,
    negate,
    power,
)


def bits(value: float) -> int:
    return int.from_bytes(struct.pack(">d", value), "big") if value else 0


def oracle_format(value: Float64) -> str:
    numerator, denominator = value.ratio()
    if numerator == 0:
        return "0.0e0"
    with localcontext() as context:
        context.prec = 1200
        exact = Decimal(numerator) / Decimal(denominator)
        exponent = exact.copy_abs().adjusted()
        quantum = Decimal(1).scaleb(exponent - 16)
        rounded = exact.quantize(quantum, rounding=ROUND_HALF_EVEN)
        exponent = rounded.copy_abs().adjusted()
        mantissa = format(rounded.scaleb(-exponent), "f")
        if "." not in mantissa:
            mantissa += ".0"
        else:
            mantissa = mantissa.rstrip("0").rstrip(".")
            if "." not in mantissa:
                mantissa += ".0"
        return mantissa + "e" + str(exponent)


def test_binary64_ratio_rounding_and_scientific_format() -> None:
    assert decimal_float("0.1").bits == 0x3FB999999999999A
    assert float_text(from_ratio(7, 2)) == "3.5e0"
    assert float_text(decimal_float("0.1")) == "1.0000000000000001e-1"
    assert decimal_float("1e-9999999999999999999999").bits == 0


@pytest.mark.parametrize(
    "spelling",
    [
        "0.0",
        "1.0",
        "1e308",
        "1.7976931348623157e308",
        "2.2250738585072014e-308",
        "2.225073858507201e-308",
        "4.9406564584124654e-324",
        "2.4703282292062327e-324",
        "2.4703282292062328e-324",
        "0.1000000000000000055511151231257827021181583404541015625",
        "9007199254740993.0",
        "1.00000000000000011102230246251565404236316680908203125",
        "1.00000000000000011102230246251565404236316680908203126",
    ],
)
def test_decimal_conversion_matches_independent_fraction_oracle(spelling: str) -> None:
    assert decimal_float(spelling).bits == bits(float(Fraction(spelling)))


def test_random_ratio_rounding_and_arithmetic_against_fraction() -> None:
    rng = random.Random(10010)
    for _ in range(1000):
        numerator = rng.randrange(-(1 << 100), 1 << 100)
        denominator = rng.randrange(1, 1 << 100)
        value = from_ratio(numerator, denominator)
        assert value.bits == bits(float(Fraction(numerator, denominator)))
        a = Float64(rng.randrange(0, 2047) << 52 | rng.getrandbits(52))
        b = Float64(rng.randrange(0, 2047) << 52 | rng.getrandbits(52))
        x, y = Fraction(*a.ratio()), Fraction(*b.ratio())
        for operator, exact in (
            ("+", x + y),
            ("-", x - y),
            ("*", x * y),
            ("/", x / y if y else None),
        ):
            if exact is None:
                with pytest.raises(NumericFault, match="zero"):
                    binary(operator, a, b)
                continue
            try:
                expected = float(exact)
            except OverflowError:
                with pytest.raises(NumericFault) as error:
                    binary(operator, a, b)
                assert error.value.code == "R001"
            else:
                assert binary(operator, a, b).bits == bits(expected)
        assert compare(a, b) == ((x > y) - (x < y))


def test_formatter_matches_decimal_oracle_and_roundtrips_bits() -> None:
    rng = random.Random(101017)
    fixed = [
        0,
        1,
        (1 << 52) - 1,
        1 << 52,
        0x7FEFFFFFFFFFFFFF,
        0x3FB999999999999A,
        bits(1e20),
        bits(1e-20),
        bits(9.999999999999998),
        bits(9.999999999999999),
    ]
    values = fixed + [
        rng.getrandbits(64) & ~(2047 << 52) | rng.randrange(2047) << 52 for _ in range(1000)
    ]
    for raw in values:
        value = Float64(raw)
        text = float_text(value)
        assert text == oracle_format(value)
        parsed = decimal_float(text.lstrip("-"))
        assert (negate(parsed) if text.startswith("-") else parsed) == value


def test_conversion_bounds_zero_normalization_and_nonfinite_rejection() -> None:
    assert Float64(1 << 63).bits == 0 and negate(Float64(0)).bits == 0
    assert float_int(int_float((1 << 63) - 1)) is None
    assert float_int(int_float(-(1 << 63))) == -(1 << 63)
    assert float_int(decimal_float("1.9")) == 1
    assert float_int(negate(decimal_float("1.9"))) == -1
    assert float_int(Float64(1)) == 0
    assert int_float(9007199254740993).bits == bits(float(9007199254740993))
    for raw in (0x7FF0000000000000, 0x7FF0000000000001, 0xFFF0000000000000):
        with pytest.raises(ValueError):
            Float64(raw)
    with pytest.raises(NumericFault) as error:
        decimal_float("1e9999999999999999999999999999")
    assert error.value.code == "R001"


def test_power_sequence_and_extreme_domains_against_independent_rounded_fraction_oracle() -> None:
    def rounded(value: Fraction) -> Float64:
        try:
            return Float64(bits(float(value)))
        except (OverflowError, ValueError) as error:
            raise NumericFault("R001", "oracle overflow") from error

    def oracle(base: Float64, exponent: int) -> Float64:
        factor = rounded(1 / Fraction(*base.ratio())) if exponent < 0 else base
        result = int_float(1)
        # Read exponent bits least-significant first; round every multiply.
        binary_digits = bin(abs(exponent))[2:][::-1] if exponent else ""
        for index, digit in enumerate(binary_digits):
            if digit == "1":
                result = rounded(Fraction(*result.ratio()) * Fraction(*factor.ratio()))
            if index + 1 < len(binary_digits):
                factor = rounded(Fraction(*factor.ratio()) ** 2)
        return result

    for spelling in ("0.5", "1.1", "2.0", "1e-50", "1e50"):
        for exponent in (-65, -3, -1, 0, 1, 2, 63):
            base = decimal_float(spelling)
            try:
                expected = oracle(base, exponent)
            except NumericFault:
                with pytest.raises(NumericFault):
                    power(base, exponent)
            else:
                assert power(base, exponent) == expected
    assert power(int_float(0), 0) == int_float(1)
    assert power(int_float(1), -(1 << 63)) == int_float(1)
    assert power(Float64(0x7FEFFFFFFFFFFFFF), 1).bits == 0x7FEFFFFFFFFFFFFF
    with pytest.raises(NumericFault) as error:
        power(Float64(0), -1)
    assert error.value.code == "R002"
    with pytest.raises(NumericFault) as error:
        power(Float64(1), -1)  # reciprocal faults before exponent loop
    assert error.value.code == "R001"


def test_long_decimal_payload_and_exponent_do_not_use_host_decimal_int_limit() -> None:
    assert decimal_float("1" + "0" * 10000 + "e-10000") == int_float(1)
    assert decimal_float("0.0e" + "9" * 10000).bits == 0
    assert decimal_float("1e-" + "9" * 10000).bits == 0


def test_long_finite_literal_reaches_typed_program_with_minimum_host_digit_limit(
    tmp_path: Path,
) -> None:
    spelling = "1" + "1" * 999 + "e-999"
    entry = tmp_path / "long finite.tfd"
    entry.write_text(f"fn f()->Float{{{spelling}}}", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "ternfold", "check", str(entry)],
        env={**os.environ, "PYTHONINTMAXSTRDIGITS": "640"},
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0 and result.stdout == result.stderr == b"", result.stderr
