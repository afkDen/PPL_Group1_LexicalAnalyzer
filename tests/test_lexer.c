#include "ternfold/lexer.h"

#include <stdlib.h>
#include <string.h>

static size_t checks;
static void check(bool condition, const char *expression, int line) {
    ++checks;
    if (!condition) {
        (void)fprintf(stderr, "test_lexer.c:%d: %s\n", line, expression);
        exit(1);
    }
}
#define CHECK(expression) check((expression), #expression, __LINE__)

static TfStatus scan(TfSource *source, TfLexResult *result, const char *text, size_t cap) {
    CHECK(tf_source_init(source, "native.tfd", text, strlen(text), NULL) == TF_OK);
    return tf_lex(result, source, cap, NULL);
}
static void release(TfSource *source, TfLexResult *result) {
    tf_lex_destroy(result);
    tf_source_destroy(source);
    /* Destruction is idempotent. */
    tf_lex_destroy(result);
    tf_source_destroy(source);
}
static void invariant(const TfSource *source, const TfLexResult *result) {
    size_t i, previous = 0;
    CHECK(result->source == source);
    CHECK(result->token_count > 0);
    CHECK(result->tokens[result->token_count - 1].kind == TF_EOF);
    for (i = 0; i < result->token_count; ++i) {
        const TfToken *token = &result->tokens[i];
        TfSpan span;
        TfLocation location;
        size_t byte;
        CHECK(token->span.source == source);
        CHECK(token->span.start >= previous);
        CHECK(tf_source_span(source, token->span.start, token->span.end, &span));
        CHECK(tf_source_location(source, token->span.start, &location));
        CHECK(tf_source_byte(source, location.line, location.column, &byte));
        CHECK(byte == token->span.start);
        if (token->kind == TF_EOF) {
            CHECK(i + 1 == result->token_count);
            CHECK(token->span.start == source->length && token->span.end == source->length);
        } else CHECK(token->span.start < token->span.end);
        if (token->kind == TF_INVALID) CHECK(token->error != TF_E_NONE && result->has_errors);
        else CHECK(token->error == TF_E_NONE);
        previous = token->span.end;
    }
}

typedef struct { const char *spelling; TfTokenKind kind; } Case;
static const Case keywords[] = {
    {"as", TF_AS}, {"div", TF_DIV}, {"else", TF_ELSE}, {"emit", TF_EMIT},
    {"enum", TF_ENUM}, {"false", TF_FALSE}, {"fn", TF_FN}, {"for", TF_FOR},
    {"from", TF_FROM}, {"guard", TF_GUARD}, {"if", TF_IF}, {"import", TF_IMPORT},
    {"in", TF_IN}, {"input", TF_INPUT}, {"let", TF_LET}, {"machine", TF_MACHINE},
    {"match", TF_MATCH}, {"next", TF_NEXT}, {"output", TF_OUTPUT}, {"pub", TF_PUB},
    {"record", TF_RECORD}, {"rejects", TF_REJECTS}, {"state", TF_STATE},
    {"stdin", TF_STDIN}, {"stdout", TF_STDOUT}, {"to", TF_TO}, {"true", TF_TRUE}, {"yields", TF_YIELDS}
};
static const char *const reserved[] = {
    "Int", "Float", "Bool", "Text", "Char", "Unit", "List", "Option", "Decision",
    "step", "len", "at", "append", "map", "fold", "range", "int_text", "bool_text",
    "parse_int", "text_len", "text_at", "text_slice", "int_float", "float_int", "float_text"
};
static const Case operators[] = {
    {"+", TF_PLUS}, {"-", TF_MINUS}, {"/", TF_SLASH}, {"*", TF_STAR},
    {"%", TF_PERCENT}, {"div", TF_DIV}, {"^", TF_CARET},
    {"&&", TF_AND_AND}, {"||", TF_OR_OR}, {"!", TF_BANG}, {">", TF_GREATER},
    {"<", TF_LESS}, {"==", TF_EQUAL_EQUAL}, {"!=", TF_BANG_EQUAL},
    {">=", TF_GREATER_EQUAL}, {"<=", TF_LESS_EQUAL},
    {"=", TF_EQUAL}, {".", TF_DOT}, {",", TF_COMMA}, {";", TF_SEMICOLON},
    {":", TF_COLON}, {"(", TF_LPAREN}, {")", TF_RPAREN}, {"[", TF_LBRACKET},
    {"]", TF_RBRACKET}, {"{", TF_LBRACE}, {"}", TF_RBRACE}, {"::", TF_DOUBLE_COLON},
    {"->", TF_ARROW}, {"=>", TF_FAT_ARROW}, {"++", TF_PLUS_PLUS}, {"*/", TF_BLOCK_CLOSE},
    {"_", TF_UNDERSCORE}
};
static void test_inventory(void) {
    size_t i;
    CHECK(sizeof(keywords) / sizeof(keywords[0]) == 28);
    CHECK(sizeof(reserved) / sizeof(reserved[0]) == 25);
    for (i = 0; i < sizeof(keywords) / sizeof(keywords[0]); ++i) {
        TfSource source;
        TfLexResult result;
        char text[128];
        int count = snprintf(text, sizeof(text), "%s %sx %s_2", keywords[i].spelling,
                              keywords[i].spelling, keywords[i].spelling);
        CHECK(count > 0 && (size_t)count < sizeof(text));
        CHECK(scan(&source, &result, text, 100) == TF_OK);
        CHECK(result.token_count == 4);
        CHECK(result.tokens[0].kind == keywords[i].kind);
        CHECK(result.tokens[1].kind == TF_IDENT && !result.tokens[1].reserved);
        CHECK(result.tokens[2].kind == TF_IDENT && !result.tokens[2].reserved);
        invariant(&source, &result);
        release(&source, &result);
    }
    for (i = 0; i < sizeof(reserved) / sizeof(reserved[0]); ++i) {
        TfSource source;
        TfLexResult result;
        char text[128];
        int count = snprintf(text, sizeof(text), "%s %sx %s_2", reserved[i], reserved[i], reserved[i]);
        CHECK(count > 0 && (size_t)count < sizeof(text));
        CHECK(scan(&source, &result, text, 100) == TF_OK);
        CHECK(result.tokens[0].kind == TF_IDENT && result.tokens[0].reserved);
        CHECK(result.tokens[1].kind == TF_IDENT && !result.tokens[1].reserved);
        CHECK(result.tokens[2].kind == TF_IDENT && !result.tokens[2].reserved);
        invariant(&source, &result);
        release(&source, &result);
    }
    for (i = 0; i < sizeof(operators) / sizeof(operators[0]); ++i) {
        TfSource source;
        TfLexResult result;
        CHECK(scan(&source, &result, operators[i].spelling, 100) == TF_OK);
        CHECK(result.token_count == 2 && result.tokens[0].kind == operators[i].kind);
        CHECK(result.tokens[0].span.start == 0 && result.tokens[0].span.end == strlen(operators[i].spelling));
        CHECK(strcmp(tf_token_name(operators[i].kind), "UNKNOWN") != 0);
        invariant(&source, &result);
        release(&source, &result);
    }
}

static void kinds(const char *text, const TfTokenKind *expected, size_t count, bool error) {
    TfSource source;
    TfLexResult result;
    size_t i;
    CHECK(scan(&source, &result, text, 100) == (error ? TF_LEX_ERROR : TF_OK));
    CHECK(result.token_count == count + 1);
    for (i = 0; i < count; ++i) CHECK(result.tokens[i].kind == expected[i]);
    invariant(&source, &result);
    release(&source, &result);
}
static void test_maximal_munch(void) {
    const TfTokenKind a[] = {TF_DOUBLE_COLON, TF_DOUBLE_COLON, TF_EQUAL_EQUAL, TF_FAT_ARROW,
                             TF_EQUAL, TF_PLUS_PLUS, TF_PLUS, TF_MINUS, TF_ARROW};
    const TfTokenKind b[] = {TF_AND_AND, TF_INVALID, TF_OR_OR, TF_INVALID};
    const TfTokenKind c[] = {TF_COMMENT_BLOCK, TF_SLASH, TF_COMMENT_BLOCK,
                             TF_COMMENT_BLOCK, TF_COMMENT_BLOCK, TF_PLUS};
    const TfTokenKind d[] = {TF_UNDERSCORE, TF_IDENT, TF_IDENT, TF_IDENT, TF_IDENT, TF_IDENT, TF_TRUE};
    const TfTokenKind e[] = {TF_COMMENT_BLOCK, TF_COMMENT_LINE, TF_SLASH};
    kinds(":::: ===>= +++ -->", a, sizeof(a) / sizeof(a[0]), false);
    kinds("&&&|||", b, sizeof(b) / sizeof(b[0]), true);
    kinds("/**// /**/ /***/ /* x /* y */+", c, sizeof(c) / sizeof(c[0]), false);
    kinds("_ _a __ A0 main TRUE true", d, sizeof(d) / sizeof(d[0]), false);
    kinds("/*x*/ // line\r\n/", e, sizeof(e) / sizeof(e[0]), false);
}

typedef struct { const char *text; TfError error; size_t end; } Bad;
static void test_numbers(void) {
    static const char *const valid[] = {"0", "1", "99999999999999999999999999999999999999999999999",
        "0.0", "1.5", "1e999", "1e-999", "1E+2", "12.345e-9", "1.0e0", "0E9"};
    static const Bad bad[] = {{"00", TF_E102, 2}, {"09", TF_E102, 2},
        {"1e+", TF_E102, 3}, {"1efoo", TF_E102, 5}, {"1.2.3", TF_E102, 5},
        {"1e++2", TF_E102, 3}, {"1efoo.bar", TF_E102, 5}, {"1e999foo", TF_E102, 8},
        {"1e2e3", TF_E102, 5}, {"0x10", TF_E102, 4}, {"1_000", TF_E102, 5},
        {"01.5e-3", TF_E102, 7}, {"1e", TF_E102, 2}, {"1e-", TF_E102, 3},
        {"1.2e+foo", TF_E102, 8}, {"1e.2", TF_E102, 4}};
    size_t i;
    for (i = 0; i < sizeof(valid) / sizeof(valid[0]); ++i) {
        TfSource source;
        TfLexResult result;
        TfTokenKind expected = i < 3 ? TF_INT : TF_FLOAT;
        CHECK(scan(&source, &result, valid[i], 100) == TF_OK);
        CHECK(result.token_count == 2 && result.tokens[0].kind == expected);
        CHECK(result.tokens[0].value_length == strlen(valid[i]));
        CHECK(memcmp(result.tokens[0].value, valid[i], strlen(valid[i])) == 0);
        invariant(&source, &result);
        release(&source, &result);
    }
    for (i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i) {
        TfSource source;
        TfLexResult result;
        CHECK(scan(&source, &result, bad[i].text, 100) == TF_LEX_ERROR);
        CHECK(result.tokens[0].kind == TF_INVALID && result.tokens[0].error == bad[i].error);
        if (result.tokens[0].span.end != bad[i].end)
            (void)fprintf(stderr, "numeric %s: expected end %zu, got %zu\n", bad[i].text,
                          bad[i].end, result.tokens[0].span.end);
        CHECK(result.tokens[0].span.start == 0 && result.tokens[0].span.end == bad[i].end);
        CHECK(result.diagnostics[0].span.end == bad[i].end);
        invariant(&source, &result);
        release(&source, &result);
    }
    {
        const TfTokenKind expected[] = {TF_INT, TF_DOT, TF_IDENT, TF_FLOAT, TF_DOT,
            TF_IDENT, TF_DOT, TF_INT, TF_INT, TF_DOT, TF_MINUS, TF_INT,
            TF_INVALID, TF_PLUS, TF_INT, TF_INVALID, TF_COMMENT_BLOCK, TF_PLUS, TF_INT};
        kinds("1.foo 1.2.foo .5 1. -2 1e++2 09/**/+2", expected,
               sizeof(expected) / sizeof(expected[0]), true);
    }
}

typedef struct { const char *text; TfTokenKind kind; const char *value; size_t length; } Literal;
static void test_literals(void) {
    static const Literal good[] = {
        {"\"\"", TF_TEXT, "", 0}, {"\"abc\"", TF_TEXT, "abc", 3},
        {"\"\xc3\xa9\xf0\x9f\x99\x82\"", TF_TEXT, "\xc3\xa9\xf0\x9f\x99\x82", 6},
        {"\"\\\"\\\\\\n\\r\\t\"", TF_TEXT, "\"\\\n\r\t", 5},
        {"\"\\u{0}\\u{10ffff}\"", TF_TEXT, "\0\xf4\x8f\xbf\xbf", 5},
        {"'A'", TF_CHAR, "A", 1}, {"'\xc3\xb1'", TF_CHAR, "\xc3\xb1", 2},
        {"'\xf0\x9f\x99\x82'", TF_CHAR, "\xf0\x9f\x99\x82", 4},
        {"'\\u{27}'", TF_CHAR, "'", 1}, {"'\\n'", TF_CHAR, "\n", 1},
        {"'\\u{000000}'", TF_CHAR, "\0", 1}, {"'\"'", TF_CHAR, "\"", 1},
        {"'\\\"'", TF_CHAR, "\"", 1}, {"'\\u{d7ff}'", TF_CHAR, "\xed\x9f\xbf", 3},
        {"'\\u{e000}'", TF_CHAR, "\xee\x80\x80", 3}
    };
    static const char *const invalid[] = {"\\'", "\\q", "\\0", "\\x41", "\\u", "\\u12",
        "\\u{}", "\\u{G}", "\\u{1234567}", "\\u{110000}", "\\u{D800}", "\\u{DFFF}", "\\u{12",
        "\\\xc3\xa9"};
    size_t i;
    for (i = 0; i < sizeof(good) / sizeof(good[0]); ++i) {
        TfSource source;
        TfLexResult result;
        CHECK(scan(&source, &result, good[i].text, 100) == TF_OK);
        CHECK(result.token_count == 2 && result.tokens[0].kind == good[i].kind);
        CHECK(result.tokens[0].value_length == good[i].length);
        if (good[i].length != 0) CHECK(memcmp(result.tokens[0].value, good[i].value, good[i].length) == 0);
        invariant(&source, &result);
        release(&source, &result);
    }
    for (i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i) {
        size_t q;
        for (q = 0; q < 2; ++q) {
            TfSource source;
            TfLexResult result;
            char text[128];
            int count = snprintf(text, sizeof(text), "%c%s%c next", q == 0 ? '"' : '\'',
                                  invalid[i], q == 0 ? '"' : '\'');
            CHECK(count > 0 && (size_t)count < sizeof(text));
            CHECK(scan(&source, &result, text, 100) == TF_LEX_ERROR);
            CHECK(result.token_count == 3);
            CHECK(result.tokens[0].error == (q == 0 ? TF_E103 : TF_E105));
            CHECK(result.tokens[0].span.end == strlen(invalid[i]) + 2);
            CHECK(result.tokens[1].kind == TF_NEXT);
            invariant(&source, &result);
            release(&source, &result);
        }
    }
    {
        const TfTokenKind expected[] = {TF_INVALID, TF_INVALID, TF_INVALID, TF_NEXT};
        kinds("'' 'ab' 'unclosed\r\nnext", expected, sizeof(expected) / sizeof(expected[0]), true);
    }
    for (i = 0; i <= 127; ++i) {
        size_t q;
        if (i >= 32 && i != 127) continue;
        for (q = 0; q < 2; ++q) {
            unsigned char data[5] = {q == 0 ? '"' : '\'', (unsigned char)i, q == 0 ? '"' : '\'', 0, 0};
            TfSource source;
            TfLexResult result;
            size_t length = 3;
            if (i == '\r') { data[2] = '\n'; data[3] = data[0]; length = 4; }
            CHECK(tf_source_init(&source, "control.tfd", data, length, NULL) == TF_OK);
            CHECK(tf_lex(&result, &source, 100, NULL) == TF_LEX_ERROR);
            CHECK(result.tokens[0].error == (q == 0 ? TF_E103 : TF_E105));
            invariant(&source, &result);
            release(&source, &result);
        }
    }
}

typedef struct { unsigned char bytes[8]; size_t length; TfError error; size_t start, end; } SourceCase;
static void test_source(void) {
    static const SourceCase cases[] = {
        {{0xff}, 1, TF_E001, 0, 1}, {{0xc0, 0x80}, 2, TF_E001, 0, 1},
        {{0xed, 0xa0, 0x80}, 3, TF_E001, 0, 1}, {{0xf4, 0x90, 0x80, 0x80}, 4, TF_E001, 0, 1},
        {{0xe2, 0x82}, 2, TF_E001, 0, 2}, {{'a', 0xe2, 0x82, 'x'}, 4, TF_E001, 1, 3},
        {{0xe0, 0x80, 0x80}, 3, TF_E001, 0, 1}, {{0xf0, 0x80, 0x80, 0x80}, 4, TF_E001, 0, 1},
        {{0x80}, 1, TF_E001, 0, 1}, {{0xf5}, 1, TF_E001, 0, 1},
        {{0xef, 0xbb, 0xbf}, 3, TF_E002, 0, 3},
        {{'a', '\r'}, 2, TF_E003, 1, 2}, {{'\r', 'a'}, 2, TF_E003, 0, 1},
        {{0xef, 0xbb, 0xbf, '\r', 0xff}, 5, TF_E001, 4, 5},
        {{0xef, 0xbb, 0xbf, '\r'}, 4, TF_E002, 0, 3}
    };
    size_t i;
    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        TfSource source;
        TfLocation location;
        TfSpan span;
        CHECK(tf_source_init(&source, "raw.tfd", cases[i].bytes, cases[i].length, NULL) == TF_SOURCE_ERROR);
        CHECK(!source.valid && source.length == cases[i].length);
        CHECK(source.error.code == cases[i].error);
        CHECK(source.error.span.source == &source);
        CHECK(source.error.span.start == cases[i].start && source.error.span.end == cases[i].end);
        CHECK(memcmp(source.bytes, cases[i].bytes, cases[i].length) == 0);
        CHECK(!tf_source_location(&source, 0, &location));
        CHECK(!tf_source_span(&source, 0, 0, &span));
        tf_source_destroy(&source);
    }
    {
        static const unsigned char bytes[] = {'\t', 0xc3, 0xa9, '\r', '\n', 'X', '\t', 0xf0, 0x9f, 0x99, 0x82, '\n'};
        static const size_t offsets[] = {0, 1, 3, 4, 5, 6, 7, 11, 12};
        static const size_t lines[] = {1, 1, 1, 1, 2, 2, 2, 2, 3};
        static const size_t columns[] = {1, 2, 3, 4, 1, 2, 3, 4, 1};
        TfSource source, other;
        TfLocation location;
        TfSpan left, right, joined;
        CHECK(tf_source_init(&source, "coords.tfd", bytes, sizeof(bytes), NULL) == TF_OK);
        CHECK(tf_source_init(&other, "coords.tfd", bytes, sizeof(bytes), NULL) == TF_OK);
        CHECK(source.scalar_count == 8 && source.line_count == 3);
        for (i = 0; i < sizeof(offsets) / sizeof(offsets[0]); ++i) {
            size_t byte;
            CHECK(tf_source_location(&source, offsets[i], &location));
            CHECK(location.line == lines[i] && location.column == columns[i]);
            CHECK(location.scalar == i);
            CHECK(tf_source_byte(&source, location.line, location.column, &byte) && byte == offsets[i]);
        }
        CHECK(tf_source_location(&source, 1, &location) && location.display_column == 5);
        CHECK(tf_source_location(&source, 7, &location) && location.display_column == 5);
        CHECK(!tf_source_location(&source, 2, &location));
        CHECK(!tf_source_location(&source, 8, &location));
        CHECK(!tf_source_location(&source, SIZE_MAX, &location));
        CHECK(!tf_source_byte(&source, 1, 5, &i));
        CHECK(!tf_source_byte(&source, 0, 1, &i));
        CHECK(!tf_source_byte(&source, 1, SIZE_MAX, &i));
        CHECK(tf_source_span(&source, 1, 3, &left));
        CHECK(tf_source_span(&source, 5, 12, &right));
        CHECK(tf_span_join(left, right, &joined) && joined.start == 1 && joined.end == 12);
        CHECK(tf_source_span(&other, 1, 3, &right));
        CHECK(!tf_span_join(left, right, &joined));
        CHECK(!tf_source_span(&source, 3, 1, &joined));
        tf_source_destroy(&other);
        tf_source_destroy(&source);
    }
    {
        TfSource source;
        TfLexResult result;
        CHECK(tf_source_init(&source, "empty.tfd", NULL, 0, NULL) == TF_OK);
        CHECK(tf_lex(&result, &source, 0, NULL) == TF_OK);
        CHECK(result.token_count == 1);
        invariant(&source, &result);
        release(&source, &result);
    }
}

static char *read_stream(FILE *stream) {
    long length;
    char *text;
    CHECK(fflush(stream) == 0);
    CHECK(fseek(stream, 0, SEEK_END) == 0);
    length = ftell(stream);
    CHECK(length >= 0);
    CHECK(fseek(stream, 0, SEEK_SET) == 0);
    text = malloc((size_t)length + 1);
    CHECK(text != NULL);
    CHECK(fread(text, 1, (size_t)length, stream) == (size_t)length);
    text[length] = '\0';
    return text;
}
static void test_reports_and_cap(void) {
    static const char text[] = "{input x: Text from /*c*/ stdin; output {\"hi\"} to stdout;} from to\n"
                               "//\xc3\xa9\r\n'\xf0\x9f\x99\x82' @ div () 1e999";
    static const char expected[] = "TOKEN TYPE\tLEXEME\nLBRACE\t\"{\"\nKEYWORD\t\"input\"\n"
        "IDENTIFIER\t\"x\"\nCOLON\t\":\"\nRESERVED_WORD\t\"Text\"\nNOISE_WORD\t\"from\"\n"
        "BLOCK_COMMENT\t\"/*c*/\"\nKEYWORD\t\"stdin\"\nSEMICOLON\t\";\"\nKEYWORD\t\"output\"\n"
        "LBRACE\t\"{\"\nTEXT_LITERAL\t\"\\\"hi\\\"\"\nRBRACE\t\"}\"\nNOISE_WORD\t\"to\"\n"
        "KEYWORD\t\"stdout\"\nSEMICOLON\t\";\"\nRBRACE\t\"}\"\nKEYWORD\t\"from\"\nKEYWORD\t\"to\"\n"
        "LINE_COMMENT\t\"//\\u00e9\"\nCHAR_LITERAL\t\"'\\ud83d\\ude42'\"\nINVALID\t\"@\"\n"
        "DIV\t\"div\"\nLPAREN\t\"(\"\nRPAREN\t\")\"\nFLOAT_LITERAL\t\"1e999\"\n";
    TfSource source;
    TfLexResult result;
    FILE *stream = tmpfile();
    char *actual;
    size_t cap;
    CHECK(stream != NULL);
    CHECK(scan(&source, &result, text, 100) == TF_LEX_ERROR);
    CHECK(tf_report_write(stream, &result) == TF_OK);
    actual = read_stream(stream);
    CHECK(strcmp(actual, expected) == 0);
    free(actual);
    CHECK(fclose(stream) == 0);
    invariant(&source, &result);
    release(&source, &result);
    for (cap = 0; cap <= 2; ++cap) {
        CHECK(scan(&source, &result, "@ @ @ /*", cap) == TF_LEX_ERROR);
        CHECK(result.diagnostic_count == cap && result.suppressed == 4 - cap && result.has_errors);
        CHECK(result.token_count == 5 && result.tokens[3].error == TF_E104);
        stream = tmpfile();
        CHECK(stream != NULL);
        CHECK(tf_diagnostics_write(stream, &source, &result) == TF_OK);
        actual = read_stream(stream);
        CHECK(strstr(actual, "further diagnostics suppressed") != NULL);
        if (cap != 0) CHECK(strstr(actual, "[bytes 0..1)") != NULL);
        free(actual);
        CHECK(fclose(stream) == 0);
        invariant(&source, &result);
        release(&source, &result);
    }
    stream = tmpfile();
    CHECK(stream != NULL && tf_report_write(stream, NULL) == TF_OK);
    actual = read_stream(stream);
    CHECK(strcmp(actual, "TOKEN TYPE\tLEXEME\n") == 0);
    free(actual);
    CHECK(fclose(stream) == 0);
    {
        static const unsigned char bad[] = {0xef, 0xbb, 0xbf, 'x'};
        CHECK(tf_source_init(&source, "bom.tfd", bad, sizeof(bad), NULL) == TF_SOURCE_ERROR);
        stream = tmpfile();
        CHECK(stream != NULL && tf_diagnostics_write(stream, &source, NULL) == TF_OK);
        actual = read_stream(stream);
        CHECK(strstr(actual, "E002") != NULL && strstr(actual, "[bytes 0..3)") != NULL);
        CHECK(strstr(actual, "raw bytes") != NULL);
        free(actual);
        CHECK(fclose(stream) == 0);
        tf_source_destroy(&source);
    }
    {
        static const unsigned char controls[] = {'/', '*', '\0', '\t', '\r', '\n', '\b', '\f', 0x7f, '*', '/'};
        CHECK(tf_source_init(&source, "comments.tfd", controls, sizeof(controls), NULL) == TF_OK);
        CHECK(tf_lex(&result, &source, 100, NULL) == TF_OK);
        stream = tmpfile();
        CHECK(stream != NULL && tf_report_write(stream, &result) == TF_OK);
        actual = read_stream(stream);
        CHECK(strcmp(actual, "TOKEN TYPE\tLEXEME\nBLOCK_COMMENT\t\"/*\\u0000\\t\\r\\n\\b\\f\\u007f*/\"\n") == 0);
        free(actual);
        CHECK(fclose(stream) == 0);
        release(&source, &result);
    }
}

/* Custom allocator detects leaked blocks at every fail point. max_align_t in
 * the header preserves the C allocator alignment contract for all records. */
typedef union { max_align_t alignment; struct { size_t marker; } info; } Allocation;
typedef struct { size_t calls, fail_at, live; } Memory;
static void *allocate(void *context, size_t size) {
    Memory *memory = context;
    Allocation *block;
    if (memory->calls++ == memory->fail_at || size > SIZE_MAX - sizeof(Allocation)) return NULL;
    block = malloc(sizeof(Allocation) + size);
    CHECK(block != NULL);
    block->info.marker = 0x514fu;
    ++memory->live;
    return block + 1;
}
static void deallocate(void *context, void *pointer) {
    Memory *memory = context;
    Allocation *block;
    CHECK(pointer != NULL && memory->live != 0);
    block = (Allocation *)pointer - 1;
    CHECK(block->info.marker == 0x514fu);
    block->info.marker = 0;
    --memory->live;
    free(block);
}
static size_t pipeline(size_t fail_at, bool *failed, bool classroom) {
    static const char text[] = "{{{{{{{{{{{{{{{{{{{{ output \"\\u{0}hello\" to stdout; @ 01 /*x*/ "
        "}}}}}}}}}}}}}}}}}}}} '\\u{1f642}' abc 1.0 0 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 "
        "@ @ @ @ @ @ @ @ @ @ @ @ @ @ @ @ @ @ @ @ @ @ @ @ "
        "\"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" "
        "\"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" "
        "\"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" "
        "\"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\" \"x\"";
    Memory memory = {0, fail_at, 0};
    TfAllocator allocator = {&memory, allocate, deallocate};
    TfSource source;
    TfLexResult result = {0};
    TfStatus status = tf_source_init(&source, "allocation.tfd", text, strlen(text), &allocator);
    if (status == TF_OK) status = tf_lex(&result, &source, 20, &allocator);
    if (status == TF_LEX_ERROR) {
        FILE *stream = tmpfile();
        CHECK(stream != NULL);
        status = classroom ? tf_report_write_classroom(stream, &result) : tf_report_write(stream, &result);
        CHECK(fclose(stream) == 0);
    }
    *failed = status == TF_HOST_ERROR;
    tf_lex_destroy(&result);
    tf_source_destroy(&source);
    CHECK(memory.live == 0);
    return memory.calls;
}
static void test_allocation_failure(void) {
    bool failed;
    size_t mode;
    for (mode = 0; mode < 2; ++mode) {
        size_t count = pipeline(SIZE_MAX, &failed, mode != 0), i;
        CHECK(!failed && count >= 12);
        for (i = 0; i < count; ++i) {
            (void)pipeline(i, &failed, mode != 0);
            CHECK(failed);
        }
    }
    {
        TfSource source;
        TfLexResult result;
        TfAllocator invalid = {0};
        CHECK(tf_source_init(&source, "x", NULL, 0, &invalid) == TF_HOST_ERROR);
        tf_source_destroy(&source);
        CHECK(tf_source_init(&source, "x", NULL, 1, NULL) == TF_HOST_ERROR);
        CHECK(tf_lex(&result, &source, 0, NULL) == TF_HOST_ERROR);
        tf_lex_destroy(&result);
        tf_source_destroy(&source);
    }
}

/* Deterministic byte corpus: never a regex oracle. Every accepted UTF-8 scalar
 * must make progress, and raw bytes are rejected or preserved exactly. */
static void test_byte_corpus(void) {
    unsigned int value;
    for (value = 0; value < 256; ++value) {
        unsigned char bytes[2] = {(unsigned char)value, '\n'};
        TfSource source;
        TfLexResult result;
        TfStatus status = tf_source_init(&source, "byte.tfd", bytes, sizeof(bytes), NULL);
        if (value >= 128) CHECK(status == TF_SOURCE_ERROR && source.error.code == TF_E001);
        else {
            CHECK(status == TF_OK);
            status = tf_lex(&result, &source, 100, NULL);
            CHECK(status == TF_OK || status == TF_LEX_ERROR);
            invariant(&source, &result);
            tf_lex_destroy(&result);
        }
        tf_source_destroy(&source);
    }
    {
        static const char text[] = "\xc2\x80\xef\xbb\xbf\xf4\x8f\xbf\xbf";
        TfSource source;
        TfLexResult result;
        CHECK(scan(&source, &result, text, 0) == TF_LEX_ERROR);
        CHECK(result.token_count == 4 && result.suppressed == 3);
        CHECK(result.tokens[0].span.end == 2 && result.tokens[1].span.end == 5 && result.tokens[2].span.end == 9);
        invariant(&source, &result);
        release(&source, &result);
    }
}

static void test_deterministic_corpus(void) {
    uint32_t state = 0x71f04du;
    size_t trial;
    static const unsigned char alphabet[] =
        "0123456789eE._+-*/^%&|<>!=:;()[]{}\"'\\ abcdefghijklmnopqrstuvwxyz\t\r\n";
    for (trial = 0; trial < 1500; ++trial) {
        unsigned char bytes[192];
        size_t i, length = trial % sizeof(bytes);
        TfSource source;
        TfLexResult result;
        TfStatus status;
        for (i = 0; i < length; ++i) {
            state = state * UINT32_C(1664525) + UINT32_C(1013904223);
            bytes[i] = alphabet[state % (sizeof(alphabet) - 1)];
        }
        status = tf_source_init(&source, "corpus.tfd", bytes, length, NULL);
        if (status == TF_OK) {
            status = tf_lex(&result, &source, trial % 4, NULL);
            CHECK(status == TF_OK || status == TF_LEX_ERROR);
            invariant(&source, &result);
            CHECK(result.token_count <= length + 1);
            CHECK(result.diagnostic_count <= trial % 4);
            CHECK(result.has_errors == (result.diagnostic_count + result.suppressed > 0));
            tf_lex_destroy(&result);
        } else CHECK(status == TF_SOURCE_ERROR && source.error.code == TF_E003);
        CHECK(source.length == length);
        if (length != 0) CHECK(memcmp(source.bytes, bytes, length) == 0);
        tf_source_destroy(&source);
    }
    /* Every proper prefix/suffix of inventory spellings still observes the
     * terminal of the consumed character path, rather than a stale terminal. */
    for (trial = 0; trial < sizeof(keywords) / sizeof(keywords[0]); ++trial) {
        size_t length = strlen(keywords[trial].spelling), prefix;
        for (prefix = 1; prefix < length; ++prefix) {
            char bytes[64];
            size_t other;
            TfTokenKind expected = TF_IDENT;
            TfSource source;
            TfLexResult result;
            memcpy(bytes, keywords[trial].spelling, prefix);
            bytes[prefix] = '\0';
            for (other = 0; other < sizeof(keywords) / sizeof(keywords[0]); ++other)
                if (strcmp(bytes, keywords[other].spelling) == 0) expected = keywords[other].kind;
            CHECK(scan(&source, &result, bytes, 100) == TF_OK);
            CHECK(result.token_count == 2 && result.tokens[0].kind == expected);
            release(&source, &result);
        }
    }
}
int main(void) {
    test_source();
    test_inventory();
    test_maximal_munch();
    test_numbers();
    test_literals();
    test_reports_and_cap();
    test_allocation_failure();
    test_byte_corpus();
    test_deterministic_corpus();
    (void)printf("native lexer: %zu checks passed\n", checks);
    return 0;
}
