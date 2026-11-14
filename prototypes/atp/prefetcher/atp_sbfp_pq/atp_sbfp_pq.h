#ifndef PREFETCHER_ATP_SBFP_PQ_H
#define PREFETCHER_ATP_SBFP_PQ_H

#include "../atp/atp.h"

// ATP with SBFP and the paper's separate prefetch queue (in the page walker).
struct atp_sbfp_pq : public atp {
  explicit atp_sbfp_pq(CACHE* cache) : atp(cache)
  {
    sbfp = true;
    pq_mode = true;
  }
};

#endif
