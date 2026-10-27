"""Pure M02 text/JSON rendering with explicit host context and bounded snippets.

``render_text(report, context)`` and ``render_json(report, context)`` return
strings and perform no I/O. Context owns root-relative naming and color;
AUTO defaults to no color unless an explicit TTY context enables it. JSON is
schema version 1, ASCII escaped, with no renderer ANSI codes. Valid spans carry
original bytes and one-based scalar coordinates; rejected-source coordinates
are null, explicitly marked ``source_valid: false``. Labels/notes/edits retain
their supplied order, while top-level diagnostics have a deterministic total
order beginning with filename/start byte/code. Source ordinals are reporting
metadata, never identity comparisons.

Text uses four-column tab stops and escapes terminal controls in every field.
Each label gets a separate snippet so overlapping/cross-file labels cannot hide
one another. Long multiline spans show their first/last lines; long source lines
are clipped around the marker. Limits bound excerpts, not diagnostic messages.
"""

from __future__ import annotations

import json
import ntpath
import posixpath
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PureWindowsPath

from ternfold.frontend.diagnostics import (
    Diagnostic,
    DiagnosticReport,
    DiagnosticSpan,
    Label,
    RawSourceSpan,
    Severity,
    Suppression,
    span_filename,
)
from ternfold.frontend.source import SourceFile, SourceSpan

SCHEMA_VERSION = 1


class ColorMode(StrEnum):
    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


@dataclass(frozen=True, slots=True)
class RenderContext:
    root: str | Path | None = None
    color: ColorMode = ColorMode.AUTO
    is_tty: bool = False
    no_color: bool = False
    term_dumb: bool = False
    max_snippet_lines: int = 6
    max_snippet_columns: int = 120

    def __post_init__(self) -> None:
        if not isinstance(self.color, ColorMode):
            raise TypeError("color must be a ColorMode")
        if self.root is not None:
            root = str(self.root)
            if not (PureWindowsPath(root).is_absolute() or posixpath.isabs(root)):
                raise ValueError("renderer root must be absolute")
        if type(self.max_snippet_lines) is not int or self.max_snippet_lines < 2:
            raise ValueError("max_snippet_lines must be an integer of at least two")
        if type(self.max_snippet_columns) is not int or self.max_snippet_columns < 16:
            raise ValueError("max_snippet_columns must be an integer of at least sixteen")

    @property
    def use_color(self) -> bool:
        return self.color is ColorMode.ALWAYS or (
            self.color is ColorMode.AUTO
            and self.is_tty
            and not self.no_color
            and not self.term_dumb
        )

    def filename(self, display_name: str) -> str:
        """Lexical path formatting; no filesystem reads, cwd, or symlink resolution."""
        if display_name.startswith("<") and display_name.endswith(">"):
            return display_name
        root = str(self.root) if self.root is not None else None
        name_drive = PureWindowsPath(display_name).drive
        root_drive = PureWindowsPath(root).drive if root is not None else ""
        windows = bool(name_drive or root_drive)
        path_module = ntpath if windows else posixpath
        name: str = path_module.normpath(display_name)
        compatible = not windows or bool(name_drive and root_drive)
        if root is not None and compatible and path_module.isabs(name):
            try:
                name = path_module.relpath(name, root)
            except ValueError:
                # Different Windows drives have no relative path representation.
                pass
        return name.replace("\\", "/") if windows else name


def _safe(text: str) -> str:
    output: list[str] = []
    for char in text:
        number = ord(char)
        if unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"}:
            output.append(f"\\x{number:02x}" if number <= 255 else f"\\u{{{number:x}}}")
        else:
            output.append(char)
    return "".join(output)


def _span_data(span: DiagnosticSpan, context: RenderContext) -> dict[str, object]:
    valid = isinstance(span, SourceSpan)
    return {
        "file": context.filename(span_filename(span)),
        "source_id": span.source_id.value,
        "source_valid": valid,
        "start": {
            "byte": span.start_byte,
            "line": span.start.line if isinstance(span, SourceSpan) else None,
            "column": span.start.column if isinstance(span, SourceSpan) else None,
        },
        "end": {
            "byte": span.end_byte,
            "line": span.end.line if isinstance(span, SourceSpan) else None,
            "column": span.end.column if isinstance(span, SourceSpan) else None,
        },
    }


def _label_data(label: Label, context: RenderContext) -> dict[str, object]:
    return {"span": _span_data(label.span, context), "message": label.message}


def _diagnostic_data(diagnostic: Diagnostic, context: RenderContext) -> dict[str, object]:
    return {
        "code": diagnostic.code,
        "severity": diagnostic.severity.value,
        "message": diagnostic.message,
        "primary": _label_data(diagnostic.primary, context),
        "secondary": [_label_data(label, context) for label in diagnostic.secondary],
        "notes": list(diagnostic.notes),
        "help": list(diagnostic.help),
        "edits": [
            {"span": _span_data(edit.span, context), "replacement": edit.replacement}
            for edit in diagnostic.edits
        ],
    }


def _ordered(report: DiagnosticReport, context: RenderContext) -> list[Diagnostic]:
    def source_bytes(span: DiagnosticSpan) -> bytes:
        return span.source.original_bytes if isinstance(span, SourceSpan) else span.original_bytes

    def key(item: Diagnostic) -> tuple[str, int, str, str, tuple[bytes, ...]]:
        return (
            context.filename(span_filename(item.primary.span)),
            item.primary.span.start_byte,
            item.code,
            json.dumps(_diagnostic_data(item, context), sort_keys=True, ensure_ascii=True),
            # Identical metadata can still name distinct snapshots. Compare
            # immutable buffers only after all metadata ties, without copying.
            tuple(
                source_bytes(span)
                for span in (
                    item.primary.span,
                    *(label.span for label in item.secondary),
                    *(edit.span for edit in item.edits),
                )
            ),
        )

    return sorted(report.diagnostics, key=key)


def _ordered_suppressions(report: DiagnosticReport, context: RenderContext) -> list[Suppression]:
    return sorted(
        report.suppressed,
        key=lambda item: (
            context.filename(item.display_name),
            item.source_id.value,
            item.count,
            item.error_count,
        ),
    )


def render_json(report: DiagnosticReport, context: RenderContext | None = None) -> str:
    """Schema-v1 JSON; original messages round-trip, without terminal coloring."""
    context = context if context is not None else RenderContext()
    data = {
        "schema_version": SCHEMA_VERSION,
        "has_errors": report.has_errors,
        "diagnostics": [_diagnostic_data(item, context) for item in _ordered(report, context)],
        "suppressed": [
            {
                "file": context.filename(item.display_name),
                "source_id": item.source_id.value,
                "count": item.count,
                "error_count": item.error_count,
                "message": item.message,
            }
            for item in _ordered_suppressions(report, context)
        ],
    }
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _paint(text: str, severity: Severity, context: RenderContext) -> str:
    if not context.use_color:
        return text
    color = {Severity.ERROR: "31", Severity.WARNING: "33", Severity.NOTE: "36"}[severity]
    return f"\x1b[{color}m{text}\x1b[0m"


def _line_view(source: SourceFile, line: int) -> tuple[str, dict[int, int], int]:
    start = source.line_starts[line - 1]
    end = source.line_starts[line] if line < len(source.line_starts) else len(source.original_bytes)
    content = source.original_bytes[start:end]
    if content.endswith(b"\r\n"):
        content = content[:-2]
    elif content.endswith(b"\n"):
        content = content[:-1]
    content_end = start + len(content)
    output: list[str] = []
    columns: dict[int, int] = {}
    byte, column = start, 0
    for char in content.decode("utf-8"):
        columns[byte] = column
        visible = " " * (4 - column % 4) if char == "\t" else _safe(char)
        output.append(visible)
        column += len(visible)
        byte += len(char.encode("utf-8"))
    columns[content_end] = column
    return "".join(output), columns, content_end


def _snippet_line(
    source: SourceFile,
    line: int,
    span: SourceSpan,
    marker: str,
    context: RenderContext,
) -> tuple[str, str]:
    text, positions, content_end = _line_view(source, line)
    line_start = source.line_starts[line - 1]
    start_byte = min(content_end, max(line_start, span.start_byte))
    end_byte = min(content_end, max(line_start, span.end_byte))
    start, end = positions[start_byte], positions[end_byte]
    width = context.max_snippet_columns
    window = max(0, min(start - width // 3, len(text) - width))
    prefix = "..." if window else ""
    suffix = "..." if window + width < len(text) else ""
    shown = prefix + text[window : window + width] + suffix
    offset = len(prefix) + start - window
    length = max(1, min(end, window + width) - start)
    return shown, " " * offset + marker * length


def _label_text(
    label: Label, primary: bool, severity: Severity, context: RenderContext
) -> list[str]:
    span = label.span
    filename = _safe(context.filename(span_filename(span)))
    arrow = "-->" if primary else ":::"
    if isinstance(span, RawSourceSpan):
        low = max(0, span.start_byte - 8)
        high = min(len(span.original_bytes), max(span.end_byte, span.start_byte + 1) + 8, low + 32)
        lines = [
            f" {arrow} {filename}:bytes {span.start_byte}..{span.end_byte}",
            f"  | bytes {low}..{high}: {span.original_bytes[low:high].hex(' ')}",
            "  | scalar coordinates unavailable for rejected source",
        ]
        if label.message:
            lines.append(f"  = {_safe(label.message)}")
        return lines

    first = span.start.line
    last = span.end.line
    if span.end_byte > span.start_byte and span.end.column == 1:
        last -= 1
    count = last - first + 1
    maximum = context.max_snippet_lines
    if count <= maximum:
        selected = list(range(first, last + 1))
    else:
        head = (maximum + 1) // 2
        tail = maximum // 2
        selected = [*range(first, first + head), *range(last - tail + 1, last + 1)]
    gutter = len(str(last))
    lines = [f" {arrow} {filename}:{first}:{span.start.column}"]
    previous = first - 1
    for line in selected:
        if line != previous + 1:
            lines.append(f" {' ' * gutter} | ...")
        text, underline = _snippet_line(span.source, line, span, "^" if primary else "-", context)
        lines.append(f" {line:>{gutter}} | {text}")
        suffix = f" {_safe(label.message)}" if line == selected[-1] and label.message else ""
        lines.append(f" {' ' * gutter} | {_paint(underline, severity, context)}{suffix}")
        previous = line
    return lines


def render_text(report: DiagnosticReport, context: RenderContext | None = None) -> str:
    context = context if context is not None else RenderContext()
    blocks: list[str] = []
    for diagnostic in _ordered(report, context):
        heading = _paint(
            f"{diagnostic.severity.value}[{diagnostic.code}]", diagnostic.severity, context
        )
        lines = [f"{heading}: {_safe(diagnostic.message)}"]
        lines.extend(_label_text(diagnostic.primary, True, diagnostic.severity, context))
        for label in diagnostic.secondary:
            lines.extend(_label_text(label, False, diagnostic.severity, context))
        lines.extend(f"  = note: {_safe(note)}" for note in diagnostic.notes)
        lines.extend(f"  = help: {_safe(help_text)}" for help_text in diagnostic.help)
        for edit in diagnostic.edits:
            span = edit.span
            name = _safe(context.filename(span.source.display_name))
            lines.append(
                f"  = edit: {name}:{span.start.line}:{span.start.column}"
                f"..{span.end.line}:{span.end.column} -> "
                f"{json.dumps(edit.replacement, ensure_ascii=True)}"
            )
        blocks.append("\n".join(lines))
    for suppressed in _ordered_suppressions(report, context):
        name = _safe(context.filename(suppressed.display_name))
        blocks.append(f"note: {name}: {suppressed.message}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")
