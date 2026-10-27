"""Deterministic schema-v1 JSON for verified Core, with original source origins."""

import json
from dataclasses import fields, is_dataclass
from enum import Enum

from ternfold.core import nodes as C
from ternfold.frontend.ast import NodeId
from ternfold.frontend.render import RenderContext
from ternfold.frontend.source import SourceSpan


def core_dump(core: C.VerifiedCore, context: RenderContext | None = None) -> str:
    context = context or RenderContext()

    def encode(value: object) -> object:
        if isinstance(value, SourceSpan):
            return {
                "file": context.filename(value.source.display_name),
                "start": {
                    "byte": value.start_byte,
                    "line": value.start.line,
                    "column": value.start.column,
                },
                "end": {"byte": value.end_byte, "line": value.end.line, "column": value.end.column},
            }
        if isinstance(value, NodeId):
            return value.value
        if isinstance(value, (C.FunctionId, C.ValueId)):
            return value.value
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, tuple):
            return [encode(item) for item in value]
        if is_dataclass(value) and not isinstance(value, type):
            return {
                "node_type": type(value).__name__,
                **{field.name: encode(getattr(value, field.name)) for field in fields(value)},
            }
        return value

    return (
        json.dumps(
            {
                "schema_version": 1,
                "phase": "verified-core",
                "language_execution": False,
                "program": encode(core.program),
            },
            ensure_ascii=True,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
