"""Frozen surface syntax, preserving original origins without semantic guesses.

Node IDs are per-parse ordinals paired with source identity. Groups are explicit;
operator/literal/name spans remain available for later diagnostics and the M06
contiguous minimum-Int rule. Magnitudes stay decimal strings. Error nodes and
missing tokens are recovery-only and must pass ParseResult.for_resolution().
Collections are tuples; no resolution, type, schedule or execution data lives here.
"""

from dataclasses import dataclass

from ternfold.frontend.source import SourceId, SourceSpan
from ternfold.frontend.tokens import TokenKind, TokenValue


@dataclass(frozen=True, slots=True)
class NodeId:
    source_id: SourceId
    value: int

    def __post_init__(self) -> None:
        if type(self.value) is not int or self.value < 0:
            raise ValueError("node ordinal must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class Node:
    node_id: NodeId
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class Name(Node):
    spelling: str


@dataclass(frozen=True, slots=True)
class Path(Node):
    parts: tuple[Name, ...]


@dataclass(frozen=True, slots=True)
class TypeSyntax(Node):
    pass


@dataclass(frozen=True, slots=True)
class NamedType(TypeSyntax):
    path: Path
    arguments: tuple[TypeSyntax, ...]


@dataclass(frozen=True, slots=True)
class FunctionType(TypeSyntax):
    parameters: tuple[TypeSyntax, ...]
    result: TypeSyntax


@dataclass(frozen=True, slots=True)
class ErrorType(TypeSyntax):
    message: str


@dataclass(frozen=True, slots=True)
class Parameter(Node):
    name: Name
    annotation: TypeSyntax


@dataclass(frozen=True, slots=True)
class Pattern(Node):
    pass


@dataclass(frozen=True, slots=True)
class WildcardPattern(Pattern):
    pass


@dataclass(frozen=True, slots=True)
class BindingPattern(Pattern):
    name: Name


@dataclass(frozen=True, slots=True)
class LiteralPattern(Pattern):
    kind: TokenKind
    value: TokenValue
    literal_span: SourceSpan
    minus_span: SourceSpan | None


@dataclass(frozen=True, slots=True)
class UnitPattern(Pattern):
    pass


@dataclass(frozen=True, slots=True)
class VariantPattern(Pattern):
    path: Path
    arguments: tuple[Pattern, ...]


@dataclass(frozen=True, slots=True)
class ErrorPattern(Pattern):
    message: str


@dataclass(frozen=True, slots=True)
class Expr(Node):
    pass


@dataclass(frozen=True, slots=True)
class LiteralExpr(Expr):
    kind: TokenKind
    value: TokenValue
    literal_span: SourceSpan


@dataclass(frozen=True, slots=True)
class UnitExpr(Expr):
    open_span: SourceSpan
    close_span: SourceSpan


@dataclass(frozen=True, slots=True)
class GroupExpr(Expr):
    expression: Expr
    open_span: SourceSpan
    close_span: SourceSpan


@dataclass(frozen=True, slots=True)
class PathExpr(Expr):
    path: Path


@dataclass(frozen=True, slots=True)
class NextExpr(Expr):
    cell: Name
    keyword_span: SourceSpan
    dot_span: SourceSpan


@dataclass(frozen=True, slots=True)
class UnaryExpr(Expr):
    operator: TokenKind
    operator_span: SourceSpan
    operand: Expr


@dataclass(frozen=True, slots=True)
class BinaryExpr(Expr):
    left: Expr
    operator: TokenKind
    operator_span: SourceSpan
    right: Expr


@dataclass(frozen=True, slots=True)
class Argument(Node):
    name: Name | None
    value: Expr


@dataclass(frozen=True, slots=True)
class CallExpr(Expr):
    callee: Expr
    arguments: tuple[Argument, ...]
    open_span: SourceSpan
    close_span: SourceSpan


@dataclass(frozen=True, slots=True)
class ProjectionExpr(Expr):
    value: Expr
    field: Name
    dot_span: SourceSpan


@dataclass(frozen=True, slots=True)
class ListExpr(Expr):
    elements: tuple[Expr, ...]
    open_span: SourceSpan
    close_span: SourceSpan


@dataclass(frozen=True, slots=True)
class Statement(Node):
    pass


@dataclass(frozen=True, slots=True)
class Binding(Statement):
    name: Name
    annotation: TypeSyntax | None
    value: Expr


@dataclass(frozen=True, slots=True)
class InputClause(Statement):
    name: Name
    annotation: TypeSyntax
    phrase_span: SourceSpan | None


@dataclass(frozen=True, slots=True)
class OutputClause(Statement):
    value: Expr
    phrase_span: SourceSpan | None


@dataclass(frozen=True, slots=True)
class ErrorStatement(Statement):
    message: str


@dataclass(frozen=True, slots=True)
class BlockExpr(Expr):
    statements: tuple[Statement, ...]
    result: Expr
    open_span: SourceSpan
    close_span: SourceSpan


@dataclass(frozen=True, slots=True)
class IfExpr(Expr):
    condition: Expr
    then_block: BlockExpr
    else_block: BlockExpr


@dataclass(frozen=True, slots=True)
class MatchArm(Node):
    pattern: Pattern
    body: BlockExpr


@dataclass(frozen=True, slots=True)
class MatchExpr(Expr):
    value: Expr
    arms: tuple[MatchArm, ...]


@dataclass(frozen=True, slots=True)
class ClosureExpr(Expr):
    parameters: tuple[Parameter, ...]
    return_type: TypeSyntax
    body: BlockExpr


@dataclass(frozen=True, slots=True)
class ForExpr(Expr):
    binder: Name
    iterable: Expr
    body: BlockExpr


@dataclass(frozen=True, slots=True)
class ErrorExpr(Expr):
    message: str


@dataclass(frozen=True, slots=True)
class Declaration(Node):
    pass


@dataclass(frozen=True, slots=True)
class ImportDecl(Node):
    path: str
    path_span: SourceSpan
    alias: Name


@dataclass(frozen=True, slots=True)
class FunctionDecl(Declaration):
    public: bool
    name: Name
    parameters: tuple[Parameter, ...]
    return_type: TypeSyntax
    body: BlockExpr


@dataclass(frozen=True, slots=True)
class Field(Node):
    name: Name
    annotation: TypeSyntax


@dataclass(frozen=True, slots=True)
class RecordDecl(Declaration):
    public: bool
    name: Name
    fields: tuple[Field, ...]


@dataclass(frozen=True, slots=True)
class EnumVariant(Node):
    name: Name
    payload: tuple[TypeSyntax, ...]


@dataclass(frozen=True, slots=True)
class EnumDecl(Declaration):
    public: bool
    name: Name
    variants: tuple[EnumVariant, ...]


@dataclass(frozen=True, slots=True)
class MachineClause(Node):
    pass


@dataclass(frozen=True, slots=True)
class StateClause(MachineClause):
    name: Name
    annotation: TypeSyntax
    value: Expr


@dataclass(frozen=True, slots=True)
class WriterClause(MachineClause):
    name: Name
    value: Expr


@dataclass(frozen=True, slots=True)
class GuardClause(MachineClause):
    condition: Expr
    error: Expr


@dataclass(frozen=True, slots=True)
class EmitClause(MachineClause):
    value: Expr


@dataclass(frozen=True, slots=True)
class ErrorClause(MachineClause):
    message: str


@dataclass(frozen=True, slots=True)
class MachineDecl(Declaration):
    public: bool
    name: Name
    parameters: tuple[Parameter, ...]
    output_type: TypeSyntax
    rejection_type: TypeSyntax
    clauses: tuple[MachineClause, ...]


@dataclass(frozen=True, slots=True)
class ErrorDecl(Declaration):
    message: str


@dataclass(frozen=True, slots=True)
class Program(Node):
    imports: tuple[ImportDecl, ...]
    declarations: tuple[Declaration, ...]


@dataclass(frozen=True, slots=True)
class MissingToken:
    kind: TokenKind
    span: SourceSpan

    def __post_init__(self) -> None:
        if self.span.start_byte != self.span.end_byte:
            raise ValueError("missing tokens must have zero-width original spans")
