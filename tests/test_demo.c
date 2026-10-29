#include "ternfold/lexer.h"
#include <stdlib.h>
#include <string.h>

static size_t checks;
static void check(bool okay, int line) {
    ++checks;
    if (!okay) { fprintf(stderr,"professor demonstration:%d\n",line); exit(1); }
}
#define CHECK(x) check((x),__LINE__)
static bool spelling(const TfToken *t,const char *s) {
    size_t n=strlen(s);
    return t->span.end-t->span.start==n && !memcmp(t->span.source->bytes+t->span.start,s,n);
}
static bool present(const TfLexResult *r,TfTokenKind kind,const char *s) {
    for(size_t i=0;i<r->token_count;++i)
        if(r->tokens[i].kind==kind && spelling(&r->tokens[i],s)) return true;
    return false;
}
static char *read_stream(FILE *f) {
    long n;char *out;
    CHECK(fflush(f)==0&&fseek(f,0,SEEK_END)==0);n=ftell(f);CHECK(n>=0);
    out=malloc((size_t)n+1);CHECK(out!=NULL&&fseek(f,0,SEEK_SET)==0);
    CHECK(fread(out,1,(size_t)n,f)==(size_t)n);out[n]=0;return out;
}
static void golden(const char *actual,const char *path) {
    FILE *f=fopen(path,"rb");char *expected;CHECK(f!=NULL);
    expected=read_stream(f);CHECK(strcmp(actual,expected)==0);free(expected);CHECK(fclose(f)==0);
}
int main(void) {
    static const struct {TfTokenKind kind;const char *text;} operators[]={
        {TF_PLUS,"+"},{TF_MINUS,"-"},{TF_SLASH,"/"},{TF_STAR,"*"},{TF_PERCENT,"%"},{TF_DIV,"div"},{TF_CARET,"^"},
        {TF_AND_AND,"&&"},{TF_OR_OR,"||"},{TF_BANG,"!"},{TF_GREATER,">"},{TF_LESS,"<"},
        {TF_EQUAL_EQUAL,"=="},{TF_BANG_EQUAL,"!="},{TF_GREATER_EQUAL,">="},{TF_LESS_EQUAL,"<="}};
    static const struct {TfTokenKind kind;const char *text;} delimiters[]={
        {TF_LPAREN,"("},{TF_RPAREN,")"},{TF_LBRACKET,"["},{TF_RBRACKET,"]"},
        {TF_LBRACE,"{"},{TF_RBRACE,"}"},{TF_COMMA,","},{TF_SEMICOLON,";"},
        {TF_COLON,":"},{TF_DOT,"."},{TF_DOUBLE_COLON,"::"},{TF_ARROW,"->"},{TF_FAT_ARROW,"=>"}};
    TfSource s;TfLexResult r;FILE *report;char *output;size_t reserved=0,keywords=0;
    CHECK(tf_source_load(&s,"examples/lexical/complete.tfd",NULL)==TF_OK);
    CHECK(tf_lex(&r,&s,100,NULL)==TF_OK&&!r.has_errors&&r.diagnostic_count==0);
    for(size_t i=0;i<sizeof operators/sizeof *operators;++i)CHECK(present(&r,operators[i].kind,operators[i].text));
    for(size_t i=0;i<sizeof delimiters/sizeof *delimiters;++i)CHECK(present(&r,delimiters[i].kind,delimiters[i].text));
    CHECK(present(&r,TF_IDENT,"visitor")&&present(&r,TF_IDENT,"square"));
    CHECK(present(&r,TF_INT,"17")&&present(&r,TF_FLOAT,"1.25e1"));
    CHECK(present(&r,TF_TRUE,"true")&&present(&r,TF_FALSE,"false"));
    CHECK(present(&r,TF_TEXT,"\"Hello\\nTernfold\"")&&present(&r,TF_CHAR,"'\xce\xa9'"));
    CHECK(present(&r,TF_FROM,"from")&&present(&r,TF_TO,"to"));
    {bool line=false,block=false;for(size_t i=0;i<r.token_count;++i){line|=r.tokens[i].kind==TF_COMMENT_LINE;block|=r.tokens[i].kind==TF_COMMENT_BLOCK;}CHECK(line&&block);}
    for(size_t i=0;i<r.token_count;++i) {
        const TfToken *t=&r.tokens[i];bool unique=true;
        if(!t->reserved&&!(t->kind>=TF_AS&&t->kind<=TF_YIELDS))continue;
        for(size_t k=0;k<i;++k){const TfToken *p=&r.tokens[k];size_t n=t->span.end-t->span.start;
            if(p->span.end-p->span.start==n&&!memcmp(s.bytes+p->span.start,s.bytes+t->span.start,n)){unique=false;break;}}
        if(unique){if(t->reserved)++reserved;else++keywords;}
    }
    CHECK(reserved>=10&&keywords>=10);
    report=tmpfile();CHECK(report!=NULL&&tf_report_write_classroom(report,&r)==TF_OK);
    output=read_stream(report);CHECK(fclose(report)==0);
    CHECK(strstr(output,"NOISE_WORD\tfrom\n")&&strstr(output,"NOISE_WORD\tto\n"));
    CHECK(strstr(output,"KEYWORD\tlet\n")&&strstr(output,"FLOAT_LITERAL\t1.25e1\n"));
    CHECK(strstr(output,"TEXT_LITERAL\t\"Hello\\\\nTernfold\"\n"));
    golden(output,"tests/fixtures/lexer/Classroom Symbol Table.txt");golden(output,"Symbol Table.txt");
    free(output);tf_lex_destroy(&r);tf_source_destroy(&s);
    CHECK(tf_source_load(&s,"examples/lexical/invalid.tfd",NULL)==TF_OK);
    CHECK(tf_lex(&r,&s,100,NULL)==TF_LEX_ERROR&&r.has_errors);
    CHECK(present(&r,TF_INVALID,"@")&&present(&r,TF_INVALID,"09")&&present(&r,TF_INVALID,"1e+"));
    report=tmpfile();CHECK(report!=NULL&&tf_report_write_classroom(report,&r)==TF_OK);
    output=read_stream(report);CHECK(fclose(report)==0);CHECK(strstr(output,"INVALID\t@\n")!=NULL);
    golden(output,"tests/fixtures/lexer/Invalid Classroom Symbol Table.txt");free(output);
    tf_lex_destroy(&r);tf_source_destroy(&s);
    printf("professor sample: %zu checks passed; %zu distinct keywords, %zu reserved names; all 7 arithmetic and 9 Boolean/relational operators and 5 literal categories visible\n",checks,keywords,reserved);
    return 0;
}
