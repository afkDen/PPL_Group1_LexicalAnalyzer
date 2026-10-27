"""Human-approved entry-only boundary uses resolved function identity."""

from pathlib import Path

import pytest

from ternfold.driver import check, resolve_source
from ternfold.frontend.diagnostics import ErrorResult, ValidResult
from ternfold.frontend.source import SourceSpan


@pytest.mark.parametrize(
    "body",
    [
        "fn f()->List[Text]{main()}",
        "fn f()->fn()->List[Text]{main}",
        "fn f()->List[Text]{let a=main;a()}",
        "fn f()->List[Text]{(fn()->List[Text]{main()})()}",
        "machine M(x:Int)yields List[Text] rejects Text{state a:Int=0;next a=x;emit main();}",
    ],
)
@pytest.mark.parametrize("clause", ["input x:Text;", 'output "staged";'])
def test_io_main_references_are_e208_by_identity(tmp_path: Path, body: str, clause: str) -> None:
    entry = tmp_path / "entry.tfd"
    entry.write_text("pub fn main()->List[Text]{" + clause + "[]}" + body, encoding="utf-8")
    result = resolve_source(entry)
    assert isinstance(result, ErrorResult)
    errors = result.diagnostics.diagnostics
    assert [d.code for d in errors] == ["E208"]
    assert isinstance(errors[0].primary.span, SourceSpan)
    assert errors[0].primary.span.text == "main"


def test_io_main_recursion_rejected_but_host_entry_and_shadowed_binders_are_valid(
    tmp_path: Path,
) -> None:
    entry = tmp_path / "entry.tfd"
    entry.write_text('pub fn main()->List[Text]{output "staged";main()}', encoding="utf-8")
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert [d.code for d in result.diagnostics.diagnostics] == ["E208"]
    entry.write_text(
        "pub fn main()->List[Text]{input x:Text;output x;[]}fn f(main:fn()->Int)->Int{main()}",
        encoding="utf-8",
    )
    assert isinstance(check(entry), ValidResult)


def test_pure_main_remains_callable_including_function_values(tmp_path: Path) -> None:
    entry = tmp_path / "entry.tfd"
    entry.write_text(
        "pub fn main()->List[Text]{[]}fn f()->List[Text]{let a=main;a()}", encoding="utf-8"
    )
    assert isinstance(check(entry), ValidResult)
