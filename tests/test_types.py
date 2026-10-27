"""M06 valid, invalid and boundary programs through the real typed pipeline."""

from dataclasses import replace
from pathlib import Path

import pytest

from ternfold.analysis.types import (
    BOOL,
    CHAR,
    ERROR,
    INT,
    TEXT,
    Constant,
    Type,
    TypedProgram,
    TypeKind,
)
from ternfold.driver import type_source as check
from ternfold.frontend.diagnostics import ErrorResult, Result, ValidResult
from ternfold.frontend.source import SourceSpan


def typed(tmp_path: Path, text: str) -> Result[TypedProgram]:
    entry = tmp_path / "lib.tfd"
    entry.write_text(text, encoding="utf-8")
    return check(entry)


def valid(tmp_path: Path, text: str) -> TypedProgram:
    result = typed(tmp_path, text)
    assert isinstance(result, ValidResult), result.diagnostics
    assert all(type_.concrete for type_ in result.value.node_types.values())
    return result.value


def rejects(tmp_path: Path, text: str, code: str) -> ErrorResult:
    result = typed(tmp_path, text)
    assert isinstance(result, ErrorResult)
    assert code in [d.code for d in result.diagnostics.diagnostics], result.diagnostics
    return result


def test_concrete_typed_function_and_body_mismatch(tmp_path: Path) -> None:
    entry = tmp_path / "lib.tfd"
    entry.write_text("fn f(x:Int)->Int{x+1}", encoding="utf-8")
    result = check(entry)
    assert isinstance(result, ValidResult)
    assert INT in result.value.node_types.values()
    entry.write_text("fn f()->Int{true}", encoding="utf-8")
    result = check(entry)
    assert isinstance(result, ErrorResult)
    assert "E302" in [d.code for d in result.diagnostics.diagnostics]


@pytest.mark.parametrize(
    "text",
    [
        "fn f()->Int{append([],1)}",  # negative return type despite builtin inference
        "fn f()->Int{if 1{2}else{3}}",
        "fn f()->Int{let x:Int=true;x}",
        "fn f()->Int{let x=[1,true];0}",
        "fn f()->Bool{1==true}",
        "fn f()->Bool{'a'< 'b'}",
        "fn f()->Text{'a'++'b'}",
        "fn f()->Int{true+1}",
        "fn f()->Int{let x=for a in 1{a};0}",
        "pub fn main()->List[Text]{input x:Text;output 1;[x]}",
        "fn f()->Int{let c=fn()->Bool{1};0}",
    ],
)
def test_type_mismatches(tmp_path: Path, text: str) -> None:
    rejects(tmp_path, text, "E302")


@pytest.mark.parametrize(
    ("expression", "result_type"),
    [
        ("append([],1)", "List[Int]"),
        ("map([],fn(x:Int)->Bool{x==0})", "List[Bool]"),
        ("fold([],0,fn(acc:Int,x:Int)->Int{acc+x})", "Int"),
        ("fold([],[],fn(a:List[Int],b:Int)->List[Int]{a})", "List[Int]"),
        ("map([[]],fn(xs:List[Int])->Int{len(xs)})", "List[Int]"),
        ("at([],0)", "Option[Int]"),
        ("append([at([],0)],Option::Some(1))", "List[Option[Int]]"),
        ("Option::None", "Option[Char]"),
        ("Option::Some([])", "Option[List[Int]]"),
        ("range(0,0)", "List[Int]"),
        ('parse_int("1")', "Option[Int]"),
        ('text_at("a",0)', "Option[Text]"),
        ('text_slice("a",0,1)', "Option[Text]"),
        ('text_len("a")', "Int"),
        ("bool_text(true)", "Text"),
        ("int_text(1)", "Text"),
        ("len([1])", "Int"),
        ("map([[1]],len)", "List[Int]"),
        ("[] ++ [1]", "List[Int]"),
    ],
)
def test_builtin_constraints_use_expected_result_and_all_arguments(
    tmp_path: Path,
    expression: str,
    result_type: str,
) -> None:
    valid(tmp_path, f"fn f()->{result_type}{{{expression}}}")


@pytest.mark.parametrize("expression", ["[]", "Option::None", "len", "len([])", "map([],len)"])
def test_unconstrained_local_values_are_not_generalized(tmp_path: Path, expression: str) -> None:
    rejects(tmp_path, f"fn f()->Int{{let x={expression};0}}", "E304")


def test_later_bindings_cannot_retroactively_solve_a_builtin_use(tmp_path: Path) -> None:
    rejects(
        tmp_path, "fn f()->Unit{let a=append([],Option::None);let b:List[Option[Int]]=a;()}", "E304"
    )


def test_match_body_cannot_late_solve_function_equality_and_hide_capability_check(
    tmp_path: Path,
) -> None:
    rejects(
        tmp_path,
        "fn f()->Bool{match at([],0){Option::Some(x)=>{"
        "let b=x==x;let y:fn()->Int=x;b},Option::None=>{false}}}",
        "E304",
    )
    rejects(
        tmp_path,
        "fn source(x:Option[fn()->Int])->Option[fn()->Int]{x}"
        "fn f()->Bool{match source(at([],0)){Option::Some(x)=>{"
        "let b=x==x;let y:fn()->Int=x;b},Option::None=>{false}}}",
        "E305",
    )
    rejects(
        tmp_path,
        "fn f()->Bool{let a:Option[fn()->Int]=at([],0);match a{"
        "Option::Some(x)=>{x==x},Option::None=>{false}}}",
        "E305",
    )


@pytest.mark.parametrize(
    "expression",
    [
        "at([],0)==Option::Some(1)",
        "if true{at([],0)}else{Option::Some(1)}",
    ],
)
def test_other_expression_consumers_cannot_solve_unconstrained_builtin_results(
    tmp_path: Path,
    expression: str,
) -> None:
    rejects(tmp_path, f"fn f()->Unit{{let value={expression};()}}", "E304")


def test_builtin_instances_are_fresh_firstclass_signatures_concrete_and_captures_typed(
    tmp_path: Path,
) -> None:
    program = valid(
        tmp_path,
        """
        fn f(x:Int)->Int{
            let a=append([],1);let b=append([],true);
            let size:fn(List[Char])->Int=len;
            let show:fn(Int)->Text=int_text;
            let c=fn()->Int{x+size(['a'])};c()
        }
    """,
    )
    assert all(instance.signature.concrete for instance in program.builtins.values())
    assert sum(instance.first_class for instance in program.builtins.values()) == 2
    captures = next(iter(program.captures.values()))
    assert [c.type.kind for c in captures] == [TypeKind.INT, TypeKind.FUNCTION]
    with pytest.raises(TypeError):
        program.node_types[next(iter(program.node_types))] = BOOL  # type: ignore[index]


def test_contextual_if_match_asymmetry_and_nested_for(tmp_path: Path) -> None:
    valid(tmp_path, "fn f()->List[Int]{if true{[]}else{[1]}}")
    valid(tmp_path, "fn f()->List[List[Int]]{for x in [1]{for y in [x]{y}}}")
    valid(tmp_path, "fn f()->Int{let x=if true{[1]}else{[]};0}")
    rejects(tmp_path, "fn f()->Int{let x=if true{[]}else{[1]};0}", "E304")
    rejects(tmp_path, "fn f()->Int{let x=match true{true=>{[]},false=>{[1]}};0}", "E304")
    valid(tmp_path, "fn f()->List[Char]{match true{true=>{[]},false=>{['x']}}}")
    rejects(tmp_path, 'fn f()->Option[Char]{text_at("a",0)}', "E302")


@pytest.mark.parametrize(
    "text",
    [
        "fn f(x:Int)->Int{x} fn g()->Int{f()}",
        "fn f(x:Int)->Int{x} fn g()->Int{f(1,2)}",
        "fn f(x:Int)->Int{x} fn g()->Int{f(x:1)}",
        "record R{x:Int} fn f()->R{R(1)}",
        "record R{x:Int} fn f()->R{R()}",
        "record R{x:Int} fn f()->R{R(x:1,x:2)}",
        "record R{x:Int} fn f()->R{R(y:1)}",
        "record R{} fn f()->Int{let c=R;0}",
        "enum E{V(Int)} fn f()->Int{let c=E::V;0}",
        "enum E{V} fn f()->E{E::V()}",
        "enum E{V(Int)} fn f()->E{E::V(x:1)}",
        "machine M(x:Int)yields Int rejects Text{state a:Int=0;next a=x;}fn f()->Int{let c=M;0}",
        "fn f()->Int{let x:List=1;0}",
        "fn f()->Int{let x:Int[Text]=1;0}",
        "record R{} fn f(x:R[Int])->Int{0}",
    ],
)
def test_exact_calls_field_sets_and_constructor_restrictions(tmp_path: Path, text: str) -> None:
    rejects(tmp_path, text, "E303")


def test_nominal_member_selection_uses_receiver_id_and_record_written_order(tmp_path: Path) -> None:
    program = valid(
        tmp_path,
        """
        record A{x:Int,y:Bool} record B{x:Char}
        fn f(a:A,b:B)->Int{let _=b.x;let c=A(y:true,x:1);a.x+c.x}
    """,
    )
    selected = [program.resolved.symbols[s] for s in program.selected_members.values()]
    assert len(selected) == 5
    assert len({s.owner for s in selected}) == 2
    assert {program.symbol_types[s.symbol_id] for s in selected} == {INT, BOOL, CHAR}
    rejects(tmp_path, "record R{x:Int}fn f(x:R)->Int{x.missing}", "E302")


@pytest.mark.parametrize(
    "text",
    [
        "record R{x:R}",
        "record R{x:List[Option[R]]}",
        "record A{b:B}enum B{V(A)}",
        "record R{x:fn()->R}",
        "machine M(x:M)yields Int rejects Text{state a:Int=0;next a=0;}",
        "machine M(x:Int)yields Option[M] rejects Text{state a:Int=0;next a=x;}",
        "machine M(x:Int)yields Int rejects R{state a:Int=0;next a=x;}record R{m:M}",
    ],
)
def test_nominal_and_machine_signature_cycles_are_e307(tmp_path: Path, text: str) -> None:
    result = rejects(tmp_path, text, "E307")
    assert all(isinstance(d.primary.span, SourceSpan) for d in result.diagnostics.diagnostics)


MACHINE = "machine M(x:Int)yields Char rejects Text{state a:Int=0;next a=x;emit 'x';}"


def test_step_and_both_decision_constructors_infer_machine_signature(tmp_path: Path) -> None:
    program = valid(
        tmp_path,
        MACHINE
        + """
        fn f()->Decision[M,Char,Text]{step(M(),1)}
        fn g()->Int{let a=Decision::Accept(M(),[]);let b=Decision::Reject(M(),"no");0}
        fn h()->Int{let s:fn(M,Int)->Decision[M,Char,Text]=step;let _=s(M(),1);0}
    """,
    )
    decisions = [t for t in program.node_types.values() if t.kind is TypeKind.DECISION]
    assert decisions and all(t.arguments[1:] == (CHAR, TEXT) for t in decisions)
    rejects(tmp_path, MACHINE + "fn f(x:Decision[Int,Char,Text])->Int{0}", "E307")
    rejects(tmp_path, MACHINE + "fn f(x:Decision[M,Text,Text])->Int{0}", "E307")
    rejects(tmp_path, MACHINE + "fn f()->Int{let _=step(M(),true);0}", "E302")
    rejects(tmp_path, MACHINE + "fn f()->Int{let _=Decision::Accept(M(),[1]);0}", "E302")


@pytest.mark.parametrize(
    "text",
    [
        "fn f(x:fn()->Int)->Bool{x==x}",
        "fn f()->Bool{let a:List[fn()->Int]=[];a==a}",
        "record R{c:Option[fn()->Int]}fn f(x:R)->Bool{x==x}",
        "enum E{Safe,Unsafe(fn()->Int)}fn f(x:E)->Bool{x==x}",
    ],
)
def test_equality_is_structural_over_full_types(tmp_path: Path, text: str) -> None:
    rejects(tmp_path, text, "E305")


def test_function_machine_signatures_do_not_make_cells_or_machine_equality_functional(
    tmp_path: Path,
) -> None:
    valid(
        tmp_path,
        """
        machine M(x:fn()->Int)yields fn()->Int rejects fn()->Int{
            state a:Int=0;next a=x();guard true else x;emit x;
        }fn f(m:M)->Bool{m==m}
    """,
    )
    rejects(
        tmp_path,
        "record R{f:List[fn()->Int]}machine M(x:Int)yields Int rejects Text{"
        "state r:R=R(f:[]);next r=r;}",
        "E407",
    )


@pytest.mark.parametrize(
    "clause",
    [
        "next a=true;",
        'next a=x;guard 1 else "no";',
        "next a=x;guard false else 1;",
        "next a=x;emit true;",
    ],
)
def test_machine_clauses_typecheck_without_scheduling(tmp_path: Path, clause: str) -> None:
    rejects(
        tmp_path, "machine M(x:Int)yields Int rejects Text{state a:Int=0;" + clause + "}", "E302"
    )


def test_machine_writer_duplicates_cycles_and_missing_writers_remain_for_m07(
    tmp_path: Path,
) -> None:
    valid(
        tmp_path,
        "machine M(x:Int)yields Int rejects Text{state a:Int=0;state b:Int=0;"
        "next a=if false{next.b}else{a};next a=next.a;}",
    )


@pytest.mark.parametrize(
    "which", ["type", "input_type", "output_type", "rejection_type", "nested_constant"]
)
def test_typed_program_rejects_nested_error_or_meta_in_all_tables(
    tmp_path: Path, which: str
) -> None:
    program = valid(tmp_path, MACHINE)
    tid = next(iter(program.nominals))
    if which == "nested_constant":
        sid = next(iter(program.constants))
        with pytest.raises(ValueError, match="concrete"):
            replace(program, constants={sid: Constant(INT, items=(Constant(ERROR),))})
    else:
        for invalid in (ERROR, Type(TypeKind.META, variable=0)):
            original = program.nominals[tid]
            info = (
                replace(original, type=invalid)
                if which == "type"
                else replace(original, input_type=invalid)
                if which == "input_type"
                else replace(original, output_type=invalid)
                if which == "output_type"
                else replace(original, rejection_type=invalid)
            )
            with pytest.raises(ValueError, match="concrete"):
                replace(program, nominals={tid: info})
