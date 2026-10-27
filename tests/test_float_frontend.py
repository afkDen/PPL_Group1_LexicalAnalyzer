"""C01 source→tokens→AST→IDs→concrete types/constants→machine plans."""

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from ternfold.analysis.numeric import Float64, decimal_float, float_text
from ternfold.analysis.resolve import PRELUDE_TYPE_IDS, PRELUDE_VALUE_IDS
from ternfold.analysis.types import FLOAT
from ternfold.driver import check, resolve_source, type_source
from ternfold.frontend import ast as A
from ternfold.frontend.ast_dump import ast_dump
from ternfold.frontend.diagnostics import ErrorResult, ValidResult
from ternfold.frontend.lexer import LexResult, lex
from ternfold.frontend.lexical_report import symbol_rows, token_dump
from ternfold.frontend.parser import parse
from ternfold.frontend.source import SourceManager, SourceSpan
from ternfold.frontend.tokens import FloatSpelling
from ternfold.frontend.tokens import TokenKind as K


def scan(text: str, cap: int = 100) -> LexResult:
    source = SourceManager().add_bytes("float.tfd", text.encode()).source
    assert source is not None
    return lex(source, max_diagnostics=cap)


def source(tmp_path: Path, text: str) -> Path:
    entry = tmp_path / "Float & (space).tfd"
    entry.write_bytes(text.encode())
    return entry


@pytest.mark.parametrize(
    "spelling", ["0.0", "1.5", "1e2", "1E+2", "1e-2", "0.00E-00", "12.34e56", "1e999"]
)
def test_exact_float_token_payload_range_deferred_and_ast_dump(spelling: str) -> None:
    result = scan(spelling)
    assert not result.diagnostics.has_errors
    assert [t.kind for t in result.tokens] == [K.FLOAT, K.EOF]
    assert result.tokens[0].value == FloatSpelling(spelling)
    assert json.loads(token_dump(result))["tokens"][0]["value"] == {"float_decimal": spelling}
    assert symbol_rows(result)[0].category == "FLOAT_LITERAL"
    tokens = scan(f"fn f()->Float{{{spelling}}}").for_parser()
    assert isinstance(tokens, ValidResult)
    parsed = parse(tokens.value)
    assert not parsed.diagnostics.has_errors
    declaration = parsed.program.declarations[0]
    assert isinstance(declaration, A.FunctionDecl)
    assert isinstance(declaration.body.result, A.LiteralExpr)
    assert declaration.body.result.value == FloatSpelling(spelling)
    dump = json.loads(ast_dump(parsed))
    assert dump["program"]["declarations"][0]["body"]["result"]["value"] == {
        "float_decimal": spelling
    }


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (".5 1.", [("DOT", "."), ("INT", "5"), ("INT", "1"), ("DOT", ".")]),
        (
            "1.foo 1.2.foo",
            [
                ("INT", "1"),
                ("DOT", "."),
                ("IDENT", "foo"),
                ("FLOAT", "1.2"),
                ("DOT", "."),
                ("IDENT", "foo"),
            ],
        ),
        ("1e++2", [("INVALID", "1e+"), ("PLUS", "+"), ("INT", "2")]),
        ("1efoo.bar", [("INVALID", "1efoo"), ("DOT", "."), ("IDENT", "bar")]),
        ("1.2.3+4", [("INVALID", "1.2.3"), ("PLUS", "+"), ("INT", "4")]),
        ("12abc;1_2", [("INVALID", "12abc"), ("SEMICOLON", ";"), ("INVALID", "1_2")]),
        ("1.0/*x*//2//y\n3e2", [("FLOAT", "1.0"), ("SLASH", "/"), ("INT", "2"), ("FLOAT", "3e2")]),
        ("1e-/*x*/2", [("INVALID", "1e-"), ("INT", "2")]),
        ("1e2e-3", [("INVALID", "1e2e-3")]),
    ],
)
def test_float_recovery_and_projection_comment_boundaries(
    text: str, expected: list[tuple[str, str]]
) -> None:
    result = scan(text)
    assert [(t.kind.value, t.lexeme) for t in result.tokens[:-1]] == expected
    assert all(t.error_code == "E102" for t in result.tokens if t.kind is K.INVALID)


@pytest.mark.parametrize(
    "text",
    ["00.1", "01e2", "1e", "1e+", "1e-", "1.2e", "1.0x", "0xFF", "1e999foo", "1e2.3", "1.2e3_4"],
)
def test_malformed_numeric_run_is_single_e102_with_original_span(text: str) -> None:
    result = scan(text)
    assert [(t.kind, t.lexeme) for t in result.tokens[:-1]] == [(K.INVALID, text)]
    error = result.diagnostics.diagnostics[0]
    assert error.code == "E102" and error.primary.span.start_byte == 0
    assert error.primary.span.end_byte == len(text)
    assert isinstance(result.for_parser(), ErrorResult)


def test_invalid_float_reports_caps_raw_rows_and_utf8_crlf_origins() -> None:
    result = scan('"ñ"\r\n' + "1e+ " * 150)
    assert len(result.diagnostics.diagnostics) == 100
    assert result.diagnostics.suppressed[0].error_count == 50
    assert sum(row.category == "INVALID" for row in symbol_rows(result)) == 150
    assert result.tokens[1].span.start.line == 2 and result.tokens[1].span.start.column == 1
    assert result.tokens[1].span.start_byte == len('"ñ"\r\n'.encode())
    assert isinstance(scan("1e+", cap=0).for_parser(), ErrorResult)


def test_seven_arithmetic_and_nine_boolean_operators_have_exact_independent_spellings() -> None:
    arithmetic = ["+", "-", "/", "*", "%", "div", "^"]
    logical = ["&&", "||", "!", ">", "<", "==", "!=", ">=", "<="]
    assert len(set(arithmetic)) == 7 and len(set(logical)) == 9
    result = scan(" ".join(arithmetic + logical))
    assert [t.kind.value for t in result.tokens[:-1]] == [
        "PLUS",
        "MINUS",
        "SLASH",
        "STAR",
        "PERCENT",
        "DIV",
        "CARET",
        "AND_AND",
        "OR_OR",
        "BANG",
        "GREATER",
        "LESS",
        "EQUAL_EQUAL",
        "BANG_EQUAL",
        "GREATER_EQUAL",
        "LESS_EQUAL",
    ]
    assert [t.lexeme for t in result.tokens[:-1]] == arithmetic + logical
    assert all(row.category == "OPERATOR" for row in symbol_rows(result))


@pytest.mark.parametrize(
    ("expression", "type_"),
    [
        ("7/2", "Float"),
        ("7.0/2", "Float"),
        ("7/2.0", "Float"),
        ("7.0/2.0", "Float"),
        ("5/2/2", "Float"),
        ("1.0+2.0", "Float"),
        ("1.0-2.0", "Float"),
        ("1.0*2.0", "Float"),
        ("-1.0", "Float"),
        ("1.0<2.0", "Bool"),
        ("1.0<=2.0", "Bool"),
        ("1.0>2.0", "Bool"),
        ("1.0>=2.0", "Bool"),
        ("1.0==1.0", "Bool"),
        ("1.0!=2.0", "Bool"),
        ("2.0^-3", "Float"),
        ("-2.0^2", "Float"),
        ("2^3", "Int"),
        ("int_float(1)", "Float"),
        ("float_int(1.9)", "Option[Int]"),
        ("float_text(1.0)", "Text"),
        ("for x in [1.0]{x/2}", "List[Float]"),
        ("append([],1.0)", "List[Float]"),
        ("map([],float_text)", "List[Text]"),
        ("Option::Some(1.0)", "Option[Float]"),
    ],
)
def test_float_operator_and_builtin_signatures(tmp_path: Path, expression: str, type_: str) -> None:
    result = type_source(source(tmp_path, f"fn f()->{type_}{{{expression}}}"))
    assert isinstance(result, ValidResult), result.diagnostics
    assert all(t.concrete for t in result.value.node_types.values())


@pytest.mark.parametrize(
    "text",
    [
        "fn f()->Float{1+2.0}",
        "fn f()->Float{1.0+2}",
        "fn f()->Float{1.0-2}",
        "fn f()->Float{1.0*2}",
        "fn f()->Float{-1}",
        "fn f()->Int{1/2}",
        "fn f()->Float{1}",
        "fn f()->Int{1.0}",
        "fn f()->Bool{1==1.0}",
        "fn f()->Bool{1<1.0}",
        "fn f()->Int{1.0 div 2}",
        "fn f()->Float{1.0%2.0}",
        "fn f()->Float{2.0^2.0}",
        "fn f()->Float{2^2.0}",
        "fn f()->Float{true/1}",
        "fn f()->Float{1/false}",
        "fn f()->Float{int_float(1.0)}",
        "fn f()->Text{float_text(1)}",
        "fn f()->Option[Int]{float_int(1)}",
        "fn f()->Float{-9223372036854775808}",
    ],
)
def test_strict_numeric_types_reject_implicit_conversion(tmp_path: Path, text: str) -> None:
    result = type_source(source(tmp_path, text))
    assert isinstance(result, ErrorResult)
    assert "E302" in [d.code for d in result.diagnostics.diagnostics]


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("7/2", "3.5e0"),
        ("-7/3", "-2.3333333333333335e0"),
        ("5/2/2", "1.25e0"),
        ("(-9223372036854775808)/-1", "9.2233720368547758e18"),
        ("-9223372036854775808/1", "-9.2233720368547758e18"),
        ("-0.0", "0.0e0"),
        ("1e-9999", "0.0e0"),
        ("2.0^-3", "1.25e-1"),
        ("-2.0^2", "-4.0e0"),
        ("(-2.0)^2", "4.0e0"),
        ("0.0^0", "1.0e0"),
        ("1.7976931348623157e308^1", "1.7976931348623157e308"),
        ("1e-300*1e-300", "0.0e0"),
    ],
)
def test_float_constants_real_division_power_and_zero_boundaries(
    tmp_path: Path, expression: str, expected: str
) -> None:
    result = check(
        source(
            tmp_path,
            "machine M(x:Float)yields Float rejects Text{"
            f"state a:Float={expression};next a=x;emit next.a;}}",
        )
    )
    assert isinstance(result, ValidResult), result.diagnostics
    constant = next(iter(result.value.typed.constants.values()))
    assert constant.type == FLOAT and isinstance(constant.scalar, Float64)
    assert float_text(constant.scalar) == expected
    assert len(result.value.plans) == 1


@pytest.mark.parametrize(
    ("expression", "operator"),
    [
        ("1/0", "/"),
        ("1.0/0.0", "/"),
        ("0.0^-1", "^"),
        ("1e308*2.0", "*"),
        ("1e308+1e308", "+"),
        ("1e308/1e-308", "/"),
        ("1e-324^-1", "^"),
        ("2.0^1024", "^"),
    ],
)
def test_float_constant_faults_are_e306_at_original_operator(
    tmp_path: Path, expression: str, operator: str
) -> None:
    result = type_source(
        source(
            tmp_path,
            f"machine M(x:Float)yields Float rejects Text{{state a:Float={expression};next a=x;}}",
        )
    )
    assert isinstance(result, ErrorResult)
    error = next(d for d in result.diagnostics.diagnostics if d.code == "E306")
    assert isinstance(error.primary.span, SourceSpan) and error.primary.span.text == operator


@pytest.mark.parametrize("expression", ["int_float(1)", "float_text(1.0)", "float_int(1.0)"])
def test_conversion_and_formatting_calls_remain_forbidden_constant_syntax(
    tmp_path: Path, expression: str
) -> None:
    type_ = (
        "Text"
        if expression.startswith("float_text")
        else "Option[Int]"
        if expression.startswith("float_int")
        else "Float"
    )
    result = type_source(
        source(
            tmp_path,
            f"machine M(x:Int)yields Int rejects Text{{state a:{type_}={expression};next a=a;}}",
        )
    )
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E306"]


@pytest.mark.parametrize("literal", ["1e999", "1.7976931348623159e308"])
def test_finite_float_literal_error_is_type_phase_e301_not_lexical(
    tmp_path: Path, literal: str
) -> None:
    entry = source(tmp_path, f"fn f()->Float{{{literal}}}")
    assert isinstance(resolve_source(entry), ValidResult)
    result = type_source(entry)
    assert isinstance(result, ErrorResult)
    assert {d.code for d in result.diagnostics.diagnostics} == {"E301"}
    error = result.diagnostics.diagnostics[0]
    assert isinstance(error.primary.span, SourceSpan) and error.primary.span.text == literal


def test_float_pattern_rounding_duplicates_zero_and_open_domain(tmp_path: Path) -> None:
    for arms in (
        "1.0=>{0}",
        "0.0=>{0},-0.0=>{1},_=>{2}",
        "0.1=>{0},0.10000000000000001=>{1},_=>{2}",
    ):
        result = type_source(source(tmp_path, "fn f(x:Float)->Int{match x{" + arms + "}}"))
        assert isinstance(result, ErrorResult)
        assert ("E310" if arms == "1.0=>{0}" else "E311") in [
            d.code for d in result.diagnostics.diagnostics
        ]
    result = type_source(
        source(tmp_path, "fn f(x:Float)->Int{match x{- 1.0=>{0},-/*gap*/2.0=>{1},_=>{2}}}")
    )
    assert isinstance(result, ValidResult), result.diagnostics
    assert isinstance(
        type_source(source(tmp_path, "fn f(x:Float)->Int{match x{1=>{0},_=>{1}}}")), ErrorResult
    )


def test_named_prelude_identity_catalog_preserves_old_option_decision_and_callables(
    tmp_path: Path,
) -> None:
    assert PRELUDE_TYPE_IDS["Option"].declaration_index == 6
    assert PRELUDE_TYPE_IDS["Decision"].declaration_index == 7
    assert PRELUDE_VALUE_IDS["step"].declaration_index == 8
    assert PRELUDE_VALUE_IDS["text_slice"].declaration_index == 20
    ids = [tid.declaration_index for tid in PRELUDE_TYPE_IDS.values()]
    ids += [sid.declaration_index for sid in PRELUDE_VALUE_IDS.values()]
    assert len(ids) == len(set(ids)) == 25
    result = type_source(
        source(
            tmp_path,
            "machine M(x:Float)yields Float rejects Text{state a:Float=0.0;next a=x;}"
            "fn f()->Decision[M,Float,Text]{let v:Option[Float]=Option::None;"
            "let _=match v{Option::Some(x)=>{x},Option::None=>{0.0}};Decision::Accept(M(),[])}",
        )
    )
    assert isinstance(result, ValidResult), result.diagnostics


def test_float_dump_and_plan_are_hashseed_stable_and_not_execution(tmp_path: Path) -> None:
    entry = source(
        tmp_path,
        "machine M(x:Float)yields Float rejects Text{state a:Float=7/2;next a=x;emit next.a;}",
    )
    for command in ("tokens", "ast", "plan"):
        results = [
            subprocess.run(
                [sys.executable, "-m", "ternfold", command, str(entry)],
                env={**os.environ, "PYTHONHASHSEED": seed},
                capture_output=True,
                check=False,
                timeout=15,
            )
            for seed in ("1", "42")
        ]
        assert all(r.returncode == 0 and r.stderr == b"" for r in results)
        assert results[0].stdout == results[1].stdout
        assert b"\r\n" not in results[0].stdout


@pytest.mark.parametrize("forged", [float("inf"), float("-inf"), float("nan"), 0, object()])
def test_typed_float_literal_table_rejects_non_float64_payloads(
    tmp_path: Path,
    forged: object,
) -> None:
    result = type_source(source(tmp_path, "fn f()->Float{1.5}"))
    assert isinstance(result, ValidResult)
    program = result.value
    literal_id = next(iter(program.float_literals))
    with pytest.raises(ValueError, match="Float64"):
        replace(program, float_literals={literal_id: cast(Float64, forged)})


def test_negative_float_pattern_stores_unsigned_token_bits_and_separate_minus_origin(
    tmp_path: Path,
) -> None:
    result = type_source(
        source(tmp_path, "fn f(x:Float)->Int{match x{-1.5=>{0},-/*gap*/0.0=>{1},_=>{2}}}")
    )
    assert isinstance(result, ValidResult), result.diagnostics
    program = result.value
    declaration = program.resolved.graph.modules[0].program.declarations[0]
    assert isinstance(declaration, A.FunctionDecl)
    matching = declaration.body.result
    assert isinstance(matching, A.MatchExpr)
    for arm, spelling in zip(matching.arms[:2], ("1.5", "0.0"), strict=True):
        pattern = arm.pattern
        assert isinstance(pattern, A.LiteralPattern)
        assert pattern.value == FloatSpelling(spelling)
        assert pattern.minus_span is not None and pattern.minus_span.text == "-"
        assert pattern.literal_span.text == spelling
        assert program.float_literals[pattern.node_id] == decimal_float(spelling)
        assert program.float_literals[pattern.node_id].bits >> 63 == 0
