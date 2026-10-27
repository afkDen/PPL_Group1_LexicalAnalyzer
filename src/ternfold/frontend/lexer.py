"""Explicit scalar-indexed finite scanning, preserving original-byte spans.

Identifier/number runs consume their maximal ASCII prefix. Comments take
priority over slash/star operators; block comments end at the first */. Quoted
literals decode only the specified escapes. A bad literal is one INVALID run
through its closing quote, or up to (excluding) newline/EOF. An unsupported
scalar is one INVALID token. Every transition consumes input or finishes; all
input remains inspectable even after the diagnostic retention cap is reached.

``lex(source)`` returns recovery tokens/trivia plus diagnostics. Only
``result.for_parser()`` grants a valid token stream; any lexical error, including
a suppressed one, returns ErrorResult. No parsing, name checks or signed range
validation occurs here. INVALID tokens retain error codes even after the cap.
"""

from dataclasses import dataclass

from ternfold.frontend.diagnostics import (
    Diagnostic,
    DiagnosticBag,
    DiagnosticReport,
    ErrorResult,
    Label,
    Result,
    Severity,
    ValidResult,
)
from ternfold.frontend.source import SourceFile, SourceSpan
from ternfold.frontend.tokens import (
    OPERATORS,
    DecimalMagnitude,
    FloatSpelling,
    Token,
    TokenKind,
    TokenValue,
    Trivia,
    TriviaKind,
    name_terminal,
    name_transition,
    number_transition,
)


@dataclass(frozen=True, slots=True)
class LexResult:
    source: SourceFile
    tokens: tuple[Token, ...]
    trivia: tuple[Trivia, ...]
    diagnostics: DiagnosticReport

    def __post_init__(self) -> None:
        object.__setattr__(self, "tokens", tuple(self.tokens))
        object.__setattr__(self, "trivia", tuple(self.trivia))
        if not self.tokens or self.tokens[-1].kind is not TokenKind.EOF:
            raise ValueError("lex result must end in EOF")
        eof = len(self.source.original_bytes)
        if self.tokens[-1].span != self.source.span(eof, eof):
            raise ValueError("EOF must be at the original snapshot's end")
        previous = 0
        for token in self.tokens:
            if token.span.source is not self.source or token.span.start_byte < previous:
                raise ValueError("tokens must be ordered in their owning snapshot")
            previous = token.span.end_byte
        if any(token.kind is TokenKind.EOF for token in self.tokens[:-1]):
            raise ValueError("EOF may appear only once")
        if not self.diagnostics.has_errors and any(
            token.kind is TokenKind.INVALID for token in self.tokens
        ):
            raise ValueError("INVALID tokens cannot belong to successful lexical results")

    def for_parser(self) -> Result[tuple[Token, ...]]:
        if self.diagnostics.has_errors:
            return ErrorResult(self.diagnostics)
        return ValidResult(self.tokens, self.diagnostics)


def _letter(char: str) -> bool:
    return "a" <= char <= "z" or "A" <= char <= "Z" or char == "_"


def _digit(char: str) -> bool:
    return "0" <= char <= "9"


class _Scanner:
    def __init__(self, source: SourceFile, max_diagnostics: int) -> None:
        self.source = source
        self.text = source.text
        self.index = 0
        self.tokens: list[Token] = []
        self.trivia: list[Trivia] = []
        self.diagnostics = DiagnosticBag(max_diagnostics)

    def span(self, start: int) -> SourceSpan:
        offsets = self.source.scalar_byte_offsets
        return self.source.span(offsets[start], offsets[self.index])

    def emit(
        self, kind: TokenKind, start: int, value: TokenValue = None, *, reserved_name: bool = False
    ) -> None:
        self.tokens.append(Token(kind, self.span(start), value, reserved_name=reserved_name))

    def invalid(self, start: int, code: str, message: str) -> None:
        span = self.span(start)
        self.tokens.append(Token(TokenKind.INVALID, span, error_code=code))
        self.diagnostics.add(Diagnostic(code, Severity.ERROR, message, Label(span)))

    def escape(self) -> tuple[str, str | None]:
        """Called after consuming backslash; stop before raw newline or EOF."""
        if self.index == len(self.text) or self.text[self.index] in "\r\n":
            return "", "incomplete escape"
        char = self.text[self.index]
        self.index += 1
        simple = {'"': '"', "\\": "\\", "n": "\n", "r": "\r", "t": "\t"}
        if char in simple:
            return simple[char], None
        if char != "u" or self.index == len(self.text) or self.text[self.index] != "{":
            return "", "unsupported escape"
        self.index += 1
        start = self.index
        while self.index < len(self.text) and self.text[self.index] in "0123456789abcdefABCDEF":
            self.index += 1
        digits = self.text[start : self.index]
        closed = self.index < len(self.text) and self.text[self.index] == "}"
        if closed:
            self.index += 1
        if not closed or not 1 <= len(digits) <= 6:
            return "", "Unicode escape requires 1-6 hex digits and a closing brace"
        scalar = int(digits, 16)  # At most six hex digits; never a decimal magnitude conversion.
        if scalar > 0x10FFFF or 0xD800 <= scalar <= 0xDFFF:
            return "", "Unicode escape is not a Unicode scalar"
        return chr(scalar), None

    def quoted(self, start: int) -> None:
        quote = self.text[self.index]
        self.index += 1
        values: list[str] = []
        error: str | None = None
        closed = False
        while self.index < len(self.text):
            char = self.text[self.index]
            if char in "\r\n":
                break
            self.index += 1
            if char == quote:
                closed = True
                break
            if char == "\\":
                value, problem = self.escape()
                values.append(value)
                error = error or problem
            elif ord(char) < 32 or ord(char) == 127:
                error = error or "raw control character in literal"
            else:
                values.append(char)
        value = "".join(values)
        if not closed:
            error = error or "unterminated literal"
        if quote == "'" and len(value) != 1:
            error = error or "Char literal must contain exactly one Unicode scalar"
        if error:
            self.invalid(start, "E103" if quote == '"' else "E105", error)
        else:
            self.emit(TokenKind.TEXT if quote == '"' else TokenKind.CHAR, start, value)

    def scan(self) -> LexResult:
        while self.index < len(self.text):
            start = self.index
            char = self.text[self.index]
            pair = self.text[self.index : self.index + 2]
            if char in " \t\r\n":
                self.index += 1
                while self.index < len(self.text) and self.text[self.index] in " \t\r\n":
                    self.index += 1
                self.trivia.append(Trivia(TriviaKind.WHITESPACE, self.span(start)))
            elif pair == "//":
                self.index += 2
                while self.index < len(self.text) and self.text[self.index] not in "\r\n":
                    self.index += 1
                self.trivia.append(Trivia(TriviaKind.COMMENT_LINE, self.span(start)))
            elif pair == "/*":
                self.index += 2
                while (
                    self.index < len(self.text) and self.text[self.index : self.index + 2] != "*/"
                ):
                    self.index += 1
                if self.index == len(self.text):
                    self.invalid(start, "E104", "unterminated block comment")
                else:
                    self.index += 2
                    self.trivia.append(Trivia(TriviaKind.COMMENT_BLOCK, self.span(start)))
            elif _letter(char):
                state = name_transition(0, char)
                self.index += 1
                while self.index < len(self.text) and (
                    _letter(self.text[self.index]) or _digit(self.text[self.index])
                ):
                    state = name_transition(state, self.text[self.index])
                    self.index += 1
                word = self.text[start : self.index]
                kind, reserved = name_terminal(state)
                payload: TokenValue = word if kind is TokenKind.IDENT else None
                if kind in {TokenKind.TRUE, TokenKind.FALSE}:
                    payload = kind is TokenKind.TRUE
                self.emit(kind, start, payload, reserved_name=reserved)
            elif _digit(char):
                state = number_transition(0, char)
                self.index += 1
                while self.index < len(self.text):
                    current = self.text[self.index]
                    if _letter(current) or _digit(current):
                        state = number_transition(state, current)
                        self.index += 1
                    elif (
                        current == "."
                        and self.index + 1 < len(self.text)
                        and _digit(self.text[self.index + 1])
                    ):
                        state = number_transition(state, current)
                        self.index += 1
                    elif current in "+-" and self.text[self.index - 1] in "eE":
                        state = number_transition(state, current)
                        self.index += 1
                    else:
                        break
                spelling = self.text[start : self.index]
                if state in {1, 2}:
                    self.emit(TokenKind.INT, start, DecimalMagnitude(spelling))
                elif state in {4, 7}:
                    self.emit(TokenKind.FLOAT, start, FloatSpelling(spelling))
                else:
                    self.invalid(start, "E102", "malformed decimal numeric literal")
            elif char in "\"'":
                self.quoted(start)
            elif len(pair) == 2 and pair in OPERATORS:
                self.index += 2
                self.emit(OPERATORS[pair], start)
            elif char in OPERATORS:
                self.index += 1
                self.emit(OPERATORS[char], start)
            else:
                self.index += 1
                self.invalid(start, "E101", "unsupported source character")
        self.emit(TokenKind.EOF, self.index)
        return LexResult(
            self.source, tuple(self.tokens), tuple(self.trivia), self.diagnostics.report()
        )


def lex(source: SourceFile, *, max_diagnostics: int = 100) -> LexResult:
    return _Scanner(source, max_diagnostics).scan()
