# PSC CACTI modeling attempts

All four requested PSC geometries were attempted at the provisional 90 nm node using CACTI's 64-byte minimum block size.

The 1x2 and 1x4 configurations were initially rejected because CACTI reported that the number of sets was too small. They were retried as fully associative configurations with one search port. In the final attempts, all four configurations (1x2, 1x4, 2x4, and 4x8) exited with code 139 before producing energy results.

Therefore, no PSC read energy, write energy, or leakage values are available from these runs. No larger-geometry proxy is used. Keep the PSC rows unavailable until a supported model produces usable results.

## CACTI version and exact diagnostics

The CACTI output reports: `CACTI (version 7.0.3DD Prerelease of Aug, 2012)`.

For the initial 1x2 and 1x4 attempts, CACTI reported: `Number of sets is too small: Need to either increase cache size, or decrease associativity or block size (or use fully associative cache)`. These two configs were then retried as fully associative with one search port. In the final attempts, all four configs (1x2, 1x4, 2x4, and 4x8) exited with status 139 before producing energy values.

## PSC upper-bound proxy

`PSC_UPPER_PROXY` uses the 64-entry fully associative PQ proxy configuration: 64-byte block at 90 nm. Values: read 0.186486 nJ/access, write 0.207663 nJ/access, leakage 5.95101 mW. Label: “upper-bound proxy; real PSC geometries (2, 4, 8 and 32 entries) failed in CACTI, exit 139”. The four geometry-specific PSC rows remain unavailable.
