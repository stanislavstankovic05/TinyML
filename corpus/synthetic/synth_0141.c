/* synthetic corpus program synth_0141
 * loops=1 nest=1 trip=s rec=none calls=6 branch=4 mem=stride mix=mixed */
typedef unsigned int u32;
static volatile u32 sink;
static u32 lcg(u32 *s) { *s = *s * 1664525u + 1013904223u; return *s; }
#define ASIZE 1024
static u32 arr[ASIZE];
static u32 chain6(u32 x) { return x ^ (x >> 3) + 42u; }
static u32 chain5(u32 x) { return chain6(x + 5u) + 35u; }
static u32 chain4(u32 x) { return chain5(x + 4u) + 28u; }
static u32 chain3(u32 x) { return chain4(x + 3u) + 21u; }
static u32 chain2(u32 x) { return chain3(x + 2u) + 14u; }
static u32 chain1(u32 x) { return chain2(x + 1u) + 7u; }
u32 work(u32 s, u32 n) {
  u32 acc = s;
  for (u32 i0_0 = 0; i0_0 < 64u; i0_0++) {
    u32 x = lcg(&s);
    acc += (x * 31u) ^ (acc / ((x & 0x3fu) + 1u)) + (x >> 1);
    if ((x & 1u) == 0u) acc += 1u; else acc ^= (x >> 1);
    if ((x & 2u) == 0u) acc += 14u; else acc ^= (x >> 2);
    if ((x & 4u) == 0u) acc += 27u; else acc ^= (x >> 3);
    if ((x & 8u) == 0u) acc += 40u; else acc ^= (x >> 4);
    arr[(i0_0 * 17u) & (ASIZE-1)] = acc; acc += arr[(i0_0 * 31u) & (ASIZE-1)];
    acc += chain1(x);
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
