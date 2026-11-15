typedef int s32; typedef short s16; typedef unsigned int u32;
typedef void (*FuncPtr2)(); extern FuncPtr2 D_80012C44;
extern char D_8000A36C[];
typedef struct { s32 info; s32 offset; s32 orig; } UsoRel_1ADC;
typedef struct { s16 flags; s16 pad; s32 value; s32 pad2; } UsoUsoRelSym_1ADC_1ADC;

#define SYM_1ADC (&symtab[rel[i].info >> 4]) /* run 186: de-named (lever-sweep 81.81 -> 93.13) */
s32 func_80001ADC(char *obj, char *base, UsoRel_1ADC *rel, s32 n) {
    UsoUsoRelSym_1ADC_1ADC *symtab;
    s32 type, val, lo;
    s32 info; UsoUsoRelSym_1ADC_1ADC *sym; /* run 186: unreferenced; their cfe homes give the target's 0x50 frame */
    s16 *hiptr;
    s32 v; /* run 186: declared after hiptr (5040-order grid): hiptr home 0x34 as in the target */
    s32 i;
    s32 hival;
    u32 *p;

    symtab = *(UsoUsoRelSym_1ADC_1ADC **)(obj + 0x3C);
    if (base == 0 || rel == 0) {
        return 0;
    }
    for (i = 0; i < n; i++) {
        if (rel[i].info & 8) {
            continue;
        }
        val = SYM_1ADC->value; /* agent-c run 326: value read before the flags test (same symtab entry; unused on the continue path) */
        if (SYM_1ADC->flags & 8) {} else { continue; }
        type = rel[i].info & 7;
        p = (u32 *)(base + rel[i].offset);
        rel[i].orig = *p;
        switch (type) {
        case 1:
            *p = ((((u32)val >> 2) & 0x3FFFFFF) + (*p & 0x3FFFFFF)) | (*p & 0xFC000000); /* agent-c run 210: folded counted use (zero code, kit CXCIV) */
            break;
        case 3:
            hiptr = (s16 *)p + 1;
            hival = ((s16 *)p)[1]; /* run 186 (lever-sweep bbsplit) */
            break;
        case 2:
            lo = ((s16 *)p)[1];
            if (hiptr != 0) {
                v = (hival << 16) + (s16)lo + val; /* run 186 (lever-sweep bbsplit) */
                *hiptr = (u32)(v - (s16)v) >> 16;
                hiptr = 0;
            }
            ((s16 *)p)[1] = (hival << 16) + lo + val;
            break;
        case 4:
            *p += val;
            break;
        default:
            D_80012C44(D_8000A36C, (void *)type);
            return -2;
        }
        rel[i].info |= 8;
    }
    return 0;
}
#undef SYM_1ADC
