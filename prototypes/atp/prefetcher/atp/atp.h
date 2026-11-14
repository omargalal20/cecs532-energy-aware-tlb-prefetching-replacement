#ifndef PREFETCHER_ATP_H
#define PREFETCHER_ATP_H

#include <array>
#include <cstdint>
#include <deque>
#include <unordered_map>
#include <list>
#include <vector>

#include "address.h"
#include "modules.h"

// ATP: Agile TLB Prefetcher, Vavouliotis et al., ISCA 2021, Sec. V.
// Decision tree over three constituent prefetchers: P0 = H2P, P1 = MASP, P2 = STP (paper leaf assignment).
// Prefetches fill the STLB directly (no separate prefetch queue, a deviation from the paper).
// With `sbfp` set (module atp_sbfp), SBFP (Sec. IV-B) is added: free neighbour PTEs from the walked PTE cache line are
// prefetched as "free" requests (flag bit in pf_metadata) that the page-table walker completes without a memory access
// (see prototypes/sbfp/sbfp-free-walk.patch).
struct atp : public champsim::modules::prefetcher {
  // ---- parameters from the paper ----
  static constexpr std::size_t FPQ_SIZE = 16;       // 16-entry fully associative, FIFO (Sec. V-B)
  static constexpr int EN_MAX = 255, SEL1_MAX = 63, SEL2_MAX = 3; // 8-, 6-, 2-bit saturating counters
  // ---- ASSUMPTIONS (not stated in the paper text we could read) ----
  static constexpr int EN_INIT = 128, SEL1_INIT = 32, SEL2_INIT = 2; // counters start with MSB set
  static constexpr std::size_t MASP_ENTRIES = 64;   // MASP table size and LRU replacement

  struct fpq_t {
    std::deque<int64_t> q;
    bool hit(int64_t vpn) const;
    void push(int64_t vpn);
  };

  int c0 = EN_INIT, c1 = SEL1_INIT, c2 = SEL2_INIT; // enable_pref, select_1, select_2
  std::array<fpq_t, 3> fpq;                        // index = P0 (H2P), P1 (MASP), P2 (STP)

  // H2P history: A (oldest), B, E (most recent) miss pages
  int64_t hA = 0, hB = 0, hE = 0;
  int hist = 0;

  // MASP table keyed by PC
  struct masp_entry { int64_t prev_vpn; int64_t stride; std::list<uint64_t>::iterator lru_it; };
  std::unordered_map<uint64_t, masp_entry> masp;
  std::list<uint64_t> masp_lru; // front = most recent

  // statistics
  uint64_t calls = 0, trigger_misses = 0, useful_pf_hits = 0, fpq_any_hit = 0;
  std::array<uint64_t, 3> fpq_hits{}, selected{};
  uint64_t disabled = 0, issued = 0, dropped = 0;

  // ---- SBFP (Sec. IV-B). Values marked (paper) are stated in the paper, (assumed) are not. ----
  static constexpr uint32_t FREE_PREFETCH_FLAG = 1u << 31; // same value as PageTableWalker::FREE_PREFETCH_FLAG
  static constexpr int FDT_SIZE = 14;                      // free distances -7..+7 without 0 (paper)
  static constexpr int FDT_MAX = 1023;                     // 10-bit counters (paper)
  static constexpr int FDT_THRESHOLD = 100;                // counter > threshold -> prefetch, else Sampler (paper)
  static constexpr std::size_t SAMPLER_SIZE = 64;          // FIFO (paper)
  static constexpr std::size_t FREE_MAP_MAX = 2048;        // bookkeeping bound for in-STLB free prefetches (ours)
  static constexpr int FDT_INIT = 0;                       // (assumed: initial value not stated)
  bool sbfp = false;
  std::array<int, FDT_SIZE> fdt{};
  std::deque<std::pair<int64_t, int>> sampler;             // (vpn, free-distance index)
  std::unordered_map<int64_t, int> free_map;               // vpn -> distance index, for free prefetches placed in the STLB
  std::deque<int64_t> free_order;
  uint64_t free_issued = 0, free_dropped = 0, free_useful = 0, sampler_inserts = 0, sampler_lookups = 0, sampler_hits = 0, fdt_updates = 0, decays = 0;

  using prefetcher::prefetcher;
  uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool useful_prefetch, access_type type,
                                    uint32_t metadata_in);
  uint32_t prefetcher_cache_fill(champsim::address addr, long set, long way, uint8_t prefetch, champsim::address evicted_addr, uint32_t metadata_in);
  void prefetcher_final_stats();

private:
  bool neighbour_mapped(int64_t q) const;
  void do_free(int64_t page, uint32_t metadata);
  std::vector<int64_t> free_selected(int64_t page) const;
  void fdt_hit(int idx);
  std::vector<int64_t> cand_h2p() const;
  std::vector<int64_t> cand_stp(int64_t vpn) const;
  std::vector<int64_t> cand_masp(int64_t vpn, uint64_t pc);
  void sat(int& c, int delta, int max) { c = c + delta < 0 ? 0 : (c + delta > max ? max : c + delta); }
};

#endif
