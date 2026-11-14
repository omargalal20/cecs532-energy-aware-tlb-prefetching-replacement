#ifndef PREFETCHER_ATP_SBFP_H
#define PREFETCHER_ATP_SBFP_H

#include "../atp/atp.h"

// ATP with SBFP enabled: same code as atp, with the sbfp flag set.
struct atp_sbfp : public atp {
  explicit atp_sbfp(CACHE* cache) : atp(cache) { sbfp = true; }
};

#endif
