"""Root-contained local module graph over immutable, successfully parsed sources.

The driver supplies the sole source-loading capability. A graph load calls it at
most once per canonical path, including failed parses. Content hashes describe
the cached bytes, never a second filesystem read. Published modules are in
dependency order; lexical import order breaks ties. No type checker is involved.
"""

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath, PureWindowsPath

from ternfold.frontend.ast import ImportDecl, Program
from ternfold.frontend.diagnostics import (
    Diagnostic,
    DiagnosticBag,
    DiagnosticReport,
    ErrorResult,
    Label,
    Result,
    Severity,
    ValidResult,
    diagnostic_from_source_error,
)
from ternfold.frontend.lexer import lex
from ternfold.frontend.parser import parse
from ternfold.frontend.source import SourceFile, SourceLoadResult


@dataclass(frozen=True, slots=True, order=True)
class ModuleId:
    path: str


@dataclass(frozen=True, slots=True)
class ImportEdge:
    declaration: ImportDecl
    target: ModuleId


@dataclass(frozen=True, slots=True)
class Module:
    module_id: ModuleId
    source: SourceFile
    content_hash: str
    program: Program
    imports: tuple[ImportEdge, ...]


@dataclass(frozen=True, slots=True)
class ModuleGraph:
    root: Path
    entry: ModuleId
    modules: tuple[Module, ...]


def valid_import_path(spelling: str) -> bool:
    """Validate decoded source spelling *before* normalizing any components."""
    return (
        bool(spelling)
        and "\\" not in spelling
        and "\0" not in spelling
        and ":" not in spelling
        and not PurePosixPath(spelling).is_absolute()
        and not PureWindowsPath(spelling).drive
        and ".." not in spelling.split("/")
        and spelling.endswith(".tfd")
    )


def load_modules(
    entry: Path,
    root: Path,
    load_source: Callable[[Path], SourceLoadResult],
    *,
    max_diagnostics: int = 100,
) -> Result[ModuleGraph]:
    """Load a fresh compilation graph; invalid entry configuration raises ValueError.

    Entry filesystem failures propagate to the driver as host errors. Import
    filesystem/path failures are source diagnostics at the import declaration.
    Invalid lex/parse results never enter a ModuleGraph or the resolver.
    """
    root = root.resolve()
    entry = entry.resolve()
    if entry.suffix != ".tfd":
        raise ValueError("source input must have the .tfd extension")
    if not root.is_dir() or not entry.is_relative_to(root):
        raise ValueError("source input must be inside the source root")
    diagnostics = DiagnosticBag(max_diagnostics)
    reports: list[DiagnosticReport] = []
    cache: dict[Path, Module | None] = {}

    def import_error(declaration: ImportDecl, message: str) -> None:
        diagnostics.add(Diagnostic("E204", Severity.ERROR, message, Label(declaration.path_span)))

    def read(path: Path, origin: ImportDecl | None) -> Module | None:
        if path in cache:
            return cache[path]
        cache[path] = None
        try:
            loaded = load_source(path)
        except (OSError, ValueError) as error:
            if origin is None:
                raise
            import_error(origin, f"cannot load import {origin.path!r}: {error}")
            return None
        if loaded.source is None:
            for source_error in loaded.errors:
                diagnostics.add(diagnostic_from_source_error(source_error))
            return None
        source = loaded.source
        lexed = lex(source, max_diagnostics=max_diagnostics)
        tokens = lexed.for_parser()
        if isinstance(tokens, ErrorResult):
            reports.append(tokens.diagnostics)
            return None
        parsed = parse(
            tokens.value, root_module=path == entry, max_diagnostics=max_diagnostics
        ).for_resolution()
        if isinstance(parsed, ErrorResult):
            reports.append(parsed.diagnostics)
            return None
        edges: list[ImportEdge] = []
        for declaration in parsed.value.imports:
            if not valid_import_path(declaration.path):
                import_error(
                    declaration, "import must be a root-contained relative POSIX .tfd path"
                )
                continue
            try:
                target = (path.parent / declaration.path).resolve()
                if not target.is_relative_to(root):
                    import_error(declaration, "resolved import is outside the source root")
                    continue
                edges.append(ImportEdge(declaration, ModuleId(target.relative_to(root).as_posix())))
            except (OSError, ValueError) as error:
                import_error(declaration, f"cannot resolve import: {error}")
        module = Module(
            ModuleId(path.relative_to(root).as_posix()),
            source,
            sha256(source.original_bytes).hexdigest(),
            parsed.value,
            tuple(edges),
        )
        cache[path] = module
        return module

    first = read(entry, None)
    ordered: list[Module] = []
    # Iterative DFS: import-chain depth does not consume the Python call stack.
    stack: list[tuple[Module, int, ImportEdge | None]] = []
    active: dict[ModuleId, int] = {}
    finished: set[ModuleId] = set()
    if first is not None:
        stack.append((first, 0, None))
        active[first.module_id] = 0
    while stack:
        module, index, incoming = stack[-1]
        if index == len(module.imports):
            stack.pop()
            del active[module.module_id]
            finished.add(module.module_id)
            ordered.append(module)
            continue
        edge = module.imports[index]
        stack[-1] = module, index + 1, incoming
        if edge.target in active:
            start = active[edge.target]
            chain = [frame[0].module_id.path for frame in stack[start:]] + [edge.target.path]
            labels = tuple(
                Label(frame[2].declaration.path_span, "cycle import")
                for frame in stack[start + 1 :]
                if frame[2] is not None
            )
            diagnostics.add(
                Diagnostic(
                    "E205",
                    Severity.ERROR,
                    "import cycle: " + " -> ".join(chain),
                    Label(edge.declaration.path_span, "closes this cycle"),
                    labels,
                    notes=(" -> ".join(chain),),
                )
            )
        elif edge.target not in finished:
            child = read(root / edge.target.path, edge.declaration)
            if child is not None:
                active[child.module_id] = len(stack)
                stack.append((child, 0, edge))
    module_report = diagnostics.report()
    report = DiagnosticReport(
        module_report.diagnostics + tuple(d for r in reports for d in r.diagnostics),
        module_report.suppressed + tuple(s for r in reports for s in r.suppressed),
    )
    if report.has_errors:
        return ErrorResult(report)
    return ValidResult(
        ModuleGraph(root, ModuleId(entry.relative_to(root).as_posix()), tuple(ordered))
    )
