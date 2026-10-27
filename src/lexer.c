#include "internal.h"

#include <string.h>

typedef struct { const char *spelling; TfTokenKind kind; bool reserved; } Name;
/* This fixed inventory builds edges. It is NEVER searched with an input word. */
static const Name names[] = {
    {"as", TF_AS, false}, {"div", TF_DIV, false}, {"else", TF_ELSE, false},
    {"emit", TF_EMIT, false}, {"enum", TF_ENUM, false}, {"false", TF_FALSE, false},
    {"fn", TF_FN, false}, {"for", TF_FOR, false}, {"from", TF_FROM, false},
    {"guard", TF_GUARD, false}, {"if", TF_IF, false}, {"import", TF_IMPORT, false},
    {"in", TF_IN, false}, {"input", TF_INPUT, false}, {"let", TF_LET, false},
    {"machine", TF_MACHINE, false}, {"match", TF_MATCH, false}, {"next", TF_NEXT, false},
    {"output", TF_OUTPUT, false}, {"pub", TF_PUB, false}, {"record", TF_RECORD, false},
    {"rejects", TF_REJECTS, false}, {"state", TF_STATE, false}, {"stdin", TF_STDIN, false},
    {"stdout", TF_STDOUT, false}, {"to", TF_TO, false}, {"true", TF_TRUE, false},
    {"yields", TF_YIELDS, false},
    {"Int", TF_IDENT, true}, {"Float", TF_IDENT, true}, {"Bool", TF_IDENT, true},
    {"Text", TF_IDENT, true}, {"Char", TF_IDENT, true}, {"Unit", TF_IDENT, true},
    {"List", TF_IDENT, true}, {"Option", TF_IDENT, true}, {"Decision", TF_IDENT, true},
    {"step", TF_IDENT, true}, {"len", TF_IDENT, true}, {"at", TF_IDENT, true},
    {"append", TF_IDENT, true}, {"map", TF_IDENT, true}, {"fold", TF_IDENT, true},
    {"range", TF_IDENT, true}, {"int_text", TF_IDENT, true}, {"bool_text", TF_IDENT, true},
    {"parse_int", TF_IDENT, true}, {"text_len", TF_IDENT, true}, {"text_at", TF_IDENT, true},
    {"text_slice", TF_IDENT, true}, {"int_float", TF_IDENT, true},
    {"float_int", TF_IDENT, true}, {"float_text", TF_IDENT, true},
    {"_", TF_UNDERSCORE, false}
};

/* Sparse trie: siblings are outgoing character edges of one state. State zero
 * is root; SIZE_MAX is an absorbing generic-identifier sink. At most the sum
 * of the inventory lengths + root states are needed; capacity checked below. */
enum { TRIE_CAPACITY = 512 };
typedef struct {
    size_t child, sibling;
    unsigned char character;
    TfTokenKind kind;
    bool reserved;
} NameState;
typedef struct { NameState states[TRIE_CAPACITY]; size_t count; } NameDfa;

static size_t name_step(const NameDfa *dfa, size_t state, unsigned char character) {
    size_t edge;
    if (state == SIZE_MAX) return SIZE_MAX;
    edge = dfa->states[state].child;
    while (edge != 0) {
        if (dfa->states[edge].character == character) return edge;
        edge = dfa->states[edge].sibling;
    }
    return SIZE_MAX;
}
static bool name_dfa_init(NameDfa *dfa) {
    size_t n;
    *dfa = (NameDfa){0};
    dfa->count = 1;
    dfa->states[0].kind = TF_IDENT;
    for (n = 0; n < sizeof(names) / sizeof(names[0]); ++n) {
        size_t at = 0, state = 0;
        while (names[n].spelling[at] != '\0') {
            unsigned char character = (unsigned char)names[n].spelling[at++];
            size_t next = name_step(dfa, state, character);
            if (next == SIZE_MAX) {
                if (dfa->count == TRIE_CAPACITY) return false;
                next = dfa->count++;
                dfa->states[next] = (NameState){0, dfa->states[state].child,
                                               character, TF_IDENT, false};
                dfa->states[state].child = next;
            }
            state = next;
        }
        dfa->states[state].kind = names[n].kind;
        dfa->states[state].reserved = names[n].reserved;
    }
    return true;
}
static bool letter(unsigned char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
}
static bool digit(unsigned char c) { return c >= '0' && c <= '9'; }
static bool whitespace(unsigned char c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }

/* Decimal states: start, zero, integer, dot, fraction, exponent,
 * exponent-sign, exponent-digits, invalid sink. Numeric recovery continues
 * through letters/digits, digit-followed dots, and signs immediately after e/E.
 * This preserves punctuation/comment boundaries even in the invalid sink. */
typedef enum { N_START, N_ZERO, N_INT, N_DOT, N_FRAC, N_EXP, N_SIGN, N_DIGITS, N_BAD } NumberState;
static NumberState number_step(NumberState state, unsigned char c) {
    switch (state) {
        case N_START: return c == '0' ? N_ZERO : digit(c) ? N_INT : N_BAD;
        case N_ZERO: return c == '.' ? N_DOT : (c == 'e' || c == 'E') ? N_EXP : N_BAD;
        case N_INT: return digit(c) ? N_INT : c == '.' ? N_DOT :
                           (c == 'e' || c == 'E') ? N_EXP : N_BAD;
        case N_DOT: return digit(c) ? N_FRAC : N_BAD;
        case N_FRAC: return digit(c) ? N_FRAC : (c == 'e' || c == 'E') ? N_EXP : N_BAD;
        case N_EXP: return digit(c) ? N_DIGITS : (c == '+' || c == '-') ? N_SIGN : N_BAD;
        case N_SIGN: case N_DIGITS: return digit(c) ? N_DIGITS : N_BAD;
        case N_BAD: return N_BAD;
    }
    return N_BAD;
}

static bool emit(TfLexResult *result, TfToken token, size_t cap) {
    void *storage = result->tokens;
    if (result->token_count == SIZE_MAX ||
        !tf_grow(&storage, &result->token_capacity, result->token_count + 1,
                 sizeof(TfToken), result->allocator)) return false;
    result->tokens = storage;
    result->tokens[result->token_count++] = token;
    if (token.error != TF_E_NONE) {
        result->has_errors = true;
        if (result->diagnostic_count < cap) {
            storage = result->diagnostics;
            if (!tf_grow(&storage, &result->diagnostic_capacity, result->diagnostic_count + 1,
                         sizeof(TfDiagnostic), result->allocator)) return false;
            result->diagnostics = storage;
            result->diagnostics[result->diagnostic_count++] = (TfDiagnostic){token.error, token.span};
        } else ++result->suppressed;
    }
    return true;
}

static int hex_digit(unsigned char c) {
    if (c >= '0' && c <= '9') return (int)(c - '0');
    if (c >= 'a' && c <= 'f') return (int)(c - 'a') + 10;
    if (c >= 'A' && c <= 'F') return (int)(c - 'A') + 10;
    return -1;
}
/* Called just after backslash. Never consumes raw CR/LF, a quote or arbitrary
 * scalar on behalf of a malformed Unicode brace body. The outer literal DFA
 * owns recovery through closing quote/newline/EOF. */
static bool escape(const TfSource *source, size_t *at, uint32_t *scalar) {
    unsigned char c;
    size_t count = 0;
    uint32_t value = 0;
    if (*at == source->length || source->bytes[*at] == '\r' || source->bytes[*at] == '\n')
        return false;
    c = source->bytes[(*at)++];
    switch (c) {
        case '"': *scalar = '"'; return true;
        case '\\': *scalar = '\\'; return true;
        case 'n': *scalar = '\n'; return true;
        case 'r': *scalar = '\r'; return true;
        case 't': *scalar = '\t'; return true;
        case 'u': break;
        default:
            /* Unsupported non-ASCII escape still consumes a complete scalar. */
            if (c >= 0x80) {
                size_t end;
                (void)tf_decode(source->bytes, source->length, *at - 1, scalar, &end);
                *at = end;
            }
            return false;
    }
    if (*at == source->length || source->bytes[*at] != '{') return false;
    ++*at;
    while (*at < source->length) {
        int h = hex_digit(source->bytes[*at]);
        if (h < 0) break;
        if (count < 6) value = value * 16u + (uint32_t)h;
        ++count;
        ++*at;
    }
    if (*at == source->length || source->bytes[*at] != '}') return false;
    ++*at;
    if (count == 0 || count > 6 || value > 0x10ffffu ||
        (value >= 0xd800u && value <= 0xdfffu)) return false;
    *scalar = value;
    return true;
}
static size_t encode(uint32_t scalar, unsigned char bytes[4]) {
    if (scalar < 0x80u) { bytes[0] = (unsigned char)scalar; return 1; }
    if (scalar < 0x800u) {
        bytes[0] = (unsigned char)(0xc0u | (scalar >> 6));
        bytes[1] = (unsigned char)(0x80u | (scalar & 0x3fu));
        return 2;
    }
    if (scalar < 0x10000u) {
        bytes[0] = (unsigned char)(0xe0u | (scalar >> 12));
        bytes[1] = (unsigned char)(0x80u | ((scalar >> 6) & 0x3fu));
        bytes[2] = (unsigned char)(0x80u | (scalar & 0x3fu));
        return 3;
    }
    bytes[0] = (unsigned char)(0xf0u | (scalar >> 18));
    bytes[1] = (unsigned char)(0x80u | ((scalar >> 12) & 0x3fu));
    bytes[2] = (unsigned char)(0x80u | ((scalar >> 6) & 0x3fu));
    bytes[3] = (unsigned char)(0x80u | (scalar & 0x3fu));
    return 4;
}
static bool quoted(TfLexResult *result, size_t *at, TfToken *token) {
    const TfSource *source = result->source;
    unsigned char quote = source->bytes[(*at)++];
    void *data = NULL;
    size_t length = 0, capacity = 0, count = 0;
    bool closed = false, bad = false;
    while (*at < source->length) {
        uint32_t scalar;
        size_t end, width;
        unsigned char encoded[4];
        unsigned char c = source->bytes[*at];
        if (c == '\r' || c == '\n') break;
        if (c == quote) { ++*at; closed = true; break; }
        if (c == '\\') {
            ++*at;
            if (!escape(source, at, &scalar)) { bad = true; continue; }
        } else {
            (void)tf_decode(source->bytes, source->length, *at, &scalar, &end);
            *at = end;
            if (scalar < 32u || scalar == 127u) { bad = true; continue; }
        }
        ++count;
        width = encode(scalar, encoded);
        if (!bad) {
            if (length > SIZE_MAX - width ||
                !tf_grow(&data, &capacity, length + width, 1, result->allocator)) {
                if (data != NULL) result->allocator.deallocate(result->allocator.context, data);
                return false;
            }
            memcpy((unsigned char *)data + length, encoded, width);
            length += width;
        }
    }
    token->span.end = *at;
    if (bad || !closed || (quote == '\'' && count != 1)) {
        if (data != NULL) result->allocator.deallocate(result->allocator.context, data);
        token->kind = TF_INVALID;
        token->error = quote == '"' ? TF_E103 : TF_E105;
    } else {
        token->kind = quote == '"' ? TF_TEXT : TF_CHAR;
        token->value = data;
        token->value_length = length;
    }
    return true;
}

static TfTokenKind operator_kind(unsigned char first, unsigned char second, size_t *width) {
    *width = 2;
    switch (first) {
        case ':': if (second == ':') return TF_DOUBLE_COLON; break;
        case '-': if (second == '>') return TF_ARROW; break;
        case '=': if (second == '>') return TF_FAT_ARROW;
                  if (second == '=') return TF_EQUAL_EQUAL; break;
        case '!': if (second == '=') return TF_BANG_EQUAL; break;
        case '<': if (second == '=') return TF_LESS_EQUAL; break;
        case '>': if (second == '=') return TF_GREATER_EQUAL; break;
        case '&': if (second == '&') return TF_AND_AND; break;
        case '|': if (second == '|') return TF_OR_OR; break;
        case '+': if (second == '+') return TF_PLUS_PLUS; break;
        case '*': if (second == '/') return TF_BLOCK_CLOSE; break;
        default: break;
    }
    *width = 1;
    switch (first) {
        case '+': return TF_PLUS; case '-': return TF_MINUS;
        case '*': return TF_STAR; case '/': return TF_SLASH;
        case '%': return TF_PERCENT; case '^': return TF_CARET;
        case '<': return TF_LESS; case '>': return TF_GREATER;
        case '=': return TF_EQUAL; case '!': return TF_BANG;
        case '.': return TF_DOT; case ',': return TF_COMMA;
        case ';': return TF_SEMICOLON; case ':': return TF_COLON;
        case '(': return TF_LPAREN; case ')': return TF_RPAREN;
        case '[': return TF_LBRACKET; case ']': return TF_RBRACKET;
        case '{': return TF_LBRACE; case '}': return TF_RBRACE;
        default: return TF_INVALID;
    }
}

TfStatus tf_lex(TfLexResult *out, const TfSource *source, size_t diagnostic_cap,
                const TfAllocator *allocator) {
    NameDfa dfa;
    size_t at = 0;
    if (out == NULL) return TF_HOST_ERROR;
    *out = (TfLexResult){0};
    out->allocator = tf_allocator(allocator);
    if (source == NULL || !source->valid || out->allocator.allocate == NULL ||
        out->allocator.deallocate == NULL ||
        !name_dfa_init(&dfa)) goto fail;
    out->source = source;
    while (at < source->length) {
        unsigned char first = source->bytes[at];
        unsigned char second = source->length - at >= 2 ? source->bytes[at + 1] : 0;
        TfToken token = {TF_INVALID, {source, at, at}, TF_E_NONE, false, NULL, 0};
        if (whitespace(first)) { ++at; continue; }
        if (first == '/' && second == '/') {
            at += 2;
            while (at < source->length && source->bytes[at] != '\r' && source->bytes[at] != '\n') ++at;
            token.kind = TF_COMMENT_LINE;
        } else if (first == '/' && second == '*') {
            bool closed = false;
            at += 2;
            while (at < source->length) {
                if (source->length - at >= 2 && source->bytes[at] == '*' && source->bytes[at + 1] == '/') {
                    at += 2;
                    closed = true;
                    break;
                }
                ++at;
            }
            if (closed) token.kind = TF_COMMENT_BLOCK;
            else token.error = TF_E104;
        } else if (letter(first)) {
            size_t state = 0;
            do {
                state = name_step(&dfa, state, source->bytes[at++]);
            } while (at < source->length && (letter(source->bytes[at]) || digit(source->bytes[at])));
            token.kind = state == SIZE_MAX ? TF_IDENT : dfa.states[state].kind;
            token.reserved = state != SIZE_MAX && dfa.states[state].reserved;
        } else if (digit(first)) {
            NumberState state = number_step(N_START, first);
            ++at;
            while (at < source->length) {
                unsigned char c = source->bytes[at];
                if (letter(c) || digit(c) ||
                    (c == '.' && source->length - at >= 2 && digit(source->bytes[at + 1])) ||
                    ((c == '+' || c == '-') && (source->bytes[at - 1] == 'e' || source->bytes[at - 1] == 'E'))) {
                    state = number_step(state, c);
                    ++at;
                } else break;
            }
            if (state == N_ZERO || state == N_INT) token.kind = TF_INT;
            else if (state == N_FRAC || state == N_DIGITS) token.kind = TF_FLOAT;
            else token.error = TF_E102;
        } else if (first == '"' || first == '\'') {
            if (!quoted(out, &at, &token)) goto fail;
        } else {
            size_t width;
            token.kind = operator_kind(first, second, &width);
            if (token.kind == TF_INVALID) {
                uint32_t scalar;
                (void)tf_decode(source->bytes, source->length, at, &scalar, &at);
                token.error = TF_E101;
            } else at += width;
        }
        token.span.end = at;
        if (token.kind == TF_IDENT || token.kind == TF_INT || token.kind == TF_FLOAT) {
            token.value = source->bytes + token.span.start;
            token.value_length = at - token.span.start;
        }
        {
            size_t previous = out->token_count;
            if (!emit(out, token, diagnostic_cap)) {
                /* If token insertion failed, its decoded value is still local.
                 * If diagnostic insertion failed, the result owns it already. */
                if (out->token_count == previous && (token.kind == TF_TEXT || token.kind == TF_CHAR) &&
                    token.value != NULL)
                    out->allocator.deallocate(out->allocator.context, (void *)token.value);
                goto fail;
            }
        }
    }
    {
        TfToken eof = {TF_EOF, {source, at, at}, TF_E_NONE, false, NULL, 0};
        if (!emit(out, eof, diagnostic_cap)) goto fail;
    }
    return out->has_errors ? TF_LEX_ERROR : TF_OK;
fail:
    tf_lex_destroy(out);
    return TF_HOST_ERROR;
}
void tf_lex_destroy(TfLexResult *result) {
    size_t i;
    if (result == NULL) return;
    if (result->allocator.deallocate != NULL) {
        for (i = 0; i < result->token_count; ++i) {
            TfToken *token = &result->tokens[i];
            if ((token->kind == TF_TEXT || token->kind == TF_CHAR) && token->value != NULL)
                result->allocator.deallocate(result->allocator.context, (void *)token->value);
        }
        if (result->tokens != NULL)
            result->allocator.deallocate(result->allocator.context, result->tokens);
        if (result->diagnostics != NULL)
            result->allocator.deallocate(result->allocator.context, result->diagnostics);
    }
    *result = (TfLexResult){0};
}

const char *tf_token_name(TfTokenKind kind) {
    static const char *const labels[] = {
        "IDENT", "INT", "FLOAT", "TEXT", "CHAR", "UNDERSCORE", "INVALID", "EOF",
        "AS", "DIV", "ELSE", "EMIT", "ENUM", "FALSE", "FN", "FOR", "FROM", "GUARD",
        "IF", "IMPORT", "IN", "INPUT", "LET", "MACHINE", "MATCH", "NEXT", "OUTPUT",
        "PUB", "RECORD", "REJECTS", "STATE", "STDIN", "STDOUT", "TO", "TRUE", "YIELDS",
        "PLUS", "MINUS", "STAR", "SLASH", "PERCENT", "CARET", "LESS", "GREATER",
        "EQUAL", "BANG", "DOT", "COMMA", "SEMICOLON", "COLON", "LPAREN", "RPAREN",
        "LBRACKET", "RBRACKET", "LBRACE", "RBRACE", "DOUBLE_COLON", "ARROW", "FAT_ARROW",
        "EQUAL_EQUAL", "BANG_EQUAL", "LESS_EQUAL", "GREATER_EQUAL", "AND_AND", "OR_OR",
        "PLUS_PLUS", "BLOCK_CLOSE", "COMMENT_LINE", "COMMENT_BLOCK"
    };
    size_t index = (size_t)kind;
    return index < sizeof(labels) / sizeof(labels[0]) ? labels[index] : "UNKNOWN";
}
const char *tf_error_code(TfError code) {
    switch (code) {
        case TF_E_NONE: return ""; case TF_E001: return "E001";
        case TF_E002: return "E002"; case TF_E003: return "E003";
        case TF_E101: return "E101"; case TF_E102: return "E102";
        case TF_E103: return "E103"; case TF_E104: return "E104";
        case TF_E105: return "E105";
    }
    return "UNKNOWN";
}
const char *tf_error_message(TfError code) {
    switch (code) {
        case TF_E_NONE: return "no error";
        case TF_E001: return "source is not valid UTF-8";
        case TF_E002: return "source must not start with a UTF-8 BOM";
        case TF_E003: return "lone CR is not a source line ending";
        case TF_E101: return "unsupported source character";
        case TF_E102: return "malformed decimal numeric literal";
        case TF_E103: return "malformed or unterminated Text literal";
        case TF_E104: return "unterminated block comment";
        case TF_E105: return "Char literal must contain exactly one valid scalar";
    }
    return "unknown error";
}
