"""Immutable M03 tokens. Int magnitudes are canonical decimal strings, not ints.

Keeping ``DecimalMagnitude.digits`` avoids Python's host decimal-conversion and
JSON integer limits. M06 can compare lengths/digits against its signed bounds;
the lexer never applies those bounds or combines unary minus with a numeral.
Identifier, keyword and reserved-name recognition advances one character through
the combined finite prefix automaton. Terminal states are observed at boundaries.
Reserved report names remain IDENT tokens; declaration checks belong to M05.
"""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from ternfold.frontend.source import SourceSpan


class TokenKind(StrEnum):
    IDENT = "IDENT"
    INT = "INT"
    FLOAT = "FLOAT"
    TEXT = "TEXT"
    CHAR = "CHAR"
    UNDERSCORE = "UNDERSCORE"
    INVALID = "INVALID"
    EOF = "EOF"
    AS = "AS"
    DIV = "DIV"
    ELSE = "ELSE"
    EMIT = "EMIT"
    ENUM = "ENUM"
    FALSE = "FALSE"
    FN = "FN"
    FOR = "FOR"
    FROM = "FROM"
    GUARD = "GUARD"
    IF = "IF"
    IMPORT = "IMPORT"
    IN = "IN"
    INPUT = "INPUT"
    LET = "LET"
    MACHINE = "MACHINE"
    MATCH = "MATCH"
    NEXT = "NEXT"
    OUTPUT = "OUTPUT"
    PUB = "PUB"
    RECORD = "RECORD"
    REJECTS = "REJECTS"
    STATE = "STATE"
    STDIN = "STDIN"
    STDOUT = "STDOUT"
    TO = "TO"
    TRUE = "TRUE"
    YIELDS = "YIELDS"
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    SLASH = "SLASH"
    PERCENT = "PERCENT"
    CARET = "CARET"
    LESS = "LESS"
    GREATER = "GREATER"
    EQUAL = "EQUAL"
    BANG = "BANG"
    DOT = "DOT"
    COMMA = "COMMA"
    SEMICOLON = "SEMICOLON"
    COLON = "COLON"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    DOUBLE_COLON = "DOUBLE_COLON"
    ARROW = "ARROW"
    FAT_ARROW = "FAT_ARROW"
    EQUAL_EQUAL = "EQUAL_EQUAL"
    BANG_EQUAL = "BANG_EQUAL"
    LESS_EQUAL = "LESS_EQUAL"
    GREATER_EQUAL = "GREATER_EQUAL"
    AND_AND = "AND_AND"
    OR_OR = "OR_OR"
    PLUS_PLUS = "PLUS_PLUS"
    BLOCK_CLOSE = "BLOCK_CLOSE"


KEYWORDS = MappingProxyType(
    {
        word: TokenKind(word.upper())
        for word in (
            "as div else emit enum false fn for from guard if import in input let machine "
            "match next output pub record rejects state stdin stdout to true yields"
        ).split()
    }
)

RESERVED_NAMES = frozenset(
    "Int Bool Text Char Unit List Option Decision step len at append map fold range "
    "int_text bool_text parse_int text_len text_at text_slice "
    "Float int_float float_int float_text".split()
)


def _name_automaton() -> tuple[
    tuple[MappingProxyType[str, int], ...], tuple[tuple[TokenKind, bool], ...]
]:
    """Compile fixed inventory into transitions, never match an input word."""
    transitions: list[dict[str, int]] = [{}]
    terminals: list[tuple[TokenKind, bool]] = [(TokenKind.IDENT, False)]
    inventory = [(word, kind, False) for word, kind in KEYWORDS.items()]
    inventory += [(word, TokenKind.IDENT, True) for word in sorted(RESERVED_NAMES)]
    inventory.append(("_", TokenKind.UNDERSCORE, False))
    for spelling, kind, reserved in inventory:
        state = 0
        for char in spelling:
            following = transitions[state].get(char)
            if following is None:
                following = len(transitions)
                transitions[state][char] = following
                transitions.append({})
                terminals.append((TokenKind.IDENT, False))
            state = following
        terminals[state] = kind, reserved
    return tuple(MappingProxyType(row) for row in transitions), tuple(terminals)


NAME_TRANSITIONS, NAME_TERMINALS = _name_automaton()


def name_transition(state: int, char: str) -> int:
    """One input scalar; -1 is the generic identifier sink state."""
    return NAME_TRANSITIONS[state].get(char, -1) if state >= 0 else -1


def name_terminal(state: int) -> tuple[TokenKind, bool]:
    return NAME_TERMINALS[state] if state >= 0 else (TokenKind.IDENT, False)


# Comments are selected before these operator transitions. A standalone */ is
# a lexical terminator token under the specified longest-match inventory; the
# parser will reject it outside a comment rather than the lexer splitting it.
OPERATORS = MappingProxyType(
    {
        "+": TokenKind.PLUS,
        "-": TokenKind.MINUS,
        "*": TokenKind.STAR,
        "/": TokenKind.SLASH,
        "%": TokenKind.PERCENT,
        "^": TokenKind.CARET,
        "<": TokenKind.LESS,
        ">": TokenKind.GREATER,
        "=": TokenKind.EQUAL,
        "!": TokenKind.BANG,
        ".": TokenKind.DOT,
        ",": TokenKind.COMMA,
        ";": TokenKind.SEMICOLON,
        ":": TokenKind.COLON,
        "(": TokenKind.LPAREN,
        ")": TokenKind.RPAREN,
        "[": TokenKind.LBRACKET,
        "]": TokenKind.RBRACKET,
        "{": TokenKind.LBRACE,
        "}": TokenKind.RBRACE,
        "::": TokenKind.DOUBLE_COLON,
        "->": TokenKind.ARROW,
        "=>": TokenKind.FAT_ARROW,
        "==": TokenKind.EQUAL_EQUAL,
        "!=": TokenKind.BANG_EQUAL,
        "<=": TokenKind.LESS_EQUAL,
        ">=": TokenKind.GREATER_EQUAL,
        "&&": TokenKind.AND_AND,
        "||": TokenKind.OR_OR,
        "++": TokenKind.PLUS_PLUS,
        "*/": TokenKind.BLOCK_CLOSE,
    }
)


@dataclass(frozen=True, slots=True)
class DecimalMagnitude:
    digits: str

    def __post_init__(self) -> None:
        if not self.digits or any(not "0" <= char <= "9" for char in self.digits):
            raise ValueError("magnitude must contain ASCII decimal digits")
        if len(self.digits) > 1 and self.digits[0] == "0":
            raise ValueError("magnitude must not contain leading zeros")


def number_transition(state: int, char: str) -> int:
    """Decimal DFA: start0, zero1, integer2, dot3, fraction4, exponent5,
    exponent-sign6, exponent-digits7, invalid-sink8.
    """
    digit = "0" <= char <= "9"
    if state == 0:
        return 1 if char == "0" else 2 if digit else 8
    if state == 1:
        return 3 if char == "." else 5 if char in "eE" else 8
    if state == 2:
        return 2 if digit else 3 if char == "." else 5 if char in "eE" else 8
    if state == 3:
        return 4 if digit else 8
    if state == 4:
        return 4 if digit else 5 if char in "eE" else 8
    if state == 5:
        return 7 if digit else 6 if char in "+-" else 8
    if state in {6, 7}:
        return 7 if digit else 8
    return 8


def float_spelling_valid(spelling: str) -> bool:
    state = 0
    for char in spelling:
        state = number_transition(state, char)
    return state in {4, 7}


@dataclass(frozen=True, slots=True)
class FloatSpelling:
    """Exact unsigned decimal syntax; range/rounding belongs to the type phase."""

    spelling: str

    def __post_init__(self) -> None:
        if not float_spelling_valid(self.spelling):
            raise ValueError("invalid decimal Float spelling")


type TokenValue = DecimalMagnitude | FloatSpelling | str | bool | None


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    span: SourceSpan
    value: TokenValue = None
    error_code: str | None = None
    reserved_name: bool = False

    def __post_init__(self) -> None:
        if type(self.reserved_name) is not bool or (
            self.reserved_name and self.kind is not TokenKind.IDENT
        ):
            raise ValueError("reserved-name terminal flag belongs only to IDENT")
        if self.kind is TokenKind.INVALID:
            if self.error_code not in {"E101", "E102", "E103", "E104", "E105"}:
                raise ValueError("invalid recovery token requires its lexical error code")
        elif self.error_code is not None:
            raise ValueError("valid tokens cannot carry lexical error codes")
        if self.kind is TokenKind.INT:
            if not isinstance(self.value, DecimalMagnitude):
                raise TypeError("Int token requires a DecimalMagnitude")
        elif self.kind is TokenKind.FLOAT:
            if not isinstance(self.value, FloatSpelling):
                raise TypeError("Float token requires a FloatSpelling")
        elif self.kind in {TokenKind.TRUE, TokenKind.FALSE}:
            if self.value is not (self.kind is TokenKind.TRUE):
                raise ValueError("Bool token requires its exact Boolean value")
        elif self.kind in {TokenKind.IDENT, TokenKind.TEXT, TokenKind.CHAR}:
            if not isinstance(self.value, str):
                raise TypeError("identifier/Text/Char token requires a string value")
            self.value.encode("utf-8", errors="strict")
            if self.kind is TokenKind.CHAR and len(self.value) != 1:
                raise ValueError("Char token requires exactly one Unicode scalar")
        elif self.value is not None:
            raise ValueError("this token kind has no literal payload")

    @property
    def lexeme(self) -> str:
        return self.span.text


class TriviaKind(StrEnum):
    WHITESPACE = "WHITESPACE"
    COMMENT_LINE = "COMMENT_LINE"
    COMMENT_BLOCK = "COMMENT_BLOCK"


@dataclass(frozen=True, slots=True)
class Trivia:
    kind: TriviaKind
    span: SourceSpan

    @property
    def lexeme(self) -> str:
        return self.span.text
