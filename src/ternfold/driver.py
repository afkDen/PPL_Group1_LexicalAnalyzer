"""Filesystem capability and explicit resolution/typing phase boundaries."""

from pathlib import Path

from ternfold.analysis.check import check as check_types
from ternfold.analysis.machines import PlannedProgram, plan_machines
from ternfold.analysis.modules import load_modules
from ternfold.analysis.resolve import ResolvedProgram, resolve
from ternfold.analysis.types import TypedProgram
from ternfold.core.lower import lower
from ternfold.core.nodes import VerifiedCore
from ternfold.frontend.diagnostics import ErrorResult, Result
from ternfold.frontend.source import SourceManager


def resolve_source(entry: str | Path, *, root: str | Path | None = None) -> Result[ResolvedProgram]:
    """Resolve a library or root module, without requiring main.

    Each call owns a fresh source session. Host configuration/entry IO failures
    raise OSError/ValueError. Import failures are structured source diagnostics.
    Success does not establish type correctness, machine validity or executability.
    """
    requested = Path(entry)
    if requested.suffix != ".tfd":
        raise ValueError("source input must have the .tfd extension")
    path = requested.resolve()
    source_root = Path(root).resolve() if root is not None else path.parent
    graph = load_modules(path, source_root, SourceManager().load_path)
    if isinstance(graph, ErrorResult):
        return graph
    return resolve(graph.value)


def type_source(entry: str | Path, *, root: str | Path | None = None) -> Result[TypedProgram]:
    """Resolve and type-check a library; machine planning/execution remain deferred."""
    resolved = resolve_source(entry, root=root)
    if isinstance(resolved, ErrorResult):
        return resolved
    return check_types(resolved.value)


def check(entry: str | Path, *, root: str | Path | None = None) -> Result[PlannedProgram]:
    """Validate the complete frontend and plan machines, without executing."""
    typed = type_source(entry, root=root)
    if isinstance(typed, ErrorResult):
        return typed
    return plan_machines(typed.value)


def compile_source(entry: str | Path, *, root: str | Path | None = None) -> Result[VerifiedCore]:
    """Lower checked source and publish only verified Core; no main required."""
    planned = check(entry, root=root)
    if isinstance(planned, ErrorResult):
        return planned
    from ternfold.frontend.diagnostics import ValidResult

    return ValidResult(lower(planned.value), planned.diagnostics)
