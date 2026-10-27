"""M09 runtime value invariants; these are not source execution evidence."""

from dataclasses import FrozenInstanceError

import pytest

from ternfold.analysis.numeric import Float64
from ternfold.analysis.types import BOOL, CHAR, FLOAT, INT, TEXT, Type, TypeKind
from ternfold.core.nodes import FunctionId
from ternfold.execution.values import Limits, Value, value_equal


@pytest.mark.parametrize(
    ("type_", "scalar"),
    [
        (INT, True),
        (BOOL, 1),
        (INT, 1 << 63),
        (INT, -(1 << 63) - 1),
        (FLOAT, 1.5),
        (FLOAT, float("inf")),
        (CHAR, "ab"),
        (CHAR, ""),
        (TEXT, "\ud800"),
    ],
)
def test_host_values_cannot_bypass_language_tags(type_: Type, scalar: object) -> None:
    with pytest.raises(ValueError):
        Value(type_, scalar)  # type: ignore[arg-type]


def test_values_are_frozen_snapshot_sequences_and_normalize_float_zero() -> None:
    children = [Value(INT, 1)]
    list_type = Type(TypeKind.LIST, (INT,))
    value = Value(list_type, items=children)  # type: ignore[arg-type]
    children.clear()
    assert value.items == (Value(INT, 1),)
    with pytest.raises(FrozenInstanceError):
        value.items = ()  # type: ignore[misc]
    assert value_equal(Value(FLOAT, Float64(1 << 63)), Value(FLOAT, Float64(0)))
    assert not value_equal(Value(INT, 1), Value(BOOL, True))


def test_structural_equality_uses_no_host_recursion_and_rejects_closures() -> None:
    # Same fixed list type and independent children exercise a deep graph without
    # recursively nested source types or recursive dataclass equality.
    vector = Type(TypeKind.LIST, (INT,))
    a = Value(vector, items=tuple(Value(INT, i) for i in range(5000)))
    b = Value(vector, items=tuple(Value(INT, i) for i in range(5000)))
    assert value_equal(a, b)
    assert not value_equal(a, Value(vector, items=b.items[:-1]))
    function = Value(Type(TypeKind.FUNCTION, (INT,)), function=FunctionId(0))
    with pytest.raises(ValueError, match="functions"):
        value_equal(function, function)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_execution_limits_reject_invalid_host_configurations(value: object) -> None:
    with pytest.raises(ValueError):
        Limits(max_steps=value)  # type: ignore[arg-type]
