# C17 implementation target (ADR0011)

# Concrete grammar — Ternfold 0.2 course-aligned target

Normative EBNF. `{ X }` means repetition, `[ X ]` optional, `|` alternatives, quoted strings terminals. Lexical tokens are defined by language-spec.md. Trivia occurs between tokens and is discarded, retaining spans. `IDENT` excludes keywords and standalone `_`. Lists permit one trailing comma only where `comma-list` is used. The empty alternative is written `ε`.

```ebnf
program       = { import-decl }, { declaration }, EOF ;
import-decl   = "import", STRING, "as", IDENT, ";" ;
declaration   = [ "pub" ], ( function | record | enum | machine ) ;
function      = "fn", IDENT, parameters, "->", type, block ;
parameters    = "(", [ parameter, { ",", parameter }, [ "," ] ], ")" ;
parameter     = IDENT, ":", type ;
record        = "record", IDENT, "{", [ field, { ",", field }, [ "," ] ], "}" ;
field         = IDENT, ":", type ;
enum          = "enum", IDENT, "{", variant, { ",", variant }, [ "," ], "}" ;
variant       = IDENT, [ "(", type, { ",", type }, [ "," ], ")" ] ;
machine       = "machine", IDENT, "(", parameter, ")", "yields", type,
                "rejects", type, "{", state, { state }, writer, { writer },
                { guard }, { emission }, "}" ;
state         = "state", IDENT, ":", type, "=", expression, ";" ;
writer        = "next", IDENT, "=", expression, ";" ;
guard         = "guard", expression, "else", expression, ";" ;
emission      = "emit", expression, ";" ;
type          = path, [ "[", type, { ",", type }, "]" ]
              | "fn", "(", [ type, { ",", type } ], ")", "->", type ;
path          = IDENT, { "::", IDENT } ;
block         = "{", { binding }, expression, "}" ;
main-block    = "{", { binding | input-clause | output-clause }, expression, "}" ;
input-clause  = "input", IDENT, ":", "Text", [ "from", "stdin" ], ";" ;
output-clause = "output", expression, [ "to", "stdout" ], ";" ;
binding       = "let", binder, [ ":", type ], "=", expression, ";" ;
binder        = IDENT | "_" ;
expression    = disjunction ;
disjunction   = conjunction, { "||", conjunction } ;
conjunction   = equality, { "&&", equality } ;
equality      = comparison, [ ( "==" | "!=" ), comparison ] ;
comparison    = addition, [ ( "<" | "<=" | ">" | ">=" ), addition ] ;
addition      = product, { ( "+" | "-" | "++" ), product } ;
product       = unary, { ( "*" | "/" | "div" | "%" ), unary } ;
unary         = ( "-" | "!" ), unary | power ;
power         = postfix, [ "^", unary ] ;
postfix       = primary, { arguments | ".", IDENT } ;
arguments     = "(", [ argument, { ",", argument }, [ "," ] ], ")" ;
argument      = [ IDENT, ":" ], expression ;
primary       = INT | FLOAT | STRING | CHAR | "true" | "false" | path
              | "next", ".", IDENT
              | "(", [ expression ], ")"
              | "[", [ expression, { ",", expression }, [ "," ] ], "]"
              | block | conditional | matching | closure | for-expression ;
for-expression = "for", IDENT, "in", expression, block ;
conditional   = "if", expression, block, "else", block ;
matching      = "match", expression, "{", arm, { ",", arm }, [ "," ], "}" ;
arm           = pattern, "=>", block ;
pattern       = "_" | IDENT | "true" | "false" | [ "-" ], ( INT | FLOAT ) | STRING | CHAR | "(", ")"
              | variant-path, [ "(", pattern, { ",", pattern }, [ "," ], ")" ] ;
variant-path  = IDENT, "::", IDENT, { "::", IDENT } ;
closure       = "fn", parameters, "->", type, block ;
```

## Context constraints that are not grammar shortcuts

- `List`, `Option`, `Decision` have arities 1, 1, 3; other type paths cannot take arguments. No user generics.
- Machine headers have exactly one input. Pair/grouped input uses a record. No trailing comma in the machine header.
- Call named arguments are syntactically recognized by two-token lookahead (`IDENT :`). Only record construction accepts them; records reject positional arguments, all other calls reject named ones. Mixed argument kinds are E112.
- `()` is Unit, not a tuple. Parentheses hold at most one expression. No tuple types.
- Paths of arbitrary length parse; resolution limits meaningful paths to `alias::symbol`, `Enum::Variant`, or `alias::Enum::Variant`. Bare IDENT in a pattern is always a new binder, never a nullary variant.
- Signed Int and Float patterns preserve separate minus/literal spans. Float
  patterns denote rounded finite values and require a residual wildcard/binder.
  Equal rounded values, including normalized zeros, are duplicate coverage. The type checker
  applies the same contiguous-minus minimum-Int exception as expressions;
  whitespace/comments before that otherwise oversized magnitude do not grant
  the exception. Ordinary smaller negative patterns remain free-field.
- Generic prelude constructors are resolved by their qualifier and context; no explicit expression-level type application syntax.
- State initializers parse as expressions, then the constant-expression checker restricts their form.
- Blocks require a final expression. A semicolon after that expression is a syntax error; add `let _ = expression; ()` for an intentional discard.
- `next.x.y` parses as projection `y` on the candidate cell `x`. Graph extraction adds the dependency on x.
- Because record construction uses parentheses, `if x { ... }` is unambiguous. `{` is not a postfix form.
- `guard if ... else ... else Error;` is legal with the inner conditional's braces consuming its own else; formatter should parenthesize it for readability.

## Handwritten parser design

Recursive descent owns declarations, blocks, types, patterns, and machine sections. A Pratt loop owns unary/binary/postfix expression forms using the spec table (primary constructs have their own parse routines). Pratt must track whether a non-associative comparison/equality operator has already occurred at its level, rather than accidentally accepting chains. Implementing the EBNF levels with precedence climbing is an acceptable internal refactor; behavior and recovery stay identical.

Recovery synchronizes at `;`, `}`, or a top-level declaration/import keyword at brace depth zero. Recoverable AST error nodes retain skipped spans but never enter name resolution/Core. For a missing delimiter, synthesize a zero-width missing token at the insertion point and record E110; do not consume a following declaration that clearly belongs to the caller. Each recovery loop must consume a token or return, with a diagnostic cap of 100 per file plus one suppression note. Unterminated strings synchronize at newline/EOF. EOF has a valid zero-width source span. Test adjacent errors and malformed nested blocks, not just single-error files.

## Revision 2 grammar constraints

- `function = ... block` is replaced by `function = ... (main-block if the declaration is the public zero-argument main entrypoint, else block)` at AST validation time. `main-block` clauses cannot appear in regular functions, machines, closures, loop blocks, or nested blocks; emit E208. `input-clause`/`output-clause` are semicolon-terminated before the mandatory final `List[Text]` expression. The lexer treats `stdin`, `stdout`, `from`, `to` as reserved keyword-like tokens; the two optional phrases must occur together, not as partial words. The `input` name cannot be `_` or a reserved name.
- `for-expression` is not a statement that mutates values. Its body is an ordinary block with a final expression; the loop binder cannot be `_` (use a named binding). Type checker requires a list iterable and yields a list of body result type. Nested loops require no separate production. Parsing `for` in the right-hand side of a binary expression follows the same primary-expression strategy as `if`/`match`.
- `power` binds more tightly than unary minus and associates rightward: `2 ^ 3 ^ 2` parses as `2 ^ (3 ^ 2)` and `-2 ^ 2` as `-(2 ^ 2)`; `2 ^ -1` parses and faults R005 for an Int base; `2.0 ^ -1` is Float 0.5. `/`, `div`, and `%` share left-associative product precedence.
- `CHAR` is one Unicode scalar delimited by `'` and follows the String escape repertoire. Bad character literals are E105. `/*...*/` is a non-nesting block comment; `//` remains a line comment. Longest-match comment detection takes precedence over `/` and `*` standalone operators.
- The extra source-level clauses must lower to explicit hidden Core input-snapshot and output-buffer operations; no ambient I/O is permitted in general expressions. One production parser may accept syntactically valid clauses in an arbitrary block for better E208 reporting, but successful checked ASTs must obey entrypoint scoping.
- `function` remains unchanged for existing 0.1 programs; the specialized `main-block` syntax extends only main. Examples in `examples/course/` are **revision-2 target fixtures**, not executable until their owning milestones pass.

## Numeric lexical terminal contract (ADR 0010)

`INT = 0 | [1-9][0-9]*`. `FLOAT` matches
`(0|[1-9][0-9]*)(\.[0-9]+([eE][+-]?[0-9]+)?|[eE][+-]?[0-9]+)`.
Signs are separate tokens; a dot joins a numeral only before a digit. Numeric
suffix/exponent/second-fraction recovery is specified in language-spec.md and
automata.md, with E102 before range checks. Type checking, not lexing, enforces
finite binary64 values (E301); literals retain original lexeme and byte spans.

## Approved I/O-bearing main reference boundary

A root public `main` with any outer input/output clause is host-entry-only.
Source references to its resolved symbol are E208 (calls, function values,
recursion, closure/machine references); the generated adapter is not nameable.
A main without I/O remains callable. Apply the rule by identity, preserving
shadowed/unrelated names. Human-approved clarification is recorded in ADR 0009;
C entry-boundary regressions are required in the owning implementation milestone.
