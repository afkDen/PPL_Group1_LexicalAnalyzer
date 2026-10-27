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
static int equal(const Json *j, size_t token, const char *s) {
    const Token *t;
    size_t length;
    if (token >= j->count) return 0;
    t = &j->tokens[token]; length = strlen(s);
    return t->type == '"' && t->end - t->start == length + 2 &&
           !memcmp(j->s + t->start + 1, s, length);
}
static size_t field(const Json *j, size_t object, const char *key) {
    if (object >= j->count || j->tokens[object].type != '{') return j->count;
    for (size_t i = object + 1; i < j->tokens[object].next;) {
        size_t v = i + 1;
        if (equal(j, i, key)) return v;
        i = j->tokens[v].next;
    }
    return j->count;
}
static const char *const ids[] = {"C-MIGRATION-01", "M00", "C00", "M01", "M02",
    "M03", "M04", "M05", "M06", "M07", "C01", "S01", "M08", "M09",
    "M10", "M11", "M12", "M13", "M14", "M15", "M16", "M17", "X01"};
static const char *const dependencies[] = {"", "", "M00", "M00,C00", "M01",
    "M01,M02", "M03", "M04", "M05", "M06", "M07", "C01", "M07,C01,S01",
    "M08", "M06,M08", "M09,M10", "M11", "M12", "M12,M13", "M14", "M14", "M14", "M14"};
static void task_graph(const char *s) {
    Json *j = calloc(1, sizeof *j);
    size_t tasks, item, count = 0;
    if (!j) { require(0, "audit allocation"); return; }
    j->s = s;
    if (!parse_document(j)) { require(0, "task JSON syntax/trailing bytes"); free(j); return; }
    tasks = field(j, 0, "tasks");
    if (tasks >= j->count || j->tokens[tasks].type != '[') {
        require(0, "tasks array missing"); free(j); return;
    }
    for (item = tasks + 1; item < j->tokens[tasks].next; item = j->tokens[item].next) {
        size_t deps, optional;
        char joined[128] = "";
        require(count < sizeof ids / sizeof *ids, "no replacement task IDs");
        if (count >= sizeof ids / sizeof *ids) break;
        require(equal(j, field(j, item, "id"), ids[count]), "canonical task identity/order");
        deps = field(j, item, "requires");
        if (deps >= j->count || j->tokens[deps].type != '[') require(0, "task dependencies missing");
        else for (size_t k = deps + 1; k < j->tokens[deps].next; k = j->tokens[k].next) {
            const Token *t = &j->tokens[k];
            size_t at = strlen(joined), length = t->end - t->start;
            if (t->type != '"' || length < 2 || length + at + 1 >= sizeof joined) {
                require(0, "dependency encoding"); break;
            }
            if (at) joined[at++] = ',';
            memcpy(joined + at, s + t->start + 1, length - 2);
            joined[at + length - 2] = 0;
        }
        require(!strcmp(joined, dependencies[count]), "canonical dependency edge changed");
        optional = field(j, item, "optional");
        require(optional < j->count && j->tokens[optional].type == (count >= 19 ? 't' : 'f'),
                "optional extensions must stay optional; required tasks required");
        ++count;
    }
    require(count == sizeof ids / sizeof *ids, "all canonical tasks present"); free(j);
}
static int string_nonempty(const Json *j, size_t i) {
    return i < j->count && j->tokens[i].type == '"' &&
           j->tokens[i].end - j->tokens[i].start > 2;
}
static int evidence_valid(const Json *j, size_t node) {
    const Token *t = &j->tokens[node];
    if (t->type == '{') {
        size_t status = field(j, node, "status");
        if (status < j->count) {
            size_t evidence = field(j, node, "evidence");
            int positive = equal(j, status, "implemented") || equal(j, status, "tested") ||
                           equal(j, status, "reviewed") || equal(j, status, "verified");
            if (!positive && !equal(j, status, "specified") && !equal(j, status, "blocked")) return 0;
            if (equal(j, status, "blocked") && !string_nonempty(j, field(j, node, "reason"))) return 0;
            if (positive && (evidence >= j->count || j->tokens[evidence].type != '[' ||
                             j->tokens[evidence].next == evidence + 1)) return 0;
            if (evidence < j->count) {
                if (j->tokens[evidence].type != '[') return 0;
                for (size_t k = evidence + 1; k < j->tokens[evidence].next; k = j->tokens[k].next) {
                    const Token *e = &j->tokens[k]; char path[1024]; size_t n = e->end - e->start;
                    FILE *f;
                    if (e->type != '"' || n <= 2 || n >= sizeof path) return 0;
                    memcpy(path, j->s + e->start + 1, n - 2); path[n - 2] = 0;
                    f = fopen(path, "rb"); if (!f) return 0; fclose(f);
                }
            }
        }
    }
    if (t->type == '{' || t->type == '[')
        for (size_t i = node + 1; i < t->next; i = j->tokens[i].next)
            if (!evidence_valid(j, i)) return 0;
    return 1;
}
static const char *const requirement_ids[] = {"intro", "sigma", "identifiers", "arithmetic",
    "relational", "logical", "words", "automata", "noise", "comments", "spaces", "delimiters",
    "format", "constants", "precedence", "input", "output", "assignment", "conditionals",
    "single_loop", "nested_loop", "extension", "invalid", "symbol_table", "native"};
static int ledger_valid(const Json *j) {
    size_t array = field(j, 0, "requirements"), count = 0;
    unsigned char seen[25] = {0};
    if (array >= j->count || j->tokens[array].type != '[' || !evidence_valid(j, 0)) return 0;
    for (size_t i = array + 1; i < j->tokens[array].next; i = j->tokens[i].next) {
        size_t owner = field(j, i, "owner"), id = field(j, i, "id");
        size_t status = field(j, i, "status");
        int known_owner = 0, known_id = 0;
        if (!string_nonempty(j, status)) return 0;
        for (size_t k = 0; k < sizeof ids / sizeof *ids; ++k) known_owner |= equal(j, owner, ids[k]);
        for (size_t k = 0; k < sizeof requirement_ids / sizeof *requirement_ids; ++k)
            if (equal(j, id, requirement_ids[k])) {
                if (seen[k]) return 0;
                seen[k] = 1; known_id = 1;
            }
        if (!known_owner || !known_id) return 0;
        ++count;
    }
    return count == 25;
}
static void ledger_regressions(void) {
    for (unsigned trial = 0; trial < 8; ++trial) {
        char buffer[8192]; size_t at = 0;
        Json *j = calloc(1, sizeof *j);
        int fits = 1;
        int n = snprintf(buffer, sizeof buffer, "{\"requirements\":[");
        require(j != NULL, "ledger regression allocation");
        if (!j) return;
        at = (size_t)n;
        for (size_t i = 0; i < 25; ++i) {
            const char *id = requirement_ids[trial == 1 && i == 1 ? 0 : i];
            const char *state = i == 0 && (trial == 3 || trial == 4) ? "blocked" : "specified";
            const char *reason = i == 0 && trial == 4 ? ",\"reason\":\"external condition\"" : "";
            if (trial == 2 && i == 0) id = "unknown";
            n = snprintf(buffer + at, sizeof buffer - at,
                         "%s{\"id\":\"%s\",\"owner\":\"M03\",\"status\":\"%s\",\"evidence\":[]%s}",
                         i ? "," : "", id, state, reason);
            if (n < 0 || (size_t)n >= sizeof buffer - at) { fits = 0; break; }
            at += (size_t)n;
        }
        if (fits) {
            const char *tail = trial == 5 ? ",\"stages\":{\"nested\":{\"status\":\"verified\"}}}" :
                trial == 6 ? ",\"stages\":{\"nested\":{\"status\":\"verified\",\"evidence\":[\"does/not/exist\"]}}}" :
                trial == 7 ? ",\"stages\":{\"nested\":{\"status\":\"verified\",\"evidence\":[\"src/lexer.c\"]}}}" : "}";
            n = snprintf(buffer + at, sizeof buffer - at, "]%s", tail);
            fits = n >= 0 && (size_t)n < sizeof buffer - at;
        }
        require(fits, "bounded ledger regression fixture");
        if (fits) {
            j->s = buffer; require(parse_document(j), "ledger regression JSON valid");
            require(ledger_valid(j) == (trial == 0 || trial == 4 || trial == 7),
                    "duplicate IDs, blocked reason, nested evidence regression");
        }
        free(j);
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
    const char *const documents[] = {"README.md", "MASTER_IMPLEMENTATION.md", "AGENTS.md",
        "docs/codex-handoff.md", "docs/progress.md", "docs/architecture.md",
        "docs/compiler-pipeline.md", "docs/environment.md", "docs/testing.md",
        "docs/implementation-plan.md", "docs/language-spec.md", "docs/grammar.md",
        "docs/type-system.md", "docs/module-system.md", "docs/core-ir.md", "docs/runtime.md",
        "docs/standard-library.md", "docs/course-requirements.md", "docs/automata.md",
        "docs/agent-orchestration.md", "docs/agent-skills.md", "docs/what-codex-builds.md"};
    const char *const roles[] = {"frontend-engineer", "semantics-core-engineer",
        "backend-runtime-engineer", "quality-engineer", "reviewer", "semantic-auditor", "native-safety-auditor"};
    const char *const skills[] = {"feature", "orchestration", "spec-audit", "test-design",
        "debugging", "lexical-conformance", "native-safety", "differential", "verified-completion"};
    int lexical = argc == 2 && !strcmp(argv[1], "--lexical");
    char path[256]; char *s;
    json_regressions();
    ledger_regressions();
    s = read_file("src/lexer.c"); require(s != NULL, "C scanner source");
    if (s) {
        require(!strstr(s, "strcmp") && !strstr(s, "strncmp") && !strstr(s, "strstr"),
                "scanner must use character transitions, no word comparisons"); free(s);
    }
    if (!lexical) {
        for (size_t i = 0; i < sizeof documents / sizeof *documents; ++i) document(documents[i], 1);
        for (size_t i = 0; i < sizeof ids / sizeof *ids; ++i) {
            snprintf(path, sizeof path, "docs/tasks/%s.md", ids[i]); document(path, 1);
        }
        s = read_file("docs/tasks.json"); require(s != NULL, "task graph");
        if (s) { task_graph(s); free(s); }
        s = read_file("docs/course-acceptance.json"); require(s != NULL, "course ledger");
        if (s) {
            Json *j = calloc(1, sizeof *j);
            require(j != NULL, "ledger allocation");
            if (j) { int valid; j->s = s; valid = parse_document(j); require(valid, "course ledger JSON syntax/trailing bytes");
                if (valid) require(ledger_valid(j), "course identities/owners/states/evidence including nested stages"); free(j); }
            require(!strstr(s, ".py\""), "no obsolete course evidence paths"); free(s);
        }
        for (size_t i = 0; i < sizeof roles / sizeof *roles; ++i) {
            snprintf(path, sizeof path, ".codex/agents/%s.toml", roles[i]); s = read_file(path); require(s != NULL, path);
            if (s) { require(strstr(s, "name =") && strstr(s, "description =") &&
                strstr(s, "developer_instructions =") && strstr(s, "C17"), path); free(s); }
        }
        for (size_t i = 0; i < sizeof skills / sizeof *skills; ++i) {
            snprintf(path, sizeof path, ".agents/skills/ternfold-%s/SKILL.md", skills[i]);
            document(path, 1); s = read_file(path);
            if (s) { require(!strncmp(s, "---\nname: ", 10) && strstr(s, "\ndescription:") && strstr(s, "C17"), path); free(s); }
        }
    }
    printf("Repository audit: %u checks, %u failures%s\n", checks, failures, lexical ? " (lexical slice)" : "");
    return failures ? 1 : 0;
}
