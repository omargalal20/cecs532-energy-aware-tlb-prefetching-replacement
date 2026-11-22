# STLB CACTI sensitivity and DRAM energy

The final energy table uses 90 nm, per the team decision; 22 nm is a sensitivity case. CACTI reports version 7.0.3DD Prerelease (Aug. 2012), with setup commit 1ffd8df. Both cases use a 64-byte block, 49-bit tag, and one read/write port. The actual STLB is 128 sets × 12 ways = 1,536 entries. Values below are from CACTI's Uniform Cache Access SRAM Model summary.

| Entries | Metric | 90 nm | 22 nm | Change (22−90) | Change |
|---|---|---:|---:|---:|---:|
| 1,024 (128×8) | Read (nJ/access) | 0.764013 | 0.0838914 | -0.6801216 | -89.02% |
| 1,024 (128×8) | Write (nJ/access) | 0.766323 | 0.0889089 | -0.6774141 | -88.40% |
| 1,024 (128×8) | Leakage (mW) | 30.9463 | 23.0347 | -7.9116 | -25.57% |
| 2,048 (128×16) | Read (nJ/access) | 1.86933 | 0.192163 | -1.677167 | -89.72% |
| 2,048 (128×16) | Write (nJ/access) | 1.94523 | 0.202141 | -1.743089 | -89.61% |
| 2,048 (128×16) | Leakage (mW) | 62.569 | 44.8915 | -17.6775 | -28.25% |
| 1,536 estimate (128×12) | Read (nJ/access) | 1.3166715 | 0.1380272 | -1.1786443 | -89.52% |
| 1,536 estimate (128×12) | Write (nJ/access) | 1.3557765 | 0.14552495 | -1.21025155 | -89.27% |
| 1,536 estimate (128×12) | Leakage (mW) | 46.75765 | 33.9631 | -12.79455 | -27.36% |

CACTI does not provide the exact 1,536-entry capacity, so use linear interpolation: E1536 = (E1024 + E2048) / 2. The endpoint half-ranges for read/write/leakage are 0.552659 nJ / 0.589454 nJ / 15.81135 mW at 90 nm, and 0.054136 nJ / 0.056616 nJ / 10.9284 mW at 22 nm. These indicate sensitivity, not guaranteed error bounds if CACTI's organization changes make the relationship nonlinear. The 64-byte block is a proxy for a narrower TLB entry.

| Metric | 90 nm ratio (2048/1024) | 22 nm ratio (2048/1024) | Ratio change |
|---|---:|---:|---:|
| Read energy | 2.447 | 2.291 | -6.38% |
| Write energy | 2.538 | 2.274 | -10.43% |
| Leakage | 2.022 | 1.949 | -3.61% |

Use 56 nJ per 64-byte DRAM read as the baseline estimate. David et al. report this for DDR3 at 1333 MHz with two DIMMs per channel; it includes array read, I/O, termination, and activate/precharge energy. It is an estimate under those assumptions, not a measurement of our machine. Apply it per LLC TRANSLATION MISS when that counter represents one DRAM read. In Table 2 this value is the "Average energy/read, page-closed policy, 2 DIMMs/channel" row (18 nJ array read + 1 nJ read I/O + 12 nJ extra termination + 25 nJ activate and precharge), so reads that hit an open page would cost less. The 800 MHz row is 64.7 nJ.

**Source:** H. David, C. Fallin, E. Gorbatov, U. R. Hanebutte, and O. Mutlu, “Memory Power Management via Dynamic Voltage/Frequency Scaling,” *Proc. 8th ACM Int. Conf. on Autonomic Computing (ICAC)*, 2011, pp. 31–40, Table 2. DOI: https://doi.org/10.1145/1998582.1998590. The access size (64 bytes per read) is our assumption; Table 2's caption does not state it.