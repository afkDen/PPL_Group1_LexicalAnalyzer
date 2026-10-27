"""Frontend source contracts; later phases depend on these immutable snapshots."""

from ternfold.frontend.source import (
    SourceError,
    SourceFile,
    SourceId,
    SourceLoadResult,
    SourceLocation,
    SourceManager,
    SourceSpan,
    SourceValidationError,
)

__all__ = [
    "SourceError",
    "SourceFile",
    "SourceId",
    "SourceLoadResult",
    "SourceLocation",
    "SourceManager",
    "SourceSpan",
    "SourceValidationError",
]
