"""M04 recursive descent/Pratt syntax and bounded, depth-aware recovery.

``parse(valid_tokens, root_module=True)`` accepts only a genuine EOF-terminated
stream without INVALID tokens. Future module loading must pass root_module=False
for imports. ParseResult retains the recovery program and missing-token origins;
only for_resolution() exposes a successful phase result. Types, namespaces,
record-call identity, signed bounds, machine plans and entry return types are
never inferred here. Input's bare Text annotation is an explicit grammar terminal.

No Python recursion limit is changed. Native recursion exhaustion raises
ParserResourceError (a host failure), never a fabricated syntax diagnostic.
"""

from collections.abc import Callable
from dataclasses import dataclass

from ternfold.frontend import ast as A
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
from ternfold.frontend.tokens import Token
from ternfold.frontend.tokens import TokenKind as K

_LITERALS = frozenset({K.INT, K.FLOAT, K.TEXT, K.CHAR, K.TRUE, K.FALSE})
_CLOSERS = frozenset({K.RPAREN, K.RBRACKET, K.RBRACE})
_STOPS = frozenset(
    {
        K.COMMA,
        K.SEMICOLON,
        K.ELSE,
        K.FAT_ARROW,
        K.TO,
        K.FROM,
        K.EOF,
        K.LET,
        K.STATE,
        K.GUARD,
        K.EMIT,
        *_CLOSERS,
    }
)
_BINARY = {
    K.OR_OR: 10,
    K.AND_AND: 20,
    K.EQUAL_EQUAL: 30,
    K.BANG_EQUAL: 30,
    K.LESS: 40,
    K.LESS_EQUAL: 40,
    K.GREATER: 40,
    K.GREATER_EQUAL: 40,
    K.PLUS: 50,
    K.MINUS: 50,
    K.PLUS_PLUS: 50,
    K.STAR: 60,
    K.SLASH: 60,
    K.DIV: 60,
    K.PERCENT: 60,
    K.CARET: 80,
}


class ParserResourceError(RuntimeError):
    """The host could not represent/parse the requested nesting depth."""


@dataclass(frozen=True, slots=True)
class ParseResult:
    program: A.Program
    diagnostics: DiagnosticReport
    missing_tokens: tuple[A.MissingToken, ...]

    def for_resolution(self) -> Result[A.Program]:
        if self.diagnostics.has_errors:
            return ErrorResult(self.diagnostics)
        return ValidResult(self.program, self.diagnostics)


class _Parser:
    def __init__(self, tokens: tuple[Token, ...], root_module: bool, cap: int) -> None:
        if not tokens or tokens[-1].kind is not K.EOF:
            raise ValueError("parser requires a token stream ending in EOF")
        if any(token.kind in {K.INVALID, K.EOF} for token in tokens[:-1]):
            raise ValueError("parser requires a lexically successful stream with one EOF")
        self.tokens = tokens
        self.source: SourceFile = tokens[-1].span.source
        previous = 0
        for token in tokens:
            if token.span.source is not self.source or token.span.start_byte < previous:
                raise ValueError("parser tokens must be ordered within one source snapshot")
            previous = token.span.end_byte
        eof = len(self.source.original_bytes)
        if tokens[-1].span != self.source.span(eof, eof):
            raise ValueError("EOF must be at the end of the source")
        self.index = 0
        self.next_id = 0
        self.root_module = root_module
        self.diagnostics = DiagnosticBag(cap)
        self.missing: list[A.MissingToken] = []

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def peek(self, distance: int = 1) -> Token:
        return self.tokens[min(self.index + distance, len(self.tokens) - 1)]

    def advance(self) -> Token:
        token = self.current
        if token.kind is not K.EOF:
            self.index += 1
        return token

    def take(self, kind: K) -> Token | None:
        return self.advance() if self.current.kind is kind else None

    def point(self) -> SourceSpan:
        byte = self.current.span.start_byte
        return self.source.span(byte, byte)

    def origin(self, span: SourceSpan) -> tuple[A.NodeId, SourceSpan]:
        node_id = A.NodeId(self.source.source_id, self.next_id)
        self.next_id += 1
        return node_id, span

    def error(self, message: str, span: SourceSpan | None = None, code: str = "E110") -> None:
        self.diagnostics.add(Diagnostic(code, Severity.ERROR, message, Label(span or self.point())))

    def expect(self, kind: K) -> SourceSpan:
        token = self.take(kind)
        if token is not None:
            return token.span
        span = self.point()
        self.missing.append(A.MissingToken(kind, span))
        self.error(f"expected {kind.value}", span)
        return span

    def top_boundary(self) -> bool:
        return self.current.kind in {K.PUB, K.RECORD, K.ENUM, K.MACHINE, K.IMPORT} or (
            self.current.kind is K.FN and self.peek().kind is K.IDENT
        )

    def synchronize(self, stops: frozenset[K] = frozenset({K.SEMICOLON, K.RBRACE})) -> None:
        stack: list[K] = []
        brace_depth = 0
        pairs = {K.LPAREN: K.RPAREN, K.LBRACKET: K.RBRACKET, K.LBRACE: K.RBRACE}
        while self.current.kind is not K.EOF:
            kind = self.current.kind
            # A clear declaration belongs to the caller at brace depth zero,
            # even if skipped parentheses/brackets were never closed. Actual
            # skipped braces still shield declarations nested inside them.
            if brace_depth == 0 and self.top_boundary():
                return
            if not stack and kind in stops:
                return
            if kind in pairs:
                stack.append(pairs[kind])
                if kind is K.LBRACE:
                    brace_depth += 1
            elif kind in _CLOSERS:
                if not stack or kind is not stack[-1]:
                    return
                stack.pop()
                if kind is K.RBRACE:
                    brace_depth -= 1
            self.advance()

    def name(self, *, discard: bool = False) -> A.Name:
        if self.current.kind is K.IDENT or (discard and self.current.kind is K.UNDERSCORE):
            token = self.advance()
            return A.Name(*self.origin(token.span), token.lexeme)
        span = self.expect(K.IDENT)
        return A.Name(*self.origin(span), "")

    def path(self) -> A.Path:
        names = [self.name()]
        while self.take(K.DOUBLE_COLON) is not None:
            names.append(self.name())
        return A.Path(*self.origin(names[0].span.join(names[-1].span)), tuple(names))

    def sequence[T](
        self, item: Callable[[], T], close: K, *, trailing: bool = True, minimum: int = 0
    ) -> tuple[tuple[T, ...], SourceSpan]:
        values: list[T] = []
        while self.current.kind not in {close, K.EOF}:
            if (
                self.current.kind in _CLOSERS
                or self.current.kind is K.SEMICOLON
                or self.top_boundary()
            ):
                break
            before = self.index
            values.append(item())
            comma = self.take(K.COMMA)
            if comma is not None:
                if self.current.kind is close and not trailing:
                    self.error("trailing comma is not permitted here", comma.span)
                continue
            if self.current.kind is close:
                break
            if self.index == before:
                self.synchronize(frozenset({K.COMMA, close, K.SEMICOLON, *_CLOSERS}))
                if self.take(K.COMMA) is None:
                    break
            elif (
                self.current.kind in _CLOSERS
                or self.current.kind in {K.SEMICOLON, K.EOF, K.ARROW, K.YIELDS, K.REJECTS}
                or (close in {K.RPAREN, K.RBRACKET} and self.current.kind is K.LBRACE)
                or self.top_boundary()
            ):
                break
            else:
                self.expect(K.COMMA)
        if len(values) < minimum:
            self.error("expected at least one item")
        return tuple(values), self.expect(close)

    def type_syntax(self) -> A.TypeSyntax:
        if self.current.kind is K.FN and not self.top_boundary():
            start = self.advance().span
            self.expect(K.LPAREN)
            parameters, _ = self.sequence(self.type_syntax, K.RPAREN, trailing=False)
            self.expect(K.ARROW)
            result = self.type_syntax()
            return A.FunctionType(*self.origin(start.join(result.span)), parameters, result)
        if self.current.kind is not K.IDENT:
            span = self.point()
            self.error("expected type", span)
            return A.ErrorType(*self.origin(span), "expected type")
        path = self.path()
        arguments: tuple[A.TypeSyntax, ...] = ()
        end = path.span
        if self.take(K.LBRACKET) is not None:
            arguments, end = self.sequence(self.type_syntax, K.RBRACKET, trailing=False, minimum=1)
        return A.NamedType(*self.origin(path.span.join(end)), path, arguments)

    def parameter(self) -> A.Parameter:
        name = self.name()
        self.expect(K.COLON)
        annotation = self.type_syntax()
        return A.Parameter(*self.origin(name.span.join(annotation.span)), name, annotation)

    def parameters(self, *, machine: bool = False) -> tuple[A.Parameter, ...]:
        self.expect(K.LPAREN)
        parameters, _ = self.sequence(self.parameter, K.RPAREN, trailing=not machine)
        if machine and len(parameters) != 1:
            self.error("machine header requires exactly one input parameter")
        return parameters

    def argument(self) -> A.Argument:
        name: A.Name | None = None
        if self.current.kind is K.IDENT and self.peek().kind is K.COLON:
            name = self.name()
            self.advance()
        value = self.expression()
        span = name.span.join(value.span) if name else value.span
        return A.Argument(*self.origin(span), name, value)

    def expression(self, minimum: int = 0) -> A.Expr:
        if self.current.kind in {K.MINUS, K.BANG}:
            operator = self.advance()
            operand = self.expression(70)
            left: A.Expr = A.UnaryExpr(
                *self.origin(operator.span.join(operand.span)),
                operator.kind,
                operator.span,
                operand,
            )
        else:
            left = self.primary()
        seen_nonassoc: set[int] = set()
        while True:
            kind = self.current.kind
            if kind is K.LPAREN and minimum <= 90:
                opening = self.advance().span
                arguments, closing = self.sequence(self.argument, K.RPAREN)
                if any(arg.name is None for arg in arguments) and any(
                    arg.name is not None for arg in arguments
                ):
                    self.error(
                        "cannot mix named and positional arguments", opening.join(closing), "E112"
                    )
                left = A.CallExpr(
                    *self.origin(left.span.join(closing)), left, arguments, opening, closing
                )
                continue
            if kind is K.DOT and minimum <= 90:
                dot = self.advance().span
                name = self.name()
                left = A.ProjectionExpr(*self.origin(left.span.join(name.span)), left, name, dot)
                continue
            power = _BINARY.get(kind)
            if power is None or power < minimum:
                break
            operator = self.advance()
            if power in {30, 40}:
                if power in seen_nonassoc:
                    self.error(
                        "comparison/equality operators cannot chain at this level",
                        operator.span,
                        "E111",
                    )
                seen_nonassoc.add(power)
            right = self.expression(power if kind is K.CARET else power + 1)
            left = A.BinaryExpr(
                *self.origin(left.span.join(right.span)), left, kind, operator.span, right
            )
        return left

    def primary(self) -> A.Expr:
        token = self.current
        kind = token.kind
        if kind in _LITERALS:
            self.advance()
            return A.LiteralExpr(*self.origin(token.span), kind, token.value, token.span)
        if kind is K.IDENT:
            path = self.path()
            return A.PathExpr(*self.origin(path.span), path)
        if kind is K.NEXT:
            start = self.advance().span
            dot = self.expect(K.DOT)
            name = self.name()
            return A.NextExpr(*self.origin(start.join(name.span)), name, start, dot)
        if kind is K.LPAREN:
            opening = self.advance().span
            if self.current.kind is K.RPAREN:
                closing = self.advance().span
                return A.UnitExpr(*self.origin(opening.join(closing)), opening, closing)
            value = self.expression()
            closing = self.expect(K.RPAREN)
            return A.GroupExpr(*self.origin(opening.join(closing)), value, opening, closing)
        if kind is K.LBRACKET:
            opening = self.advance().span
            values, closing = self.sequence(self.expression, K.RBRACKET)
            return A.ListExpr(*self.origin(opening.join(closing)), values, opening, closing)
        if kind is K.LBRACE:
            return self.block()
        if kind is K.IF:
            start = self.advance().span
            condition = self.expression()
            then_block = self.block()
            self.expect(K.ELSE)
            else_block = self.block()
            return A.IfExpr(
                *self.origin(start.join(else_block.span)), condition, then_block, else_block
            )
        if kind is K.MATCH:
            start = self.advance().span
            value = self.expression()
            self.expect(K.LBRACE)
            arms, end = self.sequence(self.arm, K.RBRACE, minimum=1)
            return A.MatchExpr(*self.origin(start.join(end)), value, arms)
        if kind is K.FN and not self.top_boundary():
            start = self.advance().span
            parameters = self.parameters()
            self.expect(K.ARROW)
            annotation = self.type_syntax()
            body = self.block()
            return A.ClosureExpr(*self.origin(start.join(body.span)), parameters, annotation, body)
        if kind is K.FOR:
            start = self.advance().span
            binder = self.name()
            self.expect(K.IN)
            iterable = self.expression()
            body = self.block()
            return A.ForExpr(*self.origin(start.join(body.span)), binder, iterable, body)
        if kind in {K.INPUT, K.OUTPUT}:
            statement = self.io_clause(False)
            return A.ErrorExpr(*self.origin(statement.span), "IO clause is not an expression")
        start = self.point()
        self.error("expected expression", start)
        if kind not in _STOPS and not self.top_boundary():
            self.advance()
            self.synchronize(_STOPS)
        end = (
            self.tokens[self.index - 1].span
            if self.current.span.start_byte > start.start_byte
            else start
        )
        return A.ErrorExpr(*self.origin(start.join(end)), "expected expression")

    def binding(self) -> A.Binding:
        start = self.advance().span
        name = self.name(discard=True)
        annotation = self.type_syntax() if self.take(K.COLON) is not None else None
        self.expect(K.EQUAL)
        value = self.expression()
        end = self.expect(K.SEMICOLON)
        return A.Binding(*self.origin(start.join(end)), name, annotation, value)

    def io_clause(self, allowed: bool) -> A.InputClause | A.OutputClause:
        start = self.advance()
        if not allowed:
            self.error(
                "input/output requires the outer block of root pub fn main()", start.span, "E208"
            )
        phrase: SourceSpan | None = None
        if start.kind is K.INPUT:
            name = self.name()
            self.expect(K.COLON)
            annotation = self.type_syntax()
            if not (
                isinstance(annotation, A.NamedType)
                and not annotation.arguments
                and len(annotation.path.parts) == 1
                and annotation.path.parts[0].spelling == "Text"
            ):
                self.error("input annotation must be the bare Text grammar form", annotation.span)
            connector = self.take(K.FROM)
            if connector:
                phrase = connector.span.join(self.expect(K.STDIN))
            end = self.expect(K.SEMICOLON)
            return A.InputClause(*self.origin(start.span.join(end)), name, annotation, phrase)
        value = self.expression()
        connector = self.take(K.TO)
        if connector:
            phrase = connector.span.join(self.expect(K.STDOUT))
        end = self.expect(K.SEMICOLON)
        return A.OutputClause(*self.origin(start.span.join(end)), value, phrase)

    def block(self, *, allow_io: bool = False) -> A.BlockExpr:
        opening = self.expect(K.LBRACE)
        statements: list[A.Statement] = []
        result: A.Expr | None = None
        while True:
            before = self.index
            if self.current.kind is K.LET:
                statements.append(self.binding())
            elif self.current.kind in {K.INPUT, K.OUTPUT}:
                statements.append(self.io_clause(allow_io))
            elif self.current.kind in {K.RBRACE, K.EOF} or self.top_boundary():
                self.error("block requires a final expression")
                result = A.ErrorExpr(*self.origin(self.point()), "missing final expression")
                break
            else:
                result = self.expression()
                if self.current.kind in {K.RBRACE, K.EOF} or self.top_boundary():
                    break
                self.error("expected block close; final expressions cannot end with semicolon")
                self.synchronize(frozenset({K.SEMICOLON, K.RBRACE, K.LET, K.INPUT, K.OUTPUT}))
                self.take(K.SEMICOLON)
                # Include every token consumed by expression parsing and
                # synchronization, not just the original expression. A stopped
                # boundary remains owned by its caller. No consumption means
                # a zero-width recovery origin at the current insertion point.
                skipped = (
                    self.source.span(
                        self.tokens[before].span.start_byte,
                        self.tokens[self.index - 1].span.end_byte,
                    )
                    if self.index > before
                    else self.point()
                )
                statements.append(A.ErrorStatement(*self.origin(skipped), "invalid block item"))
                result = None
            if self.index == before:
                if (
                    self.current.kind in _CLOSERS
                    or self.current.kind in {K.EOF}
                    or self.top_boundary()
                ):
                    result = result or A.ErrorExpr(
                        *self.origin(self.point()), "missing final expression"
                    )
                    break
                self.advance()
        closing = self.expect(K.RBRACE)
        assert result is not None
        return A.BlockExpr(
            *self.origin(opening.join(closing)), tuple(statements), result, opening, closing
        )

    def pattern(self) -> A.Pattern:
        token = self.current
        if token.kind is K.UNDERSCORE:
            self.advance()
            return A.WildcardPattern(*self.origin(token.span))
        if token.kind in _LITERALS or token.kind is K.MINUS:
            minus = self.take(K.MINUS)
            literal = self.current
            if literal.kind not in _LITERALS or (
                minus is not None and literal.kind not in {K.INT, K.FLOAT}
            ):
                self.error("minus in a pattern must precede an Int or Float literal")
                return A.ErrorPattern(
                    *self.origin(minus.span if minus else self.point()), "invalid literal pattern"
                )
            self.advance()
            span = minus.span.join(literal.span) if minus else literal.span
            return A.LiteralPattern(
                *self.origin(span),
                literal.kind,
                literal.value,
                literal.span,
                minus.span if minus else None,
            )
        if token.kind is K.LPAREN:
            opening = self.advance().span
            closing = self.expect(K.RPAREN)
            return A.UnitPattern(*self.origin(opening.join(closing)))
        if token.kind is K.IDENT:
            path = self.path()
            if len(path.parts) == 1:
                return A.BindingPattern(*self.origin(path.span), path.parts[0])
            arguments: tuple[A.Pattern, ...] = ()
            end = path.span
            if self.take(K.LPAREN) is not None:
                arguments, end = self.sequence(self.pattern, K.RPAREN, minimum=1)
            return A.VariantPattern(*self.origin(path.span.join(end)), path, arguments)
        self.error("expected pattern")
        span = self.point()
        if token.kind not in _STOPS and not self.top_boundary():
            span = self.advance().span
        return A.ErrorPattern(*self.origin(span), "expected pattern")

    def arm(self) -> A.MatchArm:
        pattern = self.pattern()
        self.expect(K.FAT_ARROW)
        body = self.block()
        return A.MatchArm(*self.origin(pattern.span.join(body.span)), pattern, body)

    def field(self) -> A.Field:
        name = self.name()
        self.expect(K.COLON)
        annotation = self.type_syntax()
        return A.Field(*self.origin(name.span.join(annotation.span)), name, annotation)

    def variant(self) -> A.EnumVariant:
        name = self.name()
        payload: tuple[A.TypeSyntax, ...] = ()
        end = name.span
        if self.take(K.LPAREN) is not None:
            payload, end = self.sequence(self.type_syntax, K.RPAREN, trailing=True, minimum=1)
        return A.EnumVariant(*self.origin(name.span.join(end)), name, payload)

    def import_decl(self) -> A.ImportDecl:
        start = self.advance().span
        if self.current.kind is K.TEXT:
            path = self.advance()
            path_span = path.span
            assert isinstance(path.value, str)
            spelling = path.value
        else:
            path_span, spelling = self.expect(K.TEXT), ""
        self.expect(K.AS)
        alias = self.name()
        end = self.expect(K.SEMICOLON)
        return A.ImportDecl(*self.origin(start.join(end)), spelling, path_span, alias)

    def machine(self, start: SourceSpan, public: bool, name: A.Name) -> A.MachineDecl:
        parameters = self.parameters(machine=True)
        self.expect(K.YIELDS)
        output = self.type_syntax()
        self.expect(K.REJECTS)
        rejection = self.type_syntax()
        self.expect(K.LBRACE)
        clauses: list[A.MachineClause] = []
        ranks = {K.STATE: 0, K.NEXT: 1, K.GUARD: 2, K.EMIT: 3}
        highest = -1
        seen: set[K] = set()
        while self.current.kind not in {K.RBRACE, K.EOF} and not self.top_boundary():
            before = self.index
            token = self.current
            kind = token.kind
            if kind in ranks:
                self.advance()
                if ranks[kind] < highest:
                    self.error("machine clauses must be ordered state/next/guard/emit", token.span)
                highest = max(highest, ranks[kind])
                seen.add(kind)
                clause: A.MachineClause
                if kind is K.STATE:
                    cell = self.name()
                    self.expect(K.COLON)
                    annotation = self.type_syntax()
                    self.expect(K.EQUAL)
                    value = self.expression()
                    end = self.expect(K.SEMICOLON)
                    clause = A.StateClause(
                        *self.origin(token.span.join(end)), cell, annotation, value
                    )
                elif kind is K.NEXT:
                    cell = self.name()
                    self.expect(K.EQUAL)
                    value = self.expression()
                    end = self.expect(K.SEMICOLON)
                    clause = A.WriterClause(*self.origin(token.span.join(end)), cell, value)
                elif kind is K.GUARD:
                    condition = self.expression()
                    self.expect(K.ELSE)
                    error = self.expression()
                    end = self.expect(K.SEMICOLON)
                    clause = A.GuardClause(*self.origin(token.span.join(end)), condition, error)
                else:
                    value = self.expression()
                    end = self.expect(K.SEMICOLON)
                    clause = A.EmitClause(*self.origin(token.span.join(end)), value)
                clauses.append(clause)
            elif kind in {K.INPUT, K.OUTPUT}:
                statement = self.io_clause(False)
                clauses.append(A.ErrorClause(*self.origin(statement.span), "IO in machine"))
            else:
                self.error("expected machine clause", token.span)
                self.synchronize(frozenset({K.SEMICOLON, K.RBRACE, *ranks}))
                self.take(K.SEMICOLON)
                end = self.tokens[self.index - 1].span if self.index > before else token.span
                clauses.append(
                    A.ErrorClause(*self.origin(token.span.join(end)), "invalid machine clause")
                )
            if self.index == before:
                self.advance()
        if K.STATE not in seen:
            self.error("machine requires a state clause")
        if K.NEXT not in seen:
            self.error("machine requires a next clause")
        end = self.expect(K.RBRACE)
        return A.MachineDecl(
            *self.origin(start.join(end)),
            public,
            name,
            parameters,
            output,
            rejection,
            tuple(clauses),
        )

    def declaration(self) -> A.Declaration:
        start = self.current.span
        public = self.take(K.PUB) is not None
        kind = self.current.kind
        if kind not in {K.FN, K.RECORD, K.ENUM, K.MACHINE}:
            self.error("expected declaration", self.current.span)
            before = self.index
            self.synchronize()
            self.take(K.SEMICOLON)
            if self.index == before and not self.top_boundary() and self.current.kind is not K.EOF:
                self.advance()
            end = self.tokens[self.index - 1].span if self.index > before else start
            return A.ErrorDecl(*self.origin(start.join(end)), "expected declaration")
        self.advance()
        name = self.name()
        if kind is K.FN:
            parameters = self.parameters()
            self.expect(K.ARROW)
            annotation = self.type_syntax()
            eligible = self.root_module and public and name.spelling == "main" and not parameters
            body = self.block(allow_io=eligible)
            return A.FunctionDecl(
                *self.origin(start.join(body.span)), public, name, parameters, annotation, body
            )
        if kind is K.MACHINE:
            return self.machine(start, public, name)
        self.expect(K.LBRACE)
        if kind is K.RECORD:
            fields, end = self.sequence(self.field, K.RBRACE)
            return A.RecordDecl(*self.origin(start.join(end)), public, name, fields)
        variants, end = self.sequence(self.variant, K.RBRACE, minimum=1)
        return A.EnumDecl(*self.origin(start.join(end)), public, name, variants)

    def program(self) -> ParseResult:
        imports: list[A.ImportDecl] = []
        declarations: list[A.Declaration] = []
        while self.current.kind is not K.EOF:
            before = self.index
            if self.current.kind is K.IMPORT:
                if declarations:
                    self.error("imports must precede declarations", self.current.span)
                imports.append(self.import_decl())
            else:
                declarations.append(self.declaration())
            if self.index == before:
                self.error("unexpected token at top level", self.current.span)
                self.advance()
        span = self.source.span(0, len(self.source.original_bytes))
        program = A.Program(*self.origin(span), tuple(imports), tuple(declarations))
        return ParseResult(program, self.diagnostics.report(), tuple(self.missing))


def parse(
    tokens: tuple[Token, ...], *, root_module: bool = True, max_diagnostics: int = 100
) -> ParseResult:
    try:
        return _Parser(tokens, root_module, max_diagnostics).program()
    except RecursionError as error:
        raise ParserResourceError("host parser recursion capacity exhausted") from error
