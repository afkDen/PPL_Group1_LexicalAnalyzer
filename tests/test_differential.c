#include "ternfold/lexer.h"
#include <stdlib.h>
#include <string.h>

TfStatus tf_baseline_lex(TfLexResult *, const TfSource *, size_t, const TfAllocator *);
static size_t cases, checks;
#define CHECK(x) do { ++checks; if (!(x)) { fprintf(stderr, "differential case %zu line %d: %s\n", cases, __LINE__, #x); exit(1); } } while (0)
static void bytes(FILE *a, FILE *b) {
    int x, y;
    CHECK(fflush(a) == 0 && fflush(b) == 0);
    rewind(a); rewind(b);
    do { x = fgetc(a); y = fgetc(b); CHECK(x == y); } while (x != EOF);
    CHECK(!ferror(a) && !ferror(b));
}
static void compare(const void *data, size_t length) {
    TfSource s;
    size_t cap;
    ++cases;
    if (tf_source_init(&s, "differential.tfd", data, length, NULL) != TF_OK) {
        tf_source_destroy(&s); return;
    }
    for (cap = 0; cap < 3; ++cap) {
        TfLexResult a, b;
        size_t i;
        CHECK(tf_baseline_lex(&a, &s, cap == 2 ? SIZE_MAX : cap, NULL) ==
              tf_lex(&b, &s, cap == 2 ? SIZE_MAX : cap, NULL));
        CHECK(a.token_count == b.token_count && a.diagnostic_count == b.diagnostic_count &&
              a.suppressed == b.suppressed && a.has_errors == b.has_errors);
        for (i = 0; i < a.token_count; ++i) {
            const TfToken *x = &a.tokens[i], *y = &b.tokens[i];
            CHECK(x->kind == y->kind && x->reserved == y->reserved && x->error == y->error);
            CHECK(x->span.source == y->span.source && x->span.start == y->span.start && x->span.end == y->span.end);
            CHECK(x->value_length == y->value_length);
            CHECK(x->value_length == 0 || memcmp(x->value, y->value, x->value_length) == 0);
            CHECK(memcmp(s.bytes + x->span.start, s.bytes + y->span.start, x->span.end - x->span.start) == 0);
        }
        for (i = 0; i < a.diagnostic_count; ++i) {
            CHECK(a.diagnostics[i].code == b.diagnostics[i].code &&
                  a.diagnostics[i].span.start == b.diagnostics[i].span.start &&
                  a.diagnostics[i].span.end == b.diagnostics[i].span.end);
        }
        for (i = 0; i < 3; ++i) {
            FILE *x = tmpfile(), *y = tmpfile();
            CHECK(x != NULL && y != NULL);
            if (i == 0) CHECK(tf_report_write(x, &a) == tf_report_write(y, &b));
            else if (i == 1) CHECK(tf_report_write_classroom(x, &a) == tf_report_write_classroom(y, &b));
            else CHECK(tf_diagnostics_write(x, &s, &a) == tf_diagnostics_write(y, &s, &b));
            bytes(x, y);
            CHECK(fclose(x) == 0 && fclose(y) == 0);
        }
        tf_lex_destroy(&a); tf_lex_destroy(&b);
    }
    tf_source_destroy(&s);
}
static void fixture(const char *path) {
    TfSource source;
    TfStatus status = tf_source_load(&source, path, NULL);
    CHECK(status != TF_HOST_ERROR);
    compare(source.bytes, source.length);
    tf_source_destroy(&source);
}
int main(int argc, char **argv) {
    static const char alphabet[] = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789.\"'\\/*+-=<>!&|{}[]();:, @\t\n";
    static const char *const special[] = {
        "if ifx in input let letter Int Intensity _ _x 0 01 1.2 1e-3 1e+ = == =>",
        "as div else emit enum false fn for from guard if import in input let machine match next output pub record rejects state stdin stdout to true yields",
        "Int Float Bool Text Char Unit List Option Decision step len at append map fold range int_text bool_text parse_int text_len text_at text_slice int_float float_int float_text",
        "\"a\\u{0}\\u{1f600}\" '\\u{3a9}' '\\q' \"\\u{d800}\" /*/**/*/ // note\n @",
        "\"\\u{}\" \"\\u{1234567}\" '\\' \"unterminated\n /* unclosed",
        "0e 0e+ 00 1.2.3 1e--1 1E+3 1.x 0.0 1e0 + ++ - -> / /* x */ */ //\n",
        "'\xCE\xA9' \"\xF0\x9F\x98\x80\" \xC2\xA0\r\n"
    };
    uint32_t seed = 0x53dfaceu;
    unsigned char buffer[256];
    size_t i, j;
    for (i = 0; i < sizeof special / sizeof special[0]; ++i) compare(special[i], strlen(special[i]));
    for (i = 0; i < 3000; ++i) {
        size_t n = i % sizeof buffer;
        for (j = 0; j < n; ++j) {
            seed = seed * 1664525u + 1013904223u;
            buffer[j] = (unsigned char)alphabet[seed % (sizeof alphabet - 1)];
        }
        compare(buffer, n);
    }
    /* Always cover the maintained baseline fixture set in canonical gates.
     * Additional integrated fixtures may be supplied as argv (safe paths).
     * baseline_lexer.c's runtime trie is a frozen test oracle only; it is never
     * linked into the four-source production application. */
    fixture("examples/lexical/complete.tfd");
    fixture("examples/lexical/invalid.tfd");
    fixture("examples/lexical/vocabulary.tfd");
    for (i = 1; i < (size_t)argc; ++i) fixture(argv[i]);
    printf("differential: %zu cases, %zu checks\n", cases, checks);
    return 0;
}
