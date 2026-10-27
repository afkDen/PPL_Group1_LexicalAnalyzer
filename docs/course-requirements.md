# PPL course compliance contract — Ternfold 0.2

**Status: M03–M07 historical scopes verified; C01 numerical frontend/rubric amendments verified; execution/native requirements specified.** This repository is a fresh implementation bootstrap, not the partially completed M06 workspace from an unrelated Antigravity session. Finite automata are lexical recognizers, not the Ternfold machine transition graph. Tests and evidence, not documentation promises, decide course acceptance.

**Authority:** latest user-supplied course checklist; instructor's earlier 11-criterion lexer sheet; original Ternfold group proposal (11 pages); reference Group-2 proposal *for examples of expected DFA illustrations only*. This file owns evidence mapping, not semantics. Source-of-truth language semantics: `language-spec.md`, `grammar.md`, `type-system.md`, `runtime.md`, ADR 0009.

| Requirement | Target artifact / behavior | Acceptance milestone |
|---|---|---|
| Name/background/inspiration | Ternfold triple-phase machine; Elm/Lustre/Clojure precedent without novelty overclaim | M00 |
| Sigma, English/algebraic identifiers | Explicit letters/digits/glyphs/escapes; identifiers and function `square`/`polynomial` | M03/M04 |
| Seven arithmetic `+ - / * ^ % div` | Real `/` returns Float; integer `div` floor; checked power and finite numeric domains per ADR 0010 | C01/M08/M09/M11 |
| Six relational (part of nine) | `< <= > >= == !=` with nonassociative precedence | M03/M04/M06 |
| Three logical AND/OR/NOT (nine combined) | `&& || !` short circuit | M03/M04/M09 |
| 10 keywords + 10 reserved names | 25+ keywords, 20+ reserved type/builtin names, separate explanation table | M03/M05/report |
| Finite automata | `automata.md` state diagrams + transitions/acceptance; executable DFA lexeme fixtures | M03 |
| Noise words | optional `from stdin`, `to stdout`; lex as NOISE_WORD category | M03/M04/M09 |
| Single/block comments | `//`, `/*...*/` with unterminated errors; report as trivia rows | M03 |
| Spaces & free field | SP/TAB/LF/CRLF; semicolon explicit | M01/M03 |
| Commas/semicolon/brackets | lexical and parser tests for `, ; () [] {}` | M03/M04 |
| Four constant types minimum | independent Int, Float, Bool, Text, Char tokens (plus Unit expression) | M03/C01 |
| Invalid token / wrong extension | E101 et al. plus report INVALID, `.tfd` enforced | M03 |
| Symbol Table.txt | deterministic line-column lexeme/category report with comment/invalid rows | M03 |
| Expressions and precedence | grammar and tests for exponent, div, comparisons, logic | M04/M06 |
| Input statement | `input name: Text [from stdin];` main-only snapshot binding | M04/M06/M08/M09/M11 |
| Output statement | `output expr [to stdout];` staging, all-or-nothing output | M04/M06/M08/M09/M11 |
| Assignment statement | `let name = expr;` immutable binding; `next cell = expr;` candidate writer (not mutation) | M04/M07/M09 |
| Conditional | `if Bool { expr } else { expr }`, nested else-if; existing semantics | M04/M06/M09 |
| Single loop | pure `for x in range(...) { expr }` -> List | M04/M06/M09 |
| Nested loop | `for row ... { for col ... { expr } }` -> List[List] | M04/M06/M09 |
| Native parity | input snapshot, Char, div/power, comprehensions identical in C17 | M11/M14 |

A requirement is accepted only if its owner writes positive + negative tests (where meaningful), focused and full quality gates pass, and review confirms the rubric evidence. `scripts/course_audit.py` audits the **static specification/mapping** and produces a checklist; it does **not** pretend language execution works before its milestones. The final course demonstration includes source, lexical table, invalid diagnostic, DFA diagram, single loop, nested loop, both comments, and real interpreter/native outputs.

## Teaching demonstration examples (target syntax, not runnable yet)

```tfd
fn square(x: Int) -> Int { x ^ 2 }
fn polynomial(x: Int) -> Int { 2 * (x ^ 2) + 3 * x - 1 }
fn table() -> List[List[Int]] {
    for row in range(0, 2) {
        for col in range(0, 3) { row * 10 + col }
    }
}
pub fn main() -> List[Text] {
    input visitor: Text from stdin;
    let a = 13 / 5;
    let b = -7 div 3;
    let mark: Char = 'T';
    output "Hello " ++ visitor to stdout;
    [float_text(a), int_text(b), int_text(square(3))]
}
```

Sample stdin line `Ada` should yield output lines `Hello Ada`, `2.6000000000000001e0`, `-3`, `9` after whole evaluation succeeds. This is a *target expected result*; do not mark it executable while M09/M11 are pending.

### Persistent acceptance ledger

`docs/course-acceptance.json` enumerates 25 independent rubric requirements, owner milestones and evidence references. Schema 2 distinguishes specified, implemented, tested, reviewed, verified and blocked; schema 1 remains readable. Historical verification is preserved separately from the C01 amendment. Blocked requires a reason, and implemented/tested/reviewed/verified require actual evidence paths. A later agent can change status only after real code, tests and independent review; positive implementation/test/review/verification claims require existing evidence paths and are enforced by `scripts/course_audit.py`. The final M14 review must verify all records and corresponding actual language execution, not simply set flags.

## Professor clarification and eleven-item lexical checklist

`/7` and `/9` are required operation counts, not grading points. Arithmetic:
`+ - / * % div ^` (seven); logical/relational: `&& || ! > < == != >= <=` (nine).
Real division `/` is mathematically distinct from integer `div`; ADR 0010 defines
finite Float semantics. Recognize and test every operation independently while
preserving logical short-circuiting.

The mandatory lexical checklist is: (1) .tfd only, (2) identifiers, (3) keywords,
(4) reserved words, (5) at least four literal kinds, (6) from/to noise words,
(7) line/block comments, (8) all seven plus nine operations, (9) delimiters/
brackets, (10) INVALID lexemes and recovery, (11) an actual UTF-8 text file named
`Symbol Table.txt`. C01 must provide a representative .tfd demo containing all
16 spellings with exact deterministic report/span tests. Use standalone `python analyzer.py examples/complete.tfd` to publish the
required two-column classroom table. The compiler rich report remains a
separate internal view. S01 verifies strict per-character name recognition,
without completed-word keyword or reserved-spelling matching.
The [read-only evidence audit](verification/lexical-rubric-audit-2026-10-27.md)
records existing implementation and precise amendment gaps. Windows and POSIX
results are distinct; documentation, a report fixture or a mapping audit alone
cannot establish numerical runtime/native conformance.
