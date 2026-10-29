# Professor's eleven-item demonstration checklist

Build using README.md, then run the primary example with `--classroom --output-dir build`.
Open the NEW `build/Symbol Table.txt`; the supplied root report is its reference.
Rows below use the report's exact token categories. Row numbers are recorded in
`DEMO_ROWS.md`, generated from this exact sample/report after verification.

| # | Criterion and actual input | Visible lexemes | Expected report rows / procedure |
|---|---|---|---|
| 1 | Unique filetype | `complete.tfd`; rejected `does-not-exist.txt` | `.tfd` succeeds; missing `.txt` returns1 with extension message before any input open. |
| 2 | Identifiers — complete.tfd | `square`, `visitor`, `count`, `integer` | `IDENTIFIER` rows. |
| 3 | Keywords — complete.tfd | `record enum machine state next guard emit fn pub let for match input output` | `KEYWORD` rows; demonstrated distinct inventory is measured, not assumed. |
| 4 | Reserved words — complete.tfd | `Int Float Bool Text Char Unit List Option Decision step range len float_text int_text` | `RESERVED_WORD` rows for these actual spellings. |
| 5 | At least four constants — complete.tfd | `17`, `1.25e1`, `true/false`, `"Hello\nTernfold"`, `'Ω'` | `INT_LITERAL`, `FLOAT_LITERAL`, `BOOL_LITERAL`, `TEXT_LITERAL`, `CHAR_LITERAL` — five categories. |
| 6 | Noise words — complete.tfd | `input visitor: Text from stdin;`, `output text ++ visitor to stdout;` | `NOISE_WORD` / `from`, `NOISE_WORD` / `to`; contextual readability words. |
| 7 | Comments — complete.tfd | first `//` line; multiline `/* ... */` | `LINE_COMMENT`, `BLOCK_COMMENT`; multiline content remains one escaped row. |
| 8 | Seven arithmetic + nine Boolean — complete.tfd | `+ - / * % div ^`; `&& || ! > < == != >= <=` | `PLUS MINUS SLASH STAR PERCENT DIV CARET`; `AND_AND OR_OR BANG GREATER LESS EQUAL_EQUAL BANG_EQUAL GREATER_EQUAL LESS_EQUAL`. All16 must appear. |
| 9 | Delimiters/brackets — complete.tfd | `( ) [ ] { } , ; : . :: -> =>` | Corresponding delimiter token rows; Unit is two real parentheses. |
| 10 | Invalid tokens — invalid.tfd | `@`, `09`, `1e+`, `"bad\q"`, `'ab'`, unfinished `/*` | `INVALID` rows; expected exit1, still writes the report. |
| 11 | Actual Symbol Table output | `build/Symbol Table.txt` after each run | Exactly `TOKEN TYPE` and `LEXEME` columns, source order, comments/invalids retained. |

The sample, not only hidden tests, contains every demonstrated category. The C
`test_demo` suite asserts all16operators, five literals, both comments, contextual
noise, every listed delimiter, at least10distinct keyword/reserved spellings and
exact generated primary/invalid report bytes. `test_classroom` tests escaping and
safe publication; native lexical/CLI suites cover boundaries, failures and .tfd.

Use `vocabulary.tfd` only as the separately labeled lexical inventory fixture.
The primary is coherent source intended to illustrate Ternfold, but this analyzer
only tokenizes it; successful lexing does not prove type checking or execution.
The grading sheet's `Symbol Table` output is provided as `Symbol Table.txt`.
Physical INDEX CARD / printing the finalized proposal remain the group's tasks.
