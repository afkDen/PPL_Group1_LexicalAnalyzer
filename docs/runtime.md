# Runtime, C ABI, and execution equivalence

Normative runtime target, **ABI 1**, not yet implemented. The language value/fault contract is in language-spec.md. This document owns native representation and lifetime rules.

## Chosen memory model

Immutable acyclic values with reference-counted heap objects. Scalars Int/Float/Bool/Char/Unit are inline tagged values. Text, lists, records, enum payload objects, machine snapshots, and closure environments are boxed with a header `{kind, refcount, type_id}` and fixed metadata/children. UTF-8 Text has explicit byte length and may contain NUL. Lists start as immutable contiguous vectors, O(n) append/concatenation; persistent vectors are a later compatible optimization. No object exposes identity.

No assignment, mutable captures, recursive local bindings, or runtime global value initialization exists, so constructed heap graphs point only to previously existing immutable values. Global functions are code IDs with no captured environment. This prevents reference cycles even though functions may recurse. Closure environments can form deep acyclic chains; destruction must not recurse on the C stack. Release uses an intrusive pending-free chain in zero-count headers, requiring no allocation during destruction. Visit child references, enqueue newly zero-count children, then free the object. Every reachable child is retained at construction.

Reference counts are checked 64-bit unsigned values. A retain that would overflow reports R003 before changing ownership. No silent wrapping, saturating leak, or special immortal count in ABI 1. Constant pool heap objects are owned by the runtime context and released after program roots. Limits count live allocated bytes (default native budget 256 MiB) and language call depth (default 1,024), checking size multiplication/addition before allocating. Resource failure is R003 and must clean up owned temporaries. Python and C allocation budgets need not trigger at identical values: resource-limit equivalence is not promised.

## Value ABI

The C runtime owns public types `tf_value`, `tf_context`, `tf_status`, `tf_span_id`, and metadata tables. `tf_value` is a tagged union with `int64_t`, canonical binary64 Float bits, Unicode-scalar Char, Boolean byte, or heap pointer. C must not reinterpret user Text as a format string or a null-terminated buffer. `tf_status` is `TF_OK` or `TF_FAULT`; context stores one structured fault with code/span/call frames. Set only the first fault. No longjmp, C exceptions, varargs value APIs, or process-wide mutable singleton.

Generated function calling convention:

```c
tf_status tf_f_17(tf_context *ctx,
                  const tf_value *captures, size_t capture_count,
                  const tf_value *args, size_t argc,
                  tf_value *out);
```

Arguments/captures are **borrowed** for the call, cannot be retained in returned structures without an explicit checked retain, and remain owned by the caller. Successful `out` is **owned** by the caller. On failure `out` is Unit with no ownership. Constructors accept borrowed children and retain them; projections return owned values via retain; inline copies need no retain. A closure contains a generated function-table index and an immutable captured-value vector. All runtime operations that may allocate/retain take context, span, and output slot, returning status. Primitive comparisons may return inline Bool without allocation but still retain proper source metadata for faults in prior operations.

Emitter uses a conservative initial lifetime discipline: allocate a function-local array of value slots initialized to Unit; each executed Core binding owns its slot; a yielded result is retained into its parent slot or `out`; one cleanup path releases all initialized slots exactly once on success or fault. Untaken branch slots stay Unit. This deliberately retains temporaries to function exit. A future liveness pass may shorten lifetimes after differential and sanitizer coverage. Never use pointer identity to avoid required releases. Ensure copying a value slot is either scalar copy or checked retain; raw struct assignment of owning heap values is forbidden outside move-aware runtime internals.

## Arithmetic and platform contract

Compile C with `-std=c17 -Wall -Wextra -Werror -pedantic`. Supported initial targets are 64-bit Linux/macOS with GCC >=12 or Clang >=16 and an available exact int64_t. Windows support is experimental until CI exists. GCC 13.3 is verified in this architecture environment. Configure platform support by compile probes, not version string alone.

Check signed overflow **before** executing C arithmetic. For addition/subtraction, compare bounds without overflowing intermediate expressions; for multiplication use division bounds with explicit sign cases, or verified compiler builtins behind a portable fallback. Integer `div`/`%` check zero and INT64_MIN/-1 before using C integer quotient/remainder. Negation checks INT64_MIN. Never use floating point to implement Int `div` or `%`; source `/` is Float real division under ADR 0010. Constant expressions in generated C must encode INT64_MIN safely, e.g. `(-INT64_C(9223372036854775807) - INT64_C(1))`. Length arithmetic uses checked size_t operations and rejects lengths exceeding Int max. Sanitizers are gates, not a replacement for reasoning about UB.

C expression evaluation order is insufficient for source semantics. Every operand is already a Core value; emitted calls/checks occur in separate statements in Core order. Source calls cannot be placed as two C function arguments and left for C to order. String literals are escaped as bytes or numeric byte arrays with explicit length; avoid ambiguous hex-escape concatenation. C identifiers contain generated numeric IDs, never raw user strings.

## Float representation and parity (ADR 0010)

Float is an inline tagged binary64 payload. Every constructed value is finite;
zero normalizes positive. Native compile/run probes must establish radix 2,
53-bit significand, binary64 exponent range, exact eight-byte representation,
round-to-nearest/ties-even and gradual subnormal arithmetic. Unsupported hosts
fail the native capability gate rather than silently changing numerical behavior.
Emit Float constants from verified 64-bit payloads using safe bit copies,
not locale-sensitive decimal parsing or type-punning UB. The host checker may use exact integer-ratio rounding into canonical bit
payloads, avoiding reliance on the host floating representation entirely.

Each primitive operation rounds to binary64 separately; disable fast-math,
contraction/FMA, excess precision and flush-to-zero behavior. Use capability
probes in addition to flags. `/` converts each Int operand independently with
nearest-even and returns Float for all numeric pairs. Do not use Int arithmetic
for source `/` or Float for integer division. Float `^` uses the exact checked
reciprocal-first squaring sequence in language-spec.md; do not use C/Python
`pow`. A zero denominator is R002; any nonfinite intermediate/result is R001.
Finite underflow is valid. Conversion to Int truncates then checks representable
bounds before a C cast; IntMax converted to Float rounds to 2^63 and cannot
convert back to Int. Avoid signed negation of IntMin in exponent magnitude.

`float_text` rounds the exact binary ratio to 17 significant decimal digits,
nearest/ties-even, before trimming; output is normalized scientific decimal,
one retained fractional digit, lowercase e and canonical zero `0.0e0`.
Implement equivalent exact integer rounding in both executors; neither host
repr nor printf formatting defines semantics. Test carry, subnormals, maximum
finite values and halfway ties independently of parsing. Keep implementation
bounded by the fixed binary64 domain, offline and independent of locale.

Native/interpreter conformance compares numerical finite bits where meaningful,
canonical output bytes, fault code and original operator span. This is specified,
not executed evidence: M09 and M10/M11 own the actual implementations/gates.

## Faults and host boundary

| Code | Meaning | Required behavior |
|---|---|---|
| R001 | Int overflow or nonfinite Float result | Original operator span; no wrapped result |
| R002 | Division/remainder by zero | Original operator span |
| R003 | Configured resource limit / allocation failure | No partial returned value; cleanup |
| R004 | Internal impossible runtime state | Treat as compiler/runtime bug, not a catchable domain error |

Logical runtime faults R001/R002 must agree between interpreter and C in code and source span for a given program without resource exhaustion. Result equality includes values, stdout bytes, and exit status; memory addresses, allocation counts, compiler messages, stack implementation frames and timing are excluded. R003 is tested independently in each executor. Native source call-frame ordering should agree modulo implementation-only frames. The host evaluates main fully before writing stdout. A successful output-write sequence that then suffers an OS error cannot be made atomic; report a host error without claiming rollback.

## Native build contract

`emit-c` writes a translation unit including `ternfold_rt.h`; `build` invokes the configured compiler with source, runtime C source, include directory, and explicit output path. Runtime source is shipped with the package at M11 (add package-data installation and installed-wheel tests then). Until M11, the wheel ships frontend capabilities and makes no native-runtime claim.

Development verification compiles/runs a small C17 toolchain probe. Runtime tests later use `-fsanitize=address,undefined -fno-omit-frame-pointer -g` where supported, with leak detection where available. Test partial constructor allocation failure, failed retains, shared children, nested closure releases, both match branches, and every return/guard-failure edge. A malloc fault-injection adapter is test-only; it must not become a source-level feature.

## Revision 2 runtime/ABI extension (normative; not implemented)

`Char` is an inline Unicode scalar tag with validated range U+0000..U+10FFFF excluding surrogates, distinct from Text. Extend value equality, type tables, C union payload and verifier without changing ownership rules. Add checked Int `^` with nonnegative exponent and exponentiation by squaring and `div` with mathematical floor semantics using checked truncating C division plus signed remainder correction, never signed overflow or floating-point approximation. Fault R005 = negative exponent. R001/R002 remain the overflow/zero-divisor contract and R003 remains resource exhaustion.

The driver captures stdin lines **before** starting main and passes the immutable vector through a hidden entrypoint adapter, to both Python and native modes. `input` clauses consume sequential lines or fault R006 = insufficient input. `output` clauses stage Text values privately. Host writes these staged lines followed by old `main: List[Text]` results only after complete successful evaluation. Exact newline policy: split UTF-8 input at LF, strip one trailing CR from each line, preserve empty interior lines, and do not create a synthetic final empty line for a terminal LF; unpaired CR in input data is preserved. Both execution modes must agree on input count/encoding and outputs. This boundary is intentionally **not an ambient I/O primitive** available to machines or pure functions. The hidden adapter retains existing borrowed-input/owned-output ABI invariants and C17 compatibility; native launcher captures/replays the input vector. On R006 or any other evaluation fault, suppress all staged and returned output. CLI may accept a `--stdin-file` UTF-8 path for deterministic acceptance tests.
