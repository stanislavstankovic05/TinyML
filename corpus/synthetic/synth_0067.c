/* synthetic corpus program synth_0067
 * loops=2 nest=2 trip=s rec=none calls=0 branch=0 mem=chase mix=muldiv */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
#define ASIZE 1024
static u32 arr[ASIZE];
u32 work(u32 s, u32 n) {
  u32 acc = s;
  u32 nxt = s & (ASIZE-1);
  for (u32 i0_0 = 0; i0_0 < 64u; i0_0++) {
    for (u32 i0_1 = 0; i0_1 < 8u; i0_1++) {
      u32 x = lcg(&s);
      acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
      nxt = arr[nxt & (ASIZE-1)] & (ASIZE-1); arr[nxt] ^= acc; acc += nxt;
    }
  }
  for (u32 i1_0 = 0; i1_0 < 64u; i1_0++) {
    for (u32 i1_1 = 0; i1_1 < 8u; i1_1++) {
      u32 x = lcg(&s);
      acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
      nxt = arr[nxt & (ASIZE-1)] & (ASIZE-1); arr[nxt] ^= acc; acc += nxt;
    }
  }
  return acc;
}
int main(int argc, char **argv) {
  (void)argv;
  u32 seed = 0x1234u + (u32)argc;
  u32 n = 64u;
  sink = work(seed, n);
  return (int)(sink & 0x7f);
}
