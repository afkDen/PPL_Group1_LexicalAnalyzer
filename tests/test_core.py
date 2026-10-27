"""Adversarial Core invariants, independent of the source lowerer."""

from dataclasses import replace
from typing import cast

import pytest

from ternfold.analysis.modules import ModuleId
from ternfold.analysis.resolve import TypeId
from ternfold.analysis.types import BOOL, FLOAT, INT, TEXT, UNIT, Type, TypeKind
from ternfold.core import nodes as C
from ternfold.core.verify import VerificationError, list_type, require_verified, verify
from ternfold.frontend.ast import NodeId
from ternfold.frontend.source import SourceFile, SourceId

SOURCE = SourceFile(SourceId(0), "core.tfd", b"origin")
ORIGIN = C.Origin(NodeId(SOURCE.source_id, 0), SOURCE.span(0, 6))


def program(
    bindings: tuple[C.Let, ...],
    result: C.ValueId,
    result_type: Type = INT,
    constants: tuple[C.Constant, ...] = (C.Constant(INT, 1),),
    parameters: tuple[C.Parameter, ...] = (),
) -> C.CoreProgram:
    return C.CoreProgram(
        (),
        constants,
        (
            C.Function(
                C.FunctionId(0),
                "f",
                parameters,
                (),
                result_type,
                C.Block(bindings, C.Yield(result)),
                ORIGIN,
            ),
        ),
    )


def let(index: int, type_: C.CoreType, op: C.Operation) -> C.Let:
    return C.Let(C.ValueId(index), type_, op, ORIGIN)


def test_valid_core_and_verified_handle() -> None:
    p = program((let(0, INT, C.Const(0)),), C.ValueId(0))
    assert verify(p) == ()
    assert require_verified(p).program is p


@pytest.mark.parametrize(
    "bindings",
    [
        (let(0, INT, C.Unary("-", C.ValueId(1))), let(1, INT, C.Const(0))),
        (let(0, INT, C.Const(0)), let(0, INT, C.Const(0))),
        (let(0, FLOAT, C.Const(0)),),
        (let(0, INT, C.Const(100)),),
        (let(-1, INT, C.Const(0)),),
        (let(0, INT, C.Binary("&&", C.ValueId(1), C.ValueId(1))),),
    ],
)
def test_bad_dominance_ids_and_types_rejected(bindings: tuple[C.Let, ...]) -> None:
    p = program(bindings, C.ValueId(0))
    assert verify(p)
    with pytest.raises(VerificationError):
        require_verified(p)


def test_private_branch_value_cannot_escape_or_reuse_function_id() -> None:
    child = C.Block((let(2, INT, C.Const(0)),), C.Yield(C.ValueId(2)))
    other = C.Block((let(3, INT, C.Const(0)),), C.Yield(C.ValueId(3)))
    p = program(
        (let(0, BOOL, C.Const(1)), let(1, INT, C.If(C.ValueId(0), child, other))),
        C.ValueId(2),
        constants=(C.Constant(INT, 1), C.Constant(BOOL, True)),
    )
    assert any("dominating" in i.message for i in verify(p))
    duplicate = replace(p, functions=p.functions * 2)
    assert any("duplicate function" in i.message for i in verify(duplicate))


@pytest.mark.parametrize(
    "constant",
    [
        C.Constant(INT, True),
        C.Constant(INT, 1 << 63),
        C.Constant(FLOAT, float_bits=0x7FF0000000000000),
        C.Constant(FLOAT, float_bits=1 << 63),
        C.Constant(FLOAT, scalar=1),
        C.Constant(TEXT, "\ud800"),
        C.Constant(UNIT, 1),
        C.Constant(Type(TypeKind.LIST, (INT,)), children=(0,)),
    ],
)
def test_malformed_constant_pool_rejected(constant: C.Constant) -> None:
    p = program((let(0, constant.type, C.Const(0)),), C.ValueId(0), constant.type, (constant,))
    assert verify(p)


def option_program(
    payload: C.Block, default: C.Block | None, cases: tuple[int, ...] = (0,)
) -> C.CoreProgram:
    option = Type(TypeKind.OPTION, (INT,))
    switch = C.SwitchTag(C.ValueId(0), tuple(C.TagCase(tag, payload) for tag in cases), default)
    return program(
        (let(1, INT, switch),), C.ValueId(1), parameters=(C.Parameter(C.ValueId(0), option),)
    )


def test_exact_tag_proof_required_for_payload_and_default_unreachable() -> None:
    projected = C.Block((let(2, INT, C.Payload(C.ValueId(0), 0, 0)),), C.Yield(C.ValueId(2)))
    fallback = C.Block((let(3, INT, C.Const(0)),), C.Yield(C.ValueId(3)))
    assert verify(option_program(projected, fallback)) == ()
    assert verify(option_program(projected, None))
    assert verify(option_program(projected, C.Block((), C.Unreachable())))
    assert verify(option_program(projected, fallback, (1,)))
    assert verify(option_program(projected, fallback, (0, 0)))
    exhaustive = C.SwitchTag(
        C.ValueId(0),
        (C.TagCase(0, projected), C.TagCase(1, fallback)),
        C.Block((), C.Unreachable()),
    )
    p = option_program(projected, fallback)
    fn = p.functions[0]
    assert (
        verify(
            replace(
                p,
                functions=(
                    replace(fn, body=C.Block((let(1, INT, exhaustive),), C.Yield(C.ValueId(1)))),
                ),
            )
        )
        == ()
    )


def test_literal_condition_cannot_justify_unreachable() -> None:
    p = program(
        (
            let(0, BOOL, C.Const(1)),
            let(
                1,
                INT,
                C.If(
                    C.ValueId(0),
                    C.Block((let(2, INT, C.Const(0)),), C.Yield(C.ValueId(2))),
                    C.Block((), C.Unreachable()),
                ),
            ),
        ),
        C.ValueId(1),
        constants=(C.Constant(INT, 1), C.Constant(BOOL, True)),
    )
    assert any("Unreachable" in i.message for i in verify(p))


@pytest.mark.parametrize(
    ("operator", "a", "b", "result", "valid"),
    [
        ("/", INT, INT, FLOAT, True),
        ("/", FLOAT, INT, FLOAT, True),
        ("+", FLOAT, INT, FLOAT, False),
        ("^", FLOAT, INT, FLOAT, True),
        ("^", FLOAT, FLOAT, FLOAT, False),
        ("div", FLOAT, INT, INT, False),
        ("&&", BOOL, BOOL, BOOL, False),
        ("==", FLOAT, FLOAT, BOOL, True),
    ],
)
def test_numeric_verifier_signatures(
    operator: str, a: Type, b: Type, result: Type, valid: bool
) -> None:
    p = program(
        (let(2, result, C.Binary(operator, C.ValueId(0), C.ValueId(1))),),
        C.ValueId(2),
        result,
        parameters=(C.Parameter(C.ValueId(0), a), C.Parameter(C.ValueId(1), b)),
    )
    assert (verify(p) == ()) is valid


def test_input_requires_hidden_entry_and_entry_cannot_be_called() -> None:
    vector = list_type(TEXT)
    p = program(
        (let(1, TEXT, C.InputAt(C.ValueId(0), 0)),),
        C.ValueId(1),
        TEXT,
        parameters=(C.Parameter(C.ValueId(0), vector),),
    )
    assert any("outside" in i.message for i in verify(p))
    body = C.Block(
        (
            let(1, TEXT, C.InputAt(C.ValueId(0), 0)),
            let(2, vector, C.ListValue(TEXT, (C.ValueId(1),))),
        ),
        C.Yield(C.ValueId(2)),
    )
    entry = replace(p.functions[0], kind="entry", result=vector, body=body)
    approved = replace(p, functions=(entry,), entry=entry.function)
    assert verify(approved) == ()
    caller = replace(
        entry,
        function=C.FunctionId(1),
        kind="user",
        body=C.Block(
            (let(1, vector, C.Call(entry.function, (C.ValueId(0),))),), C.Yield(C.ValueId(1))
        ),
    )
    assert any(
        "not callable" in i.message for i in verify(replace(approved, functions=(entry, caller)))
    )


def test_builtin_wrappers_cannot_forge_unknown_or_polymorphic_signatures() -> None:
    signature = Type(TypeKind.FUNCTION, (INT, TEXT))
    p = program(
        (let(1, TEXT, C.Builtin("int_text", signature, (C.ValueId(0),))),),
        C.ValueId(1),
        TEXT,
        parameters=(C.Parameter(C.ValueId(0), INT),),
    )
    assert verify(p) == ()
    fn = p.functions[0]
    for name in ("step", "eval", "print"):
        bad = replace(
            fn,
            body=C.Block(
                (let(1, TEXT, C.Builtin(name, signature, (C.ValueId(0),))),), C.Yield(C.ValueId(1))
            ),
        )
        assert verify(replace(p, functions=(bad,)))


def test_mutable_inputs_are_snapshotted_before_verification() -> None:
    bindings = [let(0, INT, C.Const(0))]
    block = C.Block(bindings, C.Yield(C.ValueId(0)))  # type: ignore[arg-type]
    p = program((), C.ValueId(0))
    functions = [replace(p.functions[0], body=block)]
    p = replace(p, functions=functions)  # type: ignore[arg-type]
    verified = require_verified(p)
    bindings[0] = let(0, INT, C.Const(999))
    functions.clear()
    assert verify(verified.program) == ()
    assert isinstance(verified.program.functions[0].body.bindings, tuple)
    with pytest.raises(TypeError):
        replace(verified, program=replace(p, constants=()))


@pytest.mark.parametrize("capture", [False, True])
def test_internal_tag_types_cannot_hide_in_unused_function_signatures(capture: bool) -> None:
    p = program((let(1, INT, C.Const(0)),), C.ValueId(1))
    parameter = C.Parameter(C.ValueId(0), C.TagType(Type(TypeKind.OPTION, (INT,))))  # type: ignore[arg-type]
    fn = (
        replace(p.functions[0], captures=(parameter,))
        if capture
        else replace(p.functions[0], parameters=(parameter,))
    )
    assert any("invalid binding" in issue.message for issue in verify(replace(p, functions=(fn,))))


def test_nominal_cycles_include_containers_and_machine_headers() -> None:
    a = TypeId(ModuleId("a.tfd"), 0)
    b = TypeId(ModuleId("a.tfd"), 1)
    record_a = Type(TypeKind.RECORD, nominal_id=a)
    record_b = Type(TypeKind.RECORD, nominal_id=b)
    machine = Type(TypeKind.MACHINE, nominal_id=a)
    cases = [
        (C.Nominal(record_a, (record_a,), names=("x",)),),
        (
            C.Nominal(record_a, (list_type(record_b),), names=("x",)),
            C.Nominal(record_b, (record_a,), names=("y",)),
        ),
        (
            C.Nominal(
                machine,
                (INT,),
                names=("x",),
                input_type=machine,
                output_type=INT,
                rejection_type=TEXT,
            ),
        ),
    ]
    for nominals in cases:
        assert any(
            "recursive nominal" in issue.message
            for issue in verify(C.CoreProgram(nominals, (), ()))
        )


@pytest.mark.parametrize(
    "case", ["missing_headers", "error_header", "empty_enum", "bad_names", "record_variants"]
)
def test_malformed_nominal_layouts_rejected(case: str) -> None:
    tid = TypeId(ModuleId("a.tfd"), 0)
    machine = Type(TypeKind.MACHINE, nominal_id=tid)
    nominal = {
        "missing_headers": C.Nominal(machine, (INT,), names=("x",)),
        "error_header": C.Nominal(
            machine,
            (INT,),
            names=("x",),
            input_type=Type(TypeKind.ERROR),
            output_type=INT,
            rejection_type=TEXT,
        ),
        "empty_enum": C.Nominal(Type(TypeKind.ENUM, nominal_id=tid)),
        "bad_names": C.Nominal(Type(TypeKind.RECORD, nominal_id=tid), (INT,)),
        "record_variants": C.Nominal(Type(TypeKind.RECORD, nominal_id=tid), variants=((),)),
    }[case]
    assert verify(C.CoreProgram((nominal,), (), ()))


@pytest.mark.parametrize("alias", [True, 1.0, -1])
@pytest.mark.parametrize("site", ["yield", "operand", "call", "closure", "entry"])
def test_reference_ids_cannot_alias_valid_integer_definitions(alias: object, site: str) -> None:
    bad_value = C.ValueId(cast(int, alias))
    bad_function = C.FunctionId(cast(int, alias))
    p = program((let(1, INT, C.Const(0)),), C.ValueId(1))
    if site == "yield":
        fn = replace(p.functions[0], body=C.Block(p.functions[0].body.bindings, C.Yield(bad_value)))
        forged = replace(p, functions=(fn,))
    elif site == "operand":
        forged = program(
            (let(1, INT, C.Const(0)), let(2, INT, C.Unary("-", bad_value))), C.ValueId(2)
        )
    elif site == "entry":
        vector = list_type(TEXT)
        entry = replace(
            p.functions[0],
            function=C.FunctionId(1),
            parameters=(C.Parameter(C.ValueId(0), vector),),
            result=vector,
            kind="entry",
            body=C.Block((), C.Yield(C.ValueId(0))),
        )
        forged = replace(p, functions=(entry,), entry=bad_function)
    else:
        target = replace(p.functions[0], function=C.FunctionId(1))
        op = C.Call(bad_function, ()) if site == "call" else C.Closure(bad_function, ())
        result_type = INT if site == "call" else Type(TypeKind.FUNCTION, (INT,))
        caller = replace(
            p.functions[0],
            result=result_type,
            body=C.Block((let(0, result_type, op),), C.Yield(C.ValueId(0))),
        )
        forged = replace(p, functions=(caller, target))
    assert verify(forged)
    with pytest.raises(VerificationError):
        require_verified(forged)


@pytest.mark.parametrize("alias", [True, 1.0, -1])
def test_nominal_reference_id_cannot_alias_a_valid_layout(alias: object) -> None:
    tid = TypeId(ModuleId("record.tfd"), 1)
    record = Type(TypeKind.RECORD, nominal_id=tid)
    p = program(
        (let(0, record, C.Record(TypeId(tid.module, cast(int, alias)), ())),), C.ValueId(0), record
    )
    p = replace(p, nominals=(C.Nominal(record),))
    assert verify(p)


@pytest.mark.parametrize("alias", [True, 1.0])
@pytest.mark.parametrize("site", ["variant", "list", "builtin"])
def test_operation_owned_types_do_not_bypass_nominal_identity_validation(
    alias: object, site: str
) -> None:
    tid = TypeId(ModuleId("enum.tfd"), 1)
    enum = Type(TypeKind.ENUM, nominal_id=tid)
    malformed = Type(TypeKind.ENUM, nominal_id=TypeId(tid.module, cast(int, alias)))
    if site == "variant":
        p = program((let(0, enum, C.Variant(malformed, 0, ())),), C.ValueId(0), enum)
    elif site == "list":
        p = program(
            (let(0, list_type(enum), C.ListValue(malformed, ())),), C.ValueId(0), list_type(enum)
        )
    else:
        p = program(
            (
                let(
                    1,
                    INT,
                    C.Builtin(
                        "len", Type(TypeKind.FUNCTION, (list_type(malformed), INT)), (C.ValueId(0),)
                    ),
                ),
            ),
            C.ValueId(1),
            parameters=(C.Parameter(C.ValueId(0), list_type(enum)),),
        )
    p = replace(p, nominals=(C.Nominal(enum, variants=((),), names=("A",)),))
    assert verify(p)
