---
name: ternfold-lexical-conformance
description: Use for Ternfold lexer, lexical automata, keyword/reserved-word recognition, course symbol table output, comments and invalid token classification.
---

# Lexical automata and course conformance

1. Read `docs/automata.md`, `docs/grammar.md`, `docs/course-requirements.md`, and the precise source snapshot/byte-span contract. Do not confuse DFA recognition with parser nesting/semantic checks.
2. For each token family, document the alphabet classes, start/accept/reject states, maximal-munch priority, and what happens after a prefix of a keyword continues into an identifier (`letx` must be one identifier if allowed). Keywords/reserved names must advance a character DFA/trie during scanning; terminal metadata at the boundary supplies classification. Never use completed-input-word lookup or reserved-spelling set matching.
3. Test single and block comment boundaries (including EOF/unterminated forms), quote escapes, Unicode scalar validity, Char vs Text, four literal categories, `^`, `div`, `from`/`to`, and single/multi-character delimiters. Keep byte spans reproducible on CRLF and Unicode inputs.
4. The course-facing `Symbol Table.txt` is an output/report; its token names must agree with the actual lexer rules. It must not replace structured tokens/diagnostics or redefine language syntax.
5. Add adversarial valid/invalid examples and a deterministic report golden file; verify `.tfd` entry-file policy. Update DFA documentation only when the language specification permits the rule.
6. Show test evidence and course acceptance status. Do not mark DFA diagrams alone as implementing the lexer.

For parser-only behavior, use `ternfold-test-design` instead.

## Authorized numerical/rubric amendment

Mandatory professor clarification: seven arithmetic + - / * % div ^ and nine logical/relational && || ! > < == != >= <= are required operator counts. Accepted ADR 0010 defines real / and finite Float, distinct from integer div. Preserve completed work and use C01 before M08; require executable eleven-item lexical evidence and actual UTF-8 Symbol Table.txt. Historical Int-only passes do not verify new Float or executor/native parity.

S01 standalone classroom output has exactly TOKEN TYPE and LEXEME; detailed internal views remain separate. Keep checklists/review/class documents in the development repository, outside the minimal ZIP/GitHub contents.
