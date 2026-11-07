#include "atp.h"

#include <algorithm>
#include <cstdio>

bool atp::fpq_t::hit(int64_t vpn) const { return std::find(q.begin(), q.end(), vpn) != q.end(); }

void atp::fpq_t::push(int64_t vpn)
{
  if (hit(vpn))
    return;
  if (q.size() == FPQ_SIZE)
    q.pop_front(); // FIFO
  q.push_back(vpn);
}

std::vector<int64_t> atp::cand_stp(int64_t vpn) const { return {vpn - 2, vpn - 1, vpn + 1, vpn + 2}; }

// d(X, Y) = X - Y (signed distance). E is the most recent miss: prefetch E + d(E,B) and E + d(B,A).
std::vector<int64_t> atp::cand_h2p() const
{
  if (hist < 3)
    return {};
  return {hE + (hE - hB), hE + (hB - hA)};
}

// MASP: table indexed by PC {previous miss page, stride}. On a hit with entry (E, +s): prefetch A + s and A + d(A,E).
std::vector<int64_t> atp::cand_masp(int64_t vpn, uint64_t pc)
{
  std::vector<int64_t> out;
  auto it = masp.find(pc);
  if (it != masp.end()) {
    out = {vpn + it->second.stride, vpn + (vpn - it->second.prev_vpn)};
    it->second.stride = vpn - it->second.prev_vpn;
    it->second.prev_vpn = vpn;
    masp_lru.erase(it->second.lru_it);
    masp_lru.push_front(pc);
    it->second.lru_it = masp_lru.begin();
  } else {
    if (masp.size() == MASP_ENTRIES) {
      masp.erase(masp_lru.back());
      masp_lru.pop_back();
    }
    masp_lru.push_front(pc);
    masp[pc] = masp_entry{vpn, 0, masp_lru.begin()};
  }
  return out;
}

uint32_t atp::prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool useful_prefetch, access_type, uint32_t metadata_in)
{
  ++calls;
  // In the paper a prefetched translation sits in the PQ, so a demand access that finds it is a TLB miss as far as ATP is concerned.
  // Here prefetches fill the STLB itself, so a hit on a prefetched entry (useful_prefetch) is counted as a miss to keep the same miss stream.
  if (cache_hit && !useful_prefetch)
    return metadata_in;
  ++trigger_misses;
  if (cache_hit)
    ++useful_pf_hits;

  const int64_t vpn = static_cast<int64_t>(champsim::page_number{addr}.to<uint64_t>());
  const uint64_t pc = ip.to<uint64_t>();

  // step 1: look the missing page up in all FPQs
  const bool h0 = fpq[0].hit(vpn), h1 = fpq[1].hit(vpn), h2 = fpq[2].hit(vpn);
  fpq_hits[0] += h0; fpq_hits[1] += h1; fpq_hits[2] += h2;
  fpq_any_hit += (h0 || h1 || h2);

  // step 2: update counters (Fig. 7 table: rows are P0/P1/P2 FPQ hit/miss)
  if (!h0 && !h1 && !h2) {
    sat(c0, -1, EN_MAX);
  } else {
    sat(c0, +1, EN_MAX);
    if (!h0 && !h1 && h2) { sat(c1, -1, SEL1_MAX); sat(c2, +1, SEL2_MAX); }
    else if (!h0 && h1 && !h2) { sat(c1, -1, SEL1_MAX); sat(c2, -1, SEL2_MAX); }
    else if (!h0 && h1 && h2) { sat(c1, -1, SEL1_MAX); }
    else if (h0 && !h1 && !h2) { sat(c1, +1, SEL1_MAX); }
    else if (h0 && !h1 && h2) { sat(c2, +1, SEL2_MAX); }
    else if (h0 && h1 && !h2) { sat(c2, -1, SEL2_MAX); }
    // h0 && h1 && h2: only C0++
  }

  // candidates every constituent prefetcher would issue (also used to fill its FPQ in step 4)
  const std::array<std::vector<int64_t>, 3> cand{cand_h2p(), cand_masp(vpn, pc), cand_stp(vpn)};

  // step 3: select
  int sel = -1; // -1 = disabled
  if (c0 >= 128) {
    if (c1 >= 32)
      sel = 0;
    else
      sel = (c2 >= 2) ? 2 : 1;
  }
  if (sel < 0) {
    ++disabled;
  } else {
    ++selected[static_cast<std::size_t>(sel)];
    for (auto p : cand[static_cast<std::size_t>(sel)]) {
      if (p < 0)
        continue;
      if (prefetch_line(champsim::address{static_cast<uint64_t>(p) << LOG2_PAGE_SIZE}, true, metadata_in))
        ++issued;
      else
        ++dropped;
    }
  }

  // step 4: update every FPQ with the fake prefetches, then the H2P history
  for (std::size_t i = 0; i < 3; ++i)
    for (auto p : cand[i])
      if (p >= 0)
        fpq[i].push(p);
  hA = hB; hB = hE; hE = vpn;
  hist = std::min(hist + 1, 3);
  return metadata_in;
}

uint32_t atp::prefetcher_cache_fill(champsim::address, long, long, uint8_t, champsim::address, uint32_t metadata_in) { return metadata_in; }

void atp::prefetcher_final_stats()
{
  std::printf("[ATP] operate_calls=%lu trigger_misses=%lu (of which hits_on_prefetched=%lu) fpq_any_hit=%lu fpq_hits[H2P,MASP,STP]=%lu,%lu,%lu\n", calls,
              trigger_misses, useful_pf_hits, fpq_any_hit, fpq_hits[0], fpq_hits[1], fpq_hits[2]);
  std::printf("[ATP] selected[H2P,MASP,STP]=%lu,%lu,%lu disabled=%lu issued=%lu dropped_pq_full=%lu counters(c0,c1,c2)=%d,%d,%d\n", selected[0], selected[1],
              selected[2], disabled, issued, dropped, c0, c1, c2);
}
