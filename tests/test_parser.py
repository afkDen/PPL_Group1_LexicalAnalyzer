"""M04 surface grammar, original origins, phase boundaries and recovery."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from ternfold.frontend import ast as A
from ternfold.frontend.ast_dump import ast_dump
from ternfold.frontend.diagnostics import ErrorResult, ValidResult
from ternfold.frontend.lexer import lex
from ternfold.frontend.parser import ParseResult, ParserResourceError, parse
from ternfold.frontend.source import SourceFile, SourceId, SourceSpan
from ternfold.frontend.tokens import DecimalMagnitude, Token
from ternfold.frontend.tokens import TokenKind as K

FIXTURES = Path(__file__).parent / "fixtures" / "parser"


def parsed(text: str, *, root: bool = True, cap: int = 100) -> ParseResult:
    source = SourceFile(SourceId(0), "example.tfd", text.encode())
    lexical = lex(source)
    assert not lexical.diagnostics.has_errors
    return parse(lexical.tokens, root_module=root, max_diagnostics=cap)


def expression(text: str) -> A.Expr:
    result = parsed("fn f() -> Unknown { " + text + " }")
    assert not result.diagnostics.has_errors, result.diagnostics
    declaration = result.program.declarations[0]
    assert isinstance(declaration, A.FunctionDecl)
    return declaration.body.result


def shape(expr: A.Expr) -> object:
    if isinstance(expr, A.BinaryExpr):
        return (expr.operator.value, shape(expr.left), shape(expr.right))
    if isinstance(expr, A.UnaryExpr):
        return (expr.operator.value, shape(expr.operand))
    if isinstance(expr, A.GroupExpr):
        return ("group", shape(expr.expression))
    if isinstance(expr, A.LiteralExpr):
        return expr.value.digits if isinstance(expr.value, DecimalMagnitude) else expr.value
    if isinstance(expr, A.PathExpr):
        return "::".join(name.spelling for name in expr.path.parts)
    if isinstance(expr, A.CallExpr):
        return ("call", shape(expr.callee), tuple(shape(arg.value) for arg in expr.arguments))
    if isinstance(expr, A.ProjectionExpr):
        return ("field", shape(expr.value), expr.field.spelling)
    return type(expr).__name__


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1+2*3", ("PLUS", "1", ("STAR", "2", "3"))),
        ("1*2+3", ("PLUS", ("STAR", "1", "2"), "3")),
        ("1-2-3", ("MINUS", ("MINUS", "1", "2"), "3")),
        ("1 / 2 div 3 % 4", ("PERCENT", ("DIV", ("SLASH", "1", "2"), "3"), "4")),
        ("2^3^2", ("CARET", "2", ("CARET", "3", "2"))),
        ("-2^2", ("MINUS", ("CARET", "2", "2"))),
        ("(-2)^2", ("CARET", ("group", ("MINUS", "2")), "2")),
        ("2^-1", ("CARET", "2", ("MINUS", "1"))),
        ("2^-1^2", ("CARET", "2", ("MINUS", ("CARET", "1", "2")))),
        ("!-x", ("BANG", ("MINUS", "x"))),
        (
            "a || b && c == d < e + f * -g ^ h",
            (
                "OR_OR",
                "a",
                (
                    "AND_AND",
                    "b",
                    (
                        "EQUAL_EQUAL",
                        "c",
                        ("LESS", "d", ("PLUS", "e", ("STAR", "f", ("MINUS", ("CARET", "g", "h"))))),
                    ),
                ),
            ),
        ),
        ("f(1).x(2)", ("call", ("field", ("call", "f", ("1",)), "x"), ("2",))),
        ("-f().x ^ 2", ("MINUS", ("CARET", ("field", ("call", "f", ()), "x"), "2"))),
        ("a++b+c", ("PLUS", ("PLUS_PLUS", "a", "b"), "c")),
    ],
)
def test_precedence_association_and_postfix_shapes(text: str, expected: object) -> None:
    assert shape(expression(text)) == expected


@pytest.mark.parametrize("level", [["<", "<=", ">", ">="], ["==", "!="]])
def test_every_same_level_nonassociative_pair_is_e111(level: list[str]) -> None:
    for first in level:
        for second in level:
            result = parsed(f"fn f() -> Bool {{ a {first} b {second} c }}")
            errors = result.diagnostics.diagnostics
            assert [error.code for error in errors] == ["E111"]
            assert isinstance(errors[0].primary.span, SourceSpan)
            assert errors[0].primary.span.text == second
            assert isinstance(result.for_resolution(), ErrorResult)


@pytest.mark.parametrize(
    "text",
    ["a < b == c < d", "(a < b) == true", "(a==b)==c", "a < (b<c)", "a<b && c<d", "a==b || c!=d"],
)
def test_separate_or_parenthesized_comparison_levels_parse(text: str) -> None:
    expression(text)


@pytest.mark.parametrize("text", ["f(1, x: 2)", "f(x: 1, 2)", "Unknown(1, x: 2, 3)"])
def test_mixed_argument_modes_only_are_e112(text: str) -> None:
    result = parsed(f"fn f() -> X {{ {text} }}")
    assert [error.code for error in result.diagnostics.diagnostics] == ["E112"]


@pytest.mark.parametrize(
    "text",
    [
        "Unknown(x: 1)",
        "unknown(x: 1, y: 2,)",
        "KnownRecord(1, 2)",
        "alias::Record(x: 1)",
        "(fn () -> X { 1 })()",
    ],
)
def test_call_identity_and_named_argument_eligibility_are_deferred(text: str) -> None:
    assert isinstance(expression(text), A.CallExpr)


@pytest.mark.parametrize(
    "text",
    [
        "-9223372036854775808",
        "- 9223372036854775808",
        "-/*gap*/9223372036854775808",
        "-(9223372036854775808)",
        "(-9223372036854775808)",
        "-9223372036854775808^0",
    ],
)
def test_minimum_magnitude_grouping_and_operator_origins_remain_exact(text: str) -> None:
    value = expression(text)
    assert value.span.text == text
    if isinstance(value, A.GroupExpr):
        assert value.open_span.text == "(" and value.close_span.text == ")"
        value = value.expression
    assert isinstance(value, A.UnaryExpr) and value.operator is K.MINUS
    assert value.operator_span.text == "-"
    if "^" in text:
        assert isinstance(value.operand, A.BinaryExpr) and value.operand.operator is K.CARET
    elif "-(" in text:
        assert isinstance(value.operand, A.GroupExpr)
    else:
        assert isinstance(value.operand, A.LiteralExpr)
        assert value.operand.value == DecimalMagnitude("9223372036854775808")
        gap = value.span.source.original_bytes[
            value.operator_span.end_byte : value.operand.span.start_byte
        ]
        assert bool(gap) is (" " in text or "/*" in text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        'import "a.tfd" as a; import "b.tfd" as b;',
        "record Empty {} pub record Pair { left: Int, right: alien::T, }",
        "enum E { None, One(Int), Both(Text, fn(Int, Text) -> Unit), }",
        "fn f(a: List[Option[Int]], cb: fn(Int) -> fn() -> Unit,) -> Other[X,Y] { cb(a) }",
        "fn f() -> Int { let _ = 1; let x: Int = 2; x }",
        "pub fn main() -> Int { 0 }",
        'fn f() -> Int { "wrong type later" }',
        "fn f() -> Unit { if 1 { () } else { if false { () } else { () } } }",
        "fn f() -> X { match x { _ => { () }, false => { true }, -3 => { 0 }, "
        "\"x\" => { 1 }, 'é' => { 2 }, () => { 3 }, None => { 4 }, "
        "Option::None => { 5 }, a::E::Both(x,x,) => { 6 }, } }",
        "fn f() -> X { for row in range(0,2) { for col in xs { row+col } } }",
        "fn f() -> X { [if true { 1 } else { 2 }, fn(x: Int)->Int{x}, "
        "for x in xs{x}, {let z=1;z},] }",
        "fn f() -> X { next.cell.field }",
        "machine M(request: Unit) yields Int rejects Text { state a: Int = f(); "
        "next a = if false { next.a } else { 0 }; next a = (fn()->Int{next.a})(); "
        "guard if true { true } else { false } else bad(); "
        "guard false else later(); emit next.a; emit f(); }",
    ],
)
def test_full_grammar_accepts_unresolved_wrongtyped_and_machine_semantic_errors(text: str) -> None:
    result = parsed(text)
    assert not result.diagnostics.has_errors, result.diagnostics
    assert isinstance(result.for_resolution(), ValidResult)


def test_pattern_binding_vs_variant_and_duplicate_binder_spans() -> None:
    value = expression("match x { None => { 0 }, Option::None => { 1 }, Pair::Both(x,x) => { 2 } }")
    assert isinstance(value, A.MatchExpr)
    assert isinstance(value.arms[0].pattern, A.BindingPattern)
    assert isinstance(value.arms[1].pattern, A.VariantPattern)
    both = value.arms[2].pattern
    assert isinstance(both, A.VariantPattern)
    left, right = both.arguments
    assert isinstance(left, A.BindingPattern) and isinstance(right, A.BindingPattern)
    assert left.name.spelling == right.name.spelling == "x"
    assert left.name.span.end_byte < right.name.span.start_byte


@pytest.mark.parametrize("payload", ["Int,", "Int, Text,", "fn(Int)->Unit,"])
def test_enum_payload_allows_one_trailing_comma_per_normative_variant_grammar(payload: str) -> None:
    result = parsed(f"enum E {{ V({payload}), }}")
    assert not result.diagnostics.has_errors
    declaration = result.program.declarations[0]
    assert isinstance(declaration, A.EnumDecl)
    assert len(declaration.variants) == 1
    assert len(declaration.variants[0].payload) == (2 if payload == "Int, Text," else 1)


def test_machine_clause_order_and_origins_preserve_future_fault_and_dependency_rules() -> None:
    result = parsed(
        "machine M(r: Unit) yields Int rejects Text { state a:Int=0; "
        "next a=if false {next.a} else {1}; next a=2; guard x else first; "
        "guard y else second; emit next.a; }"
    )
    assert not result.diagnostics.has_errors
    machine = result.program.declarations[0]
    assert isinstance(machine, A.MachineDecl)
    assert [type(clause).__name__ for clause in machine.clauses] == [
        "StateClause",
        "WriterClause",
        "WriterClause",
        "GuardClause",
        "GuardClause",
        "EmitClause",
    ]
    first, second = machine.clauses[1:3]
    assert isinstance(first, A.WriterClause) and isinstance(second, A.WriterClause)
    assert first.name.spelling == second.name.spelling == "a"
    assert first.name.span.end_byte < second.name.span.start_byte
    assert isinstance(first.value, A.IfExpr)
    assert isinstance(first.value.then_block.result, A.NextExpr)


@pytest.mark.parametrize(
    "phrase", ['input x: Text; output "a";', 'input x: Text from stdin; output "a" to stdout;']
)
def test_main_outer_io_and_explicit_root_context(phrase: str) -> None:
    text = f"pub fn main() -> Int {{ {phrase} 0 }}"
    result = parsed(text)
    assert not result.diagnostics.has_errors  # Return type remains M06's job.
    decl = result.program.declarations[0]
    assert isinstance(decl, A.FunctionDecl)
    assert isinstance(decl.body.statements[0], A.InputClause)
    assert isinstance(decl.body.statements[1], A.OutputClause)
    assert (decl.body.statements[0].phrase_span is not None) is ("from" in phrase)
    imported = parsed(text, root=False)
    assert [error.code for error in imported.diagnostics.diagnostics] == ["E208", "E208"]


@pytest.mark.parametrize(
    "text",
    [
        'fn main()->Unit { output "x"; () }',
        "pub fn f()->Unit { input x:Text; () }",
        'pub fn main(x:Int)->Unit { output "x"; () }',
        'pub fn main()->Unit { { output "x"; () } }',
        'pub fn main()->Unit { let f=fn()->Unit{output "x";()}; () }',
        "pub fn main()->Unit { for x in xs { input y:Text; () } }",
        'pub fn main()->Unit { if true { output "x"; () } else { () } }',
        'pub fn main()->Unit { match x { _ => {output "x";()} } }',
        'machine M(r:Unit) yields Int rejects Text {state a:Int=0; next a=1; output "x";}',
    ],
)
def test_nested_nonmain_and_machine_io_reject_e208(text: str) -> None:
    result = parsed(text)
    assert result.diagnostics.has_errors
    assert "E208" in [error.code for error in result.diagnostics.diagnostics]
    assert isinstance(result.for_resolution(), ErrorResult)


@pytest.mark.parametrize(
    "clause",
    [
        "input x: Int;",
        "input x: alias::Text;",
        "input _: Text;",
        "input x: Text from;",
        "input x: Text stdin;",
        'output "x" to;',
        'output "x" stdout;',
        "input x: Text to stdout;",
        'output "x" from stdin;',
    ],
)
def test_io_grammar_requires_bare_text_binder_and_paired_phrase(clause: str) -> None:
    result = parsed(f"pub fn main()->Unit {{ {clause} () }}")
    assert result.diagnostics.has_errors


@pytest.mark.parametrize(
    "text",
    [
        "fn f()->Unit {}",
        "fn f()->Unit {let x=1;}",
        "fn f()->Int {1;}",
        "fn f()->X {(1,2)}",
        "fn f()->(Int) {1}",
        "fn f()->X {for _ in xs {1}}",
        "enum E {}",
        "enum E {V()}",
        "fn f()->X {match x {}}",
        "fn f()->X {match x {E::V() => {1}}}",
        "fn f()->List[] {[]}",
        "fn f()->List[Int,] {[]}",
        "fn f()->fn(Int,)->Int {x}",
        "machine M() yields Int rejects Text {state a:Int=0;next a=1;}",
        "machine M(x:Int,) yields Int rejects Text {state a:Int=0;next a=1;}",
        "machine M(x:Int,y:Int) yields Int rejects Text {state a:Int=0;next a=1;}",
        "machine M(x:Int) yields Int rejects Text {next a=1;}",
        "machine M(x:Int) yields Int rejects Text {state a:Int=0;}",
        "machine M(x:Int) yields Int rejects Text {state a:Int=0;next a=1;state b:Int=2;}",
        "machine M(x:Int) yields Int rejects Text "
        "{state a:Int=0;next a=1;emit 1;guard true else x;}",
        'fn f()->Int {0} import "x.tfd" as x;',
        "fn f(input:Int)->Int {input}",
    ],
)
def test_negative_grammar_matrix(text: str) -> None:
    result = parsed(text)
    assert result.diagnostics.has_errors, text
    assert isinstance(result.for_resolution(), ErrorResult)


def test_recovery_preserves_following_declaration_and_zero_width_missing_origins() -> None:
    text = "fn broken(x:Int -> Int { let a = ; let b=2 b }\nfn good()->Int {3}"
    result = parsed(text)
    assert result.diagnostics.has_errors
    names = [
        node.name.spelling
        for node in result.program.declarations
        if isinstance(node, A.FunctionDecl)
    ]
    assert names == ["broken", "good"]
    assert any(item.kind is K.RPAREN for item in result.missing_tokens)
    assert any(item.kind is K.SEMICOLON for item in result.missing_tokens)
    for token in result.missing_tokens:
        assert token.span.start_byte == token.span.end_byte
    assert all(error.code == "E110" for error in result.diagnostics.diagnostics)


def test_missing_brace_does_not_consume_following_top_level_function() -> None:
    result = parsed("fn first()->Int { 1\nfn second()->Int {2}")
    assert [
        node.name.spelling
        for node in result.program.declarations
        if isinstance(node, A.FunctionDecl)
    ] == ["first", "second"]
    assert [item.kind for item in result.missing_tokens] == [K.RBRACE]
    assert result.missing_tokens[0].span.start_byte == result.program.span.text.index("fn second")


@pytest.mark.parametrize(
    ("suffix", "following"),
    [
        ("}", ""),
        ("", ""),
        ("let recovered=2; recovered }", "let"),
        ("fn following()->Int {2}", "fn"),
    ],
)
@pytest.mark.parametrize("garbage", ["garbage", "garbage(2, [3, {4}])", "garbage /*gap*/ (2)"])
def test_recovery_error_statement_covers_all_consumed_tokens_before_boundary(
    suffix: str, following: str, garbage: str
) -> None:
    skipped = "1 " + garbage
    text = "fn f()->Int { " + skipped + " " + suffix
    result = parsed(text)
    assert result.diagnostics.has_errors
    function = result.program.declarations[0]
    assert isinstance(function, A.FunctionDecl)
    statement = function.body.statements[0]
    assert isinstance(statement, A.ErrorStatement)
    assert statement.span.text == skipped
    assert statement.span.end_byte == text.index(skipped) + len(skipped.encode())
    if following == "let":
        assert isinstance(function.body.statements[1], A.Binding)
        assert function.body.statements[1].name.spelling == "recovered"
        assert statement.span.end_byte < function.body.statements[1].span.start_byte
    elif following == "fn":
        next_function = result.program.declarations[1]
        assert isinstance(next_function, A.FunctionDecl)
        assert next_function.name.spelling == "following"
        assert statement.span.end_byte < next_function.span.start_byte


def test_recovery_error_statement_does_not_include_unconsumed_let_without_garbage() -> None:
    result = parsed("fn f()->Int { 1 let x=2; x }")
    function = result.program.declarations[0]
    assert isinstance(function, A.FunctionDecl)
    statement, binding = function.body.statements
    assert isinstance(statement, A.ErrorStatement) and statement.span.text == "1"
    assert isinstance(binding, A.Binding) and binding.name.spelling == "x"


@pytest.mark.parametrize("opener", ["(", "["])
def test_unmatched_skipped_delimiter_preserves_named_declaration_at_brace_depth_zero(
    opener: str,
) -> None:
    skipped = "0 garbage" + opener
    text = "fn f()->Int{" + skipped + " fn g()->Int{0}"
    result = parsed(text)
    assert result.diagnostics.has_errors
    functions = [node for node in result.program.declarations if isinstance(node, A.FunctionDecl)]
    assert [node.name.spelling for node in functions] == ["f", "g"]
    statement = functions[0].body.statements[0]
    assert isinstance(statement, A.ErrorStatement)
    assert statement.span.text == skipped
    assert statement.span.end_byte < text.index("fn g")
    assert any(item.kind is K.RBRACE for item in result.missing_tokens)
    assert all(item.span.start_byte == item.span.end_byte for item in result.missing_tokens)
    assert functions[1].body.result.span.text == "0"


@pytest.mark.parametrize("opener", ["(", "["])
def test_skipped_braces_hide_nested_named_declaration_despite_unmatched_delimiters(
    opener: str,
) -> None:
    skipped = "0 garbage" + opener + " { fn nested()->Int{1} }"
    text = "fn f()->Int{" + skipped + " fn g()->Int{0}"
    result = parsed(text)
    assert result.diagnostics.has_errors
    functions = [node for node in result.program.declarations if isinstance(node, A.FunctionDecl)]
    assert [node.name.spelling for node in functions] == ["f", "g"]
    statement = functions[0].body.statements[0]
    assert isinstance(statement, A.ErrorStatement)
    assert statement.span.text == skipped
    assert statement.span.end_byte < text.index("fn g")
    assert "fn nested" in statement.span.text


def test_depth_aware_recovery_and_diagnostic_cap_cannot_hide_failure() -> None:
    result = parsed("fn f()->Int { " + ";" * 140 + "0 } fn good()->Int{1}")
    assert len(result.diagnostics.diagnostics) == 100
    assert len(result.diagnostics.suppressed) == 1
    assert result.diagnostics.suppressed[0].error_count > 0
    assert isinstance(result.for_resolution(), ErrorResult)
    assert isinstance(result.program.declarations[-1], A.FunctionDecl)
    only_suppressed = parsed("fn f()->Int {}", cap=0)
    assert not only_suppressed.diagnostics.diagnostics
    assert only_suppressed.diagnostics.has_errors
    assert isinstance(only_suppressed.for_resolution(), ErrorResult)


def test_huge_magnitudes_and_group_spans_dump_without_host_integer_conversion() -> None:
    digits = "9" * 6001
    result = parsed(f"fn f()->Int {{ -({digits}) }}")
    assert not result.diagnostics.has_errors
    assert digits in ast_dump(result)


def test_parser_rejects_failed_lexical_stream_and_malformed_eof_contract() -> None:
    source = SourceFile(SourceId(0), "bad", b"@")
    with pytest.raises(ValueError):
        parse(lex(source).tokens)
    with pytest.raises(ValueError):
        parse(())
    eof = source.span(1, 1)
    with pytest.raises(ValueError):
        parse((Token(K.EOF, eof), Token(K.EOF, eof)))


def test_records_frozen_slotted_unique_ids_and_nested_original_span_coordinates() -> None:
    result = parsed('fn f(x:Text)->Text {\r\n let x="é🙂"; (x)\r\n}')
    pending: list[A.Node] = [result.program]
    nodes = []
    while pending:
        node = pending.pop()
        nodes.append(node)
        assert not hasattr(node, "__dict__")
        assert node.node_id.source_id is node.span.source_id
        assert node.span.start_byte <= node.span.end_byte
        for field in fields(node):
            value = getattr(node, field.name)
            if isinstance(value, A.Node):
                pending.append(value)
            elif isinstance(value, tuple):
                pending.extend(item for item in value if isinstance(item, A.Node))
    assert len({node.node_id.value for node in nodes}) == len(nodes)
    assert sorted(node.node_id.value for node in nodes) == list(range(len(nodes)))
    with pytest.raises(FrozenInstanceError):
        result.program.imports = ()  # type: ignore[misc]
    for node in nodes:
        for position in (node.span.start, node.span.end):
            assert (
                node.span.source.byte_offset(position.line, position.column) == position.byte_offset
            )


def test_all_maintained_examples_parse_without_semantic_checks() -> None:
    paths = sorted((Path(__file__).parents[1] / "examples").rglob("*.tfd"))
    assert len(paths) >= 21
    for path in paths:
        source = SourceFile(SourceId(0), path.as_posix(), path.read_bytes())
        result = parse(lex(source).tokens)
        assert not result.diagnostics.has_errors, (path, result.diagnostics)


@pytest.mark.parametrize("name", ["surface", "recovery"])
def test_exact_ast_golden_fixtures(name: str) -> None:
    data = (FIXTURES / f"{name}.tfd").read_bytes()
    source = SourceFile(SourceId(0), f"{name}.tfd", data)
    result = parse(lex(source).tokens)
    assert ast_dump(result) == (FIXTURES / f"{name}.json").read_text(encoding="utf-8")
    assert result.diagnostics.has_errors is (name == "recovery")
    encoded = json.loads(ast_dump(result))
    assert encoded["schema_version"] == 1
    assert encoded["program"]["node_type"] == "Program"


def test_recursion_exhaustion_is_host_resource_error_not_e110() -> None:
    tokens = lex(
        SourceFile(
            SourceId(0), "deep", ("fn f()->Int {" + "(" * 2000 + "0" + ")" * 2000 + "}").encode()
        )
    ).tokens
    with pytest.raises(ParserResourceError, match="recursion"):
        parse(tokens)


@pytest.mark.property
@settings(max_examples=150, deadline=None)
@given(
    st.lists(
        st.sampled_from(
            [
                "fn",
                "f",
                "(",
                ")",
                "{",
                "}",
                "[",
                "]",
                ";",
                ",",
                "let",
                "=",
                "0",
                "->",
                "Int",
                "next",
                "input",
                "output",
                "if",
                "else",
                "match",
                "for",
                "in",
                "::",
                ":",
                "=>",
                "pub",
                "machine",
            ]
        ),
        max_size=100,
    )
)
@example(["fn", "f", "(", ")", "->", "Int", "{", "let", "=", "0", ";", "}"])
def test_bounded_malformed_token_fuzz_terminates_and_blocks_invalid_resolution(
    parts: list[str],
) -> None:
    result = parsed(" ".join(parts))
    assert len(result.diagnostics.diagnostics) <= 100
    assert isinstance(result.for_resolution(), ErrorResult) is result.diagnostics.has_errors
    assert result.program.span.end_byte == len(" ".join(parts).encode())
