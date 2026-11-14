#ifndef REPLACEMENT_ITP_H
#define REPLACEMENT_ITP_H

#include <cstdint>
#include <vector>

#include "cache.h"
#include "modules.h"

// iTP (instruction Translation Prioritization), ASPLOS'25 Chasapis et al., Sec. 4.1.
// Per set: a recency stack (position 0 = MRU, position W-1 = LRU), a 1-bit Type per entry (0 = instruction, 1 = data)
// and a 3-bit Freq counter per entry. The type of the request being handled is read from CACHE::current_is_instruction.
struct itp : public champsim::modules::replacement {
  static constexpr long N = 4;              // instruction insertion: N positions below MRU (paper Table 1)
  static constexpr long M = 8;              // data hit promotion: M positions above LRU (paper Table 1)
  static constexpr uint8_t FREQ_MAX = 7;    // 3-bit counter; saturation value is an ASSUMPTION (not stated in the text we read)

  long NUM_SET, NUM_WAY;
  std::vector<long> stack;     // [set * NUM_WAY + pos] = way
  std::vector<uint8_t> is_data; // [set * NUM_WAY + way]
  std::vector<uint8_t> freq;    // [set * NUM_WAY + way]

  // run-time counters (printed at the end, used to check the policy behaves as intended)
  uint64_t fills_instr = 0, fills_data = 0, hits_instr = 0, hits_data = 0, victims_instr = 0, victims_data = 0;

  explicit itp(CACHE* cache);

  long find_victim(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
                   champsim::address full_addr, access_type type);
  void replacement_cache_fill(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, champsim::address victim_addr,
                              access_type type);
  void update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                                champsim::address victim_addr, access_type type, uint8_t hit);
  void replacement_final_stats();

private:
  long position_of(long set, long way) const;
  void move_to(long set, long way, long new_pos);
};

#endif
