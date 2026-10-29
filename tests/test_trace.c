#include "ternfold/lexer.h"
#include <stdlib.h>
#include <string.h>

static size_t checks;
#define CHECK(x) do { ++checks; if (!(x)) { fprintf(stderr, "test_trace:%d: %s\n", __LINE__, #x); exit(1); } } while (0)
typedef struct { size_t calls, fail, live; } Allocations;
static void *allocate(void *context, size_t size) {
    Allocations *a = context;
    void *p;
    if (a->calls++ == a->fail) return NULL;
    p = malloc(size);
    if (p != NULL) ++a->live;
    return p;
}
static void deallocate(void *context, void *p) {
    Allocations *a = context;
    CHECK(p != NULL && a->live > 0);
    --a->live; free(p);
}
static void same_result(const TfLexResult *a, const TfLexResult *b) {
    size_t i;
    CHECK(a->token_count == b->token_count && a->diagnostic_count == b->diagnostic_count && a->suppressed == b->suppressed);
    for (i = 0; i < a->token_count; ++i) {
        const TfToken *x = &a->tokens[i], *y = &b->tokens[i];
        CHECK(x->kind == y->kind && x->error == y->error && x->reserved == y->reserved);
        CHECK(x->span.start == y->span.start && x->span.end == y->span.end);
        CHECK(x->value_length == y->value_length && (x->value_length == 0 || memcmp(x->value, y->value, x->value_length) == 0));
    }
}
static void literal_continuity(void) {
    static const char *const cases[]={
        "\"\\u{}\"", "\"\\u{d800}\"", "\"\\u{110000}\"", "\"\\u{1234567}\"",
        "\"\\u{12X}\"", "\"\\uZ\"", "\"\\q\\n\"", "\"\\\xce\xa9\"",
        "'ab'", "''", "'\\u{}'", "'\\\xf0\x9f\x99\x82'", "\"\\", "\"\\u{12",
        "\"okay\\n\\u{3a9}\"", "'\\u{0}'"
    };
    for(size_t i=0;i<sizeof cases/sizeof cases[0];++i){
        TfSource source;TfLexResult plain,traced;FILE *f=tmpfile();
        char line[1024];size_t previous=0,last=0,steps=0;bool active=false;
        CHECK(f!=NULL);CHECK(tf_source_init(&source,"continuity.tfd",cases[i],strlen(cases[i]),NULL)==TF_OK);
        CHECK(tf_lex(&plain,&source,100,NULL)!=TF_HOST_ERROR);
        CHECK(tf_lex_trace(&traced,&source,100,NULL,f)!=TF_HOST_ERROR);same_result(&plain,&traced);
        CHECK(fflush(f)==0&&fseek(f,0,SEEK_SET)==0);
        while(fgets(line,sizeof line,f)!=NULL){
            char family[16];size_t start,end,state,next;
            if(strstr(line," FINAL ")!=NULL){active=false;continue;}
            if(sscanf(line,"DFA %15s offset=%zu end=%zu state=%zu next=%zu",family,&start,&end,&state,&next)==5&&
               (!strcmp(family,"text")||!strcmp(family,"char"))){
                CHECK(end>start&&end<=source.length);
                if(active){CHECK(start==last);CHECK(state==previous);}else CHECK(state==0);
                last=end;previous=next;active=true;++steps;
            }
        }
        CHECK(!ferror(f)&&steps>0);CHECK(fclose(f)==0);
        tf_lex_destroy(&plain);tf_lex_destroy(&traced);tf_source_destroy(&source);
    }
}
static void consumed_once(void) {
    static const char *const cases[]={
        "\xce\xa9 @ & && | || \xf0\x9f\x99\x82 ",
        "if ifx 1.25e-2 1e+ = == => //\xce\xa9\n/*a**/\"\\u{}\" '\xce\xa9'",
        "\"\\\xce\xa9\\n\" '\\q'\r\n 0 09 */ ",
        "\"unterminated\nlet okay = 1; /* unterminated"
    };
    for(size_t i=0;i<sizeof cases/sizeof cases[0];++i){
        TfSource source;TfLexResult result;FILE *f=tmpfile();char line[1024];size_t previous=0,steps=0;
        CHECK(f!=NULL);CHECK(tf_source_init(&source,"once.tfd",cases[i],strlen(cases[i]),NULL)==TF_OK);
        CHECK(tf_lex_trace(&result,&source,100,NULL,f)!=TF_HOST_ERROR);
        CHECK(fflush(f)==0&&fseek(f,0,SEEK_SET)==0);
        while(fgets(line,sizeof line,f)!=NULL){
            char family[16];size_t start,end;
            if(sscanf(line,"DFA %15s offset=%zu end=%zu",family,&start,&end)==3){
                CHECK(start==previous);CHECK(end>start&&end<=source.length);previous=end;++steps;
            }
        }
        CHECK(!ferror(f)&&steps>0&&previous==source.length);CHECK(fclose(f)==0);
        tf_lex_destroy(&result);tf_source_destroy(&source);
    }
}
int main(void) {
    const char *text = "if ifx in input let letter Int Intensity 0 01 1.2 1e+ = == => && & \"hi\\u{3a9}\" '\\u{0}' // hi\n /*x*/ @ /*open";
    const char *need[] = {"state=0 next=32 accept character=\"i\" bytes=69", "offset=1 end=2 state=32 next=33 accept character=\"f\" bytes=66", "state=33 next=IDENT_FALLBACK accept character=\"x\" bytes=78", "vocabulary-terminal=true kind=IF", "kind=IN", "kind=INPUT", "kind=LET", "kind=IDENT reserved=true", "DFA number", "DFA operator", "DFA text", "DFA char", "DFA line-comment", "DFA block-comment", "DFA invalid", "FINAL", "error=E102", "error=E104", "missing prefix edge", "nonaccept"};
    TfSource source;
    TfLexResult plain, traced;
    FILE *trace = tmpfile();
    char *output;
    long length;
    size_t i;
    CHECK(trace != NULL);
    CHECK(tf_source_init(&source, "trace.tfd", text, strlen(text), NULL) == TF_OK);
    CHECK(tf_lex(&plain, &source, 100, NULL) == TF_LEX_ERROR);
    CHECK(tf_lex_trace(&traced, &source, 100, NULL, trace) == TF_LEX_ERROR);
    same_result(&plain, &traced);
    CHECK(fflush(trace) == 0 && fseek(trace, 0, SEEK_END) == 0);
    length = ftell(trace); CHECK(length >= 0);
    output = malloc((size_t)length + 1); CHECK(output != NULL);
    rewind(trace); CHECK(fread(output, 1, (size_t)length, trace) == (size_t)length);
    output[length] = '\0';
    for (i = 0; i < sizeof need / sizeof need[0]; ++i) CHECK(strstr(output, need[i]) != NULL);
    free(output); CHECK(fclose(trace) == 0);
    tf_lex_destroy(&traced); tf_lex_destroy(&plain);
    /* A readable-only stream deterministically fails a write; HOST_ERROR must
     * leave no token/payload ownership even when the input contains literals. */
    trace = fopen("tests/test_trace.c", "rb"); CHECK(trace != NULL);
    CHECK(tf_lex_trace(&traced, &source, 100, NULL, trace) == TF_HOST_ERROR);
    CHECK(traced.tokens == NULL && traced.diagnostics == NULL && traced.source == NULL);
    CHECK(ferror(trace)); (void)fclose(trace);
    tf_lex_destroy(&traced); tf_source_destroy(&source);
    CHECK(tf_source_init(&source, "owned.tfd", "\"payload\" '\\u{3a9}' @", 22, NULL) == TF_OK);
    trace = fopen("tests/test_trace.c", "rb"); CHECK(trace != NULL);
    CHECK(tf_lex_trace(&traced, &source, 100, NULL, trace) == TF_HOST_ERROR);
    CHECK(traced.tokens == NULL && traced.source == NULL);
    (void)fclose(trace);
    /* Every allocation failure in both entry points must return the same status
     * and release all owned vectors and decoded literal payloads. */
    for (i = 0; i < 100; ++i) {
        Allocations a = {0, i, 0}, b = {0, i, 0};
        TfAllocator aa = {&a, allocate, deallocate}, bb = {&b, allocate, deallocate};
        TfStatus x, y;
        trace = tmpfile(); CHECK(trace != NULL);
        x = tf_lex(&plain, &source, 100, &aa);
        y = tf_lex_trace(&traced, &source, 100, &bb, trace);
        CHECK(x == y && a.calls == b.calls);
        if (x != TF_HOST_ERROR) same_result(&plain, &traced);
        else CHECK(traced.tokens == NULL && traced.source == NULL);
        tf_lex_destroy(&plain); tf_lex_destroy(&traced);
        CHECK(a.live == 0 && b.live == 0);
        CHECK(fclose(trace) == 0);
        if (x != TF_HOST_ERROR) break;
    }
    CHECK(i < 100);
    tf_source_destroy(&source);
    literal_continuity();
    consumed_once();
    printf("actual trace: %zu checks\n", checks);
    return 0;
}
