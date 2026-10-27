#ifndef TERNFOLD_INTERNAL_H
#define TERNFOLD_INTERNAL_H

#include "ternfold/lexer.h"

TfAllocator tf_allocator(const TfAllocator *allocator);
bool tf_allocator_valid(TfAllocator allocator);
bool tf_grow(void **data, size_t *capacity, size_t needed, size_t width,
             TfAllocator allocator);
/* Strict UTF-8. On failure end is the first invalid sequence's exclusive raw
 * end, matching the consumed valid prefix (offending continuation excluded). */
bool tf_decode(const unsigned char *bytes, size_t length, size_t at,
               uint32_t *scalar, size_t *end);
bool tf_file_identity(FILE *stream, TfFileIdentity *out);
bool tf_identity_path(const char *path, TfFileIdentity *out);

#endif
