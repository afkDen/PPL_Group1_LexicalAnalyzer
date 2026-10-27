"""Deterministic lexer-derived views, never a parser or semantic symbol table.

``token_dump`` emits schema-v1 JSON with all genuine tokens, including recovery
INVALID and EOF. Int values are objects ``{"decimal": "..."}`` at every size;
no host decimal-int conversion or JSON numeric conversion is used.

``symbol_rows`` retains genuine tokens (excluding EOF), adds comment trivia,
and additional UNIT_LITERAL composite rows. Empty parentheses may enclose any
trivia, but are excluded after IDENT/literals/closing delimiters/FN, recognizable
call/parameter shapes. Both genuine parens and enclosed comments remain rows.
This shape view does not establish a Unit expression or valid syntax.

NOISE_WORD overlays FROM/TO only in a lexical INPUT/OUTPUT-led segment, followed
respectively by STDIN/STDOUT and a semicolon. Semicolons reset the current brace
segment; a brace-context stack preserves outer clauses across block expressions.
Trivia is ignored for this check. It does not establish main scope, a valid
binder/type/expression, or any other parser/semantic property. Other FROM/TO
tokens remain KEYWORD. Reserved names use the IDENT token
flag supplied by the character DFA terminal; no report spelling lookup occurs.

The UTF-8 report is TSV with JSON-escaped lexemes and filename, explicit token/
trivia/composite views, byte endpoints, scalar endpoints and lexical error codes.
It preserves invalid rows even after diagnostic suppression. No file I/O occurs
here; the driver owns all output publication and path policy.
"""

import json
from dataclasses import dataclass

from ternfold.frontend.lexer import LexResult
from ternfold.frontend.render import RenderContext
from ternfold.frontend.source import SourceSpan
from ternfold.frontend.tokens import (
    KEYWORDS,
    DecimalMagnitude,
    FloatSpelling,
    Token,
    TokenKind,
    TriviaKind,
)

_DELIMITERS = frozenset(
    {
        TokenKind.DOT,
        TokenKind.COMMA,
        TokenKind.SEMICOLON,
        TokenKind.COLON,
        TokenKind.LPAREN,
        TokenKind.RPAREN,
        TokenKind.LBRACKET,
        TokenKind.RBRACKET,
        TokenKind.LBRACE,
        TokenKind.RBRACE,
        TokenKind.DOUBLE_COLON,
        TokenKind.UNDERSCORE,
        TokenKind.BLOCK_CLOSE,
    }
)
_CALLEE_ENDS = frozenset(
    {
        TokenKind.IDENT,
        TokenKind.INT,
        TokenKind.FLOAT,
        TokenKind.TEXT,
        TokenKind.CHAR,
        TokenKind.TRUE,
        TokenKind.FALSE,
        TokenKind.RPAREN,
        TokenKind.RBRACKET,
        TokenKind.RBRACE,
        TokenKind.FN,
    }
)


def _span_data(span: SourceSpan) -> dict[str, object]:
    return {
        "start": {"byte": span.start_byte, "line": span.start.line, "column": span.start.column},
        "end": {"byte": span.end_byte, "line": span.end.line, "column": span.end.column},
    }


def token_dump(result: LexResult, context: RenderContext | None = None) -> str:
    context = context if context is not None else RenderContext()
    tokens: list[dict[str, object]] = []
    for token in result.tokens:
        value = (
            {"decimal": token.value.digits}
            if isinstance(token.value, DecimalMagnitude)
            else {"float_decimal": token.value.spelling}
            if isinstance(token.value, FloatSpelling)
            else token.value
        )
        tokens.append(
            {
                "kind": token.kind.value,
                "lexeme": token.lexeme,
                "span": _span_data(token.span),
                "value": value,
                "error_code": token.error_code,
            }
        )
    return (
        json.dumps(
            {
                "schema_version": 1,
                "file": context.filename(result.source.display_name),
                "has_errors": result.diagnostics.has_errors,
                "tokens": tokens,
            },
            ensure_ascii=True,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


@dataclass(frozen=True, slots=True)
class SymbolRow:
    span: SourceSpan
    category: str
    kind: str
    view: str
    error_code: str | None = None


def _noise_indices(tokens: tuple[Token, ...]) -> set[int]:
    indices: set[int] = set()
    clause: TokenKind | None = None
    at_start = True
    contexts: list[tuple[TokenKind | None, bool]] = []
    for index, token in enumerate(tokens):
        kind = token.kind
        if kind is TokenKind.LBRACE:
            contexts.append((clause, at_start))
            clause, at_start = None, True
            continue
        if kind is TokenKind.RBRACE:
            clause, at_start = contexts.pop() if contexts else (None, True)
            continue
        if kind is TokenKind.SEMICOLON:
            clause, at_start = None, True
            continue
        if at_start:
            clause = kind if kind in {TokenKind.INPUT, TokenKind.OUTPUT} else None
            at_start = False
        if index + 2 >= len(tokens) or tokens[index + 2].kind is not TokenKind.SEMICOLON:
            continue
        if (clause, kind, tokens[index + 1].kind) in {
            (TokenKind.INPUT, TokenKind.FROM, TokenKind.STDIN),
            (TokenKind.OUTPUT, TokenKind.TO, TokenKind.STDOUT),
        }:
            indices.add(index)
    return indices


def _category(token: Token, noise: bool) -> str:
    kind = token.kind
    if kind is TokenKind.INVALID:
        return "INVALID"
    if kind is TokenKind.IDENT:
        return "RESERVED_NAME" if token.reserved_name else "IDENTIFIER"
    if kind in {TokenKind.TRUE, TokenKind.FALSE}:
        return "BOOL_LITERAL"
    if kind in {TokenKind.INT, TokenKind.FLOAT, TokenKind.TEXT, TokenKind.CHAR}:
        return f"{kind.value}_LITERAL"
    if noise:
        return "NOISE_WORD"
    if kind is TokenKind.DIV:
        return "OPERATOR"
    if kind in KEYWORDS.values():
        return "KEYWORD"
    return "DELIMITER" if kind in _DELIMITERS else "OPERATOR"


def symbol_rows(result: LexResult) -> tuple[SymbolRow, ...]:
    rows: list[SymbolRow] = []
    noise = _noise_indices(result.tokens)
    for index, token in enumerate(result.tokens):
        if token.kind is TokenKind.EOF:
            continue
        rows.append(
            SymbolRow(
                token.span,
                _category(token, index in noise),
                token.kind.value,
                "token",
                token.error_code,
            )
        )
        if (
            token.kind is TokenKind.LPAREN
            and result.tokens[index + 1].kind is TokenKind.RPAREN
            and (index == 0 or result.tokens[index - 1].kind not in _CALLEE_ENDS)
        ):
            rows.append(
                SymbolRow(
                    token.span.join(result.tokens[index + 1].span),
                    "UNIT_LITERAL",
                    "LPAREN+RPAREN",
                    "composite",
                )
            )
    for trivia in result.trivia:
        if trivia.kind is not TriviaKind.WHITESPACE:
            rows.append(SymbolRow(trivia.span, trivia.kind.value, trivia.kind.value, "trivia"))
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.span.start_byte,
                row.view == "composite",
                row.span.end_byte,
                row.category,
            ),
        )
    )


def render_symbol_table(result: LexResult, context: RenderContext | None = None) -> str:
    context = context if context is not None else RenderContext()
    lines = [
        "Ternfold lexical report v1",
        "file\t" + json.dumps(context.filename(result.source.display_name), ensure_ascii=True),
        "start_byte\tend_byte\tline\tcolumn\tend_line\tend_column\tview\tcategory\tkind\tlexeme\tdiagnostic",
    ]
    for row in symbol_rows(result):
        span = row.span
        lines.append(
            "\t".join(
                (
                    str(span.start_byte),
                    str(span.end_byte),
                    str(span.start.line),
                    str(span.start.column),
                    str(span.end.line),
                    str(span.end.column),
                    row.view,
                    row.category,
                    row.kind,
                    json.dumps(span.text, ensure_ascii=True),
                    row.error_code or "",
                )
            )
        )
    return "\n".join(lines) + "\n"
