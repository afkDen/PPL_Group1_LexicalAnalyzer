"""M01 source contract: bytes, scalar coordinates, errors and snapshot lifetime."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from ternfold.frontend import (
    SourceError,
    SourceFile,
    SourceId,
    SourceLoadResult,
    SourceLocation,
    SourceManager,
    SourceSpan,
    SourceValidationError,
)


def snapshot(data: bytes) -> SourceFile:
    return SourceFile(SourceId(0), "<test>", data)


def test_original_bytes_scalar_map_and_no_unicode_normalization() -> None:
    text = "a\u00e9\U0001f642e\u0301\r\n\t\x00\ufeff"
    data = text.encode("utf-8")
    source = snapshot(data)
    assert source.original_bytes is data
    assert source.text == text
    assert source.scalar_byte_offsets == (0, 1, 3, 7, 8, 10, 11, 12, 13, 14, 17)
    assert source.line_starts == (0, 12)
    assert source.span(1, 7).text == "\u00e9\U0001f642"
    assert source.span(1, 7).original_bytes == data[1:7]


@pytest.mark.parametrize("data", [b"", b"ascii", b"\n", b"\r\n", b"a\n\r\nb\n"])
def test_empty_and_eof(data: bytes) -> None:
    source = snapshot(data)
    eof = source.span(len(data), len(data))
    assert eof.original_bytes == b""
    assert eof.text == ""
    assert eof.start == eof.end == source.location(len(data))
    assert source.byte_offset(eof.end.line, eof.end.column) == len(data)
    assert source.byte_offset_for_scalar(len(source.text)) == len(data)
    assert source.line_starts[0] == 0
    if not data:
        assert (eof.start.line, eof.start.column) == (1, 1)
        assert source.scalar_byte_offsets == (0,)
        assert source.line_starts == (0,)


def test_crlf_positions_are_exact_and_only_lf_advances_line() -> None:
    source = snapshot("\u00e9\r\n\tX\n".encode())
    expected = [(0, 1, 1), (2, 1, 2), (3, 1, 3), (4, 2, 1), (5, 2, 2), (6, 2, 3), (7, 3, 1)]
    assert source.line_starts == (0, 4, 7)
    for byte, line, column in expected:
        location = source.location(byte)
        assert (location.byte_offset, location.line, location.column) == (byte, line, column)
        assert location.source_id is source.source_id
        assert source.byte_offset(line, column) == byte
    assert source.span(2, 4).text == "\r\n"
    assert source.span(3, 4).text == "\n"
    with pytest.raises(ValueError, match="column"):
        source.byte_offset(1, 4)


@pytest.mark.parametrize(
    ("text", "displays"),
    [
        ("\t\tX", [1, 5, 9, 10]),
        ("a\tb\t", [1, 2, 5, 6, 9]),
        ("abcd\t", [1, 2, 3, 4, 5, 9]),
        ("\u00e9\U0001f642\tZ", [1, 2, 3, 5, 6]),
        ("\t\r\n\t", [1, 5, 6, 1, 5]),
        ("e\u0301\t", [1, 2, 3, 5]),
    ],
)
def test_tab_display_is_separate_from_scalar_columns(text: str, displays: list[int]) -> None:
    source = snapshot(text.encode())
    assert [source.display_column(byte) for byte in source.scalar_byte_offsets] == displays
    for byte in source.scalar_byte_offsets:
        location = source.location(byte)
        line_prefix = source.original_bytes[source.line_starts[location.line - 1] : byte].decode()
        assert location.column == len(line_prefix) + 1


def test_nul_escape_remains_source_spelling_and_raw_controls_belong_to_lexer() -> None:
    data = b'"\\u{0}" "\\n" \'\\u{0}\'\x00\x7f'
    source = snapshot(data)
    assert source.text == data.decode("utf-8")
    assert source.span(1, 6).text == "\\u{0}"
    assert source.text[-2:] == "\x00\x7f"


@pytest.mark.parametrize(
    ("data", "code", "start", "end"),
    [
        (b"\xff", "E001", 0, 1),
        (b"a\xc3", "E001", 1, 2),
        (b"\xc0\x80", "E001", 0, 1),
        (b"\x80", "E001", 0, 1),
        (b"\xed\xa0\x80", "E001", 0, 1),
        (b"\xf4\x90\x80\x80", "E001", 0, 1),
        (b"\xef\xbb\xbf", "E002", 0, 3),
        (b"\xef\xbb\xbfa", "E002", 0, 3),
        (b"\r", "E003", 0, 1),
        (b"x\ry", "E003", 1, 2),
        ("\u00e9\r".encode(), "E003", 2, 3),
        (b"a\r\n\r\r\n", "E003", 3, 4),
    ],
)
def test_source_errors_are_data_with_exact_original_byte_ranges(
    data: bytes, code: str, start: int, end: int, capsys: pytest.CaptureFixture[str]
) -> None:
    result = SourceManager().add_bytes("bad.tfd", data)
    assert result.source is None
    assert len(result.errors) == 1
    error = result.errors[0]
    assert (error.code, error.start_byte, error.end_byte) == (code, start, end)
    assert error.original_bytes is data
    assert error.display_name == "bad.tfd"
    assert error.message
    with pytest.raises(SourceValidationError) as raised:
        SourceFile(error.source_id, "bad.tfd", data)
    assert raised.value.error == error
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"\xef\xbb\xbf\xff\r", "E001"),
        (b"\xef\xbb\xbf\r", "E002"),
        (b"\r\xff", "E001"),
    ],
)
def test_validation_order_is_deterministic(data: bytes, code: str) -> None:
    result = SourceManager().add_bytes("errors", data)
    assert result.errors[0].code == code


@pytest.mark.parametrize(("start", "end"), [(-1, 0), (0, 4), (3, 2), (1, 2), (0, 1)])
def test_span_creation_rejects_bounds_order_and_multibyte_interiors(start: int, end: int) -> None:
    source = snapshot("\u00e9x".encode())
    with pytest.raises(ValueError):
        SourceSpan(source, start, end)


@pytest.mark.parametrize("offset", [-1, 1, 4])
def test_locations_and_display_reject_invalid_byte_offsets(offset: int) -> None:
    source = snapshot("\u00e9x".encode())
    with pytest.raises(ValueError):
        SourceLocation(source, offset)
    with pytest.raises(ValueError):
        source.scalar_index(offset)
    with pytest.raises(ValueError):
        source.display_column(offset)


@pytest.mark.parametrize(("line", "column"), [(0, 1), (-1, 1), (3, 1), (1, 0), (1, 4), (2, 2)])
def test_coordinate_inverse_rejects_nonexistent_positions(line: int, column: int) -> None:
    with pytest.raises(ValueError):
        snapshot(b"a\n").byte_offset(line, column)


@pytest.mark.parametrize("index", [-1, 3])
def test_scalar_inverse_rejects_nonexistent_indices(index: int) -> None:
    with pytest.raises(ValueError):
        snapshot("\U0001f642x".encode()).byte_offset_for_scalar(index)


def test_invalid_argument_types_are_not_truncated_or_treated_as_offsets() -> None:
    source = snapshot(b"abc")
    with pytest.raises(TypeError):
        source.span(True, 2)
    with pytest.raises(TypeError):
        source.scalar_index(1.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        source.byte_offset(1, False)
    with pytest.raises(TypeError):
        source.byte_offset_for_scalar(1.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        snapshot(bytearray(b"mutable"))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        SourceId(-1)
    with pytest.raises(TypeError):
        SourceId(True)


def test_spans_join_covering_range_regardless_of_order_overlap_or_eof() -> None:
    source = snapshot(b"abc\ndef")
    first, second, eof = source.span(0, 1), source.span(4, 7), source.span(7, 7)
    assert first.source_id is source.source_id
    assert first.join(second) == second.join(first) == source.span(0, 7)
    assert first.join(first) == first
    assert second.join(eof) == second
    assert source.span(0, 5).join(source.span(3, 6)) == source.span(0, 6)
    with pytest.raises(ValueError, match="different source"):
        first.join(snapshot(b"abc\ndef").span(0, 1))
    # Even accidental reuse of an ID cannot join distinct snapshots.
    duplicate = SourceFile(source.source_id, source.display_name, source.original_bytes)
    with pytest.raises(ValueError, match="different source"):
        first.join(duplicate.span(0, 1))
    with pytest.raises(ValueError):
        replace(first, end_byte=100)


def test_source_records_are_frozen_and_slotted() -> None:
    source = snapshot(b"x")
    source_id = source.source_id
    span = source.span(0, 1)
    location = source.location(0)
    assert not any(hasattr(record, "__dict__") for record in (source_id, source, span, location))
    with pytest.raises(FrozenInstanceError):
        source_id.value = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        source.original_bytes = b"y"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        span.end_byte = 0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        location.column = 2  # type: ignore[misc]


def test_manager_byte_loads_always_get_fresh_identity_even_across_managers() -> None:
    manager = SourceManager()
    first = manager.add_bytes("same", b"a")
    second = manager.add_bytes("same", b"b")
    third = SourceManager().add_bytes("same", b"a")
    assert first.source is not None and second.source is not None and third.source is not None
    assert first.source.source_id.value == third.source.source_id.value == 0
    assert second.source.source_id.value == 1
    assert first.source.source_id != second.source.source_id
    assert first.source.source_id != third.source.source_id
    assert first.source.text == "a"
    assert not first.errors and not second.errors and not third.errors


def test_manager_caches_canonical_path_without_reading_again(tmp_path: Path) -> None:
    path = tmp_path / "spaces & symbols.source"
    path.write_bytes(b"old\r\n")
    manager = SourceManager()
    result = manager.load_path(path)
    assert result.source is not None
    source = result.source
    retained_span = source.span(0, 3)
    assert source.display_name == str(path.resolve())
    path.write_bytes(b"new")
    with patch.object(Path, "read_bytes", side_effect=AssertionError("reread")):
        assert manager.load_path(tmp_path / "." / path.name) is result
        assert manager.load_path(str(path.resolve())) is result
    assert retained_span.text == "old"
    assert source.original_bytes == b"old\r\n"
    fresh = SourceManager().load_path(path)
    assert fresh.source is not None and fresh.source.text == "new"
    path.unlink()
    assert manager.load_path(path) is result


def test_manager_caches_rejected_snapshot_and_does_not_apply_extension_policy(
    tmp_path: Path,
) -> None:
    path = tmp_path / "not-tfd.txt"
    path.write_bytes(b"\xff")
    manager = SourceManager()
    result = manager.load_path(path)
    path.write_bytes(b"fixed")
    assert manager.load_path(path) is result
    assert result.errors[0].original_bytes == b"\xff"
    fresh = SourceManager().load_path(path)
    assert fresh.source is not None and fresh.source.text == "fixed"


def test_manager_resolves_aliases_to_canonical_path(tmp_path: Path) -> None:
    path = tmp_path / "file.tfd"
    path.write_bytes(b"same")
    manager = SourceManager()
    with patch.object(Path, "resolve", return_value=path):
        assert manager.load_path("alias.tfd") is manager.load_path(path)


def test_manager_filesystem_error_is_left_to_driver(tmp_path: Path) -> None:
    manager = SourceManager()
    path = tmp_path / "absent.tfd"
    with pytest.raises(FileNotFoundError):
        manager.load_path(path)
    path.write_bytes(b"now present")
    assert manager.load_path(path).source is not None


def test_load_result_cannot_claim_both_success_and_failure_or_neither() -> None:
    with pytest.raises(ValueError):
        SourceLoadResult(None, ())
    source = snapshot(b"x")
    error = SourceError("E003", "CR", source.source_id, "bad", b"\r", 0, 1)
    with pytest.raises(ValueError):
        SourceLoadResult(source, (error,))


# Unicode scalar strings, explicit LF/CRLF atoms, and no initial BOM. Raw NUL
# is valid at this phase: literal escape/control validation belongs to M03.
scalar = st.characters(exclude_categories=["Cs"], exclude_characters="\r\n\ufeff")
source_text = st.lists(st.one_of(scalar, st.sampled_from(["\n", "\r\n", "\t"])), max_size=80).map(
    "".join
)


@pytest.mark.property
@settings(max_examples=150)
@given(source_text)
@example("")
@example("\r\n\r\n")
@example("\u00e9\U0001f642\r\n\t\x00e\u0301\n")
@example("\ud7ff\ue000\U0010ffff\u0085\u2028\u2029")
def test_scalar_byte_and_line_column_roundtrips(text: str) -> None:
    source = snapshot(text.encode("utf-8"))
    expected_byte = 0
    line, column, display = 1, 1, 1
    for scalar_index, char in enumerate(text + "\0"):
        # The extra sentinel visits EOF without adding it to the snapshot.
        location = source.location(expected_byte)
        assert (location.line, location.column) == (line, column)
        assert source.display_column(expected_byte) == display
        assert source.scalar_index(expected_byte) == scalar_index
        assert source.byte_offset_for_scalar(scalar_index) == expected_byte
        assert source.byte_offset(line, column) == expected_byte
        assert source.span(expected_byte, expected_byte).start == location
        if scalar_index == len(text):
            break
        next_byte = expected_byte + len(char.encode("utf-8"))
        assert source.span(expected_byte, next_byte).text == char
        for interior in range(expected_byte + 1, next_byte):
            with pytest.raises(ValueError):
                source.location(interior)
        expected_byte = next_byte
        if char == "\n":
            line, column, display = line + 1, 1, 1
        else:
            column += 1
            display += 4 - (display - 1) % 4 if char == "\t" else 1
    assert expected_byte == len(source.original_bytes)


@pytest.mark.property
@given(source_text, st.data())
def test_generated_span_slices_and_joins(text: str, choices: st.DataObject) -> None:
    source = snapshot(text.encode())
    indices = sorted(choices.draw(st.lists(st.integers(0, len(text)), min_size=4, max_size=4)))
    a, b, c, d = indices
    offsets = source.scalar_byte_offsets
    left = source.span(offsets[a], offsets[b])
    right = source.span(offsets[c], offsets[d])
    assert left.text == text[a:b]
    assert right.text == text[c:d]
    assert left.join(right).text == text[a:d]
