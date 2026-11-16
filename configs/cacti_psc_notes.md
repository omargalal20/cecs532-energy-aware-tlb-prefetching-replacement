# PSC CACTI modeling attempts

All four requested PSC geometries were attempted at the provisional 90 nm node using CACTI's 64-byte minimum block size.

The 1x2 and 1x4 configurations were initially rejected because CACTI reported that the number of sets was too small. They were retried as fully associative configurations with one search port. In the final attempts, all four configurations (1x2, 1x4, 2x4, and 4x8) exited with code 139 before producing energy results.

Therefore, no PSC read energy, write energy, or leakage values are available from these runs. No larger-geometry proxy is used. Keep the PSC rows unavailable until a supported model produces usable results.
