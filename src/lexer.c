#include "internal.h"

#include <string.h>

#include "name_dfa.inc"

size_t tf_name_dfa_state_count(void) { return sizeof name_states / sizeof name_states[0]; }
bool tf_name_dfa_state(size_t state, TfNameDfaState *out) {
    if (out == NULL) return false;
    if (state == SIZE_MAX) { *out = (TfNameDfaState){SIZE_MAX, SIZE_MAX, 0, TF_IDENT, false, false}; return true; }
    if (state >= tf_name_dfa_state_count()) return false;
    *out = name_states[state];
    return true;
}
size_t tf_name_dfa_step(size_t state, unsigned char character) {
    size_t edge;
    if (state >= tf_name_dfa_state_count()) return SIZE_MAX;
    edge = name_states[state].child;
    while (edge != 0) {
        if (name_states[edge].character == character) return edge;
        edge = name_states[edge].sibling;
    }
    return SIZE_MAX;
}

typedef struct { FILE *stream; bool failed; } Trace;
static void trace_state(Trace *trace, size_t state) {
    if (trace->failed) return;
    if (state == SIZE_MAX) {
        if (fputs("IDENT_FALLBACK", trace->stream) < 0) trace->failed = true;
    } else if (fprintf(trace->stream, "%zu", state) < 0) trace->failed = true;
}
static void trace_step(Trace *trace, const char *family, const TfSource *source,
                       size_t start, size_t end, size_t state, size_t next, bool accept) {
    size_t i;
    if (trace->stream == NULL || trace->failed) return;
    if (fprintf(trace->stream, "DFA %s offset=%zu end=%zu state=", family, start, end) < 0) trace->failed = true;
    trace_state(trace, state);
    if (fputs(" next=", trace->stream) < 0) trace->failed = true;
    trace_state(trace, next);
    if (fprintf(trace->stream, " %s character=\"", accept ? "accept" : "nonaccept") < 0) trace->failed = true;
    for (i = start; i < end && !trace->failed; ++i) {
        unsigned char c = source->bytes[i];
        if (c >= 32 && c <= 126 && c != '"' && c != '\\') {
            if (fputc(c, trace->stream) == EOF) trace->failed = true;
        } else if (fprintf(trace->stream, "\\x%02X", (unsigned)c) < 0) trace->failed = true;
    }
    if (fputs("\" bytes=", trace->stream) < 0) trace->failed = true;
    for (i = start; i < end && !trace->failed; ++i)
        if (fprintf(trace->stream, "%02X", (unsigned)source->bytes[i]) < 0) trace->failed = true;
    if (fputc('\n', trace->stream) == EOF) trace->failed = true;
}
static void trace_final(Trace *trace, const char *family, TfToken token, const char *reason) {
    if (trace->stream != NULL && !trace->failed &&
        fprintf(trace->stream, "DFA %s FINAL [%zu,%zu) %s reserved=%s error=%s reason=%s\n",
                family, token.span.start, token.span.end, tf_token_name(token.kind),
                token.reserved ? "true" : "false", tf_error_code(token.error), reason) < 0)
        trace->failed = true;
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
static bool number_accept(NumberState state) {
    return state == N_ZERO || state == N_INT || state == N_FRAC || state == N_DIGITS;
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
/* Literal states: opening=0, body=1, escape=2, Unicode-u=3, brace=4,
 * hex=5, closed=6, malformed=7. Body is not a complete literal accept state. */
enum { Q_START, Q_BODY, Q_ESCAPE, Q_U, Q_BRACE, Q_HEX, Q_CLOSED, Q_BAD };
static void quote_step(Trace *trace, const char *family, const TfSource *source,
                       size_t start, size_t end, size_t *state, size_t next, bool accept) {
    trace_step(trace,family,source,start,end,*state,next,accept);
    *state=next;
}
static bool escape(const TfSource *source, size_t *at, uint32_t *scalar, Trace *trace,
                   const char *family, size_t *state, bool prior_bad) {
    unsigned char c;
    size_t count = 0;
    uint32_t value = 0;
    if (*at == source->length || source->bytes[*at] == '\r' || source->bytes[*at] == '\n')
        return false;
    c = source->bytes[*at];
    if (c >= 0x80) {
        size_t end;
        (void)tf_decode(source->bytes,source->length,*at,scalar,&end);
        quote_step(trace,family,source,*at,end,state,Q_BAD,false);
        *at=end;
        return false;
    }
    ++*at;
    quote_step(trace, family, source, *at - 1, *at, state,
               c == 'u' ? Q_U : (c == '"' || c == '\\' || c == 'n' || c == 'r' || c == 't') ?
               (prior_bad ? Q_BAD : Q_BODY) : Q_BAD, false);
    switch (c) {
        case '"': *scalar = '"'; return true;
        case '\\': *scalar = '\\'; return true;
        case 'n': *scalar = '\n'; return true;
        case 'r': *scalar = '\r'; return true;
        case 't': *scalar = '\t'; return true;
        case 'u': break;
        default: return false;
    }
    if (*at == source->length || source->bytes[*at] != '{') return false;
    quote_step(trace, family, source, *at, *at + 1, state, Q_BRACE, false);
    ++*at;
    while (*at < source->length) {
        int h = hex_digit(source->bytes[*at]);
        if (h < 0) break;
        if (count < 6) value = value * 16u + (uint32_t)h;
        quote_step(trace, family, source, *at, *at + 1,state,Q_HEX,false);
        ++count;
        ++*at;
    }
    if (*at == source->length || source->bytes[*at] != '}') return false;
    quote_step(trace, family, source, *at, *at + 1, state,
               count == 0 || count > 6 || value > 0x10ffffu ||
               (value >= 0xd800u && value <= 0xdfffu) || prior_bad ? Q_BAD : Q_BODY, false);
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
static bool quoted(TfLexResult *result, size_t *at, TfToken *token, Trace *trace) {
    const TfSource *source = result->source;
    unsigned char quote = source->bytes[(*at)++];
    void *data = NULL;
    size_t length = 0, capacity = 0, count = 0, state = Q_START;
    bool closed = false, bad = false;
    const char *family = quote == '"' ? "text" : "char";
    quote_step(trace, family, source, *at - 1, *at, &state, Q_BODY, false);
    while (*at < source->length) {
        uint32_t scalar;
        size_t end, width;
        unsigned char encoded[4];
        unsigned char c = source->bytes[*at];
        if (c == '\r' || c == '\n') break;
        if (c == quote) {
            bool valid = !bad && (quote == '"' || count == 1);
            quote_step(trace, family, source, *at, *at + 1, &state,
                       valid ? Q_CLOSED : Q_BAD, valid);
            ++*at; closed = true; break;
        }
        if (c == '\\') {
            quote_step(trace, family, source, *at, *at + 1, &state, Q_ESCAPE, false);
            ++*at;
            if (!escape(source, at, &scalar, trace, family, &state, bad)) {
                bad = true; continue;
            }
        } else {
            (void)tf_decode(source->bytes, source->length, *at, &scalar, &end);
            quote_step(trace, family, source, *at, end, &state,
                       bad || scalar < 32u || scalar == 127u ? Q_BAD : Q_BODY, false);
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

static TfTokenKind operator_pair(unsigned char first, unsigned char second) {
    switch (first) {
        case ':': if (second == ':') return TF_DOUBLE_COLON; break;
        case '-': if (second == '>') return TF_ARROW; break;
        case '=':
            if (second == '>') return TF_FAT_ARROW;
            if (second == '=') return TF_EQUAL_EQUAL;
            break;
        case '!': if (second == '=') return TF_BANG_EQUAL; break;
        case '<': if (second == '=') return TF_LESS_EQUAL; break;
        case '>': if (second == '=') return TF_GREATER_EQUAL; break;
        case '&': if (second == '&') return TF_AND_AND; break;
        case '|': if (second == '|') return TF_OR_OR; break;
        case '+': if (second == '+') return TF_PLUS_PLUS; break;
        case '*': if (second == '/') return TF_BLOCK_CLOSE; break;
        default: break;
    }
    return TF_INVALID;
}
static TfTokenKind operator_single(unsigned char first) {
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

TfStatus tf_lex_trace(TfLexResult *out, const TfSource *source, size_t diagnostic_cap,
                      const TfAllocator *allocator, FILE *stream) {
    Trace trace = {stream, false};
    size_t at = 0;
    if (out == NULL) return TF_HOST_ERROR;
    *out = (TfLexResult){0};
    out->allocator = tf_allocator(allocator);
    if (source == NULL || !source->valid || out->allocator.allocate == NULL ||
        out->allocator.deallocate == NULL) goto fail;
    out->source = source;
    while (at < source->length) {
        unsigned char first = source->bytes[at];
        unsigned char second = source->length - at >= 2 ? source->bytes[at + 1] : 0;
        TfToken token = {TF_INVALID, {source, at, at}, TF_E_NONE, false, NULL, 0};
        const char *family = "operator", *reason = "maximal-munch boundary";
        if (whitespace(first)) {
            trace_step(&trace, "whitespace", source, at, at + 1, 0, 1, true);
            ++at;
            if (trace.failed) goto fail;
            continue;
        }
        if (first == '/' && second == '/') {
            family = "line-comment";
            trace_step(&trace, family, source, at, at + 1, 0, 1, false);
            trace_step(&trace, family, source, at + 1, at + 2, 1, 2, true);
            at += 2;
            while (at < source->length && source->bytes[at] != '\r' && source->bytes[at] != '\n') {
                trace_step(&trace, family, source, at, at + 1, 2, 2, true);
                ++at;
            }
            token.kind = TF_COMMENT_LINE;
        } else if (first == '/' && second == '*') {
            bool closed = false;
            size_t state = 2;
            family = "block-comment";
            trace_step(&trace, family, source, at, at + 1, 0, 1, false);
            trace_step(&trace, family, source, at + 1, at + 2, 1, 2, false);
            at += 2;
            while (at < source->length) {
                if (source->length - at >= 2 && source->bytes[at] == '*' && source->bytes[at + 1] == '/') {
                    trace_step(&trace, family, source, at, at + 1, state, 3, false);
                    trace_step(&trace, family, source, at + 1, at + 2, 3, 4, true);
                    at += 2;
                    closed = true;
                    break;
                }
                trace_step(&trace, family, source, at, at + 1, state, source->bytes[at] == '*' ? 3 : 2, false);
                state = source->bytes[at] == '*' ? 3u : 2u;
                ++at;
            }
            if (closed) token.kind = TF_COMMENT_BLOCK;
            else { token.error = TF_E104; reason = "EOF before block-comment close"; }
        } else if (letter(first)) {
            size_t state = 0;
            family = "name";
            do {
                size_t previous = state;
                state = tf_name_dfa_step(state, source->bytes[at]);
                trace_step(&trace, "name", source, at, at + 1, previous, state, true);
                if (trace.stream != NULL && !trace.failed &&
                    fprintf(trace.stream, "DFA name metadata vocabulary-terminal=%s kind=%s reserved=%s\n",
                            state != SIZE_MAX && name_states[state].terminal ? "true" : "false",
                            tf_token_name(state == SIZE_MAX ? TF_IDENT : name_states[state].kind),
                            state != SIZE_MAX && name_states[state].reserved ? "true" : "false") < 0)
                    trace.failed = true;
                ++at;
            } while (at < source->length && (letter(source->bytes[at]) || digit(source->bytes[at])));
            token.kind = state == SIZE_MAX ? TF_IDENT : name_states[state].kind;
            token.reserved = state != SIZE_MAX && name_states[state].reserved;
            reason = state == SIZE_MAX ? "missing prefix edge; absorbing generic IDENT sink" :
                     name_states[state].terminal ? "terminal metadata at maximal name boundary" :
                     "nonterminal vocabulary prefix falls back to IDENT";
        } else if (digit(first)) {
            NumberState state = number_step(N_START, first);
            family = "number";
            trace_step(&trace, family, source, at, at + 1, N_START, (size_t)state, number_accept(state));
            ++at;
            while (at < source->length) {
                unsigned char c = source->bytes[at];
                if (letter(c) || digit(c) ||
                    (c == '.' && source->length - at >= 2 && digit(source->bytes[at + 1])) ||
                    ((c == '+' || c == '-') && (source->bytes[at - 1] == 'e' || source->bytes[at - 1] == 'E'))) {
                    NumberState previous = state;
                    state = number_step(state, c);
                    trace_step(&trace, family, source, at, at + 1, (size_t)previous, (size_t)state, number_accept(state));
                    ++at;
                } else break;
            }
            if (state == N_ZERO || state == N_INT) token.kind = TF_INT;
            else if (state == N_FRAC || state == N_DIGITS) token.kind = TF_FLOAT;
            else { token.error = TF_E102; reason = "numeric boundary in nonaccepting state"; }
        } else if (first == '"' || first == '\'') {
            family = first == '"' ? "text" : "char";
            if (!quoted(out, &at, &token, &trace)) goto fail;
            if (token.error != TF_E_NONE) reason = "literal closure, escape, scalar or Char count failed";
        } else {
            TfTokenKind pair;
            size_t state;
            token.kind = operator_single(first);
            /* Operator states are token-kind + 1; zero is start. A lone &/|
             * is pending state 100/101, distinct from invalid state 7. */
            state = first == '&' ? 100u : first == '|' ? 101u : (size_t)token.kind + 1;
            pair = operator_pair(first, second);
            if (token.kind == TF_INVALID && pair == TF_INVALID) {
                uint32_t scalar;
                (void)tf_decode(source->bytes, source->length, at, &scalar, &at);
                family = "invalid";
                trace_step(&trace, family, source, token.span.start, at, 0, state, false);
                token.error = TF_E101;
                reason = "unsupported scalar or incomplete operator";
            } else {
                trace_step(&trace, family, source, at, at + 1, 0, state, token.kind != TF_INVALID);
                if (pair != TF_INVALID) {
                    trace_step(&trace, family, source, at + 1, at + 2, state, (size_t)pair + 1, true);
                    token.kind = pair;
                    at += 2;
                } else ++at;
            }
        }
        token.span.end = at;
        trace_final(&trace, family, token, reason);
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
        if (trace.failed) goto fail;
    }
    {
        TfToken eof = {TF_EOF, {source, at, at}, TF_E_NONE, false, NULL, 0};
        if (!emit(out, eof, diagnostic_cap)) goto fail;
        trace_final(&trace, "eof", eof, "end of source");
    }
    if (trace.failed) goto fail;
    return out->has_errors ? TF_LEX_ERROR : TF_OK;
fail:
    tf_lex_destroy(out);
    return TF_HOST_ERROR;
}
TfStatus tf_lex(TfLexResult *out, const TfSource *source, size_t diagnostic_cap,
                const TfAllocator *allocator) {
    return tf_lex_trace(out, source, diagnostic_cap, allocator, NULL);
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
