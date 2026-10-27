import pytest
from hypothesis import given
from hypothesis import strategies as st

from experiments.transition_model import Equation, schedule, transition


def test_swap_uses_snapshot() -> None:
    equations = (
        Equation("a", (), lambda old, new, x: old["b"]),
        Equation("b", (), lambda old, new, x: old["a"]),
    )
    assert dict(transition({"a": 2, "b": 9}, 0, equations, (), ()).state) == {"a": 9, "b": 2}


def test_proposal_dependency_overrides_declaration_order() -> None:
    equations = (
        Equation("b", ("a",), lambda old, new, x: new["a"] * 2),
        Equation("a", (), lambda old, new, x: old["a"] + x),
    )
    assert [e.name for e in schedule(equations)] == ["a", "b"]
    assert transition({"a": 3, "b": 0}, 4, equations, (), ()).state["b"] == 14


def test_cycle_even_if_expression_would_not_read_it() -> None:
    equations = (Equation("a", ("a",), lambda old, new, x: 1),)
    with pytest.raises(ValueError, match="cycle"):
        schedule(equations)


def test_duplicate_writer() -> None:
    eq = Equation("a", (), lambda old, new, x: x)
    with pytest.raises(ValueError, match="duplicate"):
        schedule((eq, eq))


def test_unknown_dependency() -> None:
    with pytest.raises(ValueError, match="unknown"):
        schedule((Equation("a", ("b",), lambda old, new, x: x),))


def test_rejection_suppresses_later_guards_and_emissions() -> None:
    def forbidden(old: object, new: object, x: int) -> bool:
        raise AssertionError("evaluated after rejection")

    result = transition(
        {"a": 8},
        -9,
        (Equation("a", (), lambda old, new, x: old["a"] + x),),
        ((lambda old, new, x: new["a"] >= 0, "negative"), (forbidden, "later")),
        (lambda old, new, x: 1 // 0,),
    )
    assert result.error == "negative"
    assert dict(result.state) == {"a": 8}
    assert result.emissions == ()


@pytest.mark.property
@given(st.integers(min_value=0, max_value=10000), st.integers(min_value=-10000, max_value=10000))
def test_transition_property(old_value: int, delta: int) -> None:
    original = {"value": old_value}
    result = transition(
        original,
        delta,
        (Equation("value", (), lambda old, new, x: old["value"] + x),),
        ((lambda old, new, x: new["value"] >= 0, "negative"),),
        (lambda old, new, x: new["value"],),
    )
    assert original == {"value": old_value}
    if old_value + delta < 0:
        assert dict(result.state) == original and not result.accepted
        assert result.emissions == ()
    else:
        assert result.state["value"] == old_value + delta
        assert result.emissions == (old_value + delta,)
