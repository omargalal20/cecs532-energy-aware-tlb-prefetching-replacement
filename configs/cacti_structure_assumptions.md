# CACTI structure assumptions and results

## Node and entry assumptions

- Final energy-table node: 22 nm, per Sanket's recommendation.
- 90 nm values are retained as node-sensitivity results; the earlier 90 nm setting came from the CACTI sample config.
- Virtual addresses are 64 bits; with 4 KB pages, VPN is 52 bits.
- PPN is assumed to be 52 bits; physical-address width was not independently verified.
- Single core and one address space; no CPU-ID or ASID bits.
- DTLB/ITLB: 16 sets x 4 ways. VPN tag is 48 bits. Base entry is 103 bits: 48-bit tag, 52-bit PPN, and 3 flags. Adding 10 permission bits gives a 113-bit sensitivity entry. The permission sensitivity is approximated by increasing CACTI tag size from 48 to 58 bits.
- PQ entry: 109 bits (52-bit VPN, 52-bit PPN, 4-bit distance, valid).
- ATP fake-queue entry: 53 bits (52-bit VPN and valid); three queues of 16 entries each.
- SBFP sampler entry: 56 bits (52-bit VPN and 4-bit distance).
- SBFP FDT: 14 counters x 10 bits.

## CACTI proxy method and results

The modeled blocks exceed the real entry widths, so the CACTI numbers are labeled proxies and likely overestimate per-access energy. Final runs were executed from the CACTI directory.

- DTLB/ITLB: 128B-block, 16-set, 4-way configs supply the 22 nm CSV values. 64B configs failed with “no valid data array organizations found.” 256B configs provide a geometry sensitivity. The +10 permission-bit configs use a 58-bit tag proxy.
- PQ: 64B-block config supplies the 22 nm CSV value; 128B provides a geometry sensitivity.
- SBFP_FDT: modeled as RAM. The 128B-block RAM config supplies the 22 nm CSV value; 64B RAM failed with “no valid data array organizations found.” The 256B RAM config provides a geometry sensitivity.
- SBFP_SAMPLER: 64B-block config supplies the 22 nm CSV value; 128B provides a geometry sensitivity.
- ATP_FPQ: one 16-entry queue was modeled with a 64B block. The 22 nm CSV value is per queue; energy accounting must include all three queues. The 128B config provides a geometry sensitivity.
- The 90 nm same-geometry sensitivity values are recorded in the CSV notes.
- PSC: see cacti_psc_notes.md. Its rows remain unavailable because CACTI produced no energy values.
- L1D, L2C, and LLC are optional and remain TBD in the CSV.
