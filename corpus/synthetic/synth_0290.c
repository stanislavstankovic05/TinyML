/* synthetic corpus program synth_0290
 * loops=1 nest=3 trip=s rec=tree calls=6 branch=2 mem=seq mix=muldiv */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
#define ASIZE 1024
static u32 arr[ASIZE];
static u32 rec_t(u32 n) {
  if (n < 2u) return n + 1u;
  return rec_t(n - 1u) + rec_t(n - 2u);
}
static u32 chain6(u32 x) { return x ^ (x >> 3) + 42u; }
static u32 chain5(u32 x) { return chain6(x + 5u) + 35u; }
static u32 chain4(u32 x) { return chain5(x + 4u) + 28u; }
static u32 chain3(u32 x) { return chain4(x + 3u) + 21u; }
static u32 chain2(u32 x) { return chain3(x + 2u) + 14u; }
static u32 chain1(u32 x) { return chain2(x + 1u) + 7u; }
u32 work(u32 s, u32 n) {
  u32 acc = s;
  for (u32 i0_0 = 0; i0_0 < 64u; i0_0++) {
    for (u32 i0_1 = 0; i0_1 < 8u; i0_1++) {
      for (u32 i0_2 = 0; i0_2 < 8u; i0_2++) {
        u32 x = lcg(&s);
        acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
        if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
        if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
        arr[i0_0 & (ASIZE-1)] = acc; acc += arr[(i0_0 + 1) & (ASIZE-1)];
        acc += chain1(x);
      }
    }
  }
  acc += rec_t((s & 7u) + 10u);
  return acc;
}
int main(int argc, char **argv) {
  (void)argv;
  u32 seed = 0x1234u + (u32)argc;
  u32 n = 64u;
  sink = work(seed, n);
  return (int)(sink & 0x7f);
}
