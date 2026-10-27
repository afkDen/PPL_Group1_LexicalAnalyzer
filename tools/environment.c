#include <float.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
int main(void) {
    if (CHAR_BIT != 8 || sizeof(uint32_t) != 4 || sizeof(int64_t) != 8 ||
        sizeof(size_t) < 4) {
        fputs("FAIL: require 8-bit bytes, exact int64_t/uint32_t, >=32-bit size_t\n", stderr);
        return 1;
    }
    printf("PASS C17 native compile/run: %zu-bit pointers; binary64 target %s\n",
           sizeof(void *) * (size_t)CHAR_BIT,
           FLT_RADIX == 2 && DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024 ? "available" : "unverified");
    return 0;
}
