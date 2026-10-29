# Actual demonstration report rows

Rows are one-based physical lines, including the header as row1. Generated from
the supplied primary and invalid reports; use them to locate sample lexemes.

| Category | Representative lexeme | Primary report rows |
|---|---|---|
| IDENTIFIER | Point | 5, 7, 11, 16, 18 |
| KEYWORD | record | 4, 15, 22, 29, 31 |
| RESERVED_WORD | Int | 9, 13, 27, 30, 32 |
| INT_LITERAL | 0 | 39, 53, 75, 90, 93 |
| FLOAT_LITERAL | 1.25e1 | 127 |
| BOOL_LITERAL | true | 134, 220, 222, 309 |
| TEXT_LITERAL | "negative" | 55, 141 |
| CHAR_LITERAL | 'Ω' | 148 |
| NOISE_WORD | from | 112, 317 |
| LINE_COMMENT | // Ternfold lexical demonstration: every required category. | 2 |
| BLOCK_COMMENT | /* Block comments are included in the table.\n   They stop at the first closing delimiter. */ | 3 |
| PLUS | + | 45, 89 |
| MINUS | - | 94, 160 |
| SLASH | / | 154 |
| STAR | * | 92, 239 |
| PERCENT | % | 169 |
| DIV | div | 162 |
| CARET | ^ | 74, 176 |
| AND_AND | && | 187, 193, 199, 205, 211 |
| OR_OR | \|\| | 221 |
| BANG | ! | 219 |
| GREATER | > | 184 |
| LESS | < | 190 |
| EQUAL_EQUAL | == | 196 |
| BANG_EQUAL | != | 202 |
| GREATER_EQUAL | >= | 52, 208 |
| LESS_EQUAL | <= | 214 |
| LPAREN | ( | 24, 65, 79, 87, 100 |
| RPAREN | ) | 28, 69, 83, 91, 101 |
| LBRACKET | [ | 104, 265, 320 |
| RBRACKET | ] | 106, 271, 330 |
| LBRACE | { | 6, 17, 33, 72, 86 |
| RBRACE | } | 14, 21, 62, 76, 96 |
| COMMA | , | 10, 19, 234, 267, 269 |
| SEMICOLON | ; | 40, 47, 56, 61, 114 |
| COLON | : | 8, 12, 26, 36, 67 |
| DOT | . | 50, 59 |
| DOUBLE_COLON | :: | 287, 294, 305 |
| ARROW | -> | 70, 84, 102 |
| FAT_ARROW | => | 299, 307 |

Invalid demonstration report: INVALID rows 3, 4, 5, 6, 7, 13; expected exit1. Both reports have exactly two tab-separated columns.
