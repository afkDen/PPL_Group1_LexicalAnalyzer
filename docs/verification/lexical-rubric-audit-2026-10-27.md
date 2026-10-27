# Read-only eleven-item lexical audit — 2026-10-27

Provenance: human-authorized sidechat `01a17cbc-8b6b-7aa3-a196-329fe5c632b7`.
The auditor changed no files, selected no numerical semantics, contacted no
agents and advanced no acceptance claims. Supervisor persisted this handoff.
Platform: Windows, Python 3.14.4. No fresh POSIX/native/executor claim.

## Fresh observed evidence

- `.venv/Scripts/python.exe -B -m pytest tests/test_lexer.py -q -p
  no:cacheprovider -k 'not fuzz_scanner and not generated_text'`: 278 passed,
  two explicitly deselected property tests, 0.57 seconds. Full/CLI/property
  suites and package build were not rerun by this audit.
- Independent in-memory probes passed: exact seven arithmetic and nine logical/
  relational token kinds, report categories and byte endpoints; 28 keyword
  continuation boundaries; 21 reserved overlays/prefix boundaries; three live
  wrong-extension CLI calls returning 2; 150 INVALID tokens/report rows with
  50 suppressed diagnostics at cap 100 and a blocked parser; all 21 examples
  lexed; 300 deterministic malformed Unicode/CRLF inputs (seed 27011) preserved
  byte coverage, progress, EOF and diagnostic bounds.
- Both saved reports matched fresh in-memory render bytes and independent TSV
  byte-slice/line/scalar-coordinate checks. No report was newly published to
  disk by this read-only audit; committed CLI tests establish publication.
  `tests/fixtures/lexer/Symbol Table.txt`: 2673 bytes, 53 rows, SHA-256
  `fefcb35656f5740476d01611a60061a70aa82e8b5f2600593f49a453b7f1657f`.
  `docs/verification/M03/Symbol Table.txt`: 7000 bytes, 141 rows, SHA-256
  `773827f917d033b9f254cd8b3e1e22a5744bd2b47350f5f0087f915786744a52`.
  UTF-8/LF, no BOM; the M03 report matches main_io.tfd. Token JSON golden
  also matched byte-for-byte.

## Mandatory checklist reconciliation

| Item | Existing executable evidence | Amendment obligation |
|---|---|---|
| Only .tfd | Tokens CLI extension test covers txt/TFD/no suffix; module import spelling tests; three fresh CLI probes | Carry into future run/build |
| Identifiers | Every keyword continuation and adjacency tests; ASCII starts/continuations, wildcard and unsupported Unicode | New reserved-name prefix boundaries |
| Keywords | Fixed 28-name inventory and parameterized boundaries; div and Bool payloads | Preserve exact whole-word recognition |
| Reserved words | Fixed 21-name inventory and IDENT/report overlay; resolution namespace tests | Add Float/conversions coherently if selected |
| At least four literal kinds | Int/Bool/Text/Char valid/invalid/Unicode/cardinality tests and actual reports; Unit is additional composite view | New Float lexer/AST/type/report tests if selected; replace old 1.5 split expectation |
| from/to noise | Contextual lexical clause-shape tests include nesting, trivia and mismatches | Preserve distinction between overlay and parser validity |
| Line/block comments | EOF/CRLF/nonnesting/unterminated whole-run and report tests | Numeric slash/comment adjacency |
| Seven arithmetic + nine logical/relational | Exact seven and nine kinds/categories/endpoints independently probed; operator/keyword tests | Real division semantics absent; add explicit fixed-count regression and all16 source/report demo |
| Delimiters/brackets | Independent tokens for punctuation, paired delimiters and longest match | Float dot versus member projection boundaries |
| INVALID/recovery | E101–E105, cap-zero/all-token retention, raw-source diagnostics, CLI report/diagnostics; 300 fresh progress probes | Explicit malformed Float run recovery boundaries |
| Actual Symbol Table.txt | CLI atomic publication/error preservation/hash-seed goldens, hardlink/pipe tests; two saved files freshly matched | Float rows and representative all16 report; explicit filename option is documented |

Existing spelling sets are precisely arithmetic `{PLUS, MINUS, SLASH, STAR,
PERCENT, DIV, CARET}` and Boolean/relational `{AND_AND, OR_OR, BANG, GREATER,
LESS, EQUAL_EQUAL, BANG_EQUAL, GREATER_EQUAL, LESS_EQUAL}`. Assignment, arrows
and `++` do not count toward either total. Recognition is implemented; real
numeric division and executor short-circuiting are not yet verified.

## Concrete missing work

Current course examples collectively omit `/`, `%` and all nine logical/
relational spellings; add a representative `.tfd` demonstration containing all
16 with exact independent token/span/category assertions and an actual report.
Update numeric literal DFA/regex and dot/exponent recovery only after ADR
selection. Extend ledger/audit compatibility beyond specified/implemented/
verified to tested/reviewed/blocked while separating lexical recognition,
numerical typing and execution evidence. Existing relational verification is
for the earlier Int-only contract; it cannot imply new Float parity.

Treat changes as targeted C01 amendments before M08. Preserve M03–M06 history,
the active M07 writer, UTF-8/LF and argv/path safety, and honest platform limits.
