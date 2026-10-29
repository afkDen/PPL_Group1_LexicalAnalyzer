#include "ternfold/lexer.h"
#include <stdlib.h>
#include <string.h>

/* Independent specification inventory; never reads scanner tables/graphs. */
typedef struct { const char *word; TfTokenKind kind; bool reserved; } Word;
#define K(w,k) {w,k,false}
#define R(w) {w,TF_IDENT,true}
static const Word words[] = {
    K("as",TF_AS), K("div",TF_DIV), K("else",TF_ELSE), K("emit",TF_EMIT),
    K("enum",TF_ENUM), K("false",TF_FALSE), K("fn",TF_FN), K("for",TF_FOR),
    K("from",TF_FROM), K("guard",TF_GUARD), K("if",TF_IF), K("import",TF_IMPORT),
    K("in",TF_IN), K("input",TF_INPUT), K("let",TF_LET), K("machine",TF_MACHINE),
    K("match",TF_MATCH), K("next",TF_NEXT), K("output",TF_OUTPUT), K("pub",TF_PUB),
    K("record",TF_RECORD), K("rejects",TF_REJECTS), K("state",TF_STATE),
    K("stdin",TF_STDIN), K("stdout",TF_STDOUT), K("to",TF_TO), K("true",TF_TRUE),
    K("yields",TF_YIELDS), R("Int"), R("Float"), R("Bool"), R("Text"), R("Char"),
    R("Unit"), R("List"), R("Option"), R("Decision"), R("step"), R("len"), R("at"),
    R("append"), R("map"), R("fold"), R("range"), R("int_text"), R("bool_text"),
    R("parse_int"), R("text_len"), R("text_at"), R("text_slice"), R("int_float"),
    R("float_int"), R("float_text")
};
static const Word symbols[] = {
    K("+",TF_PLUS), K("-",TF_MINUS), K("/",TF_SLASH), K("*",TF_STAR),
    K("%",TF_PERCENT), K("^",TF_CARET), K("&&",TF_AND_AND), K("||",TF_OR_OR),
    K("!",TF_BANG), K(">",TF_GREATER), K("<",TF_LESS), K("==",TF_EQUAL_EQUAL),
    K("!=",TF_BANG_EQUAL), K(">=",TF_GREATER_EQUAL), K("<=",TF_LESS_EQUAL),
    K("_",TF_UNDERSCORE), K("++",TF_PLUS_PLUS), K("->",TF_ARROW), K("=>",TF_FAT_ARROW),
    K("::",TF_DOUBLE_COLON), K("(",TF_LPAREN), K(")",TF_RPAREN), K("[",TF_LBRACKET),
    K("]",TF_RBRACKET), K("{",TF_LBRACE), K("}",TF_RBRACE), K(",",TF_COMMA),
    K(";",TF_SEMICOLON), K(":",TF_COLON), K(".",TF_DOT), K("=",TF_EQUAL)
};
static const Word ordinary[]={K("main",TF_IDENT),K("Some",TF_IDENT),
    K("None",TF_IDENT),K("Accept",TF_IDENT),K("Reject",TF_IDENT)};
#define COUNT(a) (sizeof(a)/sizeof *(a))
static size_t checks, corpus_cases;
static void check(bool okay, const char *expr, int line) {
    ++checks;
    if (!okay) { fprintf(stderr,"coverage:%d: %s\n",line,expr); exit(1); }
}
#define CHECK(x) check((x),#x,__LINE__)
static bool spelling(const TfToken *t, const char *s) {
    size_t n = strlen(s);
    return t->span.end-t->span.start == n && !memcmp(t->span.source->bytes+t->span.start,s,n);
}
static void scan(TfSource *s, TfLexResult *r, const char *text) {
    CHECK(tf_source_init(s,"coverage.tfd",text,strlen(text),NULL)==TF_OK);
    { TfStatus status=tf_lex(r,s,100,NULL); CHECK(status==TF_OK || status==TF_LEX_ERROR); }
}
static void destroy(TfSource *s, TfLexResult *r) { tf_lex_destroy(r); tf_source_destroy(s); }
static void hex(FILE *f, const unsigned char *bytes, size_t n) {
    for(size_t i=0;i<n;++i) CHECK(fprintf(f,"%02x",(unsigned)bytes[i])==2);
}
static void copy(FILE *to, FILE *from) {
    int c; CHECK(fflush(from)==0 && fseek(from,0,SEEK_SET)==0);
    while((c=fgetc(from))!=EOF) CHECK(fputc(c,to)!=EOF);
    CHECK(!ferror(from));
}
static void exact(FILE *actual,const char *path) {
    FILE *expected=fopen(path,"rb"); int a,b;
    CHECK(expected!=NULL); CHECK(fflush(actual)==0 && fseek(actual,0,SEEK_SET)==0);
    do { a=fgetc(actual); b=fgetc(expected); CHECK(a==b); } while(a!=EOF);
    CHECK(!ferror(actual)&&!ferror(expected)); CHECK(fclose(expected)==0);
}
/* Baseline includes original bytes, payloads, token/diagnostic spans, exact
 * diagnostic text and both report encodings. Bounded, deterministic, no RNG. */
static void snapshot(FILE *out,const char *text) {
    TfSource s; TfLexResult r; FILE *f;
    scan(&s,&r,text); ++corpus_cases;
    CHECK(fprintf(out,"CASE %zu ",corpus_cases)>0); hex(out,s.bytes,s.length);
    CHECK(fprintf(out,"\nRESULT %d %zu %zu %zu\n",r.has_errors?1:0,r.token_count,r.diagnostic_count,r.suppressed)>0);
    for(size_t i=0;i<r.token_count;++i) {
        const TfToken *t=&r.tokens[i];
        CHECK(fprintf(out,"T %s %zu %zu %d %s ",tf_token_name(t->kind),t->span.start,t->span.end,t->reserved?1:0,tf_error_code(t->error))>0);
        hex(out,t->value,t->value_length); CHECK(fputc('\n',out)!=EOF);
    }
    for(size_t i=0;i<r.diagnostic_count;++i) {
        TfDiagnostic d=r.diagnostics[i];
        CHECK(fprintf(out,"D %s %zu %zu %s\n",tf_error_code(d.code),d.span.start,d.span.end,tf_error_message(d.code))>0);
    }
    f=tmpfile(); CHECK(f!=NULL); CHECK(tf_diagnostics_write(f,&s,&r)==TF_OK);
    copy(out,f); CHECK(fclose(f)==0);
    f=tmpfile(); CHECK(f!=NULL); CHECK(tf_report_write(f,&r)==TF_OK);
    copy(out,f); CHECK(fclose(f)==0);
    f=tmpfile(); CHECK(f!=NULL); CHECK(tf_report_write_classroom(f,&r)==TF_OK);
    copy(out,f); CHECK(fclose(f)==0); destroy(&s,&r);
}
static void corpus(FILE *out) {
    static const char *const suffix[]={"","x","0","_","_tail"};
    static const char *const nums[]={"0","9","17","00","09","1.","1.foo","1.2.foo","1.25e1","1e-3","1e999","9223372036854775808","1e","1e+","1e-","1efoo","1e++2","1efoo.bar","1.2.3","1e999foo","2_0","2e3e4"};
    static const char *const ends[]={"", ";let recovered=3;", "/*ok*/next", "\r\ntrue"};
    static const char *const odd[]={"", "//end", "/*x*/", "/*outer /*inner*/ */", "/*unfinished", "& | @ \\ ` $", "\xce\xa9 let recovered=3;", "\"bad\\q\" let recovered=3;", "\"bad\nlet recovered=3;", "'' 'ab' '\\q' '\\u{d800}'", "\"\\u{110000}\"", "'\xce\xa9' \"\\u{0}\\u{10ffff}\"", "input x:Text from stdin; output x to stdout;", "from to stdin stdout", "a+++b->c=>d::e!=f<=g>=h==i&&j||!k", "1/*x*/+2//z\n3", "*/", "_ __ _0 _a", "\"\\u{}\" \"\\u{1234567}\"", "'\nlet recovered=3;", "\"unterminated", "'unterminated"};
    char text[256];
    for(size_t i=0;i<COUNT(words);++i) for(size_t j=0;j<COUNT(suffix);++j) {
        int n=snprintf(text,sizeof text,"%s%s",words[i].word,suffix[j]);
        CHECK(n>=0 && (size_t)n<sizeof text); snapshot(out,text);
        if(j==0) continue;
        n=snprintf(text,sizeof text,"_%s%s",words[i].word,suffix[j]);
        CHECK(n>=0 && (size_t)n<sizeof text); snapshot(out,text);
    }
    for(size_t i=0;i<COUNT(nums);++i) for(size_t j=0;j<COUNT(ends);++j) {
        int n=snprintf(text,sizeof text,"%s%s",nums[i],ends[j]);
        CHECK(n>=0 && (size_t)n<sizeof text); snapshot(out,text);
    }
    for(size_t i=0;i<COUNT(odd);++i) snapshot(out,odd[i]);
    for(size_t i=0;i<COUNT(symbols);++i) snapshot(out,symbols[i].word);
}
static void boundaries(void) {
    static const char *const tails[]={"x","0","_","_tail"};
    char text[80]; TfSource s; TfLexResult r;
    CHECK(COUNT(words)==53 && COUNT(symbols)==31);
    for(size_t i=0;i<COUNT(words);++i) {
        scan(&s,&r,words[i].word);
        CHECK(!r.has_errors && r.token_count==2 && r.diagnostic_count==0);
        CHECK(r.tokens[0].kind==words[i].kind && r.tokens[0].reserved==words[i].reserved);
        CHECK(r.tokens[0].span.start==0 && r.tokens[0].span.end==strlen(words[i].word));
        CHECK(r.tokens[1].kind==TF_EOF && r.tokens[1].span.start==s.length && r.tokens[1].span.end==s.length);
        destroy(&s,&r);
        for(size_t j=0;j<COUNT(tails);++j) {
            int n=snprintf(text,sizeof text,"%s%s",words[i].word,tails[j]);
            CHECK(n>=0 && (size_t)n<sizeof text); scan(&s,&r,text);
            CHECK(!r.has_errors && r.token_count==2);
            CHECK(r.tokens[0].kind==TF_IDENT && !r.tokens[0].reserved && spelling(&r.tokens[0],text));
            destroy(&s,&r);
        }
    }
}
static void inventory(const char *path, FILE *matrix) {
    TfSource s; TfLexResult r;
    CHECK(tf_source_load(&s,path,NULL)==TF_OK);
    CHECK(tf_lex(&r,&s,100,NULL)==TF_OK && !r.has_errors && r.diagnostic_count==0);
    for(size_t i=0;i<COUNT(words)+COUNT(symbols)+COUNT(ordinary);++i) {
        const Word *w=i<COUNT(words)?&words[i]:i<COUNT(words)+COUNT(symbols)?
            &symbols[i-COUNT(words)]:&ordinary[i-COUNT(words)-COUNT(symbols)];
        size_t found=0;
        for(size_t j=0;j<r.token_count;++j) if(spelling(&r.tokens[j],w->word)) {
            TfLocation loc; const TfToken *t=&r.tokens[j];
            CHECK(t->kind==w->kind && t->reserved==w->reserved && t->error==TF_E_NONE);
            CHECK(tf_source_location(&s,t->span.start,&loc)); ++found;
            if(matrix) CHECK(fprintf(matrix,"%s\t%s\t%s\t%d\t%zu\t%zu\t%zu\t%zu\n",path,w->word,tf_token_name(t->kind),t->reserved?1:0,t->span.start,t->span.end,loc.line,loc.column)>0);
        }
        if(!found) fprintf(stderr,"missing actual token %s in %s\n",w->word,path);
        CHECK(found>0);
    }
    destroy(&s,&r);
}
static void invalid_rules(void) {
    static const struct { const char *bad; TfError error; const char *separator; } cases[]={
        {"@",TF_E101," "},{"&",TF_E101," "},{"|",TF_E101," "},
        {"\\",TF_E101," "},{"`",TF_E101," "},{"$",TF_E101," "},
        {"\xce\xa9",TF_E101," "},{"\0",TF_E101," "},
        {"09",TF_E102," "},{"00",TF_E102," "},{"1e",TF_E102," "},
        {"1e+",TF_E102," "},{"1e-",TF_E102," "},{"1efoo",TF_E102," "},
        {"1e999foo",TF_E102," "},{"1.2.3",TF_E102," "},
        {"1_0",TF_E102," "},{"2e3e4",TF_E102," "},
        {"\"bad\\q\"",TF_E103," "},{"\"\\u{}\"",TF_E103," "},
        {"\"\\u{d800}\"",TF_E103," "},{"\"\\u{110000}\"",TF_E103," "},
        {"\"\\u{1234567}\"",TF_E103," "},{"\"\\u{xyz}\"",TF_E103," "},
        {"\"unterminated",TF_E103,"\n"},{"\"raw\tcontrol\"",TF_E103," "},
        {"''",TF_E105," "},{"'ab'",TF_E105," "},{"'\\q'",TF_E105," "},
        {"'\\u{}'",TF_E105," "},{"'\\u{d800}'",TF_E105," "},
        {"'\\u{110000}'",TF_E105," "},{"'\\u{1234567}'",TF_E105," "},
        {"'unterminated",TF_E105,"\n"},{"'\t'",TF_E105," "}
    };
    static const struct { TfError error; const char *code,*message; } errors[]={
        {TF_E001,"E001","source is not valid UTF-8"},
        {TF_E002,"E002","source must not start with a UTF-8 BOM"},
        {TF_E003,"E003","lone CR is not a source line ending"},
        {TF_E101,"E101","unsupported source character"},
        {TF_E102,"E102","malformed decimal numeric literal"},
        {TF_E103,"E103","malformed or unterminated Text literal"},
        {TF_E104,"E104","unterminated block comment"},
        {TF_E105,"E105","Char literal must contain exactly one valid scalar"}
    };
    for(size_t i=0;i<COUNT(errors);++i) {
        CHECK(!strcmp(tf_error_code(errors[i].error),errors[i].code));
        CHECK(!strcmp(tf_error_message(errors[i].error),errors[i].message));
    }
    for(size_t i=0;i<COUNT(cases);++i) {
        TfSource s; TfLexResult r; unsigned char input[128];
        size_t n=i==7?1:strlen(cases[i].bad), sep=strlen(cases[i].separator);
        memcpy(input,cases[i].bad,n); memcpy(input+n,cases[i].separator,sep);
        memcpy(input+n+sep,"recovered",9);
        CHECK(tf_source_init(&s,"invalid-rule.tfd",input,n+sep+9,NULL)==TF_OK);
        for(size_t cap=0;cap<2;++cap) {
            CHECK(tf_lex(&r,&s,cap,NULL)==TF_LEX_ERROR && r.has_errors);
            CHECK(r.token_count==3 && r.tokens[0].kind==TF_INVALID);
            CHECK(r.tokens[0].error==cases[i].error && r.tokens[0].span.start==0 && r.tokens[0].span.end==n);
            CHECK(r.tokens[1].kind==TF_IDENT && !r.tokens[1].reserved && spelling(&r.tokens[1],"recovered"));
            CHECK(r.tokens[1].span.start==n+sep && r.tokens[1].span.end==n+sep+9);
            CHECK(r.tokens[2].kind==TF_EOF && r.tokens[2].span.start==s.length && r.tokens[2].span.end==s.length);
            CHECK(r.diagnostic_count==cap && r.suppressed==1-cap);
            if(cap) CHECK(r.diagnostics[0].code==cases[i].error && r.diagnostics[0].span.start==0 && r.diagnostics[0].span.end==n);
            tf_lex_destroy(&r);
        }
        tf_source_destroy(&s);
    }
    { TfSource s; TfLexResult r;
      scan(&s,&r,"/*unfinished");
      CHECK(r.has_errors && r.token_count==2 && r.diagnostic_count==1);
      CHECK(r.tokens[0].kind==TF_INVALID && r.tokens[0].error==TF_E104);
      CHECK(r.tokens[0].span.start==0 && r.tokens[0].span.end==12);
      destroy(&s,&r);
    }
}
static void valid_boundaries(void) {
    static const struct { const char *text; TfTokenKind kind; } cases[]={
        {"0",TF_INT},{"9223372036854775808",TF_INT},{"1e999",TF_FLOAT},
        {"0.0",TF_FLOAT},{"1e-3",TF_FLOAT},{"1E+3",TF_FLOAT},
        {"'\xce\xa9'",TF_CHAR},{"'\\u{10ffff}'",TF_CHAR},{"'\\u{0}'",TF_CHAR},
        {"\"\\u{0}\\u{10ffff}\"",TF_TEXT},{"\"\\\"\\\\\\n\\r\\t\"",TF_TEXT},
        {"//at EOF",TF_COMMENT_LINE},{"/*a /*b*/",TF_COMMENT_BLOCK},
        {"*/",TF_BLOCK_CLOSE},{"_",TF_UNDERSCORE},{"__",TF_IDENT}
    };
    for(size_t i=0;i<COUNT(cases);++i) {
        TfSource s; TfLexResult r; scan(&s,&r,cases[i].text);
        CHECK(!r.has_errors && r.diagnostic_count==0 && r.token_count==2);
        CHECK(r.tokens[0].kind==cases[i].kind && !r.tokens[0].reserved);
        CHECK(r.tokens[0].span.start==0 && r.tokens[0].span.end==strlen(cases[i].text));
        destroy(&s,&r);
    }
    { TfSource s; TfLexResult r; scan(&s,&r,"1e++2 1efoo.bar 1.foo 1.2.foo");
      static const Word expected[]={K("1e+",TF_INVALID),K("+",TF_PLUS),K("2",TF_INT),
          K("1efoo",TF_INVALID),K(".",TF_DOT),K("bar",TF_IDENT),K("1",TF_INT),
          K(".",TF_DOT),K("foo",TF_IDENT),K("1.2",TF_FLOAT),K(".",TF_DOT),K("foo",TF_IDENT)};
      CHECK(r.has_errors && r.token_count==COUNT(expected)+1 && r.diagnostic_count==2);
      for(size_t i=0;i<COUNT(expected);++i) CHECK(r.tokens[i].kind==expected[i].kind && spelling(&r.tokens[i],expected[i].word));
      destroy(&s,&r);
    }
    { TfSource s; TfLexResult r; TfLocation loc;
      scan(&s,&r,"'\xce\xa9'\r\n\tlet x=0;");
      CHECK(!r.has_errors && r.token_count==7);
      CHECK(r.tokens[1].kind==TF_LET && r.tokens[1].span.start==7 && r.tokens[1].span.end==10);
      CHECK(tf_source_location(&s,7,&loc) && loc.line==2 && loc.column==2);
      destroy(&s,&r);
    }
}
static void source_fixtures(void) {
    static const struct { const char *path; TfError error; size_t start,end; } cases[]={
        {"tests/fixtures/invalid/utf8-invalid.tfd",TF_E001,2,3},
        {"tests/fixtures/invalid/utf8-truncated.tfd",TF_E001,2,4},
        {"tests/fixtures/invalid/utf8-bom.tfd",TF_E002,0,3},
        {"tests/fixtures/invalid/lone-cr.tfd",TF_E003,1,2}
    };
    for(size_t i=0;i<COUNT(cases);++i) {
        TfSource s; FILE *f; TfLocation loc; char header[32]={0};
        CHECK(tf_source_load(&s,cases[i].path,NULL)==TF_SOURCE_ERROR && !s.valid);
        CHECK(s.error.code==cases[i].error && s.error.span.start==cases[i].start && s.error.span.end==cases[i].end);
        CHECK(!tf_source_location(&s,0,&loc));
        f=tmpfile(); CHECK(f!=NULL && tf_report_write_classroom(f,NULL)==TF_OK);
        CHECK(fflush(f)==0 && fseek(f,0,SEEK_SET)==0);
        CHECK(fread(header,1,sizeof header,f)==18 && !strcmp(header,"TOKEN TYPE\tLEXEME\n"));
        CHECK(fclose(f)==0); tf_source_destroy(&s);
    }
    { TfSource s; TfLexResult r;
      CHECK(tf_source_load(&s,"tests/fixtures/invalid/embedded-nul.tfd",NULL)==TF_OK);
      CHECK(tf_lex(&r,&s,100,NULL)==TF_LEX_ERROR && r.token_count==4 && r.diagnostic_count==1);
      CHECK(r.tokens[1].kind==TF_INVALID && r.tokens[1].error==TF_E101 && r.tokens[1].span.start==1 && r.tokens[1].span.end==2);
      CHECK(spelling(&r.tokens[2],"b")); destroy(&s,&r);
    }
}
static void fixture_goldens(bool capture) {
    static const struct { const char *input,*stem; size_t errors; bool valid_source; } fixtures[]={
        {"examples/lexical/complete.tfd","complete",0,true},
        {"examples/lexical/vocabulary.tfd","vocabulary",0,true},
        {"examples/lexical/trace.tfd","trace",6,true},
        {"examples/lexical/invalid-comprehensive.tfd","invalid-comprehensive",33,true},
        {"tests/fixtures/invalid/utf8-invalid.tfd","utf8-invalid",0,false},
        {"tests/fixtures/invalid/utf8-truncated.tfd","utf8-truncated",0,false},
        {"tests/fixtures/invalid/utf8-bom.tfd","utf8-bom",0,false},
        {"tests/fixtures/invalid/lone-cr.tfd","lone-cr",0,false},
        {"tests/fixtures/invalid/embedded-nul.tfd","embedded-nul",1,true}
    };
    static const char *const suffix[]={"classroom.txt","lossless.txt","diagnostics.txt"};
    for(size_t i=0;i<COUNT(fixtures);++i) {
        TfSource s; TfLexResult r={0}; const TfLexResult *view=NULL;
        TfStatus status=tf_source_load(&s,fixtures[i].input,NULL);
        CHECK(status==(fixtures[i].valid_source?TF_OK:TF_SOURCE_ERROR));
        if(status==TF_OK) {
            status=tf_lex(&r,&s,100,NULL);
            CHECK(status==(fixtures[i].errors?TF_LEX_ERROR:TF_OK));
            CHECK(r.diagnostic_count==fixtures[i].errors && !r.suppressed);
            CHECK(r.has_errors==(fixtures[i].errors!=0)); view=&r;
        }
        for(size_t j=0;j<COUNT(suffix);++j) {
            char path[160]; FILE *f=tmpfile(); int n;
            CHECK(f!=NULL);
            if(j==0) CHECK(tf_report_write_classroom(f,view)==TF_OK);
            else if(j==1) CHECK(tf_report_write(f,view)==TF_OK);
            else CHECK(tf_diagnostics_write(f,&s,view)==TF_OK);
            n=snprintf(path,sizeof path,"tests/fixtures/invalid/%s.%s",fixtures[i].stem,suffix[j]);
            CHECK(n>=0 && (size_t)n<sizeof path);
            if(capture) {
                FILE *out=fopen(path,"wb"); CHECK(out!=NULL); copy(out,f); CHECK(fclose(out)==0);
            } else exact(f,path);
            CHECK(fclose(f)==0);
        }
        destroy(&s,&r);
    }
}
static void report_categories(void) {
    static const char expected[]="TOKEN TYPE\tLEXEME\nRESERVED_WORD\tBool\nBOOL_LITERAL\ttrue\nBOOL_LITERAL\tfalse\nDIV\tdiv\nBLOCK_CLOSE\t*/\n";
    TfSource s; TfLexResult r; FILE *f; char actual[sizeof expected]={0};
    scan(&s,&r,"Bool true false div */"); f=tmpfile();
    CHECK(f!=NULL && tf_report_write_classroom(f,&r)==TF_OK);
    CHECK(fflush(f)==0 && fseek(f,0,SEEK_SET)==0);
    CHECK(fread(actual,1,sizeof actual,f)==sizeof expected-1);
    CHECK(!memcmp(actual,expected,sizeof expected));
    CHECK(fclose(f)==0); destroy(&s,&r);
}
int main(int argc,char **argv) {
    if(argc==2 && !strcmp(argv[1],"--capture-fixtures")) {
        FILE *matrix;
        fixture_goldens(true);
        matrix=fopen("tests/fixtures/invalid/coverage.tsv","wb"); CHECK(matrix!=NULL);
        CHECK(fputs("source\tspelling\tkind\treserved\tstart\tend\tline\tcolumn\n",matrix)>=0);
        inventory("examples/lexical/complete.tfd",matrix);
        inventory("examples/lexical/vocabulary.tfd",matrix);
        CHECK(fclose(matrix)==0);
        puts("captured reports for documented new/expanded input fixtures only"); return 0;
    }
    FILE *f=tmpfile(); CHECK(f!=NULL); corpus(f);
    if(argc==2 && !strcmp(argv[1],"--capture-baseline")) {
        FILE *out=fopen("tests/fixtures/invalid/old-scanner.baseline.txt","wb"); CHECK(out!=NULL);
        copy(out,f); CHECK(fclose(out)==0); CHECK(fclose(f)==0);
        printf("captured %zu old-scanner cases\n",corpus_cases); return 0;
    }
    CHECK(argc==1); exact(f,"tests/fixtures/invalid/old-scanner.baseline.txt"); CHECK(fclose(f)==0);
    boundaries(); invalid_rules(); valid_boundaries(); source_fixtures();
    report_categories(); fixture_goldens(false);
    f=tmpfile(); CHECK(f!=NULL);
    CHECK(fputs("source\tspelling\tkind\treserved\tstart\tend\tline\tcolumn\n",f)>=0);
    inventory("examples/lexical/complete.tfd",f);
    inventory("examples/lexical/vocabulary.tfd",f);
    exact(f,"tests/fixtures/invalid/coverage.tsv");
    CHECK(fclose(f)==0);
    printf("independent lexical coverage: %zu checks; %zu frozen corpus cases; 28 keywords, 25 reserved, 31 symbols per demo\n",checks,corpus_cases);
    return 0;
}
