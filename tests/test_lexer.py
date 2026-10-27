"""M03 lexical DFA, recovery, original spans and genuine-token report coverage."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from ternfold.frontend.diagnostics import ErrorResult, ValidResult
from ternfold.frontend.lexer import LexResult, lex
from ternfold.frontend.lexical_report import render_symbol_table, symbol_rows, token_dump
from ternfold.frontend.source import SourceFile, SourceId, SourceManager
from ternfold.frontend.tokens import (
    KEYWORDS,
    RESERVED_NAMES,
    DecimalMagnitude,
    Token,
    TokenKind,
    TriviaKind,
)

FIXTURES = Path(__file__).parent / "fixtures" / "lexer"
KEYWORD_WORDS = (
    "as div else emit enum false fn for from guard if import in input let machine "
    "match next output pub record rejects state stdin stdout to true yields"
).split()
RESERVED_WORDS = (
    "Int Bool Text Char Unit List Option Decision step len at append map fold range "
    "int_text bool_text parse_int text_len text_at text_slice Float int_float float_int float_text"
).split()


def scan(text: str, *, cap: int = 100) -> LexResult:
    return lex(SourceFile(SourceId(0), "example.tfd", text.encode()), max_diagnostics=cap)


@pytest.mark.parametrize("word", KEYWORD_WORDS)
def test_every_keyword_and_identifier_continuation_maximal_munch(word: str) -> None:
    result = scan(f"{word} {word}x {word}_2")
    assert not result.diagnostics.has_errors
    assert [token.kind.value for token in result.tokens] == [word.upper(), "IDENT", "IDENT", "EOF"]
    if word in {"true", "false"}:
        assert result.tokens[0].value is (word == "true")
    else:
        assert result.tokens[0].value is None
    assert result.tokens[1].value == word + "x"
    assert result.tokens[2].value == word + "_2"


def test_exact_keyword_and_reserved_inventories_are_immutable() -> None:
    assert set(KEYWORDS) == set(KEYWORD_WORDS) and len(KEYWORDS) == 28
    assert RESERVED_NAMES == frozenset(RESERVED_WORDS) and len(RESERVED_NAMES) == 25
    with pytest.raises(TypeError):
        KEYWORDS["new"] = TokenKind.LET  # type: ignore[index]


@pytest.mark.parametrize("word", RESERVED_WORDS)
def test_every_reserved_name_stays_identifier_with_report_overlay(word: str) -> None:
    result = scan(word)
    assert result.tokens[0].kind is TokenKind.IDENT
    assert result.tokens[0].value == word
    assert symbol_rows(result)[0].category == "RESERVED_NAME"
    assert symbol_rows(scan(word.lower() + "x"))[0].category == "IDENTIFIER"


@pytest.mark.parametrize(
    ("glyph", "kind"),
    [
        ("+", "PLUS"),
        ("-", "MINUS"),
        ("*", "STAR"),
        ("/", "SLASH"),
        ("%", "PERCENT"),
        ("^", "CARET"),
        ("<", "LESS"),
        (">", "GREATER"),
        ("=", "EQUAL"),
        ("!", "BANG"),
        (".", "DOT"),
        (",", "COMMA"),
        (";", "SEMICOLON"),
        (":", "COLON"),
        ("(", "LPAREN"),
        (")", "RPAREN"),
        ("[", "LBRACKET"),
        ("]", "RBRACKET"),
        ("{", "LBRACE"),
        ("}", "RBRACE"),
        ("::", "DOUBLE_COLON"),
        ("->", "ARROW"),
        ("=>", "FAT_ARROW"),
        ("==", "EQUAL_EQUAL"),
        ("!=", "BANG_EQUAL"),
        ("<=", "LESS_EQUAL"),
        (">=", "GREATER_EQUAL"),
        ("&&", "AND_AND"),
        ("||", "OR_OR"),
        ("++", "PLUS_PLUS"),
        ("*/", "BLOCK_CLOSE"),
    ],
)
def test_every_operator_and_delimiter_at_eof(glyph: str, kind: str) -> None:
    result = scan(glyph)
    assert [token.kind.value for token in result.tokens] == [kind, "EOF"]
    assert result.tokens[0].lexeme == glyph
    assert result.tokens[0].span.start_byte == 0
    assert result.tokens[0].span.end_byte == len(glyph)
    assert result.tokens[-1].span.start_byte == result.tokens[-1].span.end_byte == len(glyph)
    assert isinstance(result.for_parser(), ValidResult)


@pytest.mark.parametrize(
    ("text", "kinds"),
    [
        ("::::", ["DOUBLE_COLON", "DOUBLE_COLON"]),
        ("===>=", ["EQUAL_EQUAL", "FAT_ARROW", "EQUAL"]),
        ("+++", ["PLUS_PLUS", "PLUS"]),
        ("-->", ["MINUS", "ARROW"]),
        ("&&&|||", ["AND_AND", "INVALID", "OR_OR", "INVALID"]),
        ("/**//", ["SLASH"]),
        ("/**/ /***/ /* x /* y */+", ["PLUS"]),
        ("/*x*/ // line\r\n/", ["SLASH"]),
        (
            "_ _a __ A0 main TRUE true",
            ["UNDERSCORE", "IDENT", "IDENT", "IDENT", "IDENT", "IDENT", "TRUE"],
        ),
    ],
)
def test_adjacencies_comment_priority_and_identifier_states(text: str, kinds: list[str]) -> None:
    assert [token.kind.value for token in scan(text).tokens[:-1]] == kinds


@pytest.mark.parametrize(
    ("spelling", "value"),
    [
        ('""', ""),
        ('"é🙂"', "é🙂"),
        (r'"\""', '"'),
        (r'"\\"', "\\"),
        (r'"\n"', "\n"),
        (r'"\r"', "\r"),
        (r'"\t"', "\t"),
        (r'"\u{0}"', "\0"),
        (r'"\u{000000}"', "\0"),
        (r'"\u{10FFFF}"', "\U0010ffff"),
        (r'"\u{d7ff}\u{E000}"', "\ud7ff\ue000"),
        ('"' + "'" + '"', "'"),
        ('"é"', "é"),
        ('"\x85"', "\x85"),
    ],
)
def test_text_exact_escape_repertoire_and_scalar_payloads(spelling: str, value: str) -> None:
    result = scan(spelling)
    assert not result.diagnostics.has_errors
    token = result.tokens[0]
    assert token.kind is TokenKind.TEXT and token.value == value
    assert token.lexeme == spelling
    assert token.span.end_byte == len(spelling.encode())


@pytest.mark.parametrize(
    ("body", "value"),
    [
        ("a", "a"),
        ("ñ", "ñ"),
        ("🙂", "🙂"),
        ('"', '"'),
        (r"\"", '"'),
        (r"\\", "\\"),
        (r"\n", "\n"),
        (r"\r", "\r"),
        (r"\t", "\t"),
        (r"\u{27}", "'"),
        (r"\u{0}", "\0"),
        (r"\u{1F642}", "🙂"),
        (r"\u{10ffff}", "\U0010ffff"),
    ],
)
def test_char_uses_exact_text_escapes_and_one_scalar(body: str, value: str) -> None:
    spelling = "'" + body + "'"
    result = scan(spelling)
    assert not result.diagnostics.has_errors
    assert result.tokens[0].kind is TokenKind.CHAR
    assert result.tokens[0].value == value
    assert result.tokens[0].span.end_byte == len(spelling.encode())


@pytest.mark.parametrize("quote", ['"', "'"])
@pytest.mark.parametrize(
    "escape",
    [
        r"\'",
        r"\q",
        r"\0",
        r"\x41",
        r"\u",
        r"\u12",
        r"\u{}",
        r"\u{G}",
        r"\u{1234567}",
        r"\u{110000}",
        r"\u{D800}",
        r"\u{DFFF}",
        r"\u{12",
    ],
)
def test_bad_escapes_are_one_invalid_literal_with_exact_span(quote: str, escape: str) -> None:
    spelling = quote + escape + quote
    result = scan(spelling + " next")
    assert [token.kind for token in result.tokens] == [
        TokenKind.INVALID,
        TokenKind.NEXT,
        TokenKind.EOF,
    ]
    assert len(result.diagnostics.diagnostics) == 1
    error = result.diagnostics.diagnostics[0]
    assert error.code == ("E103" if quote == '"' else "E105")
    assert error.primary.span == result.source.span(0, len(spelling.encode()))
    assert isinstance(result.for_parser(), ErrorResult)


@pytest.mark.parametrize("char", [chr(number) for number in range(32)] + ["\x7f"])
@pytest.mark.parametrize("quote", ['"', "'"])
def test_all_forbidden_raw_literal_controls(char: str, quote: str) -> None:
    # Source CR must be paired with LF before lexical validation is possible.
    body = "\r\n" if char == "\r" else char
    result = scan(quote + body + quote)
    assert result.diagnostics.has_errors
    assert result.diagnostics.diagnostics[0].code == ("E103" if quote == '"' else "E105")


@pytest.mark.parametrize("text", ["''", "'ab'", "'é'", "'", "'a", "'\\"])
def test_char_cardinality_and_eof_errors(text: str) -> None:
    result = scan(text)
    assert result.tokens[0].kind is TokenKind.INVALID
    assert result.tokens[0].error_code == "E105"
    assert result.tokens[0].span.end_byte == len(text.encode())


@pytest.mark.parametrize("text", ['"', '"abc', '"\\', '"\\u{123'])
def test_unterminated_text_and_escape_at_eof(text: str) -> None:
    result = scan(text)
    assert result.tokens[0].error_code == "E103"
    assert result.tokens[-1].kind is TokenKind.EOF
    assert result.tokens[0].span.end_byte == len(text)


def test_newline_recovery_excludes_crlf_and_preserves_following_tokens() -> None:
    result = scan('"é\r\nlet x = 1;')
    first = result.tokens[0]
    assert (first.span.start_byte, first.span.end_byte, first.error_code) == (0, 3, "E103")
    assert result.trivia[0].span.text == "\r\n"
    assert result.tokens[1].kind is TokenKind.LET
    assert (result.tokens[1].span.start.line, result.tokens[1].span.start.column) == (2, 1)


@pytest.mark.parametrize("text", ["/*", "/**", "/*é\r\n", "/* one /* two"])
def test_unterminated_block_comment_is_one_invalid_run_through_eof(text: str) -> None:
    result = scan(text)
    assert [token.kind for token in result.tokens] == [TokenKind.INVALID, TokenKind.EOF]
    assert result.tokens[0].error_code == "E104"
    assert result.tokens[0].span == result.source.span(0, len(text.encode()))
    assert symbol_rows(result)[0].category == "INVALID"


def test_comments_nonnesting_unicode_controls_and_eof() -> None:
    result = scan("/* a /* é\0 */ //🙂\x1b\r\n// eof")
    assert not result.diagnostics.has_errors
    assert [item.kind for item in result.trivia] == [
        TriviaKind.COMMENT_BLOCK,
        TriviaKind.WHITESPACE,
        TriviaKind.COMMENT_LINE,
        TriviaKind.WHITESPACE,
        TriviaKind.COMMENT_LINE,
    ]
    assert result.trivia[0].lexeme == "/* a /* é\0 */"
    assert result.trivia[2].lexeme == "//🙂\x1b"
    assert result.tokens == (
        Token(
            TokenKind.EOF,
            result.source.span(
                len(result.source.original_bytes), len(result.source.original_bytes)
            ),
        ),
    )


@pytest.mark.parametrize("text", ["00", "0123", "09", "000000"])
def test_leading_zero_digit_run_is_one_e102(text: str) -> None:
    result = scan(text + "x")
    assert result.tokens[0].lexeme == text + "x"
    assert result.tokens[0].error_code == "E102"
    assert result.tokens[1].kind is TokenKind.EOF


@pytest.mark.parametrize(
    "digits",
    ["0", "9", "9223372036854775807", "9223372036854775808", "9223372036854775809", "9" * 6001],
)
def test_unsigned_magnitudes_never_apply_signed_or_host_decimal_limits(digits: str) -> None:
    result = scan("-" + digits)
    assert not result.diagnostics.has_errors
    assert [token.kind for token in result.tokens] == [
        TokenKind.MINUS,
        TokenKind.INT,
        TokenKind.EOF,
    ]
    assert result.tokens[1].value == DecimalMagnitude(digits)
    assert json.loads(token_dump(result))["tokens"][1]["value"] == {"decimal": digits}


def test_unsupported_numeric_spellings_are_not_invented_as_tokens() -> None:
    result = scan("0xFF 1_2 1.5")
    assert [token.kind.value for token in result.tokens] == [
        "INVALID",
        "INVALID",
        "FLOAT",
        "EOF",
    ]
    assert [d.code for d in result.diagnostics.diagnostics] == ["E102", "E102"]


@pytest.mark.parametrize(
    "char",
    [
        "@",
        "&",
        "|",
        "\\",
        "?",
        "~",
        "`",
        "$",
        "é",
        "🙂",
        "\0",
        "\x1b",
        "\x7f",
        "\x85",
        "\u00a0",
        "\ufeff",
    ],
)
def test_unsupported_scalar_not_silently_ignored(char: str) -> None:
    result = scan(" " + char)
    assert result.tokens[0].error_code == "E101"
    assert result.tokens[0].span.start_byte == 1
    assert result.tokens[0].span.end_byte == 1 + len(char.encode())


def test_cap_recovers_all_tokens_preserves_invalid_report_rows_and_blocks_parser() -> None:
    result = scan("@" * 150 + " let ok = 0;")
    assert len(result.diagnostics.diagnostics) == 100
    assert len(result.diagnostics.suppressed) == 1
    assert (
        result.diagnostics.suppressed[0].count == result.diagnostics.suppressed[0].error_count == 50
    )
    assert sum(token.kind is TokenKind.INVALID for token in result.tokens) == 150
    assert sum(row.category == "INVALID" for row in symbol_rows(result)) == 150
    assert isinstance(result.for_parser(), ErrorResult)
    assert result.tokens[-2].kind is TokenKind.SEMICOLON
    suppressed_only = scan("@", cap=0)
    assert not suppressed_only.diagnostics.diagnostics
    assert isinstance(suppressed_only.for_parser(), ErrorResult)
    with pytest.raises(ValueError):
        replace(result, diagnostics=scan("").diagnostics)


@pytest.mark.parametrize(
    ("text", "noise"),
    [
        ("input x: Text from stdin;", ["from"]),
        ('output "a" to stdout;', ["to"]),
        ('output if true { "a" } else { "b" } to stdout;', ["to"]),
        ('output { let x = "a"; x } to stdout;', ["to"]),
        ("{ input x: Text /*n*/ from //n\r\n stdin; output x to stdout; }", ["from", "to"]),
        ('output { output "inner" to stdout; "outer" } to stdout;', ["to", "to"]),
        ("from stdin; to stdout; input x: Text to stdout;", []),
        ('output "x" from stdin; input x: Text from stdout;', []),
        ('output "x" to stdout', []),
        ('let x = output "x" to stdout;', []),
    ],
)
def test_contextual_noise_overlay_is_a_lexical_clause_shape(text: str, noise: list[str]) -> None:
    result = scan(text)
    assert not result.diagnostics.has_errors
    assert [row.span.text for row in symbol_rows(result) if row.category == "NOISE_WORD"] == noise
    for token in result.tokens:
        if token.lexeme in {"from", "to"}:
            assert token.kind in {TokenKind.FROM, TokenKind.TO}


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ("()", 1),
        ("( \r\n /*n*/ )", 1),
        ("(//n\n)", 1),
        ("(())", 1),
        ("f()", 0),
        ("f /*n*/ ( )", 0),
        ("fn f() -> Unit {}", 0),
        ("fn () -> Unit { () }", 1),
        ("f(())", 1),
        ("(f)()", 0),
        ("[]()", 0),
        ("let x = ();", 1),
    ],
)
def test_additional_unit_views_keep_real_parens_and_exclude_obvious_calls(
    text: str, count: int
) -> None:
    result = scan(text)
    rows = symbol_rows(result)
    assert sum(row.category == "UNIT_LITERAL" for row in rows) == count
    assert sum(row.kind == "LPAREN" for row in rows) == text.count("(")
    assert sum(row.kind == "RPAREN" for row in rows) == text.count(")")
    assert all(row.view == "composite" for row in rows if row.category == "UNIT_LITERAL")
    assert len([row for row in rows if row.view == "token"]) == len(result.tokens) - 1


def test_report_and_dump_exact_golden_and_original_coordinate_assertions() -> None:
    result = lex(SourceFile(SourceId(0), "report.tfd", (FIXTURES / "report.tfd").read_bytes()))
    assert render_symbol_table(result) == (FIXTURES / "Symbol Table.txt").read_text(
        encoding="utf-8"
    )
    assert token_dump(result) == (FIXTURES / "tokens.json").read_text(encoding="utf-8")
    categories = {row.category for row in symbol_rows(result)}
    assert categories >= {
        "KEYWORD",
        "RESERVED_NAME",
        "NOISE_WORD",
        "IDENTIFIER",
        "INT_LITERAL",
        "BOOL_LITERAL",
        "TEXT_LITERAL",
        "CHAR_LITERAL",
        "UNIT_LITERAL",
        "COMMENT_LINE",
        "COMMENT_BLOCK",
        "OPERATOR",
        "DELIMITER",
        "INVALID",
    }
    for token, data in zip(result.tokens, json.loads(token_dump(result))["tokens"], strict=True):
        assert data["lexeme"].encode() == token.span.original_bytes
        for endpoint in ("start", "end"):
            position = data["span"][endpoint]
            assert (
                result.source.byte_offset(position["line"], position["column"]) == position["byte"]
            )


def test_all_repository_examples_lex_even_when_semantically_invalid() -> None:
    examples = sorted((Path(__file__).parents[1] / "examples").rglob("*.tfd"))
    assert examples
    for path in examples:
        loaded = SourceManager().load_path(path)
        assert loaded.source is not None, str(path)
        result = lex(loaded.source)
        assert not result.diagnostics.has_errors, (str(path), result.diagnostics)


def test_token_records_and_payload_validation() -> None:
    result = scan("1 'a' true x")
    assert all(
        not hasattr(item, "__dict__")
        for item in (result, *result.tokens, *result.trivia, result.tokens[0].value)
    )
    with pytest.raises(FrozenInstanceError):
        result.tokens[0].kind = TokenKind.TEXT  # type: ignore[misc]
    span = result.tokens[0].span
    for digits in ["", "00", "-1", "１", "1_0"]:
        with pytest.raises(ValueError):
            DecimalMagnitude(digits)
    with pytest.raises(TypeError):
        Token(TokenKind.INT, span, 1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Token(TokenKind.TEXT, span)
    with pytest.raises(ValueError):
        Token(TokenKind.CHAR, span, "ab")
    with pytest.raises(ValueError):
        Token(TokenKind.TRUE, span, False)
    with pytest.raises(ValueError):
        Token(TokenKind.PLUS, span, "+")
    with pytest.raises(ValueError):
        Token(TokenKind.PLUS, span, error_code="E101")
    with pytest.raises(ValueError):
        Token(TokenKind.INVALID, span)
    with pytest.raises(ValueError):
        replace(result, tokens=result.tokens[:-1])
    with pytest.raises(ValueError):
        replace(result, tokens=(Token(TokenKind.EOF, span),))


alphabet = st.characters(exclude_categories=["Cs"], exclude_characters="\r\ufeff")


@pytest.mark.property
@settings(max_examples=150)
@given(st.text(alphabet=alphabet, max_size=200))
@example('"\\\n/* é */ @&&| 001\n')
@example("\r\n")
def test_fuzz_scanner_progress_exact_coverage_eof_and_bounded_diagnostics(text: str) -> None:
    result = scan(text)
    parts = sorted(
        [token.span for token in result.tokens[:-1]] + [item.span for item in result.trivia],
        key=lambda span: span.start_byte,
    )
    offset = 0
    for span in parts:
        assert span.start_byte == offset < span.end_byte
        offset = span.end_byte
    assert offset == len(text.encode())
    assert result.tokens[-1].span == result.source.span(offset, offset)
    assert len(result.diagnostics.diagnostics) <= 100
    assert isinstance(result.for_parser(), ErrorResult) is result.diagnostics.has_errors


@pytest.mark.property
@given(st.text(alphabet=st.characters(exclude_categories=["Cs"]), max_size=80))
def test_generated_text_escapes_roundtrip_scalar_values(value: str) -> None:
    body = "".join(
        "\\" + char
        if char in {'"', "\\"}
        else f"\\u{{{ord(char):x}}}"
        if ord(char) < 32 or ord(char) == 127
        else char
        for char in value
    )
    result = scan('"' + body + '"')
    assert not result.diagnostics.has_errors
    assert result.tokens[0].value == value
