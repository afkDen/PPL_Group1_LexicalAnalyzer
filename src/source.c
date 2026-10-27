#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include "internal.h"

#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <io.h>
#else
#include <sys/stat.h>
#include <unistd.h>
#endif

static void *default_allocate(void *context, size_t size) {
    (void)context;
    return malloc(size);
}
static void default_deallocate(void *context, void *pointer) {
    (void)context;
    free(pointer);
}
TfAllocator tf_allocator(const TfAllocator *allocator) {
    const TfAllocator standard = {NULL, default_allocate, default_deallocate};
    return allocator != NULL ? *allocator : standard;
}
bool tf_allocator_valid(TfAllocator allocator) {
    return allocator.allocate != NULL && allocator.deallocate != NULL;
}
bool tf_grow(void **data, size_t *capacity, size_t needed, size_t width,
             TfAllocator allocator) {
    size_t next;
    void *fresh;
    if (needed <= *capacity) return true;
    if (width == 0 || needed > SIZE_MAX / width) return false;
    next = *capacity == 0 ? 16 : *capacity;
    while (next < needed) {
        if (next > SIZE_MAX / 2) { next = needed; break; }
        next *= 2;
    }
    if (next > SIZE_MAX / width) next = needed;
    fresh = allocator.allocate(allocator.context, next * width);
    if (fresh == NULL) return false;
    if (*data != NULL) {
        memcpy(fresh, *data, *capacity * width);
        allocator.deallocate(allocator.context, *data);
    }
    *data = fresh;
    *capacity = next;
    return true;
}

bool tf_decode(const unsigned char *bytes, size_t length, size_t at,
               uint32_t *scalar, size_t *end) {
    unsigned char lead;
    size_t count, i;
    uint32_t value;
    if (at >= length) { *end = at; return false; }
    lead = bytes[at];
    *end = at + 1;
    if (lead < 0x80) { *scalar = lead; return true; }
    if (lead >= 0xc2 && lead <= 0xdf) { count = 2; value = lead & 0x1fu; }
    else if (lead >= 0xe0 && lead <= 0xef) { count = 3; value = lead & 0x0fu; }
    else if (lead >= 0xf0 && lead <= 0xf4) { count = 4; value = lead & 0x07u; }
    else return false;
    for (i = 1; i < count; ++i) {
        unsigned char part;
        if (i >= length - at) return false;
        part = bytes[at + i];
        if (part < 0x80 || part > 0xbf) return false;
        if (i == 1 && ((lead == 0xe0 && part < 0xa0) ||
                       (lead == 0xed && part >= 0xa0) ||
                       (lead == 0xf0 && part < 0x90) ||
                       (lead == 0xf4 && part >= 0x90))) return false;
        value = (value << 6) | (uint32_t)(part & 0x3fu);
        *end = at + i + 1;
    }
    *scalar = value;
    return true;
}

bool tf_file_identity(FILE *stream, TfFileIdentity *out) {
    *out = (TfFileIdentity){0};
#ifdef _WIN32
    {
        intptr_t descriptor = _get_osfhandle(_fileno(stream));
        BY_HANDLE_FILE_INFORMATION info;
        if (descriptor == -1 ||
            !GetFileInformationByHandle((HANDLE)descriptor, &info)) return false;
        if ((info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) return false;
        out->device = info.dwVolumeSerialNumber;
        out->index = ((uint64_t)info.nFileIndexHigh << 32) | info.nFileIndexLow;
    }
#else
    {
        struct stat info;
        if (fstat(fileno(stream), &info) != 0 || !S_ISREG(info.st_mode)) return false;
        out->device = (uint64_t)info.st_dev;
        out->index = (uint64_t)info.st_ino;
    }
#endif
    out->valid = true;
    return true;
}
bool tf_identity_path(const char *path, TfFileIdentity *out) {
    FILE *stream = fopen(path, "rb");
    bool okay;
    *out = (TfFileIdentity){0};
    if (stream == NULL) return false;
    okay = tf_file_identity(stream, out);
    if (fclose(stream) != 0) return false;
    return okay;
}

static TfStatus source_error(TfSource *source, TfError error, size_t start, size_t end) {
    source->error = (TfDiagnostic){error, {source, start, end}};
    return TF_SOURCE_ERROR;
}
static TfStatus validate_source(TfSource *source) {
    size_t at = 0, end, scalars = 0, lines = 1, i, line;
    uint32_t scalar;
    /* Validate all encoding before any BOM/line-ending policy. */
    while (at < source->length) {
        if (!tf_decode(source->bytes, source->length, at, &scalar, &end))
            return source_error(source, TF_E001, at, end);
        ++scalars;
        if (scalar == '\n') ++lines;
        at = end;
    }
    if (source->length >= 3 && source->bytes[0] == 0xef &&
        source->bytes[1] == 0xbb && source->bytes[2] == 0xbf)
        return source_error(source, TF_E002, 0, 3);
    for (i = 0; i < source->length; ++i) {
        if (source->bytes[i] == '\r' &&
            (i + 1 == source->length || source->bytes[i + 1] != '\n'))
            return source_error(source, TF_E003, i, i + 1);
    }
    if (scalars == SIZE_MAX || scalars + 1 > SIZE_MAX / sizeof(size_t) ||
        lines > SIZE_MAX / sizeof(size_t)) return TF_HOST_ERROR;
    source->scalar_offsets = source->allocator.allocate(source->allocator.context,
                                                        (scalars + 1) * sizeof(size_t));
    source->line_scalars = source->allocator.allocate(source->allocator.context,
                                                      lines * sizeof(size_t));
    if (source->scalar_offsets == NULL || source->line_scalars == NULL) return TF_HOST_ERROR;
    source->scalar_count = scalars;
    source->line_count = lines;
    source->line_scalars[0] = 0;
    at = 0;
    line = 1;
    for (i = 0; i < scalars; ++i) {
        source->scalar_offsets[i] = at;
        (void)tf_decode(source->bytes, source->length, at, &scalar, &end);
        if (scalar == '\n') source->line_scalars[line++] = i + 1;
        at = end;
    }
    source->scalar_offsets[scalars] = source->length;
    source->valid = true;
    return TF_OK;
}

TfStatus tf_source_init(TfSource *out, const char *name,
                        const void *bytes, size_t length, const TfAllocator *allocator) {
    size_t name_length;
    TfStatus status;
    if (out == NULL) return TF_HOST_ERROR;
    *out = (TfSource){0};
    out->allocator = tf_allocator(allocator);
    if (name == NULL || (bytes == NULL && length != 0) || length == SIZE_MAX ||
        !tf_allocator_valid(out->allocator)) goto fail;
    name_length = strlen(name);
    if (name_length == SIZE_MAX) goto fail;
    out->name = out->allocator.allocate(out->allocator.context, name_length + 1);
    out->bytes = out->allocator.allocate(out->allocator.context, length == 0 ? 1 : length);
    if (out->name == NULL || out->bytes == NULL) goto fail;
    memcpy(out->name, name, name_length + 1);
    if (length != 0) memcpy(out->bytes, bytes, length);
    out->length = length;
    status = validate_source(out);
    if (status != TF_HOST_ERROR) return status;
fail:
    tf_source_destroy(out);
    return TF_HOST_ERROR;
}

TfStatus tf_source_load(TfSource *out, const char *path, const TfAllocator *allocator) {
    TfAllocator memory = tf_allocator(allocator);
    FILE *stream;
    void *data = NULL;
    size_t length = 0, capacity = 0;
    TfStatus status = TF_HOST_ERROR;
    TfFileIdentity identity;
    if (out == NULL) return TF_HOST_ERROR;
    *out = (TfSource){0};
    if (path == NULL || !tf_allocator_valid(memory)) return TF_HOST_ERROR;
    stream = fopen(path, "rb");
    if (stream == NULL) return TF_HOST_ERROR;
    if (!tf_file_identity(stream, &identity)) { (void)fclose(stream); return TF_HOST_ERROR; }
    for (;;) {
        size_t got;
        if (length > SIZE_MAX - 4096 ||
            !tf_grow(&data, &capacity, length + 4096, 1, memory)) break;
        got = fread((unsigned char *)data + length, 1, capacity - length, stream);
        length += got;
        if (ferror(stream)) break;
        if (feof(stream)) { status = TF_OK; break; }
        if (got == 0) break;
    }
    if (fclose(stream) != 0) status = TF_HOST_ERROR;
    if (status == TF_OK) {
        status = tf_source_init(out, path, data, length, &memory);
        if (status != TF_HOST_ERROR) out->origin = identity;
    }
    if (data != NULL) memory.deallocate(memory.context, data);
    return status;
}

void tf_source_destroy(TfSource *source) {
    if (source == NULL) return;
    if (source->allocator.deallocate != NULL) {
        if (source->bytes != NULL) source->allocator.deallocate(source->allocator.context, source->bytes);
        if (source->name != NULL) source->allocator.deallocate(source->allocator.context, source->name);
        if (source->scalar_offsets != NULL)
            source->allocator.deallocate(source->allocator.context, source->scalar_offsets);
        if (source->line_scalars != NULL)
            source->allocator.deallocate(source->allocator.context, source->line_scalars);
    }
    *source = (TfSource){0};
}

static bool scalar_index(const TfSource *source, size_t byte, size_t *out) {
    size_t low = 0, high;
    if (source == NULL || !source->valid || byte > source->length) return false;
    high = source->scalar_count + 1;
    while (low < high) {
        size_t mid = low + (high - low) / 2;
        if (source->scalar_offsets[mid] < byte) low = mid + 1;
        else high = mid;
    }
    if (low > source->scalar_count || source->scalar_offsets[low] != byte) return false;
    *out = low;
    return true;
}
bool tf_source_location(const TfSource *source, size_t byte, TfLocation *out) {
    size_t index, low = 0, high, i, display = 1;
    if (out == NULL || !scalar_index(source, byte, &index)) return false;
    high = source->line_count;
    while (low + 1 < high) {
        size_t mid = low + (high - low) / 2;
        if (source->line_scalars[mid] <= index) low = mid;
        else high = mid;
    }
    for (i = source->line_scalars[low]; i < index; ++i) {
        size_t step = source->bytes[source->scalar_offsets[i]] == '\t'
                          ? 4 - (display - 1) % 4 : 1;
        if (display > SIZE_MAX - step) return false;
        display += step;
    }
    *out = (TfLocation){byte, index, low + 1, index - source->line_scalars[low] + 1, display};
    return true;
}
bool tf_source_byte(const TfSource *source, size_t line, size_t column, size_t *out) {
    size_t first, limit;
    if (source == NULL || !source->valid || out == NULL || line == 0 ||
        line > source->line_count || column == 0) return false;
    first = source->line_scalars[line - 1];
    limit = line < source->line_count ? source->line_scalars[line] : source->scalar_count + 1;
    if (column > limit - first) return false;
    *out = source->scalar_offsets[first + column - 1];
    return true;
}
bool tf_source_span(const TfSource *source, size_t start, size_t end, TfSpan *out) {
    size_t unused;
    if (out == NULL || start > end || !scalar_index(source, start, &unused) ||
        !scalar_index(source, end, &unused)) return false;
    *out = (TfSpan){source, start, end};
    return true;
}
bool tf_span_join(TfSpan left, TfSpan right, TfSpan *out) {
    TfSpan checked;
    if (left.source != right.source ||
        !tf_source_span(left.source, left.start, left.end, &checked) ||
        !tf_source_span(right.source, right.start, right.end, &checked)) return false;
    return tf_source_span(left.source, left.start < right.start ? left.start : right.start,
                          left.end > right.end ? left.end : right.end, out);
}
