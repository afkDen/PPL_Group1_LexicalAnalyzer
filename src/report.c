#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include "internal.h"

#include <errno.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <fcntl.h>
#include <io.h>
#include <process.h>
#else
#include <fcntl.h>
#include <unistd.h>
#endif

static bool put_text(FILE *stream, const char *text) { return fputs(text, stream) >= 0; }
static bool put_hex(FILE *stream, uint32_t scalar) {
    static const char digits[] = "0123456789abcdef";
    char encoded[7] = {'\\', 'u', '0', '0', '0', '0', '\0'};
    size_t i;
    for (i = 0; i < 4; ++i) {
        encoded[5 - i] = digits[scalar & 15u];
        scalar >>= 4;
    }
    return put_text(stream, encoded);
}
/* JSON ensure-ASCII escaping is byte-for-byte compatible with the historical
 * classroom view: non-BMP scalars use a surrogate pair. Raw source-error
 * snippets use \u00XX for undecodable bytes, and explicitly say raw bytes. */
static bool put_quoted(FILE *stream, const unsigned char *bytes, size_t length, bool raw) {
    size_t at = 0;
    if (fputc('"', stream) == EOF) return false;
    while (at < length) {
        uint32_t scalar;
        size_t end;
        if (raw) { scalar = bytes[at]; end = at + 1; }
        else if (!tf_decode(bytes, length, at, &scalar, &end)) return false;
        at = end;
        switch (scalar) {
            case '"': if (!put_text(stream, "\\\"")) return false; break;
            case '\\': if (!put_text(stream, "\\\\")) return false; break;
            case '\b': if (!put_text(stream, "\\b")) return false; break;
            case '\f': if (!put_text(stream, "\\f")) return false; break;
            case '\n': if (!put_text(stream, "\\n")) return false; break;
            case '\r': if (!put_text(stream, "\\r")) return false; break;
            case '\t': if (!put_text(stream, "\\t")) return false; break;
            default:
                if (scalar >= 32u && scalar < 127u) {
                    if (fputc((int)scalar, stream) == EOF) return false;
                } else if (scalar <= 0xffffu) {
                    if (!put_hex(stream, scalar)) return false;
                } else {
                    scalar -= 0x10000u;
                    if (!put_hex(stream, 0xd800u + (scalar >> 10)) ||
                        !put_hex(stream, 0xdc00u + (scalar & 0x3ffu))) return false;
                }
                break;
        }
    }
    return fputc('"', stream) != EOF;
}

static bool put_classroom(FILE *stream, const unsigned char *bytes, size_t length) {
    size_t at = 0;
    while (at < length) {
        uint32_t scalar;
        size_t end;
        if (!tf_decode(bytes, length, at, &scalar, &end)) return false;
        switch (scalar) {
            case '\\': if (!put_text(stream, "\\\\")) return false; break;
            case '\n': if (!put_text(stream, "\\n")) return false; break;
            case '\r': if (!put_text(stream, "\\r")) return false; break;
            case '\t': if (!put_text(stream, "\\t")) return false; break;
            default:
                if (scalar < 32u || (scalar >= 127u && scalar <= 159u)) {
                    if (!put_hex(stream, scalar)) return false;
                } else if (fwrite(bytes + at, 1, end - at, stream) != end - at) return false;
                break;
        }
        at = end;
    }
    return true;
}

static bool comment(TfTokenKind kind) { return kind == TF_COMMENT_LINE || kind == TF_COMMENT_BLOCK; }
typedef struct { TfTokenKind clause; bool at_start; } Context;
static bool noise(const TfLexResult *result, size_t index, TfTokenKind clause) {
    TfTokenKind connector = result->tokens[index].kind;
    TfTokenKind sink;
    size_t next = index + 1;
    if (!((clause == TF_INPUT && connector == TF_FROM) ||
          (clause == TF_OUTPUT && connector == TF_TO))) return false;
    while (next < result->token_count && comment(result->tokens[next].kind)) ++next;
    if (next == result->token_count) return false;
    sink = result->tokens[next++].kind;
    if ((connector == TF_FROM && sink != TF_STDIN) ||
        (connector == TF_TO && sink != TF_STDOUT)) return false;
    while (next < result->token_count && comment(result->tokens[next].kind)) ++next;
    return next < result->token_count && result->tokens[next].kind == TF_SEMICOLON;
}
static const char *category(const TfToken *token, bool is_noise) {
    switch (token->kind) {
        case TF_IDENT: return token->reserved ? "RESERVED_WORD" : "IDENTIFIER";
        case TF_INT: return "INT_LITERAL";
        case TF_FLOAT: return "FLOAT_LITERAL";
        case TF_TEXT: return "TEXT_LITERAL";
        case TF_CHAR: return "CHAR_LITERAL";
        case TF_TRUE: case TF_FALSE: return "BOOL_LITERAL";
        case TF_COMMENT_LINE: return "LINE_COMMENT";
        case TF_COMMENT_BLOCK: return "BLOCK_COMMENT";
        case TF_EQUAL: return "ASSIGN";
        case TF_DIV: return "DIV";
        default: break;
    }
    if (is_noise) return "NOISE_WORD";
    if (token->kind >= TF_AS && token->kind <= TF_YIELDS) return "KEYWORD";
    return tf_token_name(token->kind);
}

static TfStatus report_write(FILE *stream, const TfLexResult *result, bool classroom) {
    Context current = {TF_EOF, true};
    void *storage = NULL;
    size_t depth = 0, capacity = 0, i;
    TfStatus status = TF_HOST_ERROR;
    TfAllocator memory = result == NULL ? tf_allocator(NULL) : result->allocator;
    if (stream == NULL || !tf_allocator_valid(memory)) return TF_HOST_ERROR;
    if (!put_text(stream, "TOKEN TYPE\tLEXEME\n")) return TF_HOST_ERROR;
    if (result == NULL) return ferror(stream) ? TF_HOST_ERROR : TF_OK;
    for (i = 0; i < result->token_count; ++i) {
        const TfToken *token = &result->tokens[i];
        bool is_noise = false;
        if (token->kind == TF_EOF) continue;
        if (!comment(token->kind)) {
            if (token->kind == TF_LBRACE) {
                if (!tf_grow(&storage, &capacity, depth + 1, sizeof(Context), memory)) goto done;
                ((Context *)storage)[depth++] = current;
                current = (Context){TF_EOF, true};
            } else if (token->kind == TF_RBRACE) {
                current = depth != 0 ? ((Context *)storage)[--depth] : (Context){TF_EOF, true};
            } else if (token->kind == TF_SEMICOLON) {
                current = (Context){TF_EOF, true};
            } else {
                if (current.at_start) {
                    current.clause = token->kind == TF_INPUT || token->kind == TF_OUTPUT
                                         ? token->kind : TF_EOF;
                    current.at_start = false;
                }
                is_noise = noise(result, i, current.clause);
            }
        }
        if (!put_text(stream, category(token, is_noise)) || fputc('\t', stream) == EOF) goto done;
        if (classroom) {
            if (!put_classroom(stream, token->span.source->bytes + token->span.start,
                               token->span.end - token->span.start)) goto done;
        } else if (!put_quoted(stream, token->span.source->bytes + token->span.start,
                               token->span.end - token->span.start, false)) goto done;
        if (fputc('\n', stream) == EOF) goto done;
    }
    status = ferror(stream) ? TF_HOST_ERROR : TF_OK;
done:
    if (storage != NULL) memory.deallocate(memory.context, storage);
    return status;
}
TfStatus tf_report_write(FILE *stream, const TfLexResult *result) {
    return report_write(stream, result, false);
}
TfStatus tf_report_write_classroom(FILE *stream, const TfLexResult *result) {
    return report_write(stream, result, true);
}

static bool same_identity(TfFileIdentity left, TfFileIdentity right) {
    return left.valid && right.valid && left.device == right.device && left.index == right.index;
}
static bool source_alias(const char *destination, const TfSource *source) {
    TfFileIdentity target, current_source;
    if (!tf_identity_path(destination, &target)) return false;
    if (same_identity(target, source->origin)) return true;
    return source->name != NULL && tf_identity_path(source->name, &current_source) &&
           same_identity(target, current_source);
}
static unsigned long process_id(void) {
#ifdef _WIN32
    return (unsigned long)_getpid();
#else
    return (unsigned long)getpid();
#endif
}
static FILE *exclusive_stream(const char *path, bool *collision) {
    *collision = false;
#ifdef _WIN32
    {
        HANDLE handle = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_NEW,
                                    FILE_ATTRIBUTE_NORMAL, NULL);
        int fd;
        FILE *stream;
        if (handle == INVALID_HANDLE_VALUE) {
            DWORD error = GetLastError();
            *collision = error == ERROR_FILE_EXISTS || error == ERROR_ALREADY_EXISTS;
            return NULL;
        }
        fd = _open_osfhandle((intptr_t)handle, _O_WRONLY | _O_BINARY);
        if (fd < 0) { (void)CloseHandle(handle); (void)remove(path); return NULL; }
        stream = _fdopen(fd, "wb");
        if (stream == NULL) { (void)_close(fd); (void)remove(path); }
        return stream;
    }
#else
    {
        int fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0600);
        FILE *stream;
        if (fd < 0) { *collision = errno == EEXIST; return NULL; }
        stream = fdopen(fd, "wb");
        if (stream == NULL) { (void)close(fd); (void)remove(path); }
        return stream;
    }
#endif
}
static bool replace_file(const char *temporary, const char *destination) {
#ifdef _WIN32
    return MoveFileExA(temporary, destination, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
#else
    return rename(temporary, destination) == 0;
#endif
}
static TfStatus report_publish(const TfLexResult *result, const TfSource *source,
                               const char *output_directory, bool classroom) {
    static const char filename[] = "Symbol Table.txt";
    TfAllocator memory;
    size_t directory_length, path_length;
    char *destination = NULL, *temporary = NULL;
    unsigned attempt;
    TfStatus status = TF_HOST_ERROR;
    FILE *stream = NULL;
    if (source == NULL || output_directory == NULL ||
        (result != NULL && result->source != source)) return TF_HOST_ERROR;
    memory = source->allocator;
    if (!tf_allocator_valid(memory)) return TF_HOST_ERROR;
    directory_length = strlen(output_directory);
    if (directory_length == 0 || directory_length > SIZE_MAX - sizeof(filename) - 64) return TF_HOST_ERROR;
    path_length = directory_length + 1 + sizeof(filename);
    destination = memory.allocate(memory.context, path_length);
    temporary = memory.allocate(memory.context, path_length + 64);
    if (destination == NULL || temporary == NULL) goto done;
    memcpy(destination, output_directory, directory_length);
    destination[directory_length] = '/';
    memcpy(destination + directory_length + 1, filename, sizeof(filename));
    if (source_alias(destination, source)) goto done;
    for (attempt = 0; attempt < 128; ++attempt) {
        int count = snprintf(temporary, path_length + 64, "%s.tmp.%lu.%u", destination, process_id(), attempt);
        bool collision;
        if (count < 0 || (size_t)count >= path_length + 64) goto done;
        stream = exclusive_stream(temporary, &collision);
        if (stream != NULL) break;
        if (!collision) goto done;
    }
    if (stream == NULL) goto done;
    status = report_write(stream, result, classroom);
    if (fflush(stream) != 0) status = TF_HOST_ERROR;
    if (fclose(stream) != 0) status = TF_HOST_ERROR;
    stream = NULL;
    /* Recheck at publication; replacing the directory entry never follows a
     * newly swapped symlink. Concurrent hostile directory mutation is outside
     * this CLI's trust boundary; no source file is ever opened for writing. */
    if (status == TF_OK && (source_alias(destination, source) ||
                           !replace_file(temporary, destination))) status = TF_HOST_ERROR;
    if (status != TF_OK) (void)remove(temporary);
done:
    if (temporary != NULL) memory.deallocate(memory.context, temporary);
    if (destination != NULL) memory.deallocate(memory.context, destination);
    return status;
}
TfStatus tf_report_publish(const TfLexResult *result, const TfSource *source,
                          const char *output_directory) {
    return report_publish(result, source, output_directory, false);
}
TfStatus tf_report_publish_classroom(const TfLexResult *result, const TfSource *source,
                                    const char *output_directory) {
    return report_publish(result, source, output_directory, true);
}

static bool diagnostic(FILE *stream, const TfSource *source, TfDiagnostic item) {
    TfLocation location;
    if (!put_quoted(stream, (const unsigned char *)source->name, strlen(source->name), true)) return false;
    if (source->valid) {
        if (!tf_source_location(source, item.span.start, &location) ||
            fprintf(stream, ":%zu:%zu", location.line, location.column) < 0) return false;
    }
    if (fprintf(stream, ": %s: %s [bytes %zu..%zu)\n  %s", tf_error_code(item.code),
                tf_error_message(item.code), item.span.start, item.span.end,
                source->valid ? "" : "raw bytes ") < 0 ||
        !put_quoted(stream, source->bytes + item.span.start, item.span.end - item.span.start, !source->valid) ||
        fputc('\n', stream) == EOF) return false;
    return true;
}
TfStatus tf_diagnostics_write(FILE *stream, const TfSource *source,
                              const TfLexResult *result) {
    size_t i;
    if (stream == NULL || source == NULL || source->name == NULL) return TF_HOST_ERROR;
    if (!source->valid) {
        if (!diagnostic(stream, source, source->error)) return TF_HOST_ERROR;
    } else if (result != NULL) {
        if (result->source != source) return TF_HOST_ERROR;
        for (i = 0; i < result->diagnostic_count; ++i)
            if (!diagnostic(stream, source, result->diagnostics[i])) return TF_HOST_ERROR;
        if (result->suppressed != 0 &&
            fprintf(stream, "%zu further diagnostics suppressed (%zu errors)\n",
                    result->suppressed, result->suppressed) < 0) return TF_HOST_ERROR;
    }
    return ferror(stream) ? TF_HOST_ERROR : TF_OK;
}
