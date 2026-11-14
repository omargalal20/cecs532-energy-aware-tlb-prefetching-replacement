#include "atp.h"

#include <algorithm>
#include <cstdio>

#include "cache.h"
#include "sbfp_hooks.h"
#include "vmem.h"

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

// Statistics are counted in the measured phase only (not during warmup); prefetcher state keeps learning in both.
#define STAT(stmt) do { if (!intern_->warmup) { stmt; } } while (0)

namespace
{
int dist_index(int64_t d) { return d < 0 ? static_cast<int>(d + 7) : static_cast<int>(d + 6); } // -7..-1 -> 0..6, +1..+7 -> 7..13
}

// A neighbouring PTE is a valid free translation only if its page is already mapped (a real PTE for an unmapped page is invalid).
// Checking this also avoids the simulator allocating physical pages early, which would change the physical memory layout.
bool atp::neighbour_mapped(int64_t q) const
{
  const auto* vm = VirtualMemory::instance;
  return vm != nullptr && vm->is_mapped(intern_->cpu, champsim::page_number{champsim::address{static_cast<uint64_t>(q) << LOG2_PAGE_SIZE}});
}

void atp::fdt_hit(int idx)
{
  STAT(++fdt_updates);
  if (++fdt[static_cast<std::size_t>(idx)] >= FDT_MAX) { // decay: shift all counters right when one saturates (paper)
    for (auto& c : fdt)
      c >>= 1;
    STAT(++decays);
  }
}

// Free neighbours (same PTE cache line = same aligned group of 8 pages) whose FDT counter exceeds the threshold.
std::vector<int64_t> atp::free_selected(int64_t page) const
{
  std::vector<int64_t> out;
  const int64_t base = page & ~int64_t{7};
  for (int64_t q = base; q < base + 8; ++q)
    if (q != page && q >= 0 && fdt[static_cast<std::size_t>(dist_index(q - page))] > FDT_THRESHOLD && neighbour_mapped(q))
      out.push_back(q);
  return out;
}

void atp::do_free(int64_t page, uint32_t metadata)
{
  const int64_t base = page & ~int64_t{7};
  for (int64_t q = base; q < base + 8; ++q) {
    if (q == page || q < 0 || !neighbour_mapped(q))
      continue;
    const int idx = dist_index(q - page);
    if (fdt[static_cast<std::size_t>(idx)] > FDT_THRESHOLD && pq_mode) {
      if (sbfp_hooks::pq_insert && sbfp_hooks::pq_insert(q, idx))
        STAT(++free_issued);
    } else if (fdt[static_cast<std::size_t>(idx)] > FDT_THRESHOLD) {
      if (prefetch_line(champsim::address{static_cast<uint64_t>(q) << LOG2_PAGE_SIZE}, true, metadata | FREE_PREFETCH_FLAG)) {
        STAT(++free_issued);
        if (free_map.size() >= FREE_MAP_MAX) { free_map.erase(free_order.front()); free_order.pop_front(); }
        free_map[q] = idx;
        free_order.push_back(q);
      } else {
        STAT(++free_dropped);
      }
    } else {
      auto same = [q](const auto& e) { return e.first == q; };
      if (std::find_if(sampler.begin(), sampler.end(), same) == sampler.end()) {
        if (sampler.size() == SAMPLER_SIZE)
          sampler.pop_front(); // FIFO
        sampler.emplace_back(q, idx);
        STAT(++sampler_inserts);
      }
    }
  }
}

uint32_t atp::prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool useful_prefetch, access_type, uint32_t metadata_in)
{
  STAT(++calls);
  // In the paper a prefetched translation sits in the PQ, so a demand access that finds it is a TLB miss as far as ATP is concerned.
  // Here prefetches fill the STLB itself, so a hit on a prefetched entry (useful_prefetch) is counted as a miss to keep the same miss stream.
  if (cache_hit && !useful_prefetch)
    return metadata_in;
  STAT(++trigger_misses);
  if (cache_hit)
    STAT(++useful_pf_hits);

  const int64_t vpn = static_cast<int64_t>(champsim::page_number{addr}.to<uint64_t>());
  if (sbfp) {
    if (cache_hit) { // hit on a prefetched STLB entry: if it was a free prefetch, reward its free distance
      auto f = free_map.find(vpn);
      if (f != free_map.end()) { fdt_hit(f->second); STAT(++free_useful); free_map.erase(f); }
    } else if (!(pq_mode && sbfp_hooks::pq_contains && sbfp_hooks::pq_contains(vpn))) { // true miss that is not a PQ hit: look the page up in the Sampler (paper: searched on PQ misses)
      STAT(++sampler_lookups);
      auto it = std::find_if(sampler.begin(), sampler.end(), [vpn](const auto& e) { return e.first == vpn; });
      if (it != sampler.end()) { fdt_hit(it->second); STAT(++sampler_hits); sampler.erase(it); } // removal on hit: (assumed)
    }
  }
  const uint64_t pc = ip.to<uint64_t>();

  // step 1: look the missing page up in all FPQs
  const bool h0 = fpq[0].hit(vpn), h1 = fpq[1].hit(vpn), h2 = fpq[2].hit(vpn);
  STAT(fpq_hits[0] += h0; fpq_hits[1] += h1; fpq_hits[2] += h2);
  STAT(fpq_any_hit += (h0 || h1 || h2));

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
    STAT(++disabled);
  } else {
    STAT(++selected[static_cast<std::size_t>(sel)]);
    for (auto p : cand[static_cast<std::size_t>(sel)]) {
      if (p < 0)
        continue;
      if (prefetch_line(champsim::address{static_cast<uint64_t>(p) << LOG2_PAGE_SIZE}, true, metadata_in)) {
        STAT(++issued);
        if (sbfp && !pq_mode)
          do_free(p, metadata_in); // SBFP also acts on prefetch page walks (paper Sec. IV-C step 13)
      } else {
        STAT(++dropped);
      }
    }
  }
  if (sbfp && !pq_mode)
    do_free(vpn, metadata_in); // free neighbours of the demand walk, even when ATP is disabled (pq_mode: done when the walk finishes)

  // step 4: update every FPQ with the fake prefetches, then the H2P history
  for (std::size_t i = 0; i < 3; ++i)
    for (auto p : cand[i])
      if (p >= 0) {
        fpq[i].push(p);
        if (sbfp) // fake prefetch walks also contribute the free prefetches SBFP would select (paper Sec. V-A)
          for (auto q : free_selected(p))
            fpq[i].push(q);
      }
  hA = hB; hB = hE; hE = vpn;
  hist = std::min(hist + 1, 3);
  return metadata_in;
}

void atp::prefetcher_initialize()
{
  if (!pq_mode)
    return;
  // In PQ mode SBFP acts when a page walk finishes (free neighbours go into the walker's PQ) and learns from PQ hits.
  sbfp_hooks::walk_done = [this](int64_t vpn) { do_free(vpn, 0); };
  sbfp_hooks::pq_hit = [this](int idx) { fdt_hit(idx); STAT(++free_useful); };
}

uint32_t atp::prefetcher_cache_fill(champsim::address, long, long, uint8_t, champsim::address, uint32_t metadata_in) { return metadata_in; }

void atp::prefetcher_final_stats()
{
  std::printf("[ATP] operate_calls=%lu trigger_misses=%lu (of which hits_on_prefetched=%lu) fpq_any_hit=%lu fpq_hits[H2P,MASP,STP]=%lu,%lu,%lu\n", calls,
              trigger_misses, useful_pf_hits, fpq_any_hit, fpq_hits[0], fpq_hits[1], fpq_hits[2]);
  std::printf("[ATP] selected[H2P,MASP,STP]=%lu,%lu,%lu disabled=%lu issued=%lu dropped_pq_full=%lu counters(c0,c1,c2)=%d,%d,%d\n", selected[0], selected[1],
              selected[2], disabled, issued, dropped, c0, c1, c2);
  if (sbfp) {
    std::printf("[SBFP] free_issued=%lu free_dropped_pq_full=%lu free_useful=%lu sampler_inserts=%lu sampler_lookups=%lu sampler_hits=%lu fdt_updates=%lu decays=%lu\n",
                free_issued, free_dropped, free_useful, sampler_inserts, sampler_lookups, sampler_hits, fdt_updates, decays);
    std::printf("[SBFP] fdt[-7..-1,+1..+7]=");
    for (auto c : fdt)
      std::printf("%d ", c);
    std::printf("\n");
  }
}
