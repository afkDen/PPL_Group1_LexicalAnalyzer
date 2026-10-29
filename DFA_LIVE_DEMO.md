# Show the actual DFA during the oral defense

Open `src/lexer.c` and its directly included `src/name_dfa.inc` in the IDE.
The include is C source initializers, not a generated-at-startup transition file.
Keep all four implementation C files in the project; the include is not a fifth
compilation unit. `tf_name_dfa_step` follows the immutable child/sibling character
edges in `static const name_states[]`. State 0 is the start. `terminal` metadata
selects a keyword, reserved spelling or `_`; ordinary prefixes accept identifiers.
A missing edge enters the absorbing `SIZE_MAX` identifier fallback.

These paths come from the actual fixed table, not a separate teaching DFA:

| Input | Actual name-state path | Final classification |
|---|---|---|
| `if` | 0 --i-->32 --f-->33 | IF token, KEYWORD report row |
| `ifx` | 0 --i-->32 --f-->33 --x-->identifier fallback | IDENT, IDENTIFIER row |
| `in` | 0 --i-->32 --n-->39 | IN, KEYWORD |
| `input` | 0 --i-->32 --n-->39 --p-->40 --u-->41 --t-->42 | INPUT, KEYWORD |
| `let` | 0 --l-->43 --e-->44 --t-->45 | LET, KEYWORD |
| `letter` | 0 --l-->43 --e-->44 --t-->45 --t-->fallback; e/r loop there | IDENTIFIER |
| `Int` | 0 --I-->102 --n-->103 --t-->104 | IDENT with reserved metadata; RESERVED_WORD |
| `Intensity` | same prefix as Int; e enters identifier fallback | IDENTIFIER |

The scanner waits for the identifier boundary. Reaching the `if` state does not
mean it stops before an adjacent `x`. Every consumed name character calls the
same transition function used by the inspection API. The source table is fixed
at compile time; no inventory-to-trie construction runs in the application.

## Run the trace

For the script-build workflow in [README.md](README.md), build first, then run
from the extracted root. The build script creates the required `build` directory:

```sh
./build/ternfold-lexer examples/lexical/trace.tfd --classroom --output-dir build --trace-dfa 2> build/dfa-trace.txt
```

Windows uses `./build/ternfold-lexer.exe` with the same arguments.

For the root-directory executable created by [IDE_QUICK_START.md](IDE_QUICK_START.md),
use `.` as the existing output directory instead. From the extracted root:

```sh
./ternfold-lexer examples/lexical/trace.tfd --classroom --output-dir . --trace-dfa 2> dfa-trace.txt
```

On Windows, use `./ternfold-lexer.exe`. In an IDE, set the extracted root as the
working directory and use `examples/lexical/trace.tfd --classroom --output-dir . --trace-dfa`
as program arguments; trace appears on stderr.
Redirect stderr only if you want a saved trace. The trace fixture intentionally
contains a malformed number: exit 1 and an E102 diagnostic are expected.
Transition output is separate from `Symbol Table.txt`. Default runs produce no
trace. Trace and diagnostics may share stderr; both are explicitly identified.

Show the consumed character/byte offset, old and next state, accepting status
and FINAL token record. A name prefix can accept a generic identifier without
being a terminal keyword. The identifier fallback is valid identifier acceptance,
not lexical INVALID. Unsupported `@` instead follows the invalid-token path.

Open `number_step` and its `NumberState` enum. `N_START`, `N_ZERO`, `N_INT`,
`N_DOT`, `N_FRAC`, `N_EXP`, `N_SIGN`, `N_DIGITS`, `N_BAD` make the numeric graph
visible. `1.25e-2` passes through fraction/exponent/sign to exponent digits;
`1e+` ends in the nonaccepting exponent-sign state and becomes E102 INVALID.
A dot joins a number only when followed by a digit; minus outside an exponent
is a separate operator. No numeric value conversion happens during lexing.

Show the operator switch: `=` provisionally accepts EQUAL; another `=` selects
EQUAL_EQUAL, while `=>` selects FAT_ARROW. Slash branches to slash, line comment
or block comment. Quote/escape helpers validate decoded Unicode scalars and
closing quotes; Char requires exactly one scalar. Family-specific switches and
states are intentional; they are not claimed to be one universal transition table.

## Full demonstration

Run `complete.tfd`, open the new report and compare it with the maintained
classroom golden. `vocabulary.tfd` is a labeled lexical inventory, not executable
Ternfold. Run `invalid.tfd` and the rule-specific demonstrations listed in the
invalid matrix; source-invalid encoding fixtures produce a header-only report.
Check [the proposal matrix](PROPOSAL_LEXICAL_RECONCILIATION.md) rather than
counting words hidden inside comments or Text literals. Rerun `complete.tfd` to restore
the report after invalid demonstrations. No lexical example proves execution.
