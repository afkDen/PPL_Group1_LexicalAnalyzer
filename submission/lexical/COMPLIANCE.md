# Stage 1 checklist and verification scope

| # | Mandatory item | Included runnable evidence |
|---|---|---|
| 1 | .tfd-only | wrong-extension CLI regression, exact case enforced |
| 2 | identifiers | ASCII starts/continuations/case/wildcard/keyword prefixes |
| 3 | keywords | independent fixed inventory of all28, each terminal and boundary |
| 4 | reserved names | all21 proposal names plus4 numerical additions; trie flags |
| 5 | >=4 literal kinds | Int, Float, Bool, Text, Char; Unicode/escapes/invalid cases |
| 6 | from/to noise | matching lexical phrases and mismatched context tests |
| 7 | comments | //, /* */, EOF/nonnesting/unterminated, actual report rows |
| 8 | exactly7+9 | independent complete operator-kind and boundary assertions |
| 9 | delimiters/brackets | comma/semicolon/colon/dot/()[]{} and longest prefixes |
| 10 | INVALID/recovery | E101–E105, progress/caps, encoding E001–E003 diagnostics |
| 11 | Symbol Table.txt | actual two-column UTF-8/LF file, order and exact bytes |

Restrictions: stdlib-only explicit character scanner and name/number DFA; no
regex, generated lexer, premade analyzer, input-word comparisons, eval/exec or
compiler/runtime dependency. Tests inspect the recognition path and exercise
all name terminal/boundary states. The internal rich report API remains separate.

Run `python -m unittest discover -s tests -v`. Tests operate in temporary directories
and invoke the actual standalone analyzer; they do not need pytest. Source and
reports retain exact spans/lexemes. Acceptance is lexical only: numerical execution,
short-circuit runtime behavior, parsing and native code are outside Stage1.
Windows Python3.14.4 is the executed platform; other supported Python versions
and POSIX launchers require an actual run before claiming validation.
