/* Repository acceptance audit; no interpreter, Python or external parser. */
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checks, failures;
static void require(int ok, const char *message) {
    ++checks;
    if (!ok) { ++failures; fprintf(stderr, "audit: %s\n", message); }
}
static char *read_file(const char *path) {
    FILE *f = fopen(path, "rb");
    long length;
    char *s;
    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END) || (length = ftell(f)) < 0 || length > 4000000 ||
        fseek(f, 0, SEEK_SET)) { fclose(f); return NULL; }
    s = malloc((size_t)length + 1);
    if (!s) { fclose(f); return NULL; }
    if (fread(s, 1, (size_t)length, f) != (size_t)length || ferror(f)) {
        free(s); fclose(f); return NULL;
    }
    s[length] = 0;
    if (fclose(f)) { free(s); return NULL; }
    return s;
}
typedef struct { size_t start, end, next; char type; } Token;
typedef struct { const char *s; size_t at, count; Token tokens[16384]; } Json;
static void whitespace(Json *j) {
    while (j->s[j->at] == ' ' || j->s[j->at] == '\n' ||
           j->s[j->at] == '\r' || j->s[j->at] == '\t') ++j->at;
}
static int value(Json *j, unsigned depth) {
    size_t id, start;
    char c;
    if (depth > 64 || j->count == 16384) return 0;
    whitespace(j); start = j->at; c = j->s[j->at]; id = j->count++;
    j->tokens[id].start = start; j->tokens[id].type = c;
    if (c == '"') {
        ++j->at;
        while (j->s[j->at] && j->s[j->at] != '"') {
            unsigned char ch = (unsigned char)j->s[j->at++];
            if (ch < 32) return 0;
            if (ch == '\\') {
                char escape = j->s[j->at++];
                if (!escape) return 0;
                if (escape == 'u') {
                    for (unsigned i = 0; i < 4; ++i)
                        if (!isxdigit((unsigned char)j->s[j->at++])) return 0;
                } else if (!strchr("\"\\/bfnrt", escape)) return 0;
            }
        }
        if (j->s[j->at++] != '"') return 0;
    } else if (c == '[' || c == '{') {
        char close = c == '[' ? ']' : '}';
        ++j->at; whitespace(j);
        if (j->s[j->at] != close) for (;;) {
            if (c == '{') {
                whitespace(j);
                if (j->s[j->at] != '"' || !value(j, depth + 1)) return 0;
                whitespace(j); if (j->s[j->at++] != ':') return 0;
            }
            if (!value(j, depth + 1)) return 0;
            whitespace(j);
            if (j->s[j->at] == close) break;
            if (j->s[j->at++] != ',') return 0;
        }
        ++j->at;
    } else if (c == 't' || c == 'f' || c == 'n') {
        const char *word = c == 't' ? "true" : c == 'f' ? "false" : "null";
        size_t n = strlen(word);
        if (strncmp(j->s + j->at, word, n)) return 0;
        j->at += n;
    } else {
        if (c == '-') ++j->at;
        if (j->s[j->at] == '0') ++j->at;
        else {
            if (j->s[j->at] < '1' || j->s[j->at] > '9') return 0;
            while (isdigit((unsigned char)j->s[j->at])) ++j->at;
        }
        if (j->s[j->at] == '.') {
            ++j->at; if (!isdigit((unsigned char)j->s[j->at])) return 0;
            while (isdigit((unsigned char)j->s[j->at])) ++j->at;
        }
        if (j->s[j->at] == 'e' || j->s[j->at] == 'E') {
            ++j->at;
            if (j->s[j->at] == '+' || j->s[j->at] == '-') ++j->at;
            if (!isdigit((unsigned char)j->s[j->at])) return 0;
            while (isdigit((unsigned char)j->s[j->at])) ++j->at;
        }
    }
    j->tokens[id].end = j->at; j->tokens[id].next = j->count; return 1;
}
static int parse_document(Json *j) {
    /* A rejected truncated string may leave at one past the terminating NUL.
     * No cursor access is permitted after a failed value parse. */
    if (!value(j, 0)) return 0;
    whitespace(j);
    return j->s[j->at] == 0;
}
static void json_regressions(void) {
    const char *const invalid[] = {"", "\"", "\"\\", "\"\\u", "\"\\u1", "\"\\u12",
        "\"\\u123", "[", "{\"", "{\"a\":", "{\"a\"", "[1,", "-", "1e", "+1",
        "00", "]", "[1,]", "{\"a\":1,}", "\"\\x\""};
    const char *const valid[] = {"{}", "[]", "\"\"", "[1,true,null,\"\\u1234\"]", "{\"a\":[-1.5e2]}"};
    for (unsigned group = 0; group < 2; ++group) {
        size_t count = group ? sizeof valid / sizeof *valid : sizeof invalid / sizeof *invalid;
        for (size_t i = 0; i < count; ++i) {
            const char *input = group ? valid[i] : invalid[i];
            size_t length = strlen(input);
            char *copy = malloc(length + 1);
            Json *j = calloc(1, sizeof *j);
            require(copy != NULL && j != NULL, "JSON regression allocation");
            if (copy && j) {
                memcpy(copy, input, length + 1); j->s = copy;
                require(parse_document(j) == (group != 0), "bounded JSON EOF regression");
            }
            free(copy); free(j);
        }
    }
}
static void document(const char *path, int active) {
    char *s = read_file(path);
    require(s != NULL, path);
    if (!s) return;
    if (active) {
        const char *const stale[] = {"scripts/dev.py", "scripts/bootstrap.py", "pyproject.toml",
            "uv.lock", ".venv/bin/python", "scripts/course_audit.py", "python analyzer.py"};
        for (size_t i = 0; i < sizeof stale / sizeof *stale; ++i)
            require(!strstr(s, stale[i]), path);
    }
    /* Check local Markdown file links (anchors intentionally not validated). */
    for (const char *p = s; (p = strstr(p, "](")) != NULL; p += 2) {
        const char *start = p + 2, *end = strchr(start, ')');
        char linked[1024]; size_t base = 0, n;
        const char *slash = strrchr(path, '/');
        if (!end) break;
        if (*start == '<') { ++start; end = strchr(start, '>'); if (!end) break; }
        n = (size_t)(end - start);
        for (size_t i = 0; i < n; ++i) if (start[i] == '#') { n = i; break; }
        if (!n || memchr(start, ':', n)) continue;
        if (slash) base = (size_t)(slash - path) + 1;
        if (base + n >= sizeof linked) { require(0, "oversize Markdown link"); continue; }
        memcpy(linked, path, base); memcpy(linked + base, start, n); linked[base+n] = 0;
        { FILE *f = fopen(linked, "rb"); require(f != NULL, linked); if (f) fclose(f); }
    }
    free(s);
}
int main(int argc, char **argv) {
    const char *const documents[] = {"README.md", "START_HERE.md", "IDE_QUICK_START.md",
        "DFA.md", "DFA_LIVE_DEMO.md", "PROFESSOR_DEMO_GUIDE.md", "RUBRIC.md",
        "DEMO_ROWS.md", "INVALID_CASES.md", "SUBMITTED_PROPOSAL_ALIGNMENT.md",
        "PROPOSAL_LEXICAL_RECONCILIATION.md", "VERIFICATION.md", "tests/README.md"};
    char *s;
    if (argc > 2 || (argc == 2 && strcmp(argv[1], "--lexical"))) {
        fputs("Usage: audit [--lexical]\n", stderr); return 2;
    }
    json_regressions();
    s = read_file("src/lexer.c"); require(s != NULL, "C scanner source");
    if (s) {
        require(!strstr(s, "strcmp") && !strstr(s, "strncmp") && !strstr(s, "strstr"),
                "scanner must use character transitions, no word comparisons");
        require(strstr(s, "#include \"name_dfa.inc\"") != NULL,
                "production scanner includes fixed name graph");
        free(s);
    }
    s = read_file("src/name_dfa.inc"); require(s != NULL, "fixed name graph");
    if (s) {
        require(strstr(s, "static const TfNameDfaState name_states[]") != NULL,
                "name states are immutable compile-time definitions"); free(s);
    }
    for (size_t i = 0; i < sizeof documents / sizeof *documents; ++i)
        document(documents[i], 1);
    printf("Lexical repository audit: %u checks, %u failures\n", checks, failures);
    return failures ? 1 : 0;
}
