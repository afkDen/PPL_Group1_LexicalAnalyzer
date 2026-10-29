#ifndef TERNFOLD_LEXER_H
#define TERNFOLD_LEXER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

/* No global mutable state. All initialized owners must be destroyed, including
 * SOURCE_ERROR results. HOST_ERROR leaves a zeroed, destroyable output.
 * Constructors require fresh (not already owning) output objects. An allocator
 * and its context must outlive every object allocated through it. NULL selects
 * malloc/free. allocate must return storage aligned for any C object. */
typedef struct {
    void *context;
    void *(*allocate)(void *context, size_t size);
    void (*deallocate)(void *context, void *pointer);
} TfAllocator;

typedef enum { TF_OK = 0, TF_SOURCE_ERROR = 1, TF_HOST_ERROR = 2,
               TF_LEX_ERROR = 3 } TfStatus;

typedef enum {
    TF_E_NONE, TF_E001, TF_E002, TF_E003,
    TF_E101, TF_E102, TF_E103, TF_E104, TF_E105
} TfError;

typedef struct TfSource TfSource;
typedef struct { const TfSource *source; size_t start, end; } TfSpan;
typedef struct { size_t byte, scalar, line, column, display_column; } TfLocation;
typedef struct { TfError code; TfSpan span; } TfDiagnostic;
typedef struct { uint64_t device, index; bool valid; } TfFileIdentity;

/* Public fields are read-only after construction. Identity is this object's
 * address: do not copy/move a live source once borrowed by spans/results.
 * scalar_offsets includes EOF; line_scalars includes the final empty line.
 * Source errors retain bytes/name and raw error offsets, but have valid=false;
 * coordinate/span APIs reject such sources. No replacement decoding occurs. */
struct TfSource {
    unsigned char *bytes;
    size_t length;
    char *name;
    size_t *scalar_offsets, scalar_count;
    size_t *line_scalars, line_count;
    bool valid;
    TfDiagnostic error;
    TfAllocator allocator;
    TfFileIdentity origin;
};

typedef enum {
    TF_IDENT, TF_INT, TF_FLOAT, TF_TEXT, TF_CHAR, TF_UNDERSCORE,
    TF_INVALID, TF_EOF,
    TF_AS, TF_DIV, TF_ELSE, TF_EMIT, TF_ENUM, TF_FALSE, TF_FN, TF_FOR,
    TF_FROM, TF_GUARD, TF_IF, TF_IMPORT, TF_IN, TF_INPUT, TF_LET,
    TF_MACHINE, TF_MATCH, TF_NEXT, TF_OUTPUT, TF_PUB, TF_RECORD,
    TF_REJECTS, TF_STATE, TF_STDIN, TF_STDOUT, TF_TO, TF_TRUE, TF_YIELDS,
    TF_PLUS, TF_MINUS, TF_STAR, TF_SLASH, TF_PERCENT, TF_CARET,
    TF_LESS, TF_GREATER, TF_EQUAL, TF_BANG, TF_DOT, TF_COMMA,
    TF_SEMICOLON, TF_COLON, TF_LPAREN, TF_RPAREN, TF_LBRACKET,
    TF_RBRACKET, TF_LBRACE, TF_RBRACE, TF_DOUBLE_COLON, TF_ARROW,
    TF_FAT_ARROW, TF_EQUAL_EQUAL, TF_BANG_EQUAL, TF_LESS_EQUAL,
    TF_GREATER_EQUAL, TF_AND_AND, TF_OR_OR, TF_PLUS_PLUS, TF_BLOCK_CLOSE,
    TF_COMMENT_LINE, TF_COMMENT_BLOCK
} TfTokenKind;

typedef struct {
    TfTokenKind kind;
    TfSpan span;
    TfError error;
    bool reserved;
    /* IDENT/INT/FLOAT borrow exact source bytes. TEXT/CHAR are decoded UTF-8
     * owned by the result, with explicit length (embedded NUL is supported).
     * Others have NULL/0. Bool value is represented by TF_TRUE/TF_FALSE. No
     * numeric conversion/range check is performed by the scanner. */
    const unsigned char *value;
    size_t value_length;
} TfToken;

typedef struct {
    const TfSource *source; /* borrowed, must outlive result */
    TfToken *tokens;        /* ordered comments + genuine tokens + one EOF */
    size_t token_count, token_capacity;
    TfDiagnostic *diagnostics;
    size_t diagnostic_count, diagnostic_capacity, suppressed;
    bool has_errors;        /* remains true even with diagnostic cap zero */
    TfAllocator allocator;
} TfLexResult;

TfStatus tf_source_init(TfSource *out, const char *name,
                        const void *bytes, size_t length, const TfAllocator *allocator);
TfStatus tf_source_load(TfSource *out, const char *path, const TfAllocator *allocator);
void tf_source_destroy(TfSource *source);
bool tf_source_location(const TfSource *source, size_t byte, TfLocation *out);
bool tf_source_byte(const TfSource *source, size_t line, size_t column, size_t *out);
bool tf_source_span(const TfSource *source, size_t start, size_t end, TfSpan *out);
bool tf_span_join(TfSpan left, TfSpan right, TfSpan *out);

TfStatus tf_lex(TfLexResult *out, const TfSource *source, size_t diagnostic_cap,
                const TfAllocator *allocator);
void tf_lex_destroy(TfLexResult *result);
const char *tf_token_name(TfTokenKind kind);
const char *tf_error_code(TfError code);
const char *tf_error_message(TfError code);

/* Writes a two-column ASCII/UTF-8 LF report, reversible JSON quoted lexemes.
 * NULL result writes only the header (source validation failure). Caller owns
 * stream, binary mode, flush and close. Return HOST_ERROR for any write error. */
TfStatus tf_report_write(FILE *stream, const TfLexResult *result);
/* Classroom two-column LF report: no extra quote delimiters around lexemes.
 * Original Text/Char quote characters remain literal. UTF-8 Unicode is retained.
 * Reversible single-line encoding: LF -> \n, CR -> \r, TAB -> \t,
 * backslash -> \\, other U+0000..001F/U+007F..009F controls -> \u00xx
 * (four lowercase hex digits). Decode escapes once to recover original source
 * bytes; quote characters are not delimiters in this format. NULL result writes
 * the header only. Same borrowed stream/allocator/error contract as above. */
TfStatus tf_report_write_classroom(FILE *stream, const TfLexResult *result);
/* Publish via exclusively-created sibling + atomic replace. Never truncates
 * an existing report on failure. source provides original file identity for
 * alias/hard-link protection, even for an invalid source snapshot. Native host
 * path conventions apply. Output directory must exist. */
TfStatus tf_report_publish(const TfLexResult *result, const TfSource *source,
                          const char *output_directory);
/* Identical atomic publication and source-alias protections, classroom format. */
TfStatus tf_report_publish_classroom(const TfLexResult *result, const TfSource *source,
                                    const char *output_directory);
/* Diagnostic output is length-aware, escaped, and always refers to original
 * bytes. Source errors use raw byte ranges without invented coordinates. */
TfStatus tf_diagnostics_write(FILE *stream, const TfSource *source,
                              const TfLexResult *result);

#endif
