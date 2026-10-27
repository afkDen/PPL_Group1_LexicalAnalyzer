"""Closed initializers, exact arithmetic, literal spans and immutable data."""

import math
import random
from fractions import Fraction
from pathlib import Path

import pytest

from ternfold.analysis.constants import INT_MAX, INT_MIN, ConstantError, integer_binary
from ternfold.analysis.types import Constant
from ternfold.driver import type_source as check
from ternfold.frontend.diagnostics import ErrorResult, ValidResult
from ternfold.frontend.source import SourceManager, SourceSpan
from ternfold.frontend.tokens import TokenKind as K


def initializer(tmp_path: Path, expression: str, type_: str = "Int", prefix: str = "") -> Constant:
    entry = tmp_path / "constant.tfd"
    entry.write_text(
        prefix
        + f"machine M(x:Int)yields Int rejects Text{{state a:{type_}={expression};next a=a;}}",
        encoding="utf-8",
    )
    result = check(entry)
    assert isinstance(result, ValidResult), result.diagnostics
    return next(iter(result.value.constants.values()))


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("-9223372036854775808", INT_MIN),
        ("9223372036854775807", INT_MAX),
        ("(-9223372036854775808)^1", INT_MIN),
        ("(-2)^63", INT_MIN),
        ("0^0", 1),
        ("0^9223372036854775807", 0),
        ("1^9223372036854775807", 1),
        ("(-1)^9223372036854775807", -1),
        ("2^3^2", 512),
        ("-2^2", -4),
        ("(-2)^2", 4),
        ("-7 div 3", -3),
        ("7 div -3", -3),
        ("-7 div -3", 2),
        ("-7%3", -1),
        ("7%-3", 1),
        ("-9223372036854775808 div 1", INT_MIN),
        ("(-9223372036854775808)+9223372036854775807", -1),
    ],
)
def test_checked_constant_arithmetic_boundaries(
    tmp_path: Path, expression: str, expected: int
) -> None:
    assert initializer(tmp_path, expression).scalar == expected


@pytest.mark.parametrize(
    ("expression", "operator"),
    [
        ("9223372036854775807+1", "+"),
        ("(-9223372036854775808)-1", "-"),
        ("9223372036854775807*2", "*"),
        ("2^63", "^"),
        ("2^-1", "^"),
        ("-(-9223372036854775808)", "-"),
        ("(-9223372036854775808) div -1", "div"),
        ("(-9223372036854775808)%-1", "%"),
        ("1 div 0", "div"),
        ("1%0", "%"),
    ],
)
def test_constant_faults_are_e306_at_operator_span(
    tmp_path: Path, expression: str, operator: str
) -> None:
    entry = tmp_path / "bad.tfd"
    entry.write_text(
        f"machine M(x:Int)yields Int rejects Text{{state a:Int={expression};next a=a;}}",
        encoding="utf-8",
    )
    result = check(entry)
    assert isinstance(result, ErrorResult)
    error = next(d for d in result.diagnostics.diagnostics if d.code == "E306")
    assert isinstance(error.primary.span, SourceSpan)
    assert error.primary.span.text == operator
    assert len(error.secondary) == 1


@pytest.mark.parametrize(
    "expression",
    [
        "9223372036854775808",
        "- 9223372036854775808",
        "-/*gap*/9223372036854775808",
        "-(9223372036854775808)",
        "-9223372036854775809",
        pytest.param("9" * 100000, id="100000-digit-magnitude"),
    ],
)
def test_literal_range_is_e301_instead_of_constant_fault(tmp_path: Path, expression: str) -> None:
    entry = tmp_path / "bad.tfd"
    entry.write_text(
        f"machine M(x:Int)yields Int rejects Text{{state a:Int={expression};next a=a;}}",
        encoding="utf-8",
    )
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert {d.code for d in result.diagnostics.diagnostics} == {"E301"}


@pytest.mark.parametrize(
    "expression",
    ["x", "a", "helper()", "{1}", "if true{1}else{2}", "match true{_=>{1}}", "(fn()->Int{1})()"],
)
def test_forbidden_initializer_forms_are_not_general_ast_execution(
    tmp_path: Path, expression: str
) -> None:
    entry = tmp_path / "bad.tfd"
    entry.write_text(
        "fn helper()->Int{1}"
        + f"machine M(x:Int)yields Int rejects Text{{state a:Int={expression};next a=a;}}",
        encoding="utf-8",
    )
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert "E306" in [d.code for d in result.diagnostics.diagnostics]


def test_nested_machine_constructor_is_forbidden_in_constant(tmp_path: Path) -> None:
    entry = tmp_path / "bad.tfd"
    entry.write_text(
        "machine A(x:Int)yields Int rejects Text{state a:Int=0;next a=x;}"
        "machine B(x:Int)yields Int rejects Text{state a:Option[A]=Option::Some(A());next a=a;}",
        encoding="utf-8",
    )
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E306"]


def test_shortcircuit_validates_all_forms_but_evaluates_only_selected_rhs(tmp_path: Path) -> None:
    assert initializer(tmp_path, "false&&(1/0==0.0)", "Bool").scalar is False
    assert initializer(tmp_path, "true||(2^-1==0)", "Bool").scalar is True
    entry = tmp_path / "forbidden.tfd"
    entry.write_text(
        "fn helper()->Bool{true}machine M(x:Int)yields Int rejects Text{"
        "state a:Bool=false&&helper();next a=a;}",
        encoding="utf-8",
    )
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E306"]


def test_constant_aggregates_char_equality_and_declaration_order(tmp_path: Path) -> None:
    value = initializer(
        tmp_path, "R(y:['b','c'],x:Option::Some('a'))", "R", "record R{x:Option[Char],y:List[Char]}"
    )
    assert value.items[0].variant is not None and value.items[0].items[0].scalar == "a"
    assert [c.scalar for c in value.items[1].items] == ["b", "c"]
    assert initializer(tmp_path, "'a'=='a'", "Bool").scalar is True
    assert initializer(tmp_path, "[1,2]++[3]", "List[Int]").items[-1].scalar == 3
    assert initializer(tmp_path, '"a\\u{0}"++"ñ"', "Text").scalar == "a\0ñ"
    assert initializer(tmp_path, "()", "Unit").scalar is None


def test_exact_signed_division_against_fraction_oracle() -> None:
    source = SourceManager().add_bytes("op.tfd", b"/").source
    assert source is not None
    span = SourceSpan(source, 0, 1)
    rng = random.Random(606)
    for _ in range(1000):
        a = rng.randrange(INT_MIN, INT_MAX + 1)
        b = rng.randrange(INT_MIN, INT_MAX + 1) or 1
        quotient = Fraction(a, b)
        assert integer_binary(K.DIV, a, b, span) == math.floor(quotient)
        assert integer_binary(K.PERCENT, a, b, span) == a - math.trunc(quotient) * b
    for operator in (K.DIV, K.PERCENT):
        with pytest.raises(ConstantError):
            integer_binary(operator, INT_MIN, -1, span)
