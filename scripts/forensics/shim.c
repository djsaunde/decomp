#include <stdlib.h>
#include <stdint.h>
typedef struct { char *str; size_t len; size_t allocated_len; } GStr;
extern char *g_string_free(GStr *s, int free_segment);
void g_assertion_message_cmpint(const char *d, const char *f, int l, const char *fn, const char *e,
                                uint64_t a1, const char *cmp, uint64_t a2, char nt) { abort(); }
char *g_string_free_and_steal(GStr *s) { return g_string_free(s, 0); }
