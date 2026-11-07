# Preliminary STLB CACTI estimates

These are preliminary proxy estimates, not final TLB energy values.

Assumptions:
- 90 nm technology node, provisionally matching the existing CACTI config
- 49-bit STLB tag
- Separate 128-set, 8-way and 128-set, 16-way sensitivity cases
- CACTI required a 64-byte block; this is larger than the assumed 56-bit PPN and metadata entry, so the estimates do not represent an exact TLB entry model
- ChampSim's actual STLB remains 128 sets x 12 ways

CACTI outputs:
| Case | Read energy (nJ/access) | Write energy (nJ/access) | Total leakage (mW) |
| --- | ---: | ---: | ---: |
| 128 sets x 8 ways | 0.764013 | 0.766323 | 30.9463 |
| 128 sets x 16 ways | 1.86933 | 1.94523 | 62.569 |

Keep these values separate. Do not average them. Confirm the technology-node assumption and 64-byte-block proxy with the team before using them as final CSV values.
