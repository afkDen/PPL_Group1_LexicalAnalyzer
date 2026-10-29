/* Black-box CLI tests. Reports are checked against a maintained on-disk golden
 * and hand-derived compact expectations. This harness does not call the
 * scanner/report library to manufacture its own expected output.
 * Only fixtures beneath build/integration-fixtures are written. No shell runs. */
#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <direct.h>
#include <process.h>
#define MAKE_DIRECTORY(path) _mkdir(path)
#define EXE_SUFFIX ".exe"
#else
#include <dirent.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#define MAKE_DIRECTORY(path) mkdir(path, 0700)
#define EXE_SUFFIX ""
#endif

enum { PATH_CAPACITY = 2048, CHILD_TIMEOUT_MS = 15000 };
typedef struct { unsigned char *bytes; size_t length; } Bytes;
typedef enum { CAPTURE, BROKEN_PIPE } StreamMode;
static size_t checks, cases, skips;
static const char *current_case = "setup";
static char root[PATH_CAPACITY], output_path[PATH_CAPACITY], error_path[PATH_CAPACITY];

static void check(bool condition, const char *expression, int line) {
    ++checks;
    if (!condition) {
        (void)fprintf(stderr, "integration:%d [%s]: %s\nfixtures: %s\n",
                      line, current_case, expression, root);
        exit(1);
    }
}
#define CHECK(expression) check((expression), #expression, __LINE__)
static void begin(const char *name) { current_case = name; ++cases; }
static void skipped(const char *reason) {
    ++skips;
    (void)printf("SKIP [%s]: %s\n", current_case, reason);
}
static void join_path(char *out, const char *directory, const char *leaf) {
    int count = snprintf(out, PATH_CAPACITY, "%s/%s", directory, leaf);
    CHECK(count >= 0 && (size_t)count < PATH_CAPACITY);
}
static bool is_directory(const char *path) {
#ifdef _WIN32
    struct _stat info;
    return _stat(path, &info) == 0 && (info.st_mode & _S_IFDIR) != 0;
#else
    struct stat info;
    return stat(path, &info) == 0 && S_ISDIR(info.st_mode);
#endif
}
static void directory(const char *path) {
    int status = MAKE_DIRECTORY(path);
    CHECK(status == 0 || (errno == EEXIST && is_directory(path)));
}
static unsigned long process_id(void) {
#ifdef _WIN32
    return (unsigned long)_getpid();
#else
    return (unsigned long)getpid();
#endif
}
static void setup(void) {
    unsigned int attempt;
    directory("build");
    directory("build/integration-fixtures");
    for (attempt = 0; attempt < 1000; ++attempt) {
        int count = snprintf(root, sizeof(root), "build/integration-fixtures/run-%lu-%u",
                              process_id(), attempt);
        CHECK(count > 0 && (size_t)count < sizeof(root));
        if (MAKE_DIRECTORY(root) == 0) break;
        CHECK(errno == EEXIST);
    }
    CHECK(attempt < 1000);
    join_path(output_path, root, "stdout.txt");
    join_path(error_path, root, "stderr.txt");
}
static void write_bytes(const char *path, const void *data, size_t length) {
    FILE *stream = fopen(path, "wb");
    CHECK(stream != NULL);
    CHECK(fwrite(data, 1, length, stream) == length);
    CHECK(fflush(stream) == 0);
    CHECK(fclose(stream) == 0);
}
static void write_text(const char *path, const char *text) { write_bytes(path, text, strlen(text)); }
static Bytes read_bytes(const char *path) {
    Bytes result = {NULL, 0};
    size_t capacity = 4096;
    FILE *stream = fopen(path, "rb");
    CHECK(stream != NULL);
    result.bytes = malloc(capacity + 1);
    CHECK(result.bytes != NULL);
    for (;;) {
        size_t got;
        if (result.length == capacity) {
            unsigned char *fresh;
            CHECK(capacity <= (SIZE_MAX - 1) / 2);
            capacity *= 2;
            fresh = realloc(result.bytes, capacity + 1);
            CHECK(fresh != NULL);
            result.bytes = fresh;
        }
        got = fread(result.bytes + result.length, 1, capacity - result.length, stream);
        result.length += got;
        CHECK(!ferror(stream));
        if (feof(stream)) break;
        CHECK(got != 0);
    }
    result.bytes[result.length] = 0;
    CHECK(fclose(stream) == 0);
    return result;
}
static void destroy_bytes(Bytes bytes) { free(bytes.bytes); }
static void expect_bytes(const char *path, const void *data, size_t length) {
    Bytes actual = read_bytes(path);
    CHECK(actual.length == length);
    CHECK(length == 0 || memcmp(actual.bytes, data, length) == 0);
    destroy_bytes(actual);
}
static void expect_text(const char *path, const char *text) { expect_bytes(path, text, strlen(text)); }
static void expect_contains(const char *path, const char *fragment) {
    Bytes actual = read_bytes(path);
    CHECK(memchr(actual.bytes, 0, actual.length) == NULL);
    if (strstr((const char *)actual.bytes, fragment) == NULL) {
        (void)fprintf(stderr, "missing fragment: %s\nactual %s:\n%s\n", fragment, path, actual.bytes);
        CHECK(false);
    }
    destroy_bytes(actual);
}
static void expect_absent(const char *path) {
    FILE *stream;
    errno = 0;
    stream = fopen(path, "rb");
    if (stream != NULL) (void)fclose(stream);
    CHECK(stream == NULL && errno == ENOENT);
}

#ifdef _WIN32
/* Microsoft CRT command-line decoding: surround each argument with quotes,
 * double trailing backslashes and those preceding a quote, then escape quotes.
 * Application path is separate, so executable names never become shell text. */
static char *command_line(const char *const *args) {
    size_t total = 1, count = 0, n, at = 0;
    char *line;
    while (args[count] != NULL) {
        size_t length = strlen(args[count]);
        CHECK(length <= (SIZE_MAX - 4) / 2);
        CHECK(total <= SIZE_MAX - (length * 2 + 4));
        total += length * 2 + 4;
        ++count;
    }
    CHECK(total <= 32767);
    line = malloc(total);
    CHECK(line != NULL);
    for (n = 0; n < count; ++n) {
        size_t i = 0, length = strlen(args[n]);
        if (n != 0) line[at++] = ' ';
        line[at++] = '"';
        while (i < length) {
            size_t slashes = 0;
            while (i < length && args[n][i] == '\\') { ++slashes; ++i; }
            if (i == length || args[n][i] == '"') slashes *= 2;
            while (slashes != 0) { line[at++] = '\\'; --slashes; }
            if (i < length) {
                if (args[n][i] == '"') line[at++] = '\\';
                line[at++] = args[n][i++];
            }
        }
        line[at++] = '"';
    }
    line[at] = '\0';
    CHECK(at < total);
    return line;
}
static HANDLE child_stream(const char *path, StreamMode mode) {
    SECURITY_ATTRIBUTES attributes = {sizeof(SECURITY_ATTRIBUTES), NULL, TRUE};
    HANDLE stream;
    if (mode == BROKEN_PIPE) {
        HANDLE reader;
        CHECK(CreatePipe(&reader, &stream, &attributes, 0) != 0);
        CHECK(CloseHandle(reader) != 0); /* no readers when child starts */
    } else {
        stream = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, &attributes,
                             CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        CHECK(stream != INVALID_HANDLE_VALUE);
    }
    return stream;
}
static int spawn_at(const char *const *args, StreamMode out_mode, StreamMode err_mode,
                    const char *working_directory) {
    SECURITY_ATTRIBUTES attributes = {sizeof(SECURITY_ATTRIBUTES), NULL, TRUE};
    STARTUPINFOA startup = {0};
    PROCESS_INFORMATION process = {0};
    HANDLE input, output, error;
    char *line = command_line(args);
    DWORD waited, code;
    BOOL created;
    input = CreateFileA("NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &attributes,
                        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    CHECK(input != INVALID_HANDLE_VALUE);
    output = child_stream(output_path, out_mode);
    error = child_stream(error_path, err_mode);
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = input;
    startup.hStdOutput = output;
    startup.hStdError = error;
    created = CreateProcessA(args[0], line, NULL, NULL, TRUE, CREATE_NO_WINDOW,
                              NULL, working_directory, &startup, &process);
    free(line);
    CHECK(CloseHandle(input) != 0);
    CHECK(CloseHandle(output) != 0);
    CHECK(CloseHandle(error) != 0);
    if (!created) (void)fprintf(stderr, "CreateProcess failed for %s\n", args[0]);
    CHECK(created != 0);
    CHECK(CloseHandle(process.hThread) != 0);
    waited = WaitForSingleObject(process.hProcess, CHILD_TIMEOUT_MS);
    if (waited != WAIT_OBJECT_0) {
        (void)TerminateProcess(process.hProcess, 125);
        (void)WaitForSingleObject(process.hProcess, 1000);
        (void)CloseHandle(process.hProcess);
        CHECK(false); /* timeout/infrastructure failure never passes */
    }
    CHECK(GetExitCodeProcess(process.hProcess, &code) != 0);
    CHECK(CloseHandle(process.hProcess) != 0);
    CHECK(code <= 255); /* includes sanitizer crashes and loader failures */
    return (int)code;
}
#else
static int child_stream(const char *path, StreamMode mode) {
    if (mode == BROKEN_PIPE) {
        int descriptors[2];
        CHECK(pipe(descriptors) == 0);
        CHECK(close(descriptors[0]) == 0);
        return descriptors[1];
    }
    {
        int descriptor = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0600);
        CHECK(descriptor >= 0);
        return descriptor;
    }
}
static int spawn_at(const char *const *args, StreamMode out_mode, StreamMode err_mode,
                    const char *working_directory) {
    int input = open("/dev/null", O_RDONLY);
    int output = child_stream(output_path, out_mode), error = child_stream(error_path, err_mode);
    pid_t pid;
    int status;
    struct timespec start, now, pause = {0, 10000000L};
    CHECK(input >= 0);
    CHECK(fflush(NULL) == 0);
    CHECK(clock_gettime(CLOCK_MONOTONIC, &start) == 0);
    pid = fork();
    CHECK(pid >= 0);
    if (pid == 0) {
        if (working_directory != NULL && chdir(working_directory) != 0) _exit(126);
        if (dup2(input, STDIN_FILENO) < 0 || dup2(output, STDOUT_FILENO) < 0 ||
            dup2(error, STDERR_FILENO) < 0) _exit(126);
        if (input > STDERR_FILENO) (void)close(input);
        if (output > STDERR_FILENO) (void)close(output);
        if (error > STDERR_FILENO) (void)close(error);
        execv(args[0], (char *const *)args);
        _exit(127);
    }
    CHECK(close(input) == 0 && close(output) == 0 && close(error) == 0);
    for (;;) {
        pid_t waited = waitpid(pid, &status, WNOHANG);
        if (waited == pid) break;
        if (waited < 0) { CHECK(errno == EINTR); continue; }
        CHECK(clock_gettime(CLOCK_MONOTONIC, &now) == 0);
        if (now.tv_sec - start.tv_sec >= CHILD_TIMEOUT_MS / 1000) {
            (void)kill(pid, SIGKILL);
            while (waitpid(pid, &status, 0) < 0 && errno == EINTR) { }
            CHECK(false);
        }
        while (nanosleep(&pause, &pause) != 0) CHECK(errno == EINTR);
        pause = (struct timespec){0, 10000000L};
    }
    CHECK(WIFEXITED(status));
    return WEXITSTATUS(status);
}
#endif

static int spawn(const char *const *args, StreamMode out_mode, StreamMode err_mode) {
    return spawn_at(args, out_mode, err_mode, NULL);
}
static int run(const char *lexer, const char *source, const char *output_directory) {
    const char *args[] = {lexer, source, "--output-dir", output_directory, NULL};
    return spawn(args, CAPTURE, CAPTURE);
}
static void clean_temps(const char *output_directory) {
#ifdef _WIN32
    WIN32_FIND_DATAA data;
    char pattern[PATH_CAPACITY];
    HANDLE search;
    join_path(pattern, output_directory, "Symbol Table.txt.tmp.*");
    search = FindFirstFileA(pattern, &data);
    if (search != INVALID_HANDLE_VALUE) {
        (void)FindClose(search);
        CHECK(false);
    }
    CHECK(GetLastError() == ERROR_FILE_NOT_FOUND);
#else
    DIR *stream = opendir(output_directory);
    struct dirent *entry;
    CHECK(stream != NULL);
    errno = 0;
    while ((entry = readdir(stream)) != NULL)
        CHECK(strncmp(entry->d_name, "Symbol Table.txt.tmp.", 21) != 0);
    CHECK(errno == 0);
    CHECK(closedir(stream) == 0);
#endif
}
static void table_path(char *out, const char *output_directory) {
    join_path(out, output_directory, "Symbol Table.txt");
}
static void report_shape(const char *path) {
    Bytes report = read_bytes(path);
    size_t i, tabs = 0, rows = 0;
    CHECK(report.length >= strlen("TOKEN TYPE\tLEXEME\n"));
    CHECK(memcmp(report.bytes, "TOKEN TYPE\tLEXEME\n", strlen("TOKEN TYPE\tLEXEME\n")) == 0);
    CHECK(report.bytes[report.length - 1] == '\n');
    for (i = 0; i < report.length; ++i) {
        CHECK(report.bytes[i] < 128 && report.bytes[i] != '\r' && report.bytes[i] != 0);
        if (report.bytes[i] == '\t') ++tabs;
        if (report.bytes[i] == '\n') { CHECK(tabs == 1); tabs = 0; ++rows; }
    }
    CHECK(rows > 1);
    CHECK(strstr((const char *)report.bytes, "EOF\t") == NULL);
    CHECK(strstr((const char *)report.bytes, "UNIT_LITERAL\t") == NULL);
    CHECK(strstr((const char *)report.bytes, "WHITESPACE\t") == NULL);
    destroy_bytes(report);
}

static void test_examples(const char *lexer) {
    char destination[PATH_CAPACITY], table[PATH_CAPACITY], lf_source[PATH_CAPACITY];
    Bytes baseline, golden;
    begin("complete coursework example disk golden and repeat determinism");
    join_path(destination, root, "complete-example");
    directory(destination);
    table_path(table, destination);
    /* The maintained golden describes LF source bytes. Make that fixture
     * explicit even when Git checks out the demonstration with native CRLF.
     * Exact CRLF preservation is independently checked by the next test. */
    join_path(lf_source, root, "complete-lf.tfd");
    {
        Bytes example = read_bytes("examples/lexical/complete.tfd");
        size_t at, used = 0;
        for (at = 0; at < example.length; ++at) {
            if (example.bytes[at] == '\r' && at + 1 < example.length && example.bytes[at+1] == '\n') continue;
            example.bytes[used++] = example.bytes[at];
        }
        write_bytes(lf_source, example.bytes, used); destroy_bytes(example);
    }
    CHECK(run(lexer, lf_source, destination) == 0);
    golden = read_bytes("tests/fixtures/lexer/Symbol Table.txt");
    /* Git may also convert the text golden's record separators to CRLF.
     * Compare its original LF records, without changing escaped lexeme bytes. */
    {
        size_t at, used = 0;
        for (at = 0; at < golden.length; ++at) {
            if (golden.bytes[at] == '\r' && at + 1 < golden.length && golden.bytes[at+1] == '\n') continue;
            golden.bytes[used++] = golden.bytes[at];
        }
        golden.length = used;
    }
    expect_bytes(table, golden.bytes, golden.length);
    expect_text(error_path, "");
    expect_text(output_path, "Symbol Table.txt written\n");
    report_shape(table);
    expect_contains(table, "CHAR_LITERAL\t\"'\\u03a9'\"\n");
    expect_contains(table, "FLOAT_LITERAL\t\"1.25e1\"\n");
    expect_contains(table, "NOISE_WORD\t\"from\"\n");
    expect_contains(table, "NOISE_WORD\t\"to\"\n");
    expect_contains(table, "RESERVED_WORD\t\"Float\"\n");
    baseline = read_bytes(table);
    CHECK(run(lexer, lf_source, destination) == 0);
    expect_bytes(table, golden.bytes, golden.length);
    expect_bytes(table, baseline.bytes, baseline.length);
    destroy_bytes(baseline);
    destroy_bytes(golden);
    clean_temps(destination);

    begin("invalid coursework example exact report and recovery");
    join_path(destination, root, "invalid-example");
    directory(destination);
    table_path(table, destination);
    CHECK(run(lexer, "examples/lexical/invalid.tfd", destination) == 1);
    {
        static const char expected_prefix[] = "TOKEN TYPE\tLEXEME\n"
            "LINE_COMMENT\t\"// Intentionally invalid: E101, E102, E103, E105, E104.\"\n"
            "INVALID\t\"@\"\nINVALID\t\"09\"\nINVALID\t\"1e+\"\n"
            "INVALID\t\"\\\"bad\\\\q\\\"\"\nINVALID\t\"'ab'\"\n"
            "KEYWORD\t\"let\"\nIDENTIFIER\t\"recovered\"\nASSIGN\t\"=\"\n"
            "INT_LITERAL\t\"3\"\nSEMICOLON\t\";\"\n";
        Bytes example = read_bytes("examples/lexical/invalid.tfd"), report = read_bytes(table);
        const char *last;
        size_t prefix_length = strlen(expected_prefix);
        CHECK(example.length > 1 && example.bytes[example.length - 1] == '\n');
        last = example.bytes[example.length - 2] == '\r'
                   ? "INVALID\t\"/* unfinished\\r\\n\"\n" : "INVALID\t\"/* unfinished\\n\"\n";
        CHECK(report.length == prefix_length + strlen(last));
        CHECK(memcmp(report.bytes, expected_prefix, prefix_length) == 0);
        CHECK(memcmp(report.bytes + prefix_length, last, strlen(last)) == 0);
        destroy_bytes(report);
        destroy_bytes(example);
    }
    expect_contains(error_path, "E101");
    expect_contains(error_path, "E102");
    expect_contains(error_path, "E103");
    expect_contains(error_path, "E104");
    expect_contains(error_path, "E105");
    report_shape(table);
    clean_temps(destination);
}

static void test_golden_and_spaced_executable(const char *lexer) {
    static const char source_text[] = "// caf\xc3\xa9\r\n/*one\r\ntwo*/\r\n"
        "{ input who: Text from stdin; output \"hi\\n\" to stdout; }\r\n"
        "'\xce\xa9' true false 17 1.5 + - / * % div ^ && || ! > < == != >= <= ()\r\n";
    static const char expected[] = "TOKEN TYPE\tLEXEME\n"
        "LINE_COMMENT\t\"// caf\\u00e9\"\nBLOCK_COMMENT\t\"/*one\\r\\ntwo*/\"\n"
        "LBRACE\t\"{\"\nKEYWORD\t\"input\"\nIDENTIFIER\t\"who\"\nCOLON\t\":\"\n"
        "RESERVED_WORD\t\"Text\"\nNOISE_WORD\t\"from\"\nKEYWORD\t\"stdin\"\nSEMICOLON\t\";\"\n"
        "KEYWORD\t\"output\"\nTEXT_LITERAL\t\"\\\"hi\\\\n\\\"\"\nNOISE_WORD\t\"to\"\n"
        "KEYWORD\t\"stdout\"\nSEMICOLON\t\";\"\nRBRACE\t\"}\"\n"
        "CHAR_LITERAL\t\"'\\u03a9'\"\nBOOL_LITERAL\t\"true\"\nBOOL_LITERAL\t\"false\"\n"
        "INT_LITERAL\t\"17\"\nFLOAT_LITERAL\t\"1.5\"\nPLUS\t\"+\"\nMINUS\t\"-\"\n"
        "SLASH\t\"/\"\nSTAR\t\"*\"\nPERCENT\t\"%\"\nDIV\t\"div\"\nCARET\t\"^\"\n"
        "AND_AND\t\"&&\"\nOR_OR\t\"||\"\nBANG\t\"!\"\nGREATER\t\">\"\nLESS\t\"<\"\n"
        "EQUAL_EQUAL\t\"==\"\nBANG_EQUAL\t\"!=\"\nGREATER_EQUAL\t\">=\"\nLESS_EQUAL\t\"<=\"\n"
        "LPAREN\t\"(\"\nRPAREN\t\")\"\n";
    char folder[PATH_CAPACITY], executable[PATH_CAPACITY], source[PATH_CAPACITY];
    char destination[PATH_CAPACITY], table[PATH_CAPACITY], trailing[PATH_CAPACITY];
    Bytes executable_bytes;
    begin("spaced executable/source/directory and exact CRLF Unicode golden");
    join_path(folder, root, "cli folder & plain data");
    directory(folder);
    join_path(executable, folder, "ternfold spaced & executable" EXE_SUFFIX);
    executable_bytes = read_bytes(lexer);
    write_bytes(executable, executable_bytes.bytes, executable_bytes.length);
    destroy_bytes(executable_bytes);
#ifndef _WIN32
    CHECK(chmod(executable, 0700) == 0);
#endif
    join_path(source, folder, "source & data ; $().tfd");
    join_path(destination, folder, "output with spaces");
    directory(destination);
    table_path(table, destination);
    write_text(source, source_text);
    {
#ifdef _WIN32
        const char *separator = "\\";
#else
        const char *separator = "/";
#endif
        int count = snprintf(trailing, sizeof(trailing), "%s%s", destination, separator);
        CHECK(count > 0 && (size_t)count < sizeof(trailing));
    }
    CHECK(run(executable, source, trailing) == 0);
    expect_text(table, expected);
    expect_text(error_path, "");
    expect_text(source, source_text);
    CHECK(run(executable, source, destination) == 0);
    expect_text(table, expected);
    clean_temps(destination);
}

static void test_usage_and_failures(const char *lexer) {
    static const char marker[] = "previous report must remain intact\n";
    char destination[PATH_CAPACITY], table[PATH_CAPACITY], source[PATH_CAPACITY];
    char missing[PATH_CAPACITY], wrong_extension[PATH_CAPACITY];
    begin("help and usage reject before source/report mutation");
    join_path(destination, root, "failures");
    directory(destination);
    table_path(table, destination);
    join_path(source, root, "valid.tfd");
    write_text(source, "let x = 1;");
    write_text(table, marker);
    {
        const char *help[] = {lexer, "--help", NULL};
        const char *none[] = {lexer, NULL};
        const char *unknown[] = {lexer, "--unknown", NULL};
        const char *extra[] = {lexer, source, "extra", NULL};
        const char *bad_flag[] = {lexer, source, "--bad", destination, NULL};
        const char *empty[] = {lexer, source, "--output-dir", "", NULL};
        CHECK(spawn(help, CAPTURE, CAPTURE) == 0);
        expect_contains(output_path, "Usage:");
        expect_text(error_path, "");
        CHECK(spawn(none, CAPTURE, CAPTURE) == 2);
        CHECK(spawn(unknown, CAPTURE, CAPTURE) == 2);
        CHECK(spawn(extra, CAPTURE, CAPTURE) == 2);
        CHECK(spawn(bad_flag, CAPTURE, CAPTURE) == 2);
        CHECK(spawn(empty, CAPTURE, CAPTURE) == 2);
        expect_text(table, marker);
    }
    begin("missing source and exact extension rejection preserve prior report");
    join_path(missing, root, "does-not-exist.tfd");
    expect_absent(missing);
    CHECK(run(lexer, missing, destination) == 2);
    expect_text(table, marker);
    join_path(wrong_extension, root, "missing.txt");
    CHECK(run(lexer, wrong_extension, destination) == 1); /* before reading */
    expect_contains(error_path, "extension");
    expect_text(table, marker);
    join_path(wrong_extension, root, "uppercase.TFD");
    write_text(wrong_extension, "0");
    CHECK(run(lexer, wrong_extension, destination) == 1);
    expect_text(table, marker);
    join_path(wrong_extension, root, "suffix.tfd.txt");
    write_text(wrong_extension, "0");
    CHECK(run(lexer, wrong_extension, destination) == 1);
    expect_text(table, marker);
    begin("nonexistent and non-directory output fail without source mutation");
    join_path(missing, root, "missing-output-directory");
    CHECK(run(lexer, source, missing) == 2);
    expect_absent(missing);
    join_path(missing, root, "ordinary-file");
    write_text(missing, marker);
    CHECK(run(lexer, source, missing) == 2);
    expect_text(missing, marker);
    expect_text(source, "let x = 1;");
    expect_text(table, marker);
    clean_temps(destination);
}

static void test_source_errors_and_coordinates(const char *lexer) {
    typedef struct { const unsigned char *bytes; size_t length; const char *code, *span; } InvalidSource;
    static const unsigned char utf8[] = {'\r', 0xff};
    static const unsigned char truncated[] = {'x', 0xe2, 0x82};
    static const unsigned char bom[] = {0xef, 0xbb, 0xbf, '\r'};
    static const unsigned char cr[] = {'x', '\r', 'y'};
    static const InvalidSource inputs[] = {
        {utf8, sizeof(utf8), "E001", "[bytes 1..2)"},
        {truncated, sizeof(truncated), "E001", "[bytes 1..3)"},
        {bom, sizeof(bom), "E002", "[bytes 0..3)"},
        {cr, sizeof(cr), "E003", "[bytes 1..2)"}
    };
    char destination[PATH_CAPACITY], table[PATH_CAPACITY], source[PATH_CAPACITY];
    size_t i;
    begin("source validation precedence raw diagnostics and header-only reports");
    join_path(destination, root, "source-errors");
    directory(destination);
    table_path(table, destination);
    join_path(source, root, "malformed.tfd");
    for (i = 0; i < sizeof(inputs) / sizeof(inputs[0]); ++i) {
        write_bytes(source, inputs[i].bytes, inputs[i].length);
        write_text(table, "old table replaced only with a complete header\n");
        CHECK(run(lexer, source, destination) == 1);
        expect_text(table, "TOKEN TYPE\tLEXEME\n");
        expect_contains(error_path, inputs[i].code);
        expect_contains(error_path, inputs[i].span);
        expect_contains(error_path, "raw bytes");
        expect_bytes(source, inputs[i].bytes, inputs[i].length);
        clean_temps(destination);
    }
    begin("diagnostics retain UTF-8 byte offsets scalar columns and CRLF");
    write_text(source, "//\xc3\xa9\r\n\t@\r\n");
    CHECK(run(lexer, source, destination) == 1);
    expect_contains(error_path, ":2:2: E101:");
    expect_contains(error_path, "[bytes 7..8)");
    expect_text(table, "TOKEN TYPE\tLEXEME\nLINE_COMMENT\t\"//\\u00e9\"\nINVALID\t\"@\"\n");
    begin("empty valid source produces exactly the header");
    write_text(source, "");
    CHECK(run(lexer, source, destination) == 0);
    expect_text(table, "TOKEN TYPE\tLEXEME\n");
    expect_text(error_path, "");
}

static void test_default_output_and_cap(const char *lexer) {
    char destination[PATH_CAPACITY], table[PATH_CAPACITY], source[PATH_CAPACITY];
    char executable[PATH_CAPACITY];
    begin("source-only command publishes in child working directory");
    join_path(destination, root, "default-output");
    directory(destination);
    table_path(table, destination);
    join_path(source, destination, "default.tfd");
    write_text(source, "42");
#ifdef _WIN32
    {
        DWORD count = GetFullPathNameA(lexer, PATH_CAPACITY, executable, NULL);
        CHECK(count > 0 && count < PATH_CAPACITY);
    }
#else
    {
        char current[PATH_CAPACITY];
        CHECK(getcwd(current, sizeof(current)) != NULL);
        if (lexer[0] == '/') {
            int count = snprintf(executable, sizeof(executable), "%s", lexer);
            CHECK(count > 0 && (size_t)count < sizeof(executable));
        } else join_path(executable, current, lexer);
    }
#endif
    {
        const char *args[] = {executable, "default.tfd", NULL};
        CHECK(spawn_at(args, CAPTURE, CAPTURE, destination) == 0);
    }
    expect_text(table, "TOKEN TYPE\tLEXEME\nINT_LITERAL\t\"42\"\n");
    expect_text(source, "42");
    expect_text(error_path, "");
    clean_temps(destination);
    begin("CLI diagnostic cap retains all invalid report rows and failure status");
    {
        unsigned char invalid[210];
        size_t i;
        Bytes report;
        const char *at;
        for (i = 0; i < sizeof(invalid); i += 2) { invalid[i] = '@'; invalid[i + 1] = ' '; }
        write_bytes(source, invalid, sizeof(invalid));
        CHECK(run(lexer, source, destination) == 1);
        report = read_bytes(table);
        CHECK(report.length == strlen("TOKEN TYPE\tLEXEME\n") + 105 * strlen("INVALID\t\"@\"\n"));
        at = (const char *)report.bytes + strlen("TOKEN TYPE\tLEXEME\n");
        for (i = 0; i < 105; ++i) {
            CHECK(memcmp(at, "INVALID\t\"@\"\n", strlen("INVALID\t\"@\"\n")) == 0);
            at += strlen("INVALID\t\"@\"\n");
        }
        destroy_bytes(report);
        expect_contains(error_path, "5 further diagnostics suppressed (5 errors)");
        expect_bytes(source, invalid, sizeof(invalid));
        clean_temps(destination);
    }
}

static void test_publication_and_links(const char *lexer) {
    static const char marker[] = "alias source contents: never overwrite\n";
    char destination[PATH_CAPACITY], table[PATH_CAPACITY], source[PATH_CAPACITY];
    char occupied[PATH_CAPACITY], child[PATH_CAPACITY];
    begin("failed atomic replace cleans sibling and preserves destination");
    join_path(destination, root, "occupied-output");
    directory(destination);
    table_path(table, destination);
    directory(table);
    join_path(occupied, table, "keep.txt");
    write_text(occupied, marker);
    join_path(source, root, "publication.tfd");
    write_text(source, "0");
    CHECK(run(lexer, source, destination) == 2);
    CHECK(is_directory(table));
    expect_text(occupied, marker);
    expect_text(source, "0");
    clean_temps(destination);

    begin("failed replacement preserves an existing regular report");
    join_path(destination, root, "locked-output");
    directory(destination);
    table_path(table, destination);
    write_text(table, marker);
#ifdef _WIN32
    {
        /* Omitting FILE_SHARE_DELETE forces atomic replacement to fail after
         * the new sibling has been fully written and closed. */
        HANDLE locked = CreateFileA(table, GENERIC_READ, FILE_SHARE_READ, NULL,
                                     OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        int status;
        CHECK(locked != INVALID_HANDLE_VALUE);
        status = run(lexer, source, destination);
        CHECK(CloseHandle(locked) != 0);
        CHECK(status == 2);
        expect_text(table, marker);
    }
#else
    if (geteuid() == 0) skipped("root bypasses output-directory permission restrictions");
    else {
        int status;
        CHECK(chmod(destination, 0500) == 0);
        status = run(lexer, source, destination);
        CHECK(chmod(destination, 0700) == 0);
        CHECK(status == 2);
        expect_text(table, marker);
    }
#endif
    expect_text(source, "0");
    clean_temps(destination);

    begin("source hard link at report path is rejected without mutation");
    join_path(destination, root, "hardlink-output");
    directory(destination);
    table_path(table, destination);
    write_text(source, marker);
#ifdef _WIN32
    if (CreateHardLinkA(table, source, NULL) != 0) {
#else
    if (link(source, table) == 0) {
#endif
        CHECK(run(lexer, source, destination) == 2);
        expect_text(source, marker);
        expect_text(table, marker);
        clean_temps(destination);
    } else {
#ifdef _WIN32
        DWORD error = GetLastError();
        CHECK(error == ERROR_NOT_SUPPORTED || error == ERROR_INVALID_FUNCTION ||
              error == ERROR_ACCESS_DENIED || error == ERROR_PRIVILEGE_NOT_HELD);
#else
        CHECK(errno == EPERM || errno == EACCES || errno == ENOSYS || errno == EOPNOTSUPP);
#endif
        skipped("filesystem does not permit hard links");
    }
    begin("source symbolic alias to report path is rejected without mutation");
    join_path(destination, root, "symlink-output");
    directory(destination);
    table_path(table, destination);
    join_path(child, root, "symbolic-source.tfd");
    write_text(table, marker);
#ifdef _WIN32
    {
        char absolute[PATH_CAPACITY];
        DWORD count = GetFullPathNameA(table, PATH_CAPACITY, absolute, NULL);
        CHECK(count > 0 && count < PATH_CAPACITY);
        /* Unprivileged creation is allowed only on supporting Windows hosts.
         * Retry without the flag solely for older systems rejecting the flag. */
        if (CreateSymbolicLinkA(child, absolute, 2) == 0) {
            DWORD error = GetLastError();
            if (error != ERROR_INVALID_PARAMETER || CreateSymbolicLinkA(child, absolute, 0) == 0) {
                error = GetLastError();
                CHECK(error == ERROR_PRIVILEGE_NOT_HELD || error == ERROR_NOT_SUPPORTED ||
                      error == ERROR_ACCESS_DENIED || error == ERROR_INVALID_FUNCTION);
                skipped("host does not permit unprivileged symbolic links");
                return;
            }
        }
    }
#else
    /* Both children are directly below root, so this relative target resolves
     * without realpath or fixed-size absolute-path assumptions. */
    if (symlink("symlink-output/Symbol Table.txt", child) != 0) {
        CHECK(errno == EPERM || errno == EACCES || errno == ENOSYS || errno == EOPNOTSUPP);
        skipped("filesystem does not permit symbolic links");
        return;
    }
#endif
    CHECK(run(lexer, child, destination) == 2);
    expect_text(child, marker);
    expect_text(table, marker);
    clean_temps(destination);
}

static void test_broken_streams(const char *lexer) {
    char source[PATH_CAPACITY], destination[PATH_CAPACITY], table[PATH_CAPACITY];
    begin("closed stdout pipe gives host failure for help");
    {
        const char *help[] = {lexer, "--help", NULL};
        CHECK(spawn(help, BROKEN_PIPE, CAPTURE) == 2);
    }
    begin("closed stdout pipe gives host failure after successful publication");
    join_path(source, root, "streams.tfd");
    join_path(destination, root, "streams-output");
    directory(destination);
    table_path(table, destination);
    write_text(source, "0");
    {
        const char *args[] = {lexer, source, "--output-dir", destination, NULL};
        CHECK(spawn(args, BROKEN_PIPE, CAPTURE) == 2);
    }
    expect_text(table, "TOKEN TYPE\tLEXEME\nINT_LITERAL\t\"0\"\n");
    expect_text(source, "0");
    clean_temps(destination);
    begin("closed stderr pipe gives host failure while reporting lexical error");
    write_text(source, "@");
    {
        const char *args[] = {lexer, source, "--output-dir", destination, NULL};
        CHECK(spawn(args, CAPTURE, BROKEN_PIPE) == 2);
    }
    expect_text(table, "TOKEN TYPE\tLEXEME\nINVALID\t\"@\"\n");
    expect_text(source, "@");
    clean_temps(destination);
}

static void test_classroom(const char *lexer) {
    char source[PATH_CAPACITY], destination[PATH_CAPACITY], table[PATH_CAPACITY], missing[PATH_CAPACITY];
    join_path(source,root,"classroom spaced.tfd");
    join_path(destination,root,"classroom spaced output"); directory(destination); table_path(table,destination);
    join_path(missing,root,"classroom-missing");
    begin("classroom plain golden and flexible option order");
    write_text(source,"let x = 42; \"hi\" '\xc3\xa9' /*a\r\n\tb \\n*/ @");
    {
        const char *args[] = {lexer,"--classroom","--output-dir",destination,source,NULL};
        CHECK(spawn(args,CAPTURE,CAPTURE) == 1);
    }
    expect_text(table,"TOKEN TYPE\tLEXEME\nKEYWORD\tlet\nIDENTIFIER\tx\nASSIGN\t=\nINT_LITERAL\t42\n"
        "SEMICOLON\t;\nTEXT_LITERAL\t\"hi\"\nCHAR_LITERAL\t'\xc3\xa9'\nBLOCK_COMMENT\t/*a\\r\\n\\tb \\\\n*/\nINVALID\t@\n");
    expect_contains(error_path,"E101"); expect_text(output_path,"Symbol Table.txt written\n"); clean_temps(destination);
    begin("classroom rerun preserves exact golden bytes");
    {
        Bytes prior = read_bytes(table);
        const char *args[] = {lexer,source,"--classroom","--output-dir",destination,NULL};
        CHECK(spawn(args,CAPTURE,CAPTURE) == 1); expect_bytes(table,prior.bytes,prior.length); destroy_bytes(prior);
    }
    begin("classroom success and default mode backward compatibility");
    write_text(source,"let x = 1;");
    {
        const char *args[] = {lexer,source,"--output-dir",destination,"--classroom",NULL};
        CHECK(spawn(args,CAPTURE,CAPTURE) == 0);
    }
    expect_text(table,"TOKEN TYPE\tLEXEME\nKEYWORD\tlet\nIDENTIFIER\tx\nASSIGN\t=\nINT_LITERAL\t1\nSEMICOLON\t;\n");
    expect_text(error_path,"");
    CHECK(run(lexer,source,destination) == 0);
    expect_text(table,"TOKEN TYPE\tLEXEME\nKEYWORD\t\"let\"\nIDENTIFIER\t\"x\"\nASSIGN\t\"=\"\nINT_LITERAL\t\"1\"\nSEMICOLON\t\";\"\n");
    begin("classroom source error writes header only");
    write_text(source,"\xef\xbb\xbf");
    {
        const char *args[] = {lexer,source,"--classroom","--output-dir",destination,NULL};
        CHECK(spawn(args,CAPTURE,CAPTURE) == 1);
    }
    expect_text(table,"TOKEN TYPE\tLEXEME\n"); expect_contains(error_path,"E002");
    begin("classroom option errors and extension/host exit codes");
    {
        const char *duplicate[] = {lexer,source,"--classroom","--classroom",NULL};
        const char *incomplete[] = {lexer,source,"--classroom","--output-dir",NULL};
        const char *duplicate_dir[] = {lexer,source,"--output-dir",destination,"--output-dir",destination,NULL};
        const char *absent_source[] = {lexer,"--classroom",NULL};
        const char *bad_extension[] = {lexer,"not.tfd.txt","--classroom",NULL};
        const char *bad_directory[] = {lexer,source,"--classroom","--output-dir",missing,NULL};
        const char *help[] = {lexer,"--help",NULL};
        CHECK(spawn(duplicate,CAPTURE,CAPTURE) == 2); CHECK(spawn(incomplete,CAPTURE,CAPTURE) == 2);
        CHECK(spawn(duplicate_dir,CAPTURE,CAPTURE) == 2); CHECK(spawn(absent_source,CAPTURE,CAPTURE) == 2);
        CHECK(spawn(bad_extension,CAPTURE,CAPTURE) == 1); CHECK(spawn(bad_directory,CAPTURE,CAPTURE) == 2);
        CHECK(spawn(help,CAPTURE,CAPTURE) == 0); expect_contains(output_path,"--classroom");
    }
    begin("classroom hardlink source alias is never overwritten");
    write_text(source,"untouched"); CHECK(remove(table) == 0);
#ifdef _WIN32
    CHECK(CreateHardLinkA(table,source,NULL) != 0);
#else
    CHECK(link(source,table) == 0);
#endif
    {
        const char *args[] = {lexer,source,"--classroom","--output-dir",destination,NULL};
        CHECK(spawn(args,CAPTURE,CAPTURE) == 2);
    }
    expect_text(source,"untouched"); expect_text(table,"untouched"); clean_temps(destination); CHECK(remove(table) == 0);
    begin("classroom publication leaves locked or non-file destination intact");
#ifdef _WIN32
    {
        HANDLE lock;
        write_text(table,"retained");
        lock = CreateFileA(table,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
        CHECK(lock != INVALID_HANDLE_VALUE);
        { const char *args[] = {lexer,source,"--classroom","--output-dir",destination,NULL};
          CHECK(spawn(args,CAPTURE,CAPTURE) == 2); }
        CHECK(CloseHandle(lock) != 0); expect_text(table,"retained"); CHECK(remove(table) == 0);
    }
#else
    directory(table);
    { const char *args[] = {lexer,source,"--classroom","--output-dir",destination,NULL};
      CHECK(spawn(args,CAPTURE,CAPTURE) == 2); }
    CHECK(is_directory(table)); CHECK(rmdir(table) == 0);
#endif
    clean_temps(destination);
    begin("classroom closed output and diagnostic pipes preserve exit 2");
    {
        const char *args[] = {lexer,source,"--classroom","--output-dir",destination,NULL};
        CHECK(spawn(args,BROKEN_PIPE,CAPTURE) == 2);
        expect_text(table,"TOKEN TYPE\tLEXEME\nIDENTIFIER\tuntouched\n");
        write_text(source,"@"); CHECK(spawn(args,CAPTURE,BROKEN_PIPE) == 2);
        expect_text(table,"TOKEN TYPE\tLEXEME\nINVALID\t@\n");
    }
    clean_temps(destination);
    begin("hyphen-leading output directory remains a literal option value");
    {
        char executable[PATH_CAPACITY], hyphen_directory[PATH_CAPACITY], hyphen_table[PATH_CAPACITY];
#ifdef _WIN32
        DWORD count = GetFullPathNameA(lexer,PATH_CAPACITY,executable,NULL);
        CHECK(count > 0 && count < PATH_CAPACITY);
#else
        char current[PATH_CAPACITY];
        CHECK(getcwd(current,sizeof(current)) != NULL);
        if (lexer[0] == '/') {
            int count = snprintf(executable,sizeof(executable),"%s",lexer);
            CHECK(count > 0 && (size_t)count < sizeof(executable));
        } else join_path(executable,current,lexer);
#endif
        join_path(hyphen_directory,destination,"-reports"); directory(hyphen_directory);
        table_path(hyphen_table,hyphen_directory);
        join_path(source,destination,"hyphen.tfd"); write_text(source,"let");
        {
            const char *old_mode[] = {executable,"hyphen.tfd","--output-dir","-reports",NULL};
            const char *classroom_mode[] = {executable,"--classroom","hyphen.tfd","--output-dir","-reports",NULL};
            CHECK(spawn_at(old_mode,CAPTURE,CAPTURE,destination) == 0);
            expect_text(hyphen_table,"TOKEN TYPE\tLEXEME\nKEYWORD\t\"let\"\n");
            CHECK(spawn_at(classroom_mode,CAPTURE,CAPTURE,destination) == 0);
            expect_text(hyphen_table,"TOKEN TYPE\tLEXEME\nKEYWORD\tlet\n");
        }
        clean_temps(hyphen_directory);
    }
}

static void test_trace_cli(const char *lexer) {
    char source[PATH_CAPACITY], destination[PATH_CAPACITY], table[PATH_CAPACITY];
    join_path(destination,root,"trace output");directory(destination);
    join_path(source,destination,"trace input.tfd");table_path(table,destination);
    write_text(source,"if ifx in input let letter Int Intensity 1.25 = ==");
    {
        const char *plain[]={lexer,source,"--classroom","--output-dir",destination,NULL};
        const char *traced[]={lexer,source,"--classroom","--output-dir",destination,"--trace-dfa",NULL};
        const char *duplicate[]={lexer,source,"--trace-dfa","--trace-dfa",NULL};
        Bytes expected;
        begin("trace is optional and leaves actual report bytes unchanged");
        CHECK(spawn(plain,CAPTURE,CAPTURE)==0);expect_text(error_path,"");expected=read_bytes(table);
        CHECK(spawn(traced,CAPTURE,CAPTURE)==0);expect_contains(error_path,"DFA name");
        expect_contains(error_path,"FINAL");expect_contains(error_path,"IDENT_FALLBACK");
        expect_bytes(table,expected.bytes,expected.length);destroy_bytes(expected);
        begin("duplicate trace option rejects without overwriting the report");
        CHECK(spawn(duplicate,CAPTURE,CAPTURE)==2);
        begin("trace pipe failure is host error before report publication");
        write_text(table,"preserved report");CHECK(spawn(traced,CAPTURE,BROKEN_PIPE)==2);
        expect_text(table,"preserved report");clean_temps(destination);
        begin("invalid trace reports the actual INVALID token and diagnostic");
        write_text(source,"1e+ @");CHECK(spawn(traced,CAPTURE,CAPTURE)==1);
        expect_contains(error_path,"DFA number");expect_contains(error_path,"E102");
        expect_contains(error_path,"E101");expect_contains(table,"INVALID\t1e+\n");
        expect_contains(table,"INVALID\t@\n");
    }
}
int main(int argc, char **argv) {
    if (argc != 2) {
        (void)fputs("Usage: test-integration PATH-TO-LEXER\n", stderr);
        return 2;
    }
    setup();
    test_examples(argv[1]);
    test_golden_and_spaced_executable(argv[1]);
    test_usage_and_failures(argv[1]);
    test_source_errors_and_coordinates(argv[1]);
    test_default_output_and_cap(argv[1]);
    test_publication_and_links(argv[1]);
    test_broken_streams(argv[1]);
    test_classroom(argv[1]);
    test_trace_cli(argv[1]);
    (void)printf("native CLI integration: %zu cases, %zu checks passed, %zu capability skips\n"
                 "fixtures: %s\n", cases, checks, skips, root);
    return 0;
}
