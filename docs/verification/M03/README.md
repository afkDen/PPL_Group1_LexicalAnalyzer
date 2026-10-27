# M03 course lexical artifact

`Symbol Table.txt` is real lexer output for `examples/course/main_io.tfd`, not a
hand-authored table. Regenerate from the repository root with:

```powershell
.venv/Scripts/python.exe -m ternfold tokens examples/course/main_io.tfd --symbol-table "docs/verification/M03/Symbol Table.txt"
```

The command exits 0 and also emits a schema-v1 token dump to stdout. The report
uses original UTF-8 byte offsets, one-based scalar coordinates and explicit
token/trivia/composite views. Noise/reserved overlays are lexical classifications,
not evidence of parsing, scope, type checking or source execution. Exact invalid
report/dump goldens are maintained in `tests/fixtures/lexer/`.
