"""Immutable UTF-8 snapshots and original-byte coordinates (M01).

M02 may construct spans with ``source.span(start, end)`` and inspect ``text``
using ``scalar_byte_offsets`` to translate scalar indices back to bytes. All
offsets are half-open byte offsets into ``original_bytes``; endpoints must be
scalar boundaries, including EOF. Lines/columns are one-based. CR and LF in a
CRLF pair each have a scalar position on the preceding line; the next line
starts after LF. Tabs count as one source column; ``display_column`` expands
them to four-column stops. Other scalars occupy one display column (not wcwidth).

``SourceManager`` is the explicit filesystem-loading capability. It caches each
canonical path, including validation failures, for its lifetime. In-memory
loads always get fresh identities. Filesystem errors propagate to the driver.
``SourceLoadResult`` returns source errors as data, without printing. Direct
``SourceFile`` construction instead raises ``SourceValidationError`` carrying
the same data. Validation reports the first error, in order: UTF-8, BOM, lone CR.
Invalid-source errors retain raw bytes because no valid SourceSpan exists yet.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, NoReturn

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


def _integer(value: int, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")


@dataclass(frozen=True, slots=True, eq=False)
class SourceId:
    """Opaque identity, with a session-local ordinal for deterministic reporting.

    Equality is identity equality: IDs from separate managers never collide,
    even when their ordinals match. Keep the wrapper, not just ``value``.
    """

    value: int

    def __post_init__(self) -> None:
        _integer(self.value, "source ordinal")
        if self.value < 0:
            raise ValueError("source ordinal must be nonnegative")


@dataclass(frozen=True, slots=True)
class SourceError:
    """A source validation failure, located in the rejected original bytes."""

    code: Literal["E001", "E002", "E003"]
    message: str
    source_id: SourceId
    display_name: str
    original_bytes: bytes
    start_byte: int
    end_byte: int


class SourceValidationError(ValueError):
    """Direct-construction failure; ``error`` is the structured error payload."""

    def __init__(self, error: SourceError) -> None:
        self.error = error
        super().__init__(f"{error.code}: {error.message}")


@dataclass(frozen=True, slots=True, eq=False)
class SourceFile:
    """Validated immutable snapshot; construction never normalizes source bytes."""

    source_id: SourceId
    display_name: str
    original_bytes: bytes = field(repr=False)
    text: str = field(init=False, repr=False)
    line_starts: tuple[int, ...] = field(init=False)
    scalar_byte_offsets: tuple[int, ...] = field(init=False, repr=False)
    _line_scalar_starts: tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.original_bytes, bytes):
            raise TypeError("original_bytes must be immutable bytes")
        try:
            text = self.original_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            self._fail("E001", "source is not valid UTF-8", error.start, error.end)
        if text.startswith("\ufeff"):
            self._fail("E002", "source must not start with a UTF-8 BOM", 0, 3)

        byte_offsets = [0]
        line_starts = [0]
        line_scalar_starts = [0]
        offset = 0
        for index, scalar in enumerate(text):
            if scalar == "\r" and (index + 1 == len(text) or text[index + 1] != "\n"):
                self._fail("E003", "lone CR is not a source line ending", offset, offset + 1)
            offset += len(scalar.encode("utf-8"))
            byte_offsets.append(offset)
            if scalar == "\n":
                line_starts.append(offset)
                line_scalar_starts.append(index + 1)

        object.__setattr__(self, "text", text)
        object.__setattr__(self, "line_starts", tuple(line_starts))
        object.__setattr__(self, "scalar_byte_offsets", tuple(byte_offsets))
        object.__setattr__(self, "_line_scalar_starts", tuple(line_scalar_starts))

    def _fail(
        self,
        code: Literal["E001", "E002", "E003"],
        message: str,
        start: int,
        end: int,
    ) -> NoReturn:
        raise SourceValidationError(
            SourceError(
                code, message, self.source_id, self.display_name, self.original_bytes, start, end
            )
        )

    def scalar_index(self, byte_offset: int) -> int:
        """Return a scalar index (EOF included); reject UTF-8 interior bytes."""
        _integer(byte_offset, "byte offset")
        index = bisect_left(self.scalar_byte_offsets, byte_offset)
        if index == len(self.scalar_byte_offsets) or self.scalar_byte_offsets[index] != byte_offset:
            raise ValueError("byte offset must be a scalar boundary within the snapshot")
        return index

    def byte_offset_for_scalar(self, scalar_index: int) -> int:
        """Map a zero-based scalar index or EOF to its original byte offset."""
        _integer(scalar_index, "scalar index")
        if not 0 <= scalar_index < len(self.scalar_byte_offsets):
            raise ValueError("scalar index is outside the snapshot")
        return self.scalar_byte_offsets[scalar_index]

    def location(self, byte_offset: int) -> SourceLocation:
        return SourceLocation(self, byte_offset)

    def byte_offset(self, line: int, column: int) -> int:
        """Invert source coordinates, including newline scalars and EOF.

        A line ending belongs to its preceding line. A position after the line
        ending must use the next line's coordinates, never a column alias.
        """
        _integer(line, "line")
        _integer(column, "column")
        if not 1 <= line <= len(self.line_starts) or column < 1:
            raise ValueError("source coordinates are outside the snapshot")
        scalar = self._line_scalar_starts[line - 1] + column - 1
        limit = (
            self._line_scalar_starts[line]
            if line < len(self.line_starts)
            else len(self.scalar_byte_offsets)
        )
        if scalar >= limit:
            raise ValueError("column is outside the source line")
        return self.scalar_byte_offsets[scalar]

    def display_column(self, byte_offset: int) -> int:
        """One-based snippet column, expanding tabs at four-column stops."""
        scalar = self.scalar_index(byte_offset)
        line = bisect_right(self.line_starts, byte_offset) - 1
        column = 1
        for char in self.text[self._line_scalar_starts[line] : scalar]:
            column += 4 - (column - 1) % 4 if char == "\t" else 1
        return column

    def span(self, start_byte: int, end_byte: int) -> SourceSpan:
        return SourceSpan(self, start_byte, end_byte)


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Lazy scalar coordinates for one validated byte boundary in a snapshot."""

    source: SourceFile = field(repr=False)
    byte_offset: int
    line: int = field(init=False)
    column: int = field(init=False)

    def __post_init__(self) -> None:
        scalar = self.source.scalar_index(self.byte_offset)
        line_index = bisect_right(self.source.line_starts, self.byte_offset) - 1
        object.__setattr__(self, "line", line_index + 1)
        object.__setattr__(self, "column", scalar - self.source._line_scalar_starts[line_index] + 1)

    @property
    def source_id(self) -> SourceId:
        return self.source.source_id


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Validated half-open byte range retaining the exact owning snapshot."""

    source: SourceFile = field(repr=False)
    start_byte: int
    end_byte: int

    def __post_init__(self) -> None:
        self.source.scalar_index(self.start_byte)
        self.source.scalar_index(self.end_byte)
        if self.start_byte > self.end_byte:
            raise ValueError("span start must not follow its end")

    @property
    def source_id(self) -> SourceId:
        return self.source.source_id

    @property
    def start(self) -> SourceLocation:
        return self.source.location(self.start_byte)

    @property
    def end(self) -> SourceLocation:
        return self.source.location(self.end_byte)

    @property
    def original_bytes(self) -> bytes:
        return self.source.original_bytes[self.start_byte : self.end_byte]

    @property
    def text(self) -> str:
        return self.original_bytes.decode("utf-8")

    def join(self, other: SourceSpan) -> SourceSpan:
        """Smallest enclosing span; snapshots must be identical, even for EOF."""
        if self.source is not other.source:
            raise ValueError("cannot join spans from different source snapshots")
        return SourceSpan(
            self.source, min(self.start_byte, other.start_byte), max(self.end_byte, other.end_byte)
        )


@dataclass(frozen=True, slots=True)
class SourceLoadResult:
    """Exactly one valid source or a nonempty tuple of source validation errors."""

    source: SourceFile | None
    errors: tuple[SourceError, ...]

    def __post_init__(self) -> None:
        if (self.source is None) != bool(self.errors):
            raise ValueError("source load must contain either a source or errors")


class SourceManager:
    """Session owner of explicit loads; cached snapshots never silently reread.

    ``Path.resolve()`` defines canonical-path deduplication (including symlinks,
    but not hard-link inode identity). Byte loads do not deduplicate by name.
    Start a new manager to observe disk changes; no implicit refresh exists.
    File extensions and allowed roots are driver/module-loader policy.
    """

    def __init__(self) -> None:
        self._paths: dict[Path, SourceLoadResult] = {}
        self._next_id = 0

    def add_bytes(self, display_name: str, data: bytes) -> SourceLoadResult:
        source_id = SourceId(self._next_id)
        self._next_id += 1
        try:
            source = SourceFile(source_id, display_name, data)
        except SourceValidationError as error:
            return SourceLoadResult(None, (error.error,))
        return SourceLoadResult(source, ())

    def load_path(self, path: str | Path) -> SourceLoadResult:
        canonical = Path(path).resolve()
        if canonical not in self._paths:
            self._paths[canonical] = self.add_bytes(str(canonical), canonical.read_bytes())
        return self._paths[canonical]
