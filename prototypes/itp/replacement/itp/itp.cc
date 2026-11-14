#include "itp.h"

#include <algorithm>
#include <cstdio>

itp::itp(CACHE* cache)
    : replacement(cache), NUM_SET(static_cast<long>(cache->NUM_SET)), NUM_WAY(static_cast<long>(cache->NUM_WAY)),
      stack(static_cast<std::size_t>(NUM_SET * NUM_WAY)), is_data(static_cast<std::size_t>(NUM_SET * NUM_WAY), 1), freq(static_cast<std::size_t>(NUM_SET * NUM_WAY), 0)
{
  // Initial order: way 0 is MRU ... way W-1 is LRU (only matters until the set is full).
  for (long s = 0; s < NUM_SET; ++s)
    for (long p = 0; p < NUM_WAY; ++p)
      stack[static_cast<std::size_t>(s * NUM_WAY + p)] = p;
}

long itp::position_of(long set, long way) const
{
  auto begin = std::next(std::begin(stack), set * NUM_WAY);
  return std::distance(begin, std::find(begin, std::next(begin, NUM_WAY), way));
}

// Remove `way` from its current position and re-insert it at `new_pos`; entries in between shift by one.
void itp::move_to(long set, long way, long new_pos)
{
  auto begin = std::next(std::begin(stack), set * NUM_WAY);
  auto cur = std::find(begin, std::next(begin, NUM_WAY), way);
  auto dst = std::next(begin, new_pos);
  if (cur < dst)
    std::rotate(cur, std::next(cur), std::next(dst));
  else
    std::rotate(dst, cur, std::next(cur));
}

long itp::find_victim(uint32_t, uint64_t, long set, const champsim::cache_block*, champsim::address, champsim::address, access_type)
{
  // Evict the entry at the LRU position (paper: same eviction rule as LRU).
  const long way = stack[static_cast<std::size_t>(set * NUM_WAY + NUM_WAY - 1)];
  is_data[static_cast<std::size_t>(set * NUM_WAY + way)] ? ++victims_data : ++victims_instr;
  return way;
}

void itp::replacement_cache_fill(uint32_t, long set, long way, champsim::address, champsim::address, champsim::address, access_type)
{
  const bool instr = intern_->current_is_instruction;
  const auto idx = static_cast<std::size_t>(set * NUM_WAY + way);
  is_data[idx] = instr ? 0 : 1;
  freq[idx] = 0;
  if (instr) {
    ++fills_instr;
    move_to(set, way, N);            // N positions below MRU
  } else {
    ++fills_data;
    move_to(set, way, NUM_WAY - 1);  // LRU position
  }
}

void itp::update_replacement_state(uint32_t, long set, long way, champsim::address, champsim::address, champsim::address, access_type type, uint8_t hit)
{
  if (!hit || type == access_type::WRITE)
    return;
  const auto idx = static_cast<std::size_t>(set * NUM_WAY + way);
  if (!is_data[idx]) { // instruction translation
    ++hits_instr;
    if (freq[idx] < FREQ_MAX) {
      ++freq[idx];
      move_to(set, way, N);
    } else {
      move_to(set, way, 0); // saturated: MRU
    }
  } else { // data translation
    ++hits_data;
    move_to(set, way, NUM_WAY - 1 - M); // LRUpos + M
  }
}

void itp::replacement_final_stats()
{
  std::printf("[ITP] fills_instr=%lu fills_data=%lu hits_instr=%lu hits_data=%lu victims_instr=%lu victims_data=%lu\n", fills_instr, fills_data, hits_instr,
              hits_data, victims_instr, victims_data);
}
