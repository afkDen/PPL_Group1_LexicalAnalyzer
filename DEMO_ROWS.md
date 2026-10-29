# Generated primary demonstration rows

One-based physical report rows include the header as row1. These are actual generated rows for complete.tfd, not words extracted from comments/strings. Full per-spelling source lines and rows are in PROPOSAL_LEXICAL_RECONCILIATION.md.

| Report category | First actual lexeme (escaped) | Report rows (first five) |
|---|---|---|
| KEYWORD | `import` | 2, 4, 9, 20, 27 |
| TEXT_LITERAL | `"support.tfd"` | 3, 60, 146, 455, 524 |
| IDENTIFIER | `helper` | 5, 10, 12, 16, 21 |
| SEMICOLON | `;` | 6, 45, 52, 61, 66 |
| LINE_COMMENT | `// Ternfold lexical demonstration: every current keyword and reserved name.` | 7 |
| BLOCK_COMMENT | `/* Block comments are included in the table.\n   They stop at the first closing delimiter. */` | 8 |
| LBRACE | `{` | 11, 22, 38, 77, 91 |
| COLON | `:` | 13, 17, 31, 41, 72 |
| RESERVED_WORD | `Int` | 14, 18, 32, 35, 37 |
| COMMA | `,` | 15, 24, 240, 273, 275 |
| RBRACE | `}` | 19, 26, 67, 81, 101 |
| LPAREN | `(` | 29, 70, 84, 92, 105 |
| RPAREN | `)` | 33, 74, 88, 96, 106 |
| ASSIGN | `=` | 43, 48, 124, 131, 138 |
| INT_LITERAL | `0` | 44, 58, 80, 95, 98 |
| PLUS | `+` | 50, 94, 440 |
| DOT | `.` | 55, 64 |
| GREATER_EQUAL | `>=` | 57, 214 |
| ARROW | `->` | 75, 89, 107, 436 |
| CARET | `^` | 79 |
| STAR | `*` | 97, 245 |
| MINUS | `-` | 99, 165 |
| LBRACKET | `[` | 109, 271, 333, 374, 389 |
| RBRACKET | `]` | 111, 277, 335, 376, 391 |
| NOISE_WORD | `from` | 117, 583 |
| FLOAT_LITERAL | `1.25e1` | 132 |
| BOOL_LITERAL | `true` | 139, 226, 228, 366 |
| CHAR_LITERAL | `'Ω'` | 153 |
| SLASH | `/` | 159 |
| DIV | `div` | 167 |
| PERCENT | `%` | 174 |
| GREATER | `>` | 190 |
| AND_AND | `&&` | 193, 199, 205, 211, 217 |
| LESS | `<` | 196 |
| EQUAL_EQUAL | `==` | 202 |
| BANG_EQUAL | `!=` | 208 |
| LESS_EQUAL | `<=` | 220 |
| BANG | `!` | 225 |
| OR_OR | `\|\|` | 227 |
| DOUBLE_COLON | `::` | 297, 316, 338, 351, 362 |
| FAT_ARROW | `=>` | 304, 323, 356, 364, 514 |
| UNDERSCORE | `_` | 570 |
| PLUS_PLUS | `++` | 581 |

The primary contains28keyword tokens by spelling (Bool words report BOOL_LITERAL, div reports DIV, contextual connectors report NOISE_WORD),25reserved spellings,31other symbol spellings and all five literal families. Original invalid.tfd and invalid-comprehensive.tfd reports are in tests/fixtures/lexer and tests/fixtures/invalid respectively. Header-only encoding-error reports are expected and are mapped in INVALID_CASES.md. Rerun complete after any invalid demo to restore the primary report.
