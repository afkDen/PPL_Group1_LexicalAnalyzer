#include "ternfold/lexer.h"

#include <signal.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

static int host_error(const char *message) {
    (void)fprintf(stderr, "ternfold-lexer: %s\n", message);
    (void)fflush(stderr);
    return 2;
}
static bool source_extension(const char *path) {
    size_t length = strlen(path);
    return length >= 4 && path[length - 4] == '.' && path[length - 3] == 't' &&
           path[length - 2] == 'f' && path[length - 1] == 'd';
}
int main(int argc, char **argv) {
    TfSource source;
    TfLexResult result = {0};
    const char *directory = ".";
    const char *path = NULL;
    bool classroom = false, output_set = false;
    TfStatus status;
    int exit_code, i;
    TfStatus (*publish)(const TfLexResult *, const TfSource *, const char *);
#ifndef _WIN32
    /* Convert a closed stdout/stderr pipe to checked stdio failure, not signal
     * termination. Library stream writers leave signal policy to their caller. */
    if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) return 2;
#else
    if (_setmode(_fileno(stdout), _O_BINARY) == -1 ||
        _setmode(_fileno(stderr), _O_BINARY) == -1) return 2;
#endif
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        if (fputs("Usage: ternfold-lexer source.tfd [--output-dir DIR] [--classroom]\n"
                  "       ternfold-lexer --help\n"
                  "Source and options may appear in any order; options occur once. DIR must exist.\n"
                  "Writes Symbol Table.txt (TOKEN TYPE and LEXEME).\n"
                  "Default: lossless JSON-quoted lexemes. --classroom: plain lexemes, source quotes once.\n"
                  "Classroom escapes: \\n LF, \\r CR, \\t TAB, \\\\ backslash, \\u00xx other controls.\n"
                  "Decode escapes once; quotes are literal source characters. Unicode remains UTF-8.\n"
                  "Exit: 0 success, 1 source/lexical error, 2 usage/host failure.\n", stdout) < 0 ||
            fflush(stdout) != 0) return 2;
        return 0;
    }
    for (i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--classroom") == 0 && !classroom) classroom = true;
        else if (strcmp(argv[i], "--output-dir") == 0 && !output_set && i + 1 < argc &&
                 argv[i + 1][0] != '\0') {
            directory = argv[++i]; output_set = true;
        } else if (argv[i][0] != '-' && argv[i][0] != '\0' && path == NULL) path = argv[i];
        else return host_error("unknown, duplicate or incomplete argument; use --help");
    }
    if (path == NULL) return host_error("expected source.tfd [--output-dir DIR] [--classroom]; use --help");
    publish = classroom ? tf_report_publish_classroom : tf_report_publish;
    if (!source_extension(path)) {
        if (fputs("ternfold-lexer: source file extension must be exactly .tfd\n", stderr) < 0 ||
            fflush(stderr) != 0) return 2;
        return 1;
    }
    status = tf_source_load(&source, path, NULL);
    if (status == TF_HOST_ERROR) return host_error("cannot read source file or allocate source storage");
    if (status == TF_SOURCE_ERROR) {
        exit_code = 1;
        if (publish(NULL, &source, directory) != TF_OK) exit_code = 2;
    } else {
        status = tf_lex(&result, &source, 100, NULL);
        if (status == TF_HOST_ERROR) {
            tf_source_destroy(&source);
            return host_error("cannot allocate lexical result");
        }
        exit_code = status == TF_LEX_ERROR ? 1 : 0;
        if (publish(&result, &source, directory) != TF_OK) exit_code = 2;
    }
    if (tf_diagnostics_write(stderr, &source, source.valid ? &result : NULL) != TF_OK ||
        fflush(stderr) != 0) exit_code = 2;
    tf_lex_destroy(&result);
    tf_source_destroy(&source);
    if (exit_code == 2) return host_error("cannot publish report or write diagnostics");
    if (fputs("Symbol Table.txt written\n", stdout) < 0 || fflush(stdout) != 0) return 2;
    return exit_code;
}
