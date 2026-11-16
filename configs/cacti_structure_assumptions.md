# CACTI structure assumptions and results

## Assumptions

- Base technology node: 90 nm.
- Virtual addresses are 64 bits; with 4 KB pages, VPN is 52 bits.
- PPN is assumed to be 52 bits; physical-address width was not independently verified.
- Single core and one address space; no CPU-ID or ASID bits.
- DTLB/ITLB: 16 sets x 4 ways. VPN tag is 48 bits. Base entry is 103 bits: 48-bit tag, 52-bit PPN, and 3 flags. Adding 10 permission bits gives a 113-bit sensitivity entry.
- PQ entry: 109 bits (52-bit VPN, 52-bit PPN, 4-bit distance, valid).
- ATP fake-queue entry: 53 bits (52-bit VPN and valid); three queues of 16 entries each.
- SBFP sampler entry: 56 bits (52-bit VPN and 4-bit distance).
- SBFP FDT: 14 counters x 10 bits.

## CACTI proxies

CACTI's modeled blocks are larger than the real entries, so these are labeled proxy estimates and likely overestimate per-access energy. The 90 nm runs were executed from the CACTI directory.

- DTLB/ITLB: 64B configs failed with “no valid data array organizations found.” The 128B configs supply the CSV values; 256B configs are the geometry sensitivity. The +10 permission-bit case uses a 58-bit CACTI tag as an approximation of extra metadata, not its exact physical placement.
- PQ: 64B config supplies the CSV value; 128B config is the sensitivity case.
- SBFP_FDT: modeled as RAM. The 64B RAM config failed with “no valid data array organizations found.” The 128B RAM config supplies the CSV value; 256B RAM config is the sensitivity case.
- SBFP_SAMPLER: 64B config supplies the CSV value; 128B config is the sensitivity case.
- ATP_FPQ: one 16-entry queue was modeled. The 64B config supplies the CSV value; 128B config is the sensitivity case. Energy accounting must include all three queues.
- PSC: see cacti_psc_notes.md; its rows remain unavailable because CACTI produced no energy values.
