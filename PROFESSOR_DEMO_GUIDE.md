# A short classroom demonstration

1. Say: "A lexical analyzer reads characters and groups them into classified
   lexemes. This program writes a token table; it does not execute Ternfold."
2. Open `src/name_dfa.inc` and `src/lexer.c`. Show state 0, character edges,
   terminal classification and the generic identifier fallback. There is no
   runtime construction of the keyword graph.
3. Follow the actual `if` and `ifx` paths in [DFA_LIVE_DEMO.md](DFA_LIVE_DEMO.md).
   After building in step 4, run its trace fixture and locate FINAL records. Show numeric acceptance and
   `1e+` rejection, then `=` versus `==` maximal munch.
4. Compile the four C files using [IDE_QUICK_START.md](IDE_QUICK_START.md), or
   extract the separate all-in-one package and use its native launcher. Source
   compilation requires a compiler; precompiled use does not.
5. Run the complete demonstration using the matching workflow below. Open its
   newly generated report and compare it with
   `tests/fixtures/lexer/Classroom Symbol Table.txt` (under `source/` in the bundle).
6. Use [RUBRIC.md](RUBRIC.md), [DEMO_ROWS.md](DEMO_ROWS.md) and
   [PROPOSAL_LEXICAL_RECONCILIATION.md](PROPOSAL_LEXICAL_RECONCILIATION.md) to show
   all actual keyword/reserved/operator/literal/comment/delimiter rows.
7. Run the intentionally invalid samples. Explain E101–E105 and the separate
   E001–E003 source errors. Show continued valid tokens where recovery permits.
   A source-invalid file cannot produce ordinary token rows.
8. Show rejection of `README.md` before opening it. Explain exit 0 success,
   exit 1 diagnosed invalid input, exit 2 usage/host/output failure.
9. Restore the complete report by rerunning complete. For no-compiler use,
   launchers create `reports/Symbol Table.txt` in the all-in-one package.
10. Explain the immutable submitted PDF and documented later additions using
    [SUBMITTED_PROPOSAL_ALIGNMENT.md](SUBMITTED_PROPOSAL_ALIGNMENT.md). Do not
    claim later Float or packaging choices were in the original submission.

## Choose the matching run command

Run from the extracted source root for either source-build workflow:

| Build method | Command on Mac/Linux | New report |
|---|---|---|
| README build script | `./build/ternfold-lexer examples/lexical/complete.tfd --classroom --output-dir build` | `build/Symbol Table.txt` |
| IDE guide / direct four-file compile | `./ternfold-lexer examples/lexical/complete.tfd --classroom --output-dir .` | `Symbol Table.txt` |

On Windows, add `.exe` to the executable name. The script creates `build`;
the IDE commands use the existing root directory instead. In an IDE's program
arguments field, omit the executable name and set the working directory to the
extracted root. For the all-in-one ZIP, use `Run-Windows.cmd` or `Run-Mac.command`
from its root; the launcher creates `reports/Symbol Table.txt`.

## Questions to prepare for

| Question | Short answer grounded in this implementation |
|---|---|
| What is a lexeme? | The exact original character sequence, such as `if`, `visitor` or `17`. |
| What is a token? | A classified lexeme plus its original byte span and any payload/error metadata. |
| What is a transition? | Moving from the current finite state to the uniquely determined next state for a consumed character. |
| What is an accepting state? | A state at which the consumed prefix may end as a valid token; maximal munch may continue. |
| Why does `ifx` remain one identifier? | The `x` advances the name graph from the keyword terminal into the generic identifier fallback before the boundary. |
| Why is it deterministic? | One current state and input character select one next state; conflicting outgoing edges are rejected by graph tests. |
| Where are transitions hard-coded? | Immutable `name_states[]` in `src/name_dfa.inc`; other token families use the explicit switches/helpers in `src/lexer.c`. |
| Is it a premade analyzer? | No. Production recognition is handwritten C; no regex tokenizer, lexer generator or full-word lookup classifies input names. |
| What happens on invalid input? | The documented invalid/recovery path emits INVALID plus a diagnostic, or source validation prevents tokenization for E001–E003. |
| What is in Symbol Table.txt? | Exactly TOKEN TYPE and LEXEME, in source order, including comments/invalids and escaped row-breaking characters. |
| Does it execute Ternfold? | No: parsing, types and runtime semantics are outside the lexical submission. |
| What changed after submission? | The alignment document separates later Float/numeric recovery/report/C17 decisions and this fixed-DFA presentation improvement. |
