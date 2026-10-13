/* synthetic corpus program synth_0293
 * loops=1 nest=1 trip=l rec=direct calls=0 branch=8 mem=seq mix=muldiv */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
#define ASIZE 1024
static u32 arr[ASIZE];
static u32 rec_f(u32 n, u32 acc) {
  if (n == 0u) return acc;
  return rec_f(n - 1u, acc + (n ^ (acc << 1)));
}
u32 work(u32 s, u32 n) {
  u32 acc = s;
  for (u32 i0_0 = 0; i0_0 < 4096u; i0_0++) {
    u32 x = lcg(&s);
    acc += (x * 2654435761u) / ((x & 0xffu) + 1u);
    if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
    if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
    if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
    if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
    if ((x & 16u) == 0u) acc += 53u; else acc ^= (x >> 5);
    if ((x & 32u) == 0u) acc += 66u; else acc ^= (x >> 1);
    if ((x & 64u) == 0u) acc += 79u; else acc ^= (x >> 2);
    if ((x & 128u) == 0u) acc += 92u; else acc ^= (x >> 3);
    arr[i0_0 & (ASIZE-1)] = acc; acc += arr[(i0_0 + 1) & (ASIZE-1)];
  }
  acc = rec_f((s & 63u) + 8u, acc);
  return acc;
}
int main(int argc, char **argv) {
  (void)argv;
  u32 seed = 0x1234u + (u32)argc;
  u32 n = 64u;
  sink = work(seed, n);
  return (int)(sink & 0x7f);
}
