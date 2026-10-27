# C17 compiler pipeline

All implementation stages target ISO C17 (ADR 0011).
Source → tokens → AST → resolved program → typed program → machine plan →
verified Core → interpreter / structured C17 backend + runtime.

Current executable: `build/ternfold-lexer[.exe] source.tfd [--output-dir DIR]`.
It accepts only exact .tfd extensions, snapshots/validates UTF-8, scans using
character transitions, emits structured lexical diagnostics and atomically
publishes Symbol Table.txt. Exit 0 valid, 1 source/lexical error, 2 usage/host error.
The output directory must already exist. Source and report must not alias.

Later inspection/check/run/compile/REPL commands remain pending in M04–M17.
No current command claims to type-check, interpret or compile Ternfold programs.
Each future command stops at a declared phase and refuses execution after errors.
Only the verified-Core handle can enter either executor. Rich inspection output
must stay distinct from the exactly two-column classroom lexical report.
