# C17 implementation target (ADR0011)

# Prelude and standard library target

C frontend signatures remain M06/C01 work; execution remains specified until M09/M11. Historical Python signature checks are not C completion. All are deterministic and pure, except resource failures described in runtime.md. Names in this table are compiler-known and reserved in the value namespace. `A` and `B` below are specification metavariables, not source syntax for user generics. Function types use `fn(A) -> B`; calling is always fully applied. Counts/indices are Int. No API reads files, environment variables, clocks, random sources, or networks.

| API | Signature | Exact behavior |
|---|---|---|
| `step` | `(M, I) -> Decision[M,O,E]` | Uses M's declared transition, input I, output O, rejection E |
| `len` | `(List[A]) -> Int` | Element count; lengths cannot exceed Int max |
| `at` | `(List[A], Int) -> Option[A]` | None for negative/out-of-range; otherwise Some(element) |
| `append` | `(List[A], A) -> List[A]` | New list with one value at end |
| `map` | `(List[A], fn(A) -> B) -> List[B]` | Calls function exactly once per element, left to right |
| `fold` | `(List[A], B, fn(B,A) -> B) -> B` | Left fold, empty list returns initial B |
| `range` | `(Int, Int) -> List[Int]` | Half-open ascending range; start >= end yields []; checked length |
| `int_text` | `(Int) -> Text` | Decimal, optional leading minus, no leading zeros |
| `int_float` | `(Int) -> Float` | Nearest/ties-even binary64 conversion; no general implicit widening |
| `float_int` | `(Float) -> Option[Int]` | Truncate toward zero, then Some if representable, otherwise None |
| `float_text` | `(Float) -> Text` | Canonical 17-significant-digit scientific decimal described below |
| `bool_text` | `(Bool) -> Text` | `true` or `false` |
| `parse_int` | `(Text) -> Option[Int]` | Whole string matches `-?(0|[1-9][0-9]*)` and fits Int; -0 gives 0; no whitespace/+ |
| `text_len` | `(Text) -> Int` | Number of Unicode scalar values, not graphemes or UTF-8 bytes |
| `text_at` | `(Text, Int) -> Option[Text]` | One-scalar Text or None; result is Text rather than Char |
| `text_slice` | `(Text, Int, Int) -> Option[Text]` | Scalar half-open [start,end); None unless 0 <= start <= end <= length |

Builtin variants are `Option::Some(A)`, `Option::None`, `Decision::Accept(M,List[O])`, and `Decision::Reject(M,E)`. Constructing an Accept/Reject value manually is permitted as ordinary data; it does not execute or validate a machine. Therefore a Decision is not an unforgeable proof of acceptance. Only a result returned by `step` carries the specified operational guarantee. Future proof-carrying outcomes would require an explicit design change.

0.1 source standard-library modules should focus on monomorphic practical helpers (e.g. text joining and Int statistics), documented with exact signatures when introduced in M12. Do not invent a generic library syntax to implement the table: the small polymorphic prelude is an intentional trusted compiler/runtime boundary. Its operations lower to typed Core builtin calls; map/fold call Ternfold closure values, never host evaluation of source.

## Revision 2 additions and compatibility

`Char` is a primitive, not a new prelude function. Existing `range(start, end): List[Int]` enables pure `for x in range(...)` comprehensions; no mutable loop index or console I/O builtin is introduced. Entrypoint `input`/`output` are syntax lowering to a driver-provided snapshot and private output buffer, not ordinary callable builtins. Existing parse_int/int_text functions explicitly convert input Text and checked arithmetic results. No third-party runtime or network service is required.

## Float conversions and canonical text (ADR 0010)

Only `/` accepts any pair of Int/Float operands by its explicit conversion rule;
other arithmetic/equality/arguments/containers follow exact signatures, with Float ^ Int the explicit power signature. No general numeric widening exists.
`int_float` rounds nearest/ties-even; `float_int` truncates then checks bounds.
Consequently `float_int(int_float(9223372036854775807))` is None. Conversion
builtins cannot appear in the closed constant initializer syntax, which admits
primitive `/` and Float literals instead.

`float_text` takes the exact finite binary64 value, rounds to 17 significant
decimal digits nearest/ties-even, then trims fractional trailing zeros but
retains one fractional digit. Scientific form has one digit before the dot,
lowercase `e`, no positive exponent sign and no redundant exponent zeros.
Rounding occurs before trimming and includes carry into a new exponent.
Zero is `0.0e0`; 1.5 is `1.5e0`, -2.5 is `-2.5e0`, and the rounded binary64
value of 0.1 formats as `1.0000000000000001e-1`. This is exact integer-ratio
rounding, independent of locale, host default formatting, C printf or parser formatting.
No `parse_float` is introduced by this correction.
