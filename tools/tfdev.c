/* Native development driver. Compiler processes receive argv, never shell text. */
#include <errno.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <direct.h>
#include <process.h>
#define MKDIR(path) _mkdir(path)
#define EXE ".exe"
#else
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#define MKDIR(path) mkdir(path, 0777)
#define EXE ""
#endif

static int run(const char *const *args) {
    fflush(NULL);
#ifdef _WIN32
    /* The Windows CRT spawn API joins argv without protecting spaces. Quote
     * every element using its backslash/quote rules, with no shell involved. */
    char *quoted[64];
    size_t count = 0;
    intptr_t status;
    for (; args[count] && count < 63; ++count) {
        size_t length = strlen(args[count]), at = 0, i = 0;
        if (length > (SIZE_MAX - 3) / 2) return 2;
        quoted[count] = malloc(length * 2 + 3);
        if (!quoted[count]) { while (count) free(quoted[--count]); return 2; }
        quoted[count][at++] = '"';
        while (i < length) {
            size_t slashes = 0;
            while (i < length && args[count][i] == '\\') { ++slashes; ++i; }
            if (i == length || args[count][i] == '"') slashes *= 2;
            while (slashes) { quoted[count][at++] = '\\'; --slashes; }
            if (i < length) {
                if (args[count][i] == '"') quoted[count][at++] = '\\';
                quoted[count][at++] = args[count][i++];
            }
        }
        quoted[count][at++] = '"'; quoted[count][at] = '\0';
    }
    quoted[count] = NULL;
    status = _spawnvp(_P_WAIT, args[0], (const char *const *)quoted);
    while (count) free(quoted[--count]);
    if (status < 0) { perror(args[0]); return 2; }
    return (int)status;
#else
    pid_t pid = fork();
    int status;
    if (pid < 0) { perror("fork"); return 2; }
    if (pid == 0) { execvp(args[0], (char *const *)args); perror(args[0]); _exit(127); }
    while (waitpid(pid, &status, 0) < 0) { if (errno != EINTR) return 2; }
    return WIFEXITED(status) ? WEXITSTATUS(status) : 2;
#endif
}

static int directory(const char *path) {
    if (MKDIR(path) != 0 && errno != EEXIST) { perror(path); return 2; }
    return 0;
}
static int audit_run(const char *path) {
    FILE *marker = fopen("LEXICAL_PACKAGE", "rb");
    const char *args[] = {path, marker ? "--lexical" : NULL, NULL};
    if (marker) fclose(marker);
    return run(args);
}

static int compile(const char *cc, const char *output, const char *last,
                   int sanitize, int library, int release) {
    const char *args[40];
    size_t n = 0;
    args[n++] = cc;
    args[n++] = "-std=c17";
    args[n++] = "-Wall"; args[n++] = "-Wextra"; args[n++] = "-Werror";
    args[n++] = "-pedantic"; args[n++] = "-Wconversion"; args[n++] = "-Wshadow";
    args[n++] = "-g";
    if (release) args[n++] = "-O2";
    if (sanitize) { args[n++] = "-fsanitize=address,undefined";
        args[n++] = "-fno-sanitize-recover=all";
        args[n++] = "-fno-omit-frame-pointer"; }
    args[n++] = "-Iinclude";
    if (library) {
        args[n++] = "src/source.c"; args[n++] = "src/lexer.c";
        args[n++] = "src/report.c";
    }
    args[n++] = last;
    args[n++] = "-o"; args[n++] = output; args[n] = NULL;
    return run(args);
}

int main(int argc, char **argv) {
    const char *cc = getenv("TF_CC");
    const char *mode = argc > 1 ? argv[1] : "check";
    int status, sanitize = strcmp(mode, "sanitize") == 0;
    int release = strcmp(mode, "release") == 0;
    char lexer[96], unit[96], audit[96], integration[96], classroom[96], demo[96];
    if (!cc || !*cc) cc = "cc";
    if (directory("build")) return 2;
    if (strcmp(mode, "environment") == 0 || strcmp(mode, "env") == 0) {
        const char *args[] = {cc, "--version", NULL};
        status = run(args);
        if (status) return status;
        status = compile(cc, "build/environment" EXE, "tools/environment.c", 0, 0, 0);
        if (status) return status;
        { const char *probe[] = {"build/environment" EXE, NULL}; return run(probe); }
    }
    if (strcmp(mode, "audit") == 0) {
        status = compile(cc, "build/audit" EXE, "tools/audit.c", 0, 0, 0);
        if (status) return status;
        return audit_run("build/audit" EXE);
    }
    if (strcmp(mode, "build") && strcmp(mode, "test") && strcmp(mode, "check") && !sanitize && !release) {
        fprintf(stderr, "tfdev: expected environment|build|test|audit|check|sanitize|release\n");
        return 2;
    }
    snprintf(lexer, sizeof lexer, "build/ternfold-lexer%s" EXE, sanitize ? "-san" : "");
    snprintf(unit, sizeof unit, "build/test-lexer%s" EXE, sanitize ? "-san" : "");
    snprintf(integration, sizeof integration, "build/test-integration%s" EXE, sanitize ? "-san" : "");
    snprintf(audit, sizeof audit, "build/audit%s" EXE, sanitize ? "-san" : "");
    snprintf(classroom, sizeof classroom, "build/test-classroom%s" EXE, sanitize ? "-san" : "");
    snprintf(demo, sizeof demo, "build/test-demo%s" EXE, sanitize ? "-san" : "");
    status = compile(cc, lexer, "src/main.c", sanitize, 1, release);
    if (status || !strcmp(mode, "build")) return status;
    status = compile(cc, unit, "tests/test_lexer.c", sanitize, 1, release);
    if (status) return status;
    { const char *args[] = {unit, NULL}; status = run(args); if (status) return status; }
    status = compile(cc, integration, "tests/test_integration.c", sanitize, 1, release);
    if (status) return status;
    { const char *args[] = {integration, lexer, NULL}; status = run(args); if (status) return status; }
    status = compile(cc, classroom, "tests/test_classroom.c", sanitize, 1, release);
    if (status) return status;
    { const char *args[] = {classroom, NULL}; status = run(args); if (status) return status; }
    status = compile(cc, demo, "tests/test_demo.c", sanitize, 1, release);
    if (status) return status;
    { const char *args[] = {demo, NULL}; status = run(args); if (status) return status; }
    if (!strcmp(mode, "check") || release || sanitize) {
        status = compile(cc, audit, "tools/audit.c", sanitize, 0, release);
        if (status) return status;
        return audit_run(audit);
    }
    return 0;
}
