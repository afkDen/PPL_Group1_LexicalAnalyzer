"""Real source lowering structure, not a second executor or AST interpreter."""

import json
from dataclasses import fields, is_dataclass
from pathlib import Path

from ternfold.analysis.numeric import Float64
from ternfold.core import nodes as C
from ternfold.core.lower import lower
from ternfold.core.verify import verify
from ternfold.driver import check
from ternfold.frontend import ast as A
from ternfold.frontend.diagnostics import ValidResult

ROOT = Path(__file__).resolve().parents[1]


def compile_text(tmp_path: Path, text: str) -> C.CoreProgram:
    entry = tmp_path / "entry.tfd"
    entry.write_text(text, encoding="utf-8")
    result = check(entry)
    assert isinstance(result, ValidResult), result.diagnostics
    core = lower(result.value)
    assert verify(core.program) == ()
    return core.program


def operations(block: C.Block) -> list[C.Operation]:
    result: list[C.Operation] = []
    for binding in block.bindings:
        op = binding.operation
        result.append(op)
        if isinstance(op, C.If):
            result += operations(op.then) + operations(op.otherwise)
        elif isinstance(op, C.SwitchTag):
            for case in op.cases:
                result += operations(case.body)
            if op.default is not None:
                result += operations(op.default)
        elif isinstance(op, C.ListMap):
            result += operations(op.body)
    return result


def test_all_valid_manifest_fixtures_lower_without_syntax_or_plan_objects() -> None:
    valid = 0
    cases = json.loads((ROOT / "examples/manifest.json").read_text(encoding="utf-8"))["cases"]
    for case in cases:
        if case.get("diagnostic", "").startswith("E"):
            continue
        result = check(ROOT / case["path"])
        assert isinstance(result, ValidResult), case["path"]
        core = lower(result.value)
        assert verify(core.program) == (), case["path"]
        pending: list[object] = [core.program]
        while pending:
            node = pending.pop()
            assert not isinstance(node, A.Node)
            if is_dataclass(node):
                pending.extend(getattr(node, field.name) for field in fields(node))
            elif isinstance(node, tuple):
                pending.extend(node)
        valid += 1
    assert valid == 16


def test_nested_patterns_keep_one_scrutinee_and_dominating_payload_proofs(tmp_path: Path) -> None:
    core = compile_text(
        tmp_path,
        "fn f(x:Option[Bool])->Int{match x{"
        "Option::Some(true)=>{1},Option::Some(false)=>{2},Option::None=>{3}}}",
    )
    fn = core.functions[0]
    ops = operations(fn.body)
    assert sum(isinstance(op, C.Payload) for op in ops) == 1
    assert any(isinstance(op, C.If) for op in ops)
    assert any(isinstance(op, C.SwitchTag) for op in ops)


def test_machine_writers_before_ordered_guards_and_delayed_emissions(tmp_path: Path) -> None:
    core = compile_text(
        tmp_path,
        "machine M(request:Int)yields Int rejects Text{"
        "state a:Int=0;state b:Int=0;state z:Int=0;"
        "next z=request%0;next a=next.b+1;next b=request div 0;"
        'guard next.a>0 else "first";guard next.z>0 else "second";'
        "emit next.a;emit next.z;}",
    )
    step = next(fn for fn in core.functions if fn.kind == "step")
    primitive = [
        b.operation.operator for b in step.body.bindings if isinstance(b.operation, C.Binary)
    ]
    assert primitive == ["div", "+", "%", ">"]
    outer = step.body.bindings[-1].operation
    assert isinstance(outer, C.If)
    assert not any(isinstance(op, C.ListValue) for op in operations(outer.otherwise))
    assert any(isinstance(op, C.ListValue) for op in operations(outer.then))
    rejected = outer.otherwise.bindings[-1].operation
    assert isinstance(rejected, C.Variant) and rejected.tag == 1
    assert rejected.values[0] == step.parameters[0].value


def test_short_circuit_faulting_operands_stay_in_selected_blocks(tmp_path: Path) -> None:
    core = compile_text(tmp_path, "fn f()->Bool{false && (1 div 0==0)}")
    fn = core.functions[0]
    assert not any(isinstance(b.operation, C.Binary) for b in fn.body.bindings)
    branch = fn.body.bindings[-1].operation
    assert isinstance(branch, C.If)
    assert any(isinstance(op, C.Binary) and op.operator == "div" for op in operations(branch.then))
    assert not any(isinstance(op, C.Binary) for op in operations(branch.otherwise))


def test_record_arguments_evaluate_written_order_then_store_declaration_order(
    tmp_path: Path,
) -> None:
    core = compile_text(
        tmp_path, "record R{a:Int,b:Int}fn a()->Int{1}fn b()->Int{2}fn f()->R{R(b:b(),a:a())}"
    )
    fn = next(f for f in core.functions if f.name == "f")
    names = {f.function: f.name for f in core.functions}
    calls = [b for b in fn.body.bindings if isinstance(b.operation, C.Call)]
    assert [names[b.operation.function] for b in calls if isinstance(b.operation, C.Call)] == [
        "b",
        "a",
    ]
    record = fn.body.bindings[-1].operation
    assert isinstance(record, C.Record)
    assert record.values == (calls[1].value, calls[0].value)


def test_closures_and_first_class_builtin_wrappers_are_explicit_functions(tmp_path: Path) -> None:
    core = compile_text(
        tmp_path,
        "fn f()->fn(Int)->Text{let x=2;let y=3;"
        "fn(z:Int)->Text{let show:fn(Int)->Text=int_text;show(y+x+z)}}",
    )
    lifted = next(fn for fn in core.functions if fn.kind == "closure")
    assert [p.name for p in lifted.captures] == ["x", "y"]
    wrapper = next(fn for fn in core.functions if fn.kind == "builtin-wrapper")
    assert wrapper.captures == ()
    assert any(
        isinstance(op, C.Builtin) and op.name == "int_text" for op in operations(wrapper.body)
    )
    assert any(isinstance(op, C.CallClosure) for op in operations(lifted.body))


def test_for_is_structural_and_entry_output_is_staged_data(tmp_path: Path) -> None:
    core = compile_text(
        tmp_path, 'pub fn main()->List[Text]{input x:Text;output x;for y in ["a","b"]{y}}'
    )
    entry = next(fn for fn in core.functions if fn.function == core.entry)
    assert entry.kind == "entry" and len(entry.parameters) == 1
    ops = operations(entry.body)
    assert sum(isinstance(op, C.InputAt) for op in ops) == 1
    assert sum(isinstance(op, C.ListMap) for op in ops) == 1
    assert isinstance(entry.body.bindings[-1].operation, C.Binary)
    assert entry.body.bindings[-1].operation.operator == "++"
    assert not any(
        isinstance(op, C.Builtin) and op.name in {"print", "input", "output"} for op in ops
    )


def test_float_bits_and_operator_fault_origins_survive_lowering(tmp_path: Path) -> None:
    core = compile_text(tmp_path, "fn f()->Float{let x=-0.0;7/2}")
    assert any(c.float_bits == Float64(0).bits for c in core.constants if c.float_bits is not None)
    fn = core.functions[0]
    divide = fn.body.bindings[-1]
    assert isinstance(divide.operation, C.Binary) and divide.operation.operator == "/"
    assert divide.origin.span.text == "/"
