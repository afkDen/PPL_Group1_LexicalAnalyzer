"""Schema-v1 deterministic recovery AST inspection; never an executable IR.

Every dataclass node carries its kind and ordinal; spans retain original byte
and scalar endpoints. Magnitudes remain {decimal: digits}. Dataclass field order
and tuple child order are preserved. JSON keys are sorted; no Python identity,
hash iteration or source-buffer repr is serialized. Resource exhaustion remains
a host failure rather than a syntax error.
"""

import json
from dataclasses import fields, is_dataclass

from ternfold.frontend import ast as A
from ternfold.frontend.parser import ParseResult, ParserResourceError
from ternfold.frontend.render import RenderContext
from ternfold.frontend.source import SourceSpan
from ternfold.frontend.tokens import DecimalMagnitude, FloatSpelling, TokenKind


def _data(value: object) -> object:
    if isinstance(value, SourceSpan):
        return {
            "start": {
                "byte": value.start_byte,
                "line": value.start.line,
                "column": value.start.column,
            },
            "end": {"byte": value.end_byte, "line": value.end.line, "column": value.end.column},
        }
    if isinstance(value, A.NodeId):
        return value.value
    if isinstance(value, DecimalMagnitude):
        return {"decimal": value.digits}
    if isinstance(value, FloatSpelling):
        return {"float_decimal": value.spelling}
    if isinstance(value, TokenKind):
        return value.value
    if isinstance(value, tuple):
        return [_data(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "node_type": type(value).__name__,
            **{field.name: _data(getattr(value, field.name)) for field in fields(value)},
        }
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise TypeError(f"unsupported AST dump record {type(value).__name__}")


def ast_dump(result: ParseResult, context: RenderContext | None = None) -> str:
    context = context if context is not None else RenderContext()
    try:
        return (
            json.dumps(
                {
                    "schema_version": 1,
                    "file": context.filename(result.program.span.source.display_name),
                    "has_errors": result.diagnostics.has_errors,
                    "program": _data(result.program),
                    "missing_tokens": _data(result.missing_tokens),
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
    except RecursionError as error:
        raise ParserResourceError("host AST dump recursion capacity exhausted") from error
