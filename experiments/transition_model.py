"""Small executable semantic probe, not a Ternfold interpreter.

Host callables stand for already checked expressions solely in this experiment.
Production execution must interpret Core instructions, never source via eval/exec.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

State = Mapping[str, int]
Expression = Callable[[State, State, int], int]
Predicate = Callable[[State, State, int], bool]


@dataclass(frozen=True)
class Equation:
    name: str
    dependencies: tuple[str, ...]
    expression: Expression


@dataclass(frozen=True)
class Decision:
    accepted: bool
    state: State
    emissions: tuple[int, ...]
    error: str | None


def schedule(equations: tuple[Equation, ...]) -> tuple[Equation, ...]:
    pending = {eq.name: eq for eq in equations}
    if len(pending) != len(equations):
        raise ValueError("duplicate writer")
    known = set(pending)
    if any(set(eq.dependencies) - known for eq in equations):
        raise ValueError("unknown proposed-state dependency")
    done: set[str] = set()
    ordered: list[Equation] = []
    while pending:
        ready = sorted(name for name, eq in pending.items() if set(eq.dependencies) <= done)
        if not ready:
            raise ValueError("proposed-state cycle")
        name = ready[0]
        ordered.append(pending.pop(name))
        done.add(name)
    return tuple(ordered)


def transition(
    old: State,
    item: int,
    equations: tuple[Equation, ...],
    guards: tuple[tuple[Predicate, str], ...],
    emissions: tuple[Expression, ...],
) -> Decision:
    snapshot = MappingProxyType(dict(old))
    proposed: dict[str, int] = {}
    for eq in schedule(equations):
        proposed[eq.name] = eq.expression(snapshot, MappingProxyType(proposed), item)
    candidate = MappingProxyType(proposed)
    for predicate, error in guards:
        if not predicate(snapshot, candidate, item):
            return Decision(False, snapshot, (), error)
    output = tuple(expr(snapshot, candidate, item) for expr in emissions)
    return Decision(True, candidate, output, None)
