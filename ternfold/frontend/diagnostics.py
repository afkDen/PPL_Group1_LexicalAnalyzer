"""M02 diagnostic data and bounded phase results; no rendering or printing.

Construct ``Diagnostic`` with an offending primary ``Label`` and ordered
secondary labels, notes/help, and machine-applicable ``TextEdit`` records.
``DiagnosticBag`` retains at most 100 diagnostics per source identity by default;
its immutable report retains suppressed error counts so a cap cannot turn a
failed phase into success. ``ValidResult`` and ``ErrorResult`` enforce that
boundary. Later phases must branch on the result before consuming its value.

Source loading fails before SourceFile exists. ``diagnostic_from_source_error``
uses a validated raw-byte range, never a replacement-decoded fake SourceFile.
Codes are stable letter-plus-three-digit identifiers, not a semantic registry:
owning phases introduce the E/R codes specified in the language documents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ternfold.frontend.source import SourceError, SourceId, SourceSpan


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


@dataclass(frozen=True, slots=True)
class RawSourceSpan:
    """Original-byte range in a rejected source; scalar coordinates unavailable."""

    source_id: SourceId
    display_name: str
    original_bytes: bytes = field(repr=False)
    start_byte: int
    end_byte: int

    def __post_init__(self) -> None:
        if not isinstance(self.original_bytes, bytes):
            raise TypeError("raw source must be immutable bytes")
        if type(self.start_byte) is not int or type(self.end_byte) is not int:
            raise TypeError("raw span endpoints must be integer byte offsets")
        if not 0 <= self.start_byte <= self.end_byte <= len(self.original_bytes):
            raise ValueError("raw span is outside the rejected source bytes")


type DiagnosticSpan = SourceSpan | RawSourceSpan


def span_filename(span: DiagnosticSpan) -> str:
    return span.source.display_name if isinstance(span, SourceSpan) else span.display_name


@dataclass(frozen=True, slots=True)
class Label:
    span: DiagnosticSpan
    message: str = ""


@dataclass(frozen=True, slots=True)
class TextEdit:
    """A replacement in valid source bytes; edits are suggestions, never applied."""

    span: SourceSpan
    replacement: str

    def __post_init__(self) -> None:
        if not isinstance(self.span, SourceSpan):
            raise TypeError("machine-applicable edits require a valid SourceSpan")
        # A proposed replacement must itself be encodable as Unicode scalars.
        self.replacement.encode("utf-8", errors="strict")


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    severity: Severity
    message: str
    primary: Label
    secondary: tuple[Label, ...] = ()
    notes: tuple[str, ...] = ()
    help: tuple[str, ...] = ()
    edits: tuple[TextEdit, ...] = ()

    def __post_init__(self) -> None:
        if not (
            len(self.code) == 4
            and "A" <= self.code[0] <= "Z"
            and all("0" <= digit <= "9" for digit in self.code[1:])
        ):
            raise ValueError("diagnostic code must be an ASCII letter followed by three digits")
        if not isinstance(self.severity, Severity):
            raise TypeError("severity must be a Severity")
        if not self.message:
            raise ValueError("diagnostic message must not be empty")
        # Snapshot caller-owned collections instead of retaining mutable lists.
        for name in ("secondary", "notes", "help", "edits"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


def diagnostic_from_source_error(error: SourceError) -> Diagnostic:
    return Diagnostic(
        error.code,
        Severity.ERROR,
        error.message,
        Label(
            RawSourceSpan(
                error.source_id,
                error.display_name,
                error.original_bytes,
                error.start_byte,
                error.end_byte,
            )
        ),
    )


@dataclass(frozen=True, slots=True)
class Suppression:
    """One per-file suppression note, including the errors hidden by the cap."""

    source_id: SourceId
    display_name: str
    count: int
    error_count: int

    def __post_init__(self) -> None:
        if type(self.count) is not int or type(self.error_count) is not int:
            raise TypeError("suppression counts must be integers")
        if self.count < 1 or not 0 <= self.error_count <= self.count:
            raise ValueError("invalid suppression counts")

    @property
    def message(self) -> str:
        return f"{self.count} further diagnostics suppressed ({self.error_count} errors)"


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    diagnostics: tuple[Diagnostic, ...] = ()
    suppressed: tuple[Suppression, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "suppressed", tuple(self.suppressed))

    @property
    def has_errors(self) -> bool:
        return any(item.severity is Severity.ERROR for item in self.diagnostics) or any(
            item.error_count for item in self.suppressed
        )


class DiagnosticBag:
    """Mutable phase-local collector; ``report()`` returns an immutable snapshot.

    The cap counts all severities against the primary source identity. Secondary
    cross-file labels do not spend another file's budget. Insertion order decides
    retention; renderers sort retained diagnostics independently and stably.
    """

    def __init__(self, max_per_file: int = 100) -> None:
        if type(max_per_file) is not int:
            raise TypeError("diagnostic cap must be an integer")
        if max_per_file < 0:
            raise ValueError("diagnostic cap must be nonnegative")
        self._cap = max_per_file
        self._diagnostics: list[Diagnostic] = []
        self._counts: dict[SourceId, int] = {}
        self._suppressed: dict[SourceId, Suppression] = {}

    def add(self, diagnostic: Diagnostic) -> bool:
        """Return whether retained; always record a suppressed error's failure."""
        span = diagnostic.primary.span
        source_id = span.source_id
        count = self._counts.get(source_id, 0)
        if count < self._cap:
            self._diagnostics.append(diagnostic)
            self._counts[source_id] = count + 1
            return True
        previous = self._suppressed.get(source_id)
        self._suppressed[source_id] = Suppression(
            source_id,
            span_filename(span),
            (previous.count if previous else 0) + 1,
            (previous.error_count if previous else 0) + (diagnostic.severity is Severity.ERROR),
        )
        return False

    @property
    def has_errors(self) -> bool:
        return self.report().has_errors

    def report(self) -> DiagnosticReport:
        return DiagnosticReport(tuple(self._diagnostics), tuple(self._suppressed.values()))


@dataclass(frozen=True, slots=True)
class ValidResult[T]:
    value: T
    diagnostics: DiagnosticReport = field(default_factory=DiagnosticReport)

    def __post_init__(self) -> None:
        if self.diagnostics.has_errors:
            raise ValueError(
                "a valid phase result cannot contain errors, including suppressed errors"
            )


@dataclass(frozen=True, slots=True)
class ErrorResult:
    diagnostics: DiagnosticReport

    def __post_init__(self) -> None:
        if not self.diagnostics.has_errors:
            raise ValueError("an error phase result must contain an error")


type Result[T] = ValidResult[T] | ErrorResult
