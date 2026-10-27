"""Typed recursive coverage with a separately enumerated finite oracle."""

import random
import subprocess
import sys
from itertools import product
from pathlib import Path

import pytest

from ternfold.driver import type_source as check
from ternfold.frontend.diagnostics import ErrorResult, ValidResult


def codes(tmp_path: Path, text: str) -> tuple[str, ...]:
    entry = tmp_path / "patterns.tfd"
    entry.write_text(text, encoding="utf-8")
    result = check(entry)
    return tuple(d.code for d in result.diagnostics.diagnostics)


@pytest.mark.parametrize("variant_pattern", [False, True])
def test_wide_bool_payload_wildcard_coverage_is_bounded(
    tmp_path: Path,
    variant_pattern: bool,
) -> None:
    entry = tmp_path / "wide.tfd"
    pattern = "E::V(" + ",".join(["_"] * 64) + ")" if variant_pattern else "_"
    entry.write_text(
        "enum E{V(" + ",".join(["Bool"] * 64) + ")}fn f(x:E)->Int{match x{" + pattern + "=>{0}}}",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "ternfold", "check", str(entry)],
        capture_output=True,
        check=False,
        timeout=5,
    )
    assert result.returncode == 0 and result.stdout == result.stderr == b""


def test_wide_uncovered_payload_witness_remains_useful_and_type_correct(tmp_path: Path) -> None:
    entry = tmp_path / "witness.tfd"
    declaration = "enum E{V(" + ",".join(["Bool"] * 64) + "),Done}"
    entry.write_text(declaration + "fn f(x:E)->Int{match x{E::Done=>{0}}}", encoding="utf-8")
    result = check(entry)
    assert isinstance(result, ErrorResult)
    error = next(d for d in result.diagnostics.diagnostics if d.code == "E310")
    witness = error.message.split("missing ", 1)[1]
    assert witness == "E::V(" + ", ".join(["false"] * 64) + ")"
    # The concrete witness is useful, though it covers only one finite value.
    entry.write_text(
        declaration
        + "fn f(x:E)->Int{match x{E::Done=>{0},"
        + witness
        + "=>{1},E::V("
        + ",".join(["_"] * 64)
        + ")=>{2}}}",
        encoding="utf-8",
    )
    assert isinstance(check(entry), ValidResult)


@pytest.mark.parametrize("mode", ["exhaustive", "missing", "duplicate"])
def test_wide_payload_exhaustive_last_bool_split_is_bounded(tmp_path: Path, mode: str) -> None:
    entry = tmp_path / "split.tfd"
    prefix = ",".join(["_"] * 63)
    arms = f"E::V({prefix},false)=>{{0}}"
    if mode != "missing":
        arms += f",E::V({prefix},true)=>{{1}}"
    if mode == "duplicate":
        arms += f",E::V({prefix},false)=>{{2}}"
    entry.write_text(
        "enum E{V(" + ",".join(["Bool"] * 64) + ")}fn f(x:E)->Int{match x{" + arms + "}}",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "ternfold", "check", str(entry)],
        capture_output=True,
        check=False,
        timeout=5,
    )
    assert result.stdout == b""
    if mode == "exhaustive":
        assert result.returncode == 0 and result.stderr == b""
    else:
        assert result.returncode == 1
        assert (b"E310" if mode == "missing" else b"E311") in result.stderr


@pytest.mark.parametrize(
    "text",
    [
        "fn f(x:Bool)->Int{match x{true=>{1},false=>{0}}}",
        "fn f(x:Unit)->Int{match x{()=>{1}}}",
        "fn f(x:Option[Bool])->Int{match x{Option::Some(true)=>{1},"
        "Option::Some(false)=>{0},Option::None=>{2}}}",
        "enum E{A(Option[Bool]),B}fn f(x:E)->Int{match x{E::A(Option::Some(true))=>{1},"
        "E::A(Option::Some(false))=>{2},E::A(Option::None)=>{3},E::B=>{4}}}",
        "fn f(x:Int)->Int{match x{0=>{0},rest=>{rest}}}",
        'fn f(x:Text)->Int{match x{"a"=>{0},_=>{1}}}',
        "fn f(x:Char)->Int{match x{'a'=>{0},_=>{1}}}",
        "record R{x:Int}fn f(x:R)->Int{match x{whole=>{whole.x}}}",
        "fn f(x:List[Int])->Int{match x{_=>{0}}}",
        "fn f(x:fn()->Int)->Int{match x{y=>{y()}}}",
        "machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=x;}"
        "fn f(x:Decision[M,Int,Text])->Int{match x{Decision::Accept(m,items)=>{len(items)},"
        "Decision::Reject(m,why)=>{text_len(why)}}}",
    ],
)
def test_exhaustive_patterns_valid(tmp_path: Path, text: str) -> None:
    assert codes(tmp_path, text) == ()


@pytest.mark.parametrize(
    ("type_", "arms", "witness"),
    [
        ("Bool", "true=>{0}", "false"),
        ("Option[Bool]", "Option::Some(true)=>{0},Option::None=>{1}", "Option::Some(false)"),
        (
            "Option[Option[Bool]]",
            "Option::None=>{0},Option::Some(Option::None)=>{1},"
            "Option::Some(Option::Some(false))=>{2}",
            "Option::Some(Option::Some(true))",
        ),
        ("Int", "1=>{0},2=>{1}", "_"),
        ("Char", "'a'=>{0},'b'=>{1}", "_"),
        ("Text", '"a"=>{0}', "_"),
    ],
)
def test_missing_witnesses_are_nested_type_correct(
    tmp_path: Path, type_: str, arms: str, witness: str
) -> None:
    entry = tmp_path / "witness.tfd"
    entry.write_text(f"fn f(x:{type_})->Int{{match x{{{arms}}}}}", encoding="utf-8")
    result = check(entry)
    assert isinstance(result, ErrorResult)
    errors = [d for d in result.diagnostics.diagnostics if d.code == "E310"]
    assert len(errors) == 1 and errors[0].message.endswith(witness)
    # Inserting the generated residual must be useful and exhaustive.
    entry.write_text(
        f"fn f(x:{type_})->Int{{match x{{{arms},{witness}=>{{9}}}}}}", encoding="utf-8"
    )
    assert isinstance(check(entry), ValidResult)


@pytest.mark.parametrize(
    ("type_", "arms"),
    [
        ("Bool", "_=>{0},true=>{1}"),
        ("Bool", "true=>{0},false=>{1},_=>{2}"),
        ("Unit", "()=>{0},_=>{1}"),
        ("Int", "1=>{0},1=>{1},_=>{2}"),
        ("Char", "'a'=>{0},'a'=>{1},_=>{2}"),
        ("Option[Bool]", "Option::Some(_)=>{0},Option::Some(true)=>{1},Option::None=>{2}"),
    ],
)
def test_useless_arms_respect_order_and_nested_subsumption(
    tmp_path: Path, type_: str, arms: str
) -> None:
    assert "E311" in codes(tmp_path, f"fn f(x:{type_})->Int{{match x{{{arms}}}}}")


@pytest.mark.parametrize(
    "text",
    [
        "fn f(x:Bool)->Int{match x{1=>{0},_=>{1}}}",
        "fn f(x:Option[Int])->Int{match x{Option::Some(true)=>{0},_=>{1}}}",
        "enum E{A}enum F{B}fn f(x:E)->Int{match x{F::B=>{0},_=>{1}}}",
        "fn f(x:Option[Int])->Int{match x{Option::None(a)=>{a},_=>{1}}}",
        "fn f(x:Option[Int])->Int{match x{Option::Some(a,b)=>{a+b},_=>{1}}}",
        "fn f(x:Option[Int])->Int{match x{Option::Some=>{0},_=>{1}}}",
        "record R{}fn f(x:R)->Int{match x{Option::None=>{0},_=>{1}}}",
        "enum E{V(Int)}fn f(e:E)->Int{match e{E::V(x,y)=>{y}}}",
        "enum E{A}enum F{B(Int)}fn f(e:E)->Int{match e{F::B(y)=>{y},_=>{0}}}",
        "record R{}enum F{B(Int)}fn f(e:R)->Int{match e{F::B(y)=>{y},_=>{0}}}",
    ],
)
def test_invalid_pattern_type_and_arity_are_e312_without_host_exceptions(
    tmp_path: Path, text: str
) -> None:
    assert "E312" in codes(tmp_path, text)


@pytest.mark.parametrize("pattern", ["-9223372036854775808", "- 1", "-/*gap*/1"])
def test_signed_int_pattern_rules_allow_ordinary_gaps_but_minimum_is_contiguous(
    tmp_path: Path, pattern: str
) -> None:
    assert codes(tmp_path, f"fn f(x:Int)->Int{{match x{{{pattern}=>{{0}},_=>{{1}}}}}}") == ()


@pytest.mark.parametrize(
    "pattern",
    [
        "- 9223372036854775808",
        "-/*gap*/9223372036854775808",
        "9223372036854775808",
        "-9223372036854775809",
    ],
)
def test_out_of_range_pattern_literals_are_e301(tmp_path: Path, pattern: str) -> None:
    assert "E301" in codes(tmp_path, f"fn f(x:Int)->Int{{match x{{{pattern}=>{{0}},_=>{{1}}}}}}")


def test_bool_pair_matrix_against_independent_enumerated_sets(tmp_path: Path) -> None:
    # Nine pair patterns denote explicit subsets of the four concrete values.
    # This oracle does not call or reimplement specialization/usefulness.
    values = set(product((False, True), repeat=2))
    choices = list(product(("_", "false", "true"), repeat=2))
    rng = random.Random(606)
    for _ in range(80):
        sequence = rng.sample(choices, rng.randrange(1, len(choices) + 1))
        seen: set[tuple[bool, bool]] = set()
        useless = 0
        arms: list[str] = []
        for first, second in sequence:
            matched = {
                (a, b)
                for a, b in values
                if (first == "_" or a == (first == "true"))
                and (second == "_" or b == (second == "true"))
            }
            useless += not bool(matched - seen)
            seen |= matched
            arms.append(f"Pair::V({first},{second})=>{{0}}")
        observed = codes(
            tmp_path, "enum Pair{V(Bool,Bool)}fn f(x:Pair)->Int{match x{" + ",".join(arms) + "}}"
        )
        assert observed.count("E311") == useless
        assert ("E310" in observed) == (seen != values)


def test_missing_witness_uses_reachable_import_alias_and_typechecks(tmp_path: Path) -> None:
    (tmp_path / "lib.tfd").write_text("pub enum E{A,B}", encoding="utf-8")
    entry = tmp_path / "entry.tfd"
    prefix = 'import "lib.tfd" as lib;import "./lib.tfd" as other;'
    entry.write_text(prefix + "fn f(x:lib::E)->Int{match x{lib::E::A=>{1}}}", encoding="utf-8")
    result = check(entry)
    assert isinstance(result, ErrorResult)
    error = next(d for d in result.diagnostics.diagnostics if d.code == "E310")
    witness = error.message.split("missing ", 1)[1]
    assert witness == "lib::E::B"
    entry.write_text(
        prefix + f"fn f(x:lib::E)->Int{{match x{{lib::E::A=>{{1}},{witness}=>{{2}}}}}}",
        encoding="utf-8",
    )
    assert isinstance(check(entry), ValidResult)


@pytest.mark.parametrize(
    "arms",
    [
        "Option::Some(x)=>{x}",
        "Option::Some(x)=>{x},Option::Some(y)=>{y}",
    ],
)
def test_unconstrained_builtin_scrutinee_cannot_infer_from_match_arms(
    tmp_path: Path,
    arms: str,
) -> None:
    assert "E304" in codes(tmp_path, f"fn f()->Int{{match at([],0){{{arms}}}}}")


def test_contextual_builtin_scrutinee_still_checks_coverage_and_usefulness(tmp_path: Path) -> None:
    prefix = "fn source(x:Option[Int])->Option[Int]{x}"
    assert "E310" in codes(
        tmp_path, prefix + "fn f()->Int{match source(at([],0)){Option::Some(x)=>{x}}}"
    )
    observed = codes(
        tmp_path,
        prefix + "fn f()->Int{match source(at([],0)){"
        "Option::Some(x)=>{x},Option::Some(y)=>{y},Option::None=>{0}}}",
    )
    assert observed == ("E311",)
    assert "E310" in codes(
        tmp_path, "fn f()->Int{let a:Option[Int]=at([],0);match a{Option::Some(x)=>{x}}}"
    )
    assert codes(
        tmp_path,
        "fn f()->Int{let a:Option[Int]=at([],0);match a{"
        "Option::Some(x)=>{x},Option::Some(y)=>{y},Option::None=>{0}}}",
    ) == ("E311",)
