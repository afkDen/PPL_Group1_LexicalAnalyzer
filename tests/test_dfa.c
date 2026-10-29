#include "ternfold/lexer.h"
#include <stdlib.h>
#include <string.h>

static size_t checks;
#define CHECK(x) do { ++checks; if (!(x)) { fprintf(stderr, "test_dfa:%d: %s\n", __LINE__, #x); exit(1); } } while (0)
static bool seen[512];
static size_t keywords, reserved, wildcard;
static void visit(size_t state, char *prefix, size_t depth) {
    TfNameDfaState s;
    bool edges[256] = {false};
    size_t edge;
    CHECK(state < tf_name_dfa_state_count() && state < sizeof seen / sizeof seen[0]);
    CHECK(!seen[state]); seen[state] = true;
    CHECK(tf_name_dfa_state(state, &s));
    if (state != 0) {
        TfSource source;
        TfLexResult result;
        CHECK(tf_source_init(&source, "graph.tfd", prefix, depth, NULL) == TF_OK);
        CHECK(tf_lex(&result, &source, 10, NULL) == TF_OK);
        CHECK(result.token_count == 2 && result.tokens[0].kind == s.kind && result.tokens[0].reserved == s.reserved);
        tf_lex_destroy(&result); tf_source_destroy(&source);
        if (s.terminal) {
            if (s.reserved) ++reserved;
            else if (s.kind == TF_UNDERSCORE) ++wildcard;
            else ++keywords;
        }
        prefix[depth] = '9';
        CHECK(tf_source_init(&source, "suffix.tfd", prefix, depth + 1, NULL) == TF_OK);
        CHECK(tf_lex(&result, &source, 10, NULL) == TF_OK);
        CHECK(result.tokens[0].kind == TF_IDENT && !result.tokens[0].reserved && result.tokens[0].span.end == depth + 1);
        tf_lex_destroy(&result); tf_source_destroy(&source);
    }
    edge = s.child;
    while (edge != 0) {
        TfNameDfaState child;
        CHECK(tf_name_dfa_state(edge, &child));
        CHECK(!edges[child.character]); edges[child.character] = true;
        CHECK(tf_name_dfa_step(state, child.character) == edge);
        CHECK(depth + 1 < 64);
        prefix[depth] = (char)child.character;
        visit(edge, prefix, depth + 1);
        edge = child.sibling;
    }
    for (edge = 0; edge < 256; ++edge)
        if (!edges[edge]) CHECK(tf_name_dfa_step(state, (unsigned char)edge) == SIZE_MAX);
}
int main(void) {
    char prefix[64];
    size_t i;
    TfNameDfaState s;
    CHECK(tf_name_dfa_state_count() == 215);
    visit(0, prefix, 0);
    for (i = 0; i < tf_name_dfa_state_count(); ++i) CHECK(seen[i]);
    CHECK(keywords == 28 && reserved == 25 && wildcard == 1);
    CHECK(tf_name_dfa_state(SIZE_MAX, &s) && s.kind == TF_IDENT && !s.reserved);
    CHECK(!tf_name_dfa_state(tf_name_dfa_state_count(), &s));
    CHECK(!tf_name_dfa_state(0, NULL));
    for (i = 0; i < 256; ++i) CHECK(tf_name_dfa_step(SIZE_MAX, (unsigned char)i) == SIZE_MAX);
    printf("static DFA: %zu checks, %zu keywords, %zu reserved names\n", checks, keywords, reserved);
    return 0;
}
