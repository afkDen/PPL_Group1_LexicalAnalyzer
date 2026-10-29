#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include "ternfold/lexer.h"

#include <errno.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <direct.h>
#include <process.h>
#define MKDIR(p) _mkdir(p)
#else
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#define MKDIR(p) mkdir(p,0700)
#endif

static size_t checks;
static char directory[512], report_path[600];
static void check(bool okay, const char *expression, int line) {
    ++checks;
    if (!okay) { (void)fprintf(stderr,"classroom:%d: %s\n",line,expression); exit(1); }
}
#define CHECK(x) check((x),#x,__LINE__)
static char *read_stream(FILE *f) {
    long length; char *bytes;
    CHECK(fseek(f,0,SEEK_END) == 0); length = ftell(f);
    CHECK(length >= 0 && (uintmax_t)length < SIZE_MAX);
    bytes = malloc((size_t)length+1); CHECK(bytes != NULL); CHECK(fseek(f,0,SEEK_SET) == 0);
    CHECK(fread(bytes,1,(size_t)length,f) == (size_t)length); bytes[(size_t)length] = '\0';
    CHECK(memchr(bytes,0,(size_t)length) == NULL); return bytes;
}
static char *read_report(void) {
    FILE *f = fopen(report_path,"rb"); char *bytes; CHECK(f != NULL);
    bytes = read_stream(f); CHECK(fclose(f) == 0); return bytes;
}
static void write_marker(void) {
    FILE *f = fopen(report_path,"wb"); CHECK(f != NULL);
    CHECK(fputs("old report",f) >= 0); CHECK(fclose(f) == 0);
}
static unsigned hex(char c) {
    CHECK((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'));
    return c <= '9' ? (unsigned)(c-'0') : (unsigned)(c-'a')+10u;
}
/* Independent decoder checks reversibility for every emitted lexeme, including
 * raw backslash-vs-escape distinction and C1 controls encoded as UTF-8. */
static void roundtrip(const char *report, const TfLexResult *result) {
    const char *at = report;
    size_t i;
    CHECK(strncmp(at,"TOKEN TYPE\tLEXEME\n",18) == 0); at += 18;
    for (i = 0; i < result->token_count; ++i) {
        const TfToken *t = &result->tokens[i];
        unsigned char decoded[4096]; size_t length = 0;
        if (t->kind == TF_EOF) continue;
        while (*at != '\t') { CHECK(*at != '\0' && *at != '\n'); ++at; }
        ++at;
        while (*at != '\n') {
            unsigned char c = (unsigned char)*at++;
            CHECK(c != 0 && c != '\t' && c != '\r' && length < sizeof(decoded)-2);
            if (c == '\\') {
                c = (unsigned char)*at++;
                if (c == 'n') c = '\n'; else if (c == 'r') c = '\r'; else if (c == 't') c = '\t';
                else if (c == 'u') {
                    unsigned scalar = 0; size_t j;
                    for (j = 0; j < 4; ++j) { CHECK(*at != '\0'); scalar = scalar*16u+hex(*at++); }
                    CHECK(scalar < 0xa0u);
                    if (scalar >= 0x80u) { decoded[length++] = 0xc2; c = (unsigned char)scalar; }
                    else c = (unsigned char)scalar;
                } else CHECK(c == '\\');
            }
            decoded[length++] = c;
        }
        ++at; CHECK(length == t->span.end-t->span.start);
        CHECK(memcmp(decoded,t->span.source->bytes+t->span.start,length) == 0);
    }
    CHECK(*at == '\0');
}
static void test_format(void) {
    static const char input[] = "let x = 42 + 3; \"hi\" '\xc3\xa9' \"\\n\\\\\"\r\n"
        "/*line1\r\n\tline2 \\n / \\ \xf0\x9f\x99\x82*/ @ //end";
    static const char expected[] = "TOKEN TYPE\tLEXEME\nKEYWORD\tlet\nIDENTIFIER\tx\nASSIGN\t=\n"
        "INT_LITERAL\t42\nPLUS\t+\nINT_LITERAL\t3\nSEMICOLON\t;\nTEXT_LITERAL\t\"hi\"\nCHAR_LITERAL\t'\xc3\xa9'\n"
        "TEXT_LITERAL\t\"\\\\n\\\\\\\\\"\nBLOCK_COMMENT\t/*line1\\r\\n\\tline2 \\\\n / \\\\ \xf0\x9f\x99\x82*/\nINVALID\t@\nLINE_COMMENT\t//end\n";
    TfSource source; TfLexResult result; FILE *f; char *actual;
    CHECK(tf_source_init(&source,"classroom.tfd",input,sizeof(input)-1,NULL) == TF_OK);
    CHECK(tf_lex(&result,&source,100,NULL) == TF_LEX_ERROR);
    f = tmpfile(); CHECK(f != NULL); CHECK(tf_report_write_classroom(f,&result) == TF_OK);
    actual = read_stream(f);
    if (strcmp(actual,expected) != 0) (void)fprintf(stderr,"expected:\n%sactual:\n%s",expected,actual);
    CHECK(strcmp(actual,expected) == 0); roundtrip(actual,&result); free(actual); CHECK(fclose(f) == 0);
    tf_lex_destroy(&result); tf_source_destroy(&source);
    {
        static const unsigned char control[] = {'/','*',0,'\t','\r','\n','\b','\f',0x7f,0xc2,0x85,'*','/'};
        CHECK(tf_source_init(&source,"control",control,sizeof(control),NULL) == TF_OK);
        CHECK(tf_lex(&result,&source,100,NULL) == TF_OK);
        f = tmpfile(); CHECK(f != NULL); CHECK(tf_report_write_classroom(f,&result) == TF_OK);
        actual = read_stream(f);
        CHECK(strcmp(actual,"TOKEN TYPE\tLEXEME\nBLOCK_COMMENT\t/*\\u0000\\t\\r\\n\\u0008\\u000c\\u007f\\u0085*/\n") == 0);
        roundtrip(actual,&result); free(actual); CHECK(fclose(f) == 0);
        tf_lex_destroy(&result); tf_source_destroy(&source);
    }
    {
        static const char noise[] = "{input x: Text from /*x*/ stdin; output 1 to stdout;} from";
        CHECK(tf_source_init(&source,"noise",noise,sizeof(noise)-1,NULL) == TF_OK);
    }
    CHECK(tf_lex(&result,&source,100,NULL) == TF_OK);
    f = tmpfile(); CHECK(f != NULL); CHECK(tf_report_write_classroom(f,&result) == TF_OK);
    actual = read_stream(f); CHECK(strstr(actual,"NOISE_WORD\tfrom\nBLOCK_COMMENT\t/*x*/\nKEYWORD\tstdin\n") != NULL);
    CHECK(strstr(actual,"NOISE_WORD\tto\nKEYWORD\tstdout\n") != NULL);
    roundtrip(actual,&result); free(actual); CHECK(fclose(f) == 0);
    tf_lex_destroy(&result); tf_source_destroy(&source);
}
static void test_empty_and_errors(void) {
    FILE *f; char *actual; TfSource source; TfLexResult result;
    CHECK(tf_report_write_classroom(NULL,NULL) == TF_HOST_ERROR);
    f = tmpfile(); CHECK(f != NULL); CHECK(tf_report_write_classroom(f,NULL) == TF_OK);
    actual = read_stream(f); CHECK(strcmp(actual,"TOKEN TYPE\tLEXEME\n") == 0); free(actual); CHECK(fclose(f) == 0);
    CHECK(tf_source_init(&source,"bad","\xff",1,NULL) == TF_SOURCE_ERROR);
    CHECK(tf_report_publish_classroom(NULL,&source,directory) == TF_OK);
    actual = read_report(); CHECK(strcmp(actual,"TOKEN TYPE\tLEXEME\n") == 0); free(actual); tf_source_destroy(&source);
    CHECK(tf_source_init(&source,"write","x",1,NULL) == TF_OK); CHECK(tf_lex(&result,&source,100,NULL) == TF_OK);
    f = fopen(report_path,"rb"); CHECK(f != NULL); CHECK(setvbuf(f,NULL,_IONBF,0) == 0);
    CHECK(tf_report_write_classroom(f,&result) == TF_HOST_ERROR); CHECK(ferror(f) != 0); CHECK(fclose(f) == 0);
    CHECK(tf_report_publish_classroom(&result,&source,"") == TF_HOST_ERROR);
    CHECK(tf_report_publish_classroom(&result,NULL,directory) == TF_HOST_ERROR);
    tf_lex_destroy(&result); tf_source_destroy(&source);
}
typedef struct { size_t calls, fail, live; } Memory;
static void *allocate(void *context, size_t size) {
    Memory *m = context; void *p; ++m->calls;
    if (m->calls == m->fail) return NULL;
    p = malloc(size); if (p != NULL) ++m->live; return p;
}
static void deallocate(void *context, void *p) {
    Memory *m = context; CHECK(p != NULL && m->live != 0); --m->live; free(p);
}
static void no_temporary(void) {
#ifdef _WIN32
    char pattern[700]; WIN32_FIND_DATAA data; HANDLE search;
    CHECK(snprintf(pattern,sizeof(pattern),"%s.tmp.*",report_path) > 0);
    search = FindFirstFileA(pattern,&data);
    if (search != INVALID_HANDLE_VALUE) { (void)FindClose(search); CHECK(false); }
    CHECK(GetLastError() == ERROR_FILE_NOT_FOUND);
#else
    DIR *dir = opendir(directory); struct dirent *entry; CHECK(dir != NULL); errno = 0;
    while ((entry = readdir(dir)) != NULL) CHECK(strncmp(entry->d_name,"Symbol Table.txt.tmp.",21) != 0);
    CHECK(errno == 0); CHECK(closedir(dir) == 0);
#endif
}
static void test_publication_failures(void) {
    size_t position; bool success = false;
    for (position = 1; position < 30; ++position) {
        Memory m = {0}; TfAllocator a = {&m,allocate,deallocate};
        TfSource source; TfLexResult result; TfStatus status; size_t live; char *actual;
        CHECK(tf_source_init(&source,"allocation","{{{{x}}}}",9,&a) == TF_OK);
        CHECK(tf_lex(&result,&source,100,&a) == TF_OK);
        live = m.live; write_marker(); m.fail = m.calls+position;
        status = tf_report_publish_classroom(&result,&source,directory);
        actual = read_report();
        if (status == TF_HOST_ERROR) CHECK(strcmp(actual,"old report") == 0);
        else { CHECK(status == TF_OK && strstr(actual,"IDENTIFIER\tx\n") != NULL); success = true; }
        free(actual); CHECK(m.live == live); no_temporary();
        tf_lex_destroy(&result); tf_source_destroy(&source); CHECK(m.live == 0);
        if (success) break;
    }
    CHECK(success);
}
int main(void) {
    unsigned long pid; unsigned attempt;
#ifdef _WIN32
    pid = (unsigned long)_getpid();
#else
    pid = (unsigned long)getpid();
#endif
    for (attempt = 0; attempt < 1000; ++attempt) {
        CHECK(snprintf(directory,sizeof(directory),"build/classroom-%lu-%u",pid,attempt) > 0);
        if (MKDIR(directory) == 0) break;
        CHECK(errno == EEXIST);
    }
    CHECK(attempt < 1000); CHECK(snprintf(report_path,sizeof(report_path),"%s/Symbol Table.txt",directory) > 0);
    test_format(); test_empty_and_errors(); test_publication_failures();
    CHECK(remove(report_path) == 0);
#ifdef _WIN32
    CHECK(RemoveDirectoryA(directory) != 0);
#else
    CHECK(rmdir(directory) == 0);
#endif
    (void)printf("classroom report: %zu checks passed\n",checks); return 0;
}
