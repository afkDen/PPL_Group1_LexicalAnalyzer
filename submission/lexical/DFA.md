# Character-state recognition

A DFA is (Q, Sigma, delta, start, accepting states). Source is UTF-8 decoded into
Unicode scalars; original byte spans remain attached to every token.

## Names

ASCII letters or underscore start names; ASCII letters/digits/underscore continue.
`NAME_TRANSITIONS` is a finite trie compiled from the fixed 28-keyword and
25-reserved-name inventory plus `_`. Each consumed scalar calls
`name_transition(state, char)`. A missing edge enters the generic identifier
sink (-1), which stays an identifier for the rest of that run. At a boundary,
`NAME_TERMINALS[state]` supplies a keyword kind or reserved flag. Prefix states
alone never accept a keyword prematurely. `_` accepts wildcard; `_a` continues.
No input word is compared with an inventory string or used as a dictionary key.
Inventories construct the automaton once; they are not recognition lookups.

Example: q0 -l-> qL -e-> qLE -t-> qLET (LET accepting). A following `t` leaves
that keyword path and enters the identifier sink: `letter` is one IDENTIFIER.
The same transitions cover every keyword/reserved name, not just examples.
FROM/TO terminals feed a token-kind clause-state adapter: only matching
input...from stdin; and output...to stdout; receive NOISE_WORD. This is lexical
context, not proof of legal main syntax.

## Numbers

States: start0, zero1, integer2, dot3, fraction4, exponent5, exponent-sign6,
exponent-digits7, invalid8. Accept Int in 1/2, Float in 4/7.
0 + zero ->1; 0 + nonzero digit ->2. 2 loops on digits; a digit after1 ->8.
1/2 + dot-before-digit ->3; 3 + digit ->4; 4 loops on digits.
1/2/4 + e/E ->5; 5 + sign ->6; 5/6 + digit ->7; 7 loops on digits.
Any unsupported numeric continuation enters8. Recovery consumes an adjacent
identifier run, exponent sign, or second dot-before-digit without losing later
punctuation/comments. `1.foo` is INT DOT IDENTIFIER; `.5` is DOT INT.
`1e+`, `01`, `1.2.3`, `12abc` each become INVALID. Signs are separate operators.
Float form: `(0|[1-9][0-9]*)(.[0-9]+([eE][+-]?[0-9]+)?|[eE][+-]?[0-9]+)` where
the displayed dot is literal. This notation documents transitions; no regex is run.

## Comments, strings, operators

Slash provisionally accepts SLASH. Next slash enters line-comment state until
LF/CRLF/EOF; next star enters block body, then star state, then slash closes.
The first */ closes; nesting is absent; EOF in the body is INVALID E104.
Quoted Text loops over scalars/approved escapes until a closing quote. Char
accepts exactly one decoded scalar. Raw controls, bad escapes, cardinality and
missing closers are E103/E105. Escapes are ", \\, \n, \r, \t, \u{hex} with
1–6 hex digits, scalar <=10FFFF excluding surrogates.

Operator prefix transitions choose ::, ->, =>, ==, !=, <=, >=, &&, ||, ++ before
single punctuation; comments precede slash/star. A lone & or | is INVALID E101.
Exactly seven arithmetic and nine Boolean/relational spellings are tested
independently. No premade analyzer, generator, word matcher or regex is used.
