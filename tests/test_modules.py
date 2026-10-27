"""M05 explicit local imports, identities, snapshots and real link containment."""

import json
import os
import shutil
import subprocess
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest

from ternfold.analysis.modules import ModuleGraph, load_modules, valid_import_path
from ternfold.analysis.resolve import SymbolKind
from ternfold.driver import resolve_source as check
from ternfold.frontend.diagnostics import ErrorResult, RawSourceSpan, ValidResult
from ternfold.frontend.source import SourceLoadResult, SourceManager, SourceSpan


def write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def graph(root: Path, *, cap: int = 100) -> ModuleGraph:
    result = load_modules(root / "entry.tfd", root, SourceManager().load_path, max_diagnostics=cap)
    assert isinstance(result, ValidResult), result.diagnostics
    return result.value


@pytest.mark.parametrize(
    "spelling",
    [
        "",
        "/a.tfd",
        "//server/a.tfd",
        "C:foo.tfd",
        "C:/foo.tfd",
        "c:\\foo.tfd",
        "a\\b.tfd",
        "a/../b.tfd",
        "../b.tfd",
        "a/../../b.tfd",
        "https://host/a.tfd",
        "file:a.tfd",
        "a\0.tfd",
        "a.txt",
        "a.TFD",
        "a.tfd/",
        "..",
    ],
)
def test_decoded_import_spelling_rejected_before_normalization(
    tmp_path: Path, spelling: str
) -> None:
    assert not valid_import_path(spelling)
    entry = write(tmp_path, "entry.tfd", f"import {json.dumps(spelling)} as lib;")
    # JSON's NUL escape is not Ternfold syntax; spell the supported Unicode escape.
    if "\0" in spelling:
        entry.write_text('import "a\\u{0}.tfd" as lib;', encoding="utf-8")
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E204"]
    assert isinstance(result.diagnostics.diagnostics[0].primary.span, SourceSpan)


@pytest.mark.parametrize(
    "spelling", ["lib.tfd", "./lib.tfd", "sub//lib.tfd", "space & (literal)/x.tfd"]
)
def test_valid_relative_spelling_and_literal_shell_characters(
    tmp_path: Path, spelling: str
) -> None:
    assert valid_import_path(spelling)
    write(tmp_path, spelling, "pub fn f()->Int{1}")
    entry = write(tmp_path, "entry.tfd", f'import "{spelling}" as lib; fn f()->Int{{lib::f()}}')
    assert isinstance(check(entry), ValidResult)


def test_diamond_aliases_have_one_snapshot_hash_and_nominal_identity(tmp_path: Path) -> None:
    write(tmp_path, "shared.tfd", "pub record R{x:Int}")
    write(tmp_path, "a.tfd", 'import "shared.tfd" as shared; pub fn a(x:shared::R)->shared::R{x}')
    write(tmp_path, "b.tfd", 'import "./shared.tfd" as shared; pub fn b(x:shared::R)->shared::R{x}')
    entry = write(
        tmp_path,
        "entry.tfd",
        """
        import "a.tfd" as a; import "b.tfd" as b;
        import "shared.tfd" as one; import "./shared.tfd" as two;
        fn f()->one::R{two::R(x:1)}
    """,
    )
    calls: Counter[Path] = Counter()
    manager = SourceManager()

    def load(path: Path) -> SourceLoadResult:
        calls[path] += 1
        return manager.load_path(path)

    loaded = load_modules(entry, tmp_path, load)
    assert isinstance(loaded, ValidResult)
    assert {p.name: n for p, n in calls.items()} == {
        "entry.tfd": 1,
        "shared.tfd": 1,
        "a.tfd": 1,
        "b.tfd": 1,
    }
    assert [m.module_id.path for m in loaded.value.modules] == [
        "shared.tfd",
        "a.tfd",
        "b.tfd",
        "entry.tfd",
    ]
    shared = loaded.value.modules[0]
    assert shared.content_hash == sha256(shared.source.original_bytes).hexdigest()
    result = check(entry)
    assert isinstance(result, ValidResult)
    references = [
        r
        for r in result.value.references.values()
        if r.type_id is not None and r.type_id.module.path == "shared.tfd"
    ]
    assert len(references) == 6
    assert len({r.type_id for r in references}) == 1


def test_snapshot_isolation_even_when_disk_changes_mid_load(tmp_path: Path) -> None:
    original = b"pub record R{x:Int}"
    shared_path = tmp_path / "shared.tfd"
    shared_path.write_bytes(original)
    entry = write(tmp_path, "entry.tfd", 'import "shared.tfd" as a;import "./shared.tfd" as b;')
    calls: Counter[Path] = Counter()
    manager = SourceManager()

    def load(path: Path) -> SourceLoadResult:
        calls[path] += 1
        loaded = manager.load_path(path)
        if path == shared_path:
            shared_path.write_bytes(b"invalid changed bytes")
        return loaded

    loaded = load_modules(entry, tmp_path, load)
    assert isinstance(loaded, ValidResult)
    shared = loaded.value.modules[0]
    assert calls[shared_path] == 1
    assert shared.source.original_bytes == original
    assert shared.content_hash == sha256(original).hexdigest()
    assert isinstance(check(entry), ErrorResult)  # a fresh session sees the edit


@pytest.mark.parametrize(
    "imports",
    [
        'import "a.tfd" as x; import "a.tfd" as x;',
        'import "a.tfd" as x; fn x()->Int{1}',
        'import "a.tfd" as x; enum x{V}',
        'import "a.tfd" as x; record x{}',
    ],
)
def test_import_alias_reserves_both_local_namespaces(tmp_path: Path, imports: str) -> None:
    write(tmp_path, "a.tfd", "pub record R{}")
    result = check(write(tmp_path, "entry.tfd", imports))
    assert isinstance(result, ErrorResult)
    diagnostic = result.diagnostics.diagnostics[0]
    assert diagnostic.code == "E202"
    assert len(diagnostic.secondary) == 1


@pytest.mark.parametrize("alias", ["Int", "Char", "len", "step"])
def test_import_alias_respects_both_prelude_namespaces(tmp_path: Path, alias: str) -> None:
    write(tmp_path, "a.tfd", "")
    result = check(write(tmp_path, "entry.tfd", f'import "a.tfd" as {alias};'))
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E201"]


@pytest.mark.parametrize("use", ["a::f()", "a::R()", "a::E::V", "a::M()", "a::other::R()"])
def test_private_names_and_import_aliases_are_not_exports(tmp_path: Path, use: str) -> None:
    write(tmp_path, "other.tfd", "pub record R{}")
    write(
        tmp_path,
        "a.tfd",
        """
        import "other.tfd" as other;
        fn f()->Int{0} record R{} enum E{V}
        machine M(x:Int)yields Int rejects Text{state c:Int=0;next c=x;}
    """,
    )
    result = check(write(tmp_path, "entry.tfd", f'import "a.tfd" as a;fn f()->Int{{{use}}}'))
    assert isinstance(result, ErrorResult)
    diagnostic = result.diagnostics.diagnostics[0]
    assert diagnostic.code == "E206"
    assert len(diagnostic.secondary) == 1
    assert diagnostic.primary.span.source_id != diagnostic.secondary[0].span.source_id


def test_public_members_local_types_and_same_spelling_distinct_nominal_ids(tmp_path: Path) -> None:
    for name in ("one", "two"):
        write(
            tmp_path,
            f"{name}.tfd",
            """
            pub record R{x:Int} pub enum E{V(R)}
            pub machine M(x:Int)yields Int rejects Text{state c:Int=0;next c=x;}
            record Private{} fn hidden(x:Private)->Private{x}
        """,
        )
    entry = write(
        tmp_path,
        "entry.tfd",
        """
        import "one.tfd" as a;import "two.tfd" as b;
        fn f(x:a::R)->b::R{let _=a::E::V(x);let _=a::M();b::R(x:1)}
        fn cell(m:a::M)->Int{m.c}
    """,
    )
    result = check(entry)
    assert isinstance(result, ValidResult), result.diagnostics
    records = [
        s for s in result.value.symbols.values() if s.kind is SymbolKind.RECORD and s.name == "R"
    ]
    assert len({s.type_id for s in records}) == 2
    assert all(s.type_id is not None and s.type_id.declaration_index == 0 for s in records)
    assert all(len(member.candidates) == 2 for member in result.value.member_references.values())


@pytest.mark.parametrize("chain", [("entry",), ("entry", "a"), ("entry", "a", "b")])
def test_import_cycles_have_chain_and_every_origin_span(
    tmp_path: Path, chain: tuple[str, ...]
) -> None:
    for index, name in enumerate(chain):
        target = chain[(index + 1) % len(chain)]
        write(tmp_path, name + ".tfd", f'import "{target}.tfd" as lib;')
    result = check(tmp_path / "entry.tfd")
    assert isinstance(result, ErrorResult)
    diagnostic = result.diagnostics.diagnostics[0]
    assert diagnostic.code == "E205"
    expected = " -> ".join(name + ".tfd" for name in chain + (chain[0],))
    assert expected in diagnostic.message and expected in diagnostic.notes
    labels = (diagnostic.primary,) + diagnostic.secondary
    assert len(labels) == len(chain)
    assert len({label.span.source_id for label in labels}) == len(chain)


@pytest.mark.parametrize(
    ("data", "code"), [(b"\xff", "E001"), (b"@", "E101"), (b"fn f()->Int{}", "E110")]
)
def test_invalid_import_source_never_hands_recovery_to_resolution(
    tmp_path: Path, data: bytes, code: str
) -> None:
    (tmp_path / "bad.tfd").write_bytes(data)
    entry = write(tmp_path, "entry.tfd", 'import "bad.tfd" as a;fn f()->Missing{unknown}')
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == [code]
    if code == "E001":
        assert isinstance(result.diagnostics.diagnostics[0].primary.span, RawSourceSpan)


def test_imported_main_is_not_parsed_as_entry_and_unused_imports_are_checked(
    tmp_path: Path,
) -> None:
    write(tmp_path, "a.tfd", "pub fn main()->List[Text]{input x:Text;[x]}")
    entry = write(tmp_path, "entry.tfd", 'import "a.tfd" as unused;fn f()->Int{0}')
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert "E208" in [d.code for d in result.diagnostics.diagnostics]
    write(tmp_path, "a.tfd", "fn unreachable()->Int{unknown}")
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E203"]


def test_missing_import_is_source_error_but_missing_entry_is_host_failure(tmp_path: Path) -> None:
    entry = write(tmp_path, "entry.tfd", 'import "missing.tfd" as missing;')
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert result.diagnostics.diagnostics[0].code == "E204"
    with pytest.raises(OSError):
        check(tmp_path / "missing.tfd")
    with pytest.raises(ValueError, match="source root"):
        check(entry, root=tmp_path / "not-root")


@pytest.mark.parametrize("count", [99, 100, 101, 150])
@pytest.mark.parametrize("cycle", [False, True])
@pytest.mark.parametrize("cap", [0, 2, 100])
def test_import_diagnostics_are_bounded_without_hiding_failure(
    tmp_path: Path,
    count: int,
    cycle: bool,
    cap: int,
) -> None:
    imports = "".join(
        f'import "{"entry.tfd" if cycle else "../outside.tfd"}" as a{i};' for i in range(count)
    )
    entry = write(tmp_path, "entry.tfd", imports)
    result = load_modules(entry, tmp_path, SourceManager().load_path, max_diagnostics=cap)
    assert isinstance(result, ErrorResult)
    assert len(result.diagnostics.diagnostics) == min(count, cap)
    assert all(d.code == ("E205" if cycle else "E204") for d in result.diagnostics.diagnostics)
    if count > cap:
        assert len(result.diagnostics.suppressed) == 1
        assert result.diagnostics.suppressed[0].count == count - cap
        assert result.diagnostics.suppressed[0].error_count == count - cap
    else:
        assert result.diagnostics.suppressed == ()


def test_multiple_files_and_frontend_suppression_reports_are_preserved(tmp_path: Path) -> None:
    entry = write(
        tmp_path,
        "entry.tfd",
        'import "bad.tfd" as b;import "a.tfd" as a;'
        + "".join(f'import "../x.tfd" as x{i};' for i in range(4)),
    )
    write(tmp_path, "bad.tfd", "@ @ @ @")
    write(tmp_path, "a.tfd", "".join(f'import "../x.tfd" as x{i};' for i in range(5)))
    result = load_modules(entry, tmp_path, SourceManager().load_path, max_diagnostics=2)
    assert isinstance(result, ErrorResult)
    assert Counter(d.code for d in result.diagnostics.diagnostics) == {"E204": 4, "E101": 2}
    assert len(result.diagnostics.suppressed) == 3
    assert len({s.source_id for s in result.diagnostics.suppressed}) == 3
    assert sorted(s.error_count for s in result.diagnostics.suppressed) == [2, 2, 3]


@pytest.mark.parametrize(
    ("data", "code"), [(b"\xff", "E001"), (b"\xef\xbb\xbf", "E002"), (b"\r", "E003")]
)
@pytest.mark.parametrize("cap", [0, 100])
def test_raw_import_source_errors_obey_cap(
    tmp_path: Path, data: bytes, code: str, cap: int
) -> None:
    entry = write(tmp_path, "entry.tfd", 'import "bad.tfd" as bad;')
    (tmp_path / "bad.tfd").write_bytes(data)
    result = load_modules(entry, tmp_path, SourceManager().load_path, max_diagnostics=cap)
    assert isinstance(result, ErrorResult)
    if cap == 0:
        assert result.diagnostics.diagnostics == ()
        assert len(result.diagnostics.suppressed) == 1
        assert result.diagnostics.suppressed[0].error_count == 1
    else:
        diagnostic = result.diagnostics.diagnostics[0]
        assert diagnostic.code == code
        assert isinstance(diagnostic.primary.span, RawSourceSpan)
        assert diagnostic.primary.span.original_bytes == data
        assert diagnostic.primary.span.start_byte == 0
        assert diagnostic.primary.span.end_byte == len(data)


def directory_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        assert powershell is not None, "real junction coverage requires PowerShell on Windows"
        script = (
            "$ErrorActionPreference='Stop';"
            "New-Item -ItemType Junction -Path $env:TERNFOLD_LINK "
            "-Target $env:TERNFOLD_TARGET | Out-Null"
        )
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
            env={**os.environ, "TERNFOLD_LINK": str(link), "TERNFOLD_TARGET": str(target)},
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
    else:
        link.symlink_to(target, target_is_directory=True)
    assert link.resolve() == target.resolve()


def remove_directory_link(link: Path) -> None:
    # Never recurse through a junction; only unlink the link itself.
    if os.name == "nt":
        link.rmdir()
    else:
        link.unlink()


def test_real_directory_link_escape_and_entry_containment(tmp_path: Path) -> None:
    root = tmp_path / "root & (space)"
    root.mkdir()
    outside = tmp_path / "outside & (space)"
    outside.mkdir()
    write(outside, "library.tfd", "pub record R{}")
    link = root / "alias & (literal)"
    directory_link(link, outside)
    try:
        entry = write(root, "entry.tfd", 'import "alias & (literal)/library.tfd" as a;')
        result = check(entry, root=root)
        assert isinstance(result, ErrorResult)
        assert [d.code for d in result.diagnostics.diagnostics] == ["E204"]
        with pytest.raises(ValueError, match="source root"):
            check(link / "library.tfd", root=root)
    finally:
        remove_directory_link(link)
    assert (outside / "library.tfd").read_text(encoding="utf-8") == "pub record R{}"


def test_real_directory_link_import_alias_and_entry_alias_dedup(tmp_path: Path) -> None:
    target = tmp_path / "real & (space)"
    target.mkdir()
    write(target, "library.tfd", "pub record R{}")
    entry = write(
        tmp_path,
        "entry.tfd",
        'import "real & (space)/library.tfd" as a;'
        'import "alias & (space)/library.tfd" as b;fn f()->a::R{b::R()}',
    )
    link = tmp_path / "alias & (space)"
    directory_link(link, target)
    try:
        calls: Counter[Path] = Counter()
        manager = SourceManager()

        def load(path: Path) -> SourceLoadResult:
            calls[path] += 1
            return manager.load_path(path)

        loaded = load_modules(entry, tmp_path, load)
        assert isinstance(loaded, ValidResult)
        assert len(loaded.value.modules) == 2
        assert calls[target / "library.tfd"] == 1
        assert isinstance(check(entry), ValidResult)
        alias_entry = check(link / "library.tfd", root=tmp_path)
        direct_entry = check(target / "library.tfd", root=tmp_path)
        assert isinstance(alias_entry, ValidResult) and isinstance(direct_entry, ValidResult)
        assert alias_entry.value.graph.entry == direct_entry.value.graph.entry
        assert tuple(alias_entry.value.symbols) == tuple(direct_entry.value.symbols)
    finally:
        remove_directory_link(link)


def test_long_import_chain_does_not_recurse_on_host_stack(tmp_path: Path) -> None:
    depth = 1050
    for index in range(depth):
        write(
            tmp_path,
            f"m{index}.tfd",
            f'import "m{index + 1}.tfd" as a;' if index + 1 < depth else "",
        )
    write(tmp_path, "entry.tfd", 'import "m0.tfd" as a;')
    assert len(graph(tmp_path).modules) == depth + 1
