# Ternfold Lexical Analyzer

Reads a UTF-8 `.tfd` file and writes **Symbol Table.txt**. Requires Python
**3.12-3.14** and the standard library only. No installation or network is needed.
Executed verification: Windows, Python **3.14.4**. Other versions and POSIX have
not been executed here.

## Run

Extract the ZIP and open a terminal in its folder:

```text
python analyzer.py examples/complete.tfd
python -m unittest discover -s tests -v
```

On Windows, double-click `run_lexer.bat` to analyze the complete example, or pass
it a relative `.tfd` path. The launcher uses `py -3`; use the Python command above
if that launcher is unavailable. On POSIX use `python3` or `sh run_lexer.sh`.

The report is created in the current directory. Select another existing directory:

```text
python analyzer.py examples/complete.tfd --output-dir expected
```

The invalid example demonstrates diagnostics and recovery:

```text
python analyzer.py examples/invalid.tfd
```

Exit codes: **0** lexical success, **1** lexical/source errors, **2** command,
path or output errors. Invalid lexemes still appear in the report. Run the
complete example again to restore the valid table. Expected byte-exact tables
for both examples are under `expected/`; tests create fresh reports.

## Output and recognition

The report has exactly two tab-separated columns: **TOKEN TYPE** and **LEXEME**.
Rows retain source order, including comments and invalid lexemes; whitespace
and EOF are omitted. Each lexeme uses reversible quoted escaping so tabs,
newlines, quotes, backslashes and Unicode remain exact without adding rows or
columns. `json.loads` decodes that column. The file is a UTF-8/LF text table,
not a JSON document. Invalid UTF-8, a BOM or lone CR yields a header-only table
and an original-byte diagnostic. Tokens retain byte and scalar coordinates.

A single handwritten scanner advances through character states. Names advance
through a finite keyword/reserved-name trie during scanning; terminal metadata
is used only at the identifier boundary, so `let` and `letter` remain distinct.
Decimal numbers also use explicit states. There is no regex tokenization,
premade lexer/generator, completed-word lookup, eval or exec. Noise-word context
uses recognized token kinds. Comments and longer operator prefixes take priority.

The analyzer recognizes Int, Float, Bool, Text and Char literals, all 28 keywords,
25 reserved names, and the seven arithmetic/nine Boolean-relational spellings.
`/` denotes real division and `div` integer division; no numerical operation is
executed here. Parsing, name/type checking and source execution are outside this
lexical tool. Numeric ranges are semantic checks; the lexer retains magnitudes.
The complete example ends with standalone vocabulary/boundary fixtures, so it
is a lexical demonstration rather than an executable program. Imports are tokenized
without reading other files.
