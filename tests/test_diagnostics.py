"""M02 diagnostic contracts, exact render fixtures and adversarial boundaries."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from itertools import permutations
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ternfold.frontend.diagnostics import (
    Diagnostic,
    DiagnosticBag,
    DiagnosticReport,
    ErrorResult,
    Label,
    RawSourceSpan,
    Result,
    Severity,
    Suppression,
    TextEdit,
    ValidResult,
    diagnostic_from_source_error,
)
from ternfold.frontend.render import ColorMode, RenderContext, render_json, render_text
from ternfold.frontend.source import SourceFile, SourceId, SourceManager, SourceSpan

FIXTURES = Path(__file__).parent / "fixtures" / "diagnostics"
CONTEXT = RenderContext(root="/project")


def source(text: str = "abc\n", name: str = "/project/main.tfd") -> SourceFile:
    return SourceFile(SourceId(0), name, text.encode("utf-8"))


def diagnostic(
    span: SourceSpan | None = None,
    *,
    message: str = "unexpected token",
    code: str = "E110",
    severity: Severity = Severity.ERROR,
) -> Diagnostic:
    return Diagnostic(
        code, severity, message, Label(span if span is not None else source().span(0, 1))
    )


def golden_report() -> DiagnosticReport:
    main = source("let\tΩ = 'é';\r\n\tsecond\n\nlast", "/project/src/main.tfd")
    other = source("\tdecl\n", "/project/lib/decl.tfd")
    empty = source("", "/project/empty.tfd")
    omega = main.span(4, 6)
    return DiagnosticReport(
        (
            Diagnostic(
                "E203",
                Severity.ERROR,
                "unresolved name Ω",
                Label(omega, "unknown binding"),
                (
                    Label(main.span(0, 6), "overlapping context"),
                    Label(other.span(1, 5), "declared here"),
                ),
                ("names are case sensitive",),
                ("use an ASCII identifier",),
                (TextEdit(omega, "omega"),),
            ),
            Diagnostic(
                "E110",
                Severity.ERROR,
                "unfinished block",
                Label(main.span(0, len(main.original_bytes)), "block extends to EOF"),
            ),
            Diagnostic("W001", Severity.WARNING, "empty file", Label(empty.span(0, 0), "EOF")),
            Diagnostic(
                "E110",
                Severity.ERROR,
                "missing token",
                Label(main.span(len(main.original_bytes), len(main.original_bytes)), "insert here"),
            ),
        )
    )


def raw_report() -> DiagnosticReport:
    manager = SourceManager()
    diagnostics = []
    for name, data in [
        ("/project/utf8.tfd", b"a\xffb"),
        ("/project/bom.tfd", b"\xef\xbb\xbfx"),
        ("/project/cr.tfd", "é\rX".encode()),
    ]:
        loaded = manager.add_bytes(name, data)
        assert loaded.source is None
        diagnostics.append(diagnostic_from_source_error(loaded.errors[0]))
    return DiagnosticReport(tuple(diagnostics))


@pytest.mark.parametrize("kind", ["snippets", "raw"])
def test_exact_text_and_json_golden_fixtures(kind: str) -> None:
    report = golden_report() if kind == "snippets" else raw_report()
    assert render_text(report, CONTEXT) == (FIXTURES / f"{kind}.txt").read_text(encoding="utf-8")
    assert render_json(report, CONTEXT) == (FIXTURES / f"{kind}.json").read_text(encoding="utf-8")


def test_json_schema_keys_coordinate_roundtrips_and_crossfile_edit() -> None:
    report = golden_report()
    result = json.loads(render_json(report, CONTEXT))
    schema = json.loads((FIXTURES / "schema-v1.json").read_text(encoding="utf-8"))
    assert set(result) == set(schema["required"])
    assert result["schema_version"] == schema["properties"]["schema_version"]["const"] == 1
    assert result["has_errors"] is True
    assert result["suppressed"] == []
    originals = {item.message: item for item in report.diagnostics}
    for item in result["diagnostics"]:
        assert set(item) == set(schema["$defs"]["diagnostic"]["required"])
        original = originals[item["message"]]
        original_span = original.primary.span
        assert isinstance(original_span, SourceSpan)
        span = item["primary"]["span"]
        assert set(span) == set(schema["$defs"]["span"]["required"])
        assert span["source_valid"] is True
        assert not span["file"].startswith("/")
        assert "display_column" not in span
        for name, byte in [("start", original_span.start_byte), ("end", original_span.end_byte)]:
            position = span[name]
            assert set(position) == {"byte", "line", "column"}
            assert position["byte"] == byte
            assert original_span.source.byte_offset(position["line"], position["column"]) == byte
    name_error = next(item for item in result["diagnostics"] if item["code"] == "E203")
    assert name_error["primary"]["span"]["start"] == {"byte": 4, "line": 1, "column": 5}
    assert name_error["primary"]["span"]["end"] == {"byte": 6, "line": 1, "column": 6}
    assert name_error["secondary"][1]["span"]["file"] == "lib/decl.tfd"
    assert name_error["edits"][0]["replacement"] == "omega"
    assert name_error["edits"][0]["span"] == name_error["primary"]["span"]


@pytest.mark.parametrize("data", [b"\xff", b"\xef\xbb\xbf", b"a\r"])
def test_source_error_adapter_never_builds_a_fake_source(data: bytes) -> None:
    error = SourceManager().add_bytes("bad.tfd", data).errors[0]
    with patch.object(SourceFile, "__post_init__", side_effect=AssertionError("fake snapshot")):
        item = diagnostic_from_source_error(error)
        report = DiagnosticReport((item,))
        rendered = render_text(report)
        parsed = json.loads(render_json(report))
    span = item.primary.span
    assert isinstance(span, RawSourceSpan)
    assert span.original_bytes is data
    assert (span.start_byte, span.end_byte) == (error.start_byte, error.end_byte)
    encoded_span = parsed["diagnostics"][0]["primary"]["span"]
    assert encoded_span["source_valid"] is False
    assert encoded_span["start"] == {"byte": error.start_byte, "line": None, "column": None}
    assert encoded_span["end"] == {"byte": error.end_byte, "line": None, "column": None}
    assert "scalar coordinates unavailable" in rendered
    assert "\ufffd" not in rendered


def test_default_cap_is_100_per_primary_file_with_one_note_and_persistent_error_state() -> None:
    first, second = source(), source(name="/project/other.tfd")
    bag = DiagnosticBag()
    for _ in range(100):
        assert bag.add(diagnostic(first.span(0, 0), code="W001", severity=Severity.WARNING))
    before = bag.report()
    assert not before.has_errors
    assert not bag.add(diagnostic(first.span(0, 0)))
    assert not bag.add(diagnostic(first.span(0, 1)))
    assert not bag.add(diagnostic(first.span(0, 1), code="N001", severity=Severity.NOTE))
    assert bag.has_errors  # The only errors so far are suppressed after 100 warnings.
    assert bag.add(diagnostic(second.span(0, 0)))
    report = bag.report()
    assert len(report.diagnostics) == 101
    assert len(report.suppressed) == 1
    assert (report.suppressed[0].count, report.suppressed[0].error_count) == (3, 2)
    assert bag.has_errors and report.has_errors
    assert not before.has_errors and not before.suppressed
    text = render_text(report, CONTEXT)
    assert text.count("further diagnostics suppressed") == 1
    parsed = json.loads(render_json(report, CONTEXT))
    assert parsed["has_errors"] is True
    assert parsed["suppressed"][0]["error_count"] == 2


def test_suppressed_only_error_is_a_failure_and_cannot_be_valid_result() -> None:
    bag = DiagnosticBag(max_per_file=0)
    assert not bag.add(diagnostic())
    report = bag.report()
    assert not report.diagnostics and report.has_errors and bag.has_errors
    assert ErrorResult(report).diagnostics is report
    with pytest.raises(ValueError, match="suppressed"):
        ValidResult(42, report)
    assert json.loads(render_json(report))["has_errors"] is True
    assert "1 further diagnostics suppressed (1 errors)" in render_text(report)


def test_cap_counts_primary_source_identity_and_preserves_two_file_suppressions() -> None:
    first, second = source(), source()  # Same display name and ordinal, distinct identities.
    bag = DiagnosticBag(max_per_file=1)
    item = Diagnostic(
        "E202", Severity.ERROR, "duplicate", Label(first.span(0, 1)), (Label(second.span(0, 1)),)
    )
    assert bag.add(item)
    assert bag.add(diagnostic(second.span(0, 1)))
    assert not bag.add(item)
    assert not bag.add(diagnostic(second.span(0, 1)))
    assert len(bag.report().suppressed) == 2
    assert len(bag.report().diagnostics) == 2


def test_explicit_result_variants_allow_warnings_and_reject_false_success_or_failure() -> None:
    warnings = DiagnosticReport((diagnostic(code="W001", severity=Severity.WARNING),))
    valid: Result[int] = ValidResult(42, warnings)
    assert isinstance(valid, ValidResult) and valid.value == 42
    assert ValidResult(None).value is None
    errors = DiagnosticReport((diagnostic(),))
    failed: Result[int] = ErrorResult(errors)
    assert isinstance(failed, ErrorResult)
    assert not hasattr(failed, "value")
    with pytest.raises(ValueError):
        ValidResult(42, errors)
    with pytest.raises(ValueError):
        ErrorResult(warnings)
    with pytest.raises(ValueError):
        ErrorResult(DiagnosticReport())


@pytest.mark.parametrize(
    ("mode", "tty", "no_color", "dumb", "expected"),
    [
        (ColorMode.AUTO, False, False, False, False),
        (ColorMode.AUTO, True, False, False, True),
        (ColorMode.AUTO, True, True, False, False),
        (ColorMode.AUTO, True, False, True, False),
        (ColorMode.ALWAYS, False, True, True, True),
        (ColorMode.NEVER, True, False, False, False),
    ],
)
def test_explicit_color_context_and_json_never_color(
    mode: ColorMode, tty: bool, no_color: bool, dumb: bool, expected: bool
) -> None:
    context = RenderContext(color=mode, is_tty=tty, no_color=no_color, term_dumb=dumb)
    report = DiagnosticReport((diagnostic(),))
    assert ("\x1b[" in render_text(report, context)) is expected
    assert "\x1b" not in render_json(report, context)
    assert render_json(report, context) == render_json(report)


def test_raw_controls_escaped_in_every_text_field_and_json_roundtrips() -> None:
    control = "\x00\x1b[31m\x7f\x85\u202e\n\t"
    file = source("\x00\x1b\tΩ\n", "/project/unsafe" + control + ".tfd")
    item = Diagnostic(
        "E101",
        Severity.ERROR,
        control,
        Label(file.span(0, 5), control),
        (Label(file.span(1, 2), control),),
        (control,),
        (control,),
        (TextEdit(file.span(0, 0), control),),
    )
    report = DiagnosticReport((item,))
    text = render_text(report, CONTEXT)
    assert all(ord(char) >= 32 or char == "\n" for char in text)
    assert "\x7f" not in text and "\x85" not in text and "\u202e" not in text
    assert "\\x00" in text and "\\x1b" in text
    assert "\\u{202e}" in text
    parsed = json.loads(render_json(report, RenderContext(color=ColorMode.ALWAYS)))
    encoded = parsed["diagnostics"][0]
    assert encoded["message"] == encoded["primary"]["message"] == control
    assert encoded["notes"] == encoded["help"] == [control]
    assert encoded["edits"][0]["replacement"] == control
    assert "\x1b" not in render_json(report)


def test_escaped_source_controls_adjust_marker_and_four_stop_tab_positions() -> None:
    file = source("\x00\tΩ")
    text = render_text(DiagnosticReport((diagnostic(file.span(2, 4)),)), CONTEXT)
    assert " 1 | \\x00    Ω\n   |         ^\n" in text
    assert file.location(2).column == 3
    assert file.display_column(2) == 5  # Renderer additionally accounts for control escaping.


def test_multiline_and_long_line_clipping_golden() -> None:
    file = source("\n".join(f"line {index}" for index in range(1, 11)))
    long_file = source("x" * 200 + "Ω" + "y" * 100, "/project/long.tfd")
    report = DiagnosticReport(
        (diagnostic(file.span(0, len(file.original_bytes))), diagnostic(long_file.span(200, 202)))
    )
    context = RenderContext(root="/project", max_snippet_lines=4, max_snippet_columns=20)
    rendered = render_text(report, context)
    assert rendered == (FIXTURES / "clipped.txt").read_text(encoding="utf-8")
    assert "line 3" not in rendered and "line 8" not in rendered
    assert "line 1" in rendered and "line 10" in rendered
    assert "..." in rendered and "Ω" in rendered
    assert max(map(len, rendered.splitlines())) < 90


@pytest.mark.parametrize("text", ["", "\n", "\r\n", "x\n", "x\r\n"])
def test_zero_width_eof_and_newline_spans_have_visible_markers(text: str) -> None:
    file = source(text)
    eof = file.span(len(file.original_bytes), len(file.original_bytes))
    rendered = render_text(DiagnosticReport((diagnostic(eof),)))
    assert "^" in rendered
    assert f":{eof.start.line}:{eof.start.column}" in rendered
    if text:
        newline = file.span(len(file.original_bytes) - 1, len(file.original_bytes))
        snippet = render_text(DiagnosticReport((diagnostic(newline),)))
        assert "^" in snippet
        assert f" {newline.start.line + 1} |" not in snippet


def test_sort_order_filename_byte_code_and_full_content_tiebreaker() -> None:
    a = source(name="/project/a.tfd")
    z = source(name="/project/z.tfd")
    items = (
        diagnostic(z.span(0, 1)),
        diagnostic(a.span(1, 2), code="E101"),
        diagnostic(a.span(0, 1), code="E203"),
        diagnostic(a.span(0, 1), code="E101", message="z"),
        diagnostic(a.span(0, 1), code="E101", message="a"),
    )
    expected = render_json(DiagnosticReport(items), CONTEXT)
    expected_text = render_text(DiagnosticReport(items), CONTEXT)
    for order in permutations(items):
        assert render_json(DiagnosticReport(order), CONTEXT) == expected
        assert render_text(DiagnosticReport(order), CONTEXT) == expected_text
    parsed = json.loads(expected)
    assert [item["message"] for item in parsed["diagnostics"][:2]] == ["a", "z"]


def test_rendering_is_stable_across_process_hash_seeds_and_set_iteration() -> None:
    script = r"""
import sys
sys.path.insert(0, 'src')
from ternfold.frontend.source import SourceFile, SourceId
from ternfold.frontend.diagnostics import (
    Diagnostic, DiagnosticReport, Label, Severity, diagnostic_from_source_error
)
from ternfold.frontend.source import SourceManager
from ternfold.frontend.render import render_json, render_text
source = SourceFile(SourceId(0), 'same.tfd', b'abc')
items = tuple(Diagnostic('E110', Severity.ERROR, message, Label(source.span(0, 1)))
              for message in {'zeta', 'alpha', 'gamma', 'beta'})
report = DiagnosticReport(items)
sys.stdout.write(render_json(report) + render_text(report))
for label_kind in ('primary', 'secondary', 'raw', 'raw_secondary'):
    items = []
    for content in {'aaa', 'zzz', 'ccc'}:
        if label_kind.startswith('raw'):
            error = SourceManager().add_bytes('same.tfd', content.encode() + b'\xff').errors[0]
            item = diagnostic_from_source_error(error)
            if label_kind == 'raw_secondary':
                item = Diagnostic('E110', Severity.ERROR, 'same', Label(source.span(0, 1)),
                                  (item.primary,))
        else:
            snapshot = SourceFile(SourceId(0), 'same.tfd', content.encode())
            label = Label(snapshot.span(0, 1))
            item = Diagnostic('E110', Severity.ERROR, 'same',
                              label if label_kind == 'primary' else Label(source.span(0, 1)),
                              () if label_kind == 'primary' else (label,))
        items.append(item)
    report = DiagnosticReport(tuple(items))
    sys.stdout.write(render_json(report) + render_text(report))
"""
    outputs = []
    for seed in ["1", "42", "98765"]:
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).parents[1],
            env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            check=False,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr.decode()
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


@pytest.mark.parametrize("kind", ["primary", "secondary", "raw", "raw_secondary"])
def test_text_sort_ties_include_snapshot_content_even_when_json_metadata_matches(kind: str) -> None:
    first, second = source("aaa"), source("zzz")
    shared_primary = Label(source().span(0, 1))
    if kind.startswith("raw"):
        items = tuple(
            diagnostic_from_source_error(SourceManager().add_bytes("same.tfd", data).errors[0])
            for data in (b"a\xff", b"z\xff")
        )
        if kind == "raw_secondary":
            items = tuple(
                replace(item, primary=shared_primary, secondary=(item.primary,)) for item in items
            )
    else:
        items = (diagnostic(first.span(0, 1)), diagnostic(second.span(0, 1)))
        if kind == "secondary":
            items = tuple(
                replace(item, primary=shared_primary, secondary=(item.primary,)) for item in items
            )
    forward = DiagnosticReport(items)
    backward = DiagnosticReport(tuple(reversed(items)))
    assert render_json(forward) == render_json(backward)
    assert render_text(forward) == render_text(backward)


@pytest.mark.parametrize(
    ("root", "name", "expected"),
    [
        ("/project", "/project/src/a.tfd", "src/a.tfd"),
        ("/project", "/other/a.tfd", "../other/a.tfd"),
        ("/project", "relative/../a.tfd", "a.tfd"),
        ("C:\\project", "C:\\project\\src\\a.tfd", "src/a.tfd"),
        ("C:\\project", "D:\\a.tfd", "D:/a.tfd"),
        ("/project", "<repl>", "<repl>"),
    ],
)
def test_root_relative_filenames_are_lexical(root: str, name: str, expected: str) -> None:
    context = RenderContext(root=root)
    with patch("os.getcwd", side_effect=AssertionError("ambient cwd")):
        with patch.object(Path, "resolve", side_effect=AssertionError("filesystem lookup")):
            assert context.filename(name) == expected


@pytest.mark.parametrize("root", ["", ".", "relative", "C:relative", "\\relative"])
def test_relative_renderer_root_is_rejected(root: str) -> None:
    with pytest.raises(ValueError, match="absolute"):
        RenderContext(root=root)


def test_records_are_frozen_slotted_and_report_snapshots_are_immutable() -> None:
    item = diagnostic()
    bag = DiagnosticBag(max_per_file=0)
    bag.add(item)
    report = bag.report()
    label = item.primary
    edit = TextEdit(source().span(0, 0), "x")
    records = (
        item,
        label,
        edit,
        report,
        report.suppressed[0],
        ErrorResult(report),
        ValidResult(1),
        CONTEXT,
    )
    assert all(not hasattr(record, "__dict__") for record in records)
    with pytest.raises(FrozenInstanceError):
        item.message = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        report.diagnostics = ()  # type: ignore[misc]
    mutable_notes = ["original"]
    copy = replace(item, notes=mutable_notes)  # type: ignore[arg-type]
    mutable_notes.append("changed")
    assert copy.notes == ("original",)


@pytest.mark.parametrize("code", ["", "E1", "E0000", "e101", "E１２３", "1101", "E10\n"])
def test_invalid_diagnostic_codes_are_rejected(code: str) -> None:
    with pytest.raises(ValueError):
        diagnostic(code=code)


def test_invalid_records_limits_and_edits_are_rejected() -> None:
    with pytest.raises(ValueError):
        diagnostic(message="")
    with pytest.raises(TypeError):
        diagnostic(severity="error")  # type: ignore[arg-type]
    for limit in [-1, -100]:
        with pytest.raises(ValueError):
            DiagnosticBag(limit)
    with pytest.raises(TypeError):
        DiagnosticBag(True)
    with pytest.raises(ValueError):
        RenderContext(max_snippet_lines=1)
    with pytest.raises(ValueError):
        RenderContext(max_snippet_columns=15)
    with pytest.raises(TypeError):
        RenderContext(color="always")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Suppression(SourceId(0), "x", 1, 2)
    with pytest.raises(TypeError):
        Suppression(SourceId(0), "x", True, 0)
    with pytest.raises(ValueError):
        RawSourceSpan(SourceId(0), "x", b"x", 0, 2)
    with pytest.raises(TypeError):
        RawSourceSpan(SourceId(0), "x", bytearray(b"x"), 0, 1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        RawSourceSpan(SourceId(0), "x", b"x", False, 1)
    with pytest.raises(TypeError):
        TextEdit(RawSourceSpan(SourceId(0), "x", b"x", 0, 1), "")  # type: ignore[arg-type]
    with pytest.raises(UnicodeEncodeError):
        TextEdit(source().span(0, 1), "\ud800")


def test_rendering_and_collection_have_no_print_path(capsys: pytest.CaptureFixture[str]) -> None:
    bag = DiagnosticBag()
    bag.add(diagnostic())
    render_text(bag.report())
    render_json(bag.report())
    assert capsys.readouterr() == ("", "")
    assert render_text(DiagnosticReport()) == ""
    assert json.loads(render_json(DiagnosticReport()))["has_errors"] is False


@pytest.mark.property
@given(st.text(alphabet=st.characters(exclude_categories=["Cs"]), min_size=1, max_size=80))
def test_arbitrary_scalar_messages_roundtrip_json_and_text_is_control_safe(message: str) -> None:
    report = DiagnosticReport((diagnostic(message=message),))
    assert json.loads(render_json(report))["diagnostics"][0]["message"] == message
    rendered = render_text(report)
    assert all(ord(char) >= 32 or char == "\n" for char in rendered)
    assert "\x1b" not in rendered
