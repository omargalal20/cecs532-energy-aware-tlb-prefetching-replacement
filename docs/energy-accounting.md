# Energy accounting and prefetch accuracy

`energy/energy_fusion.py` combines ChampSim activity counters, per-access CACTI
values, and an explicit DRAM-read estimate. All energy results are estimates.
Missing required CACTI values leave totals and EDP blank. L1D, L2C, and LLC rows
are optional; if one is unavailable, its page-walk cache energy is excluded and
the result is labeled accordingly.

## Counters and energy

For each active on-chip structure, the script calculates

`energy_nJ = reads * read_nJ + writes * write_nJ + leakage_mW * runtime_s * 1,000,000`

where `runtime_s = cycles / (CPU_GHz * 1e9)`. ChampSim's STLB `LOAD MISS` counter
is reported as the demand-miss count; the `TOTAL ACCESS` counter is used for STLB
access energy because it includes prefetch accesses. TLB accesses are priced as
read-like accesses because the logs do not separate lookup and fill writes.

Page-walk cache activity uses the `TRANSLATION ACCESS` counters for L1D, L2C, and
LLC. Each LLC `TRANSLATION MISS` is counted as one DRAM read and multiplied by
`--dram-nj-per-access` (default 56 nJ). This is a modeling assumption, not an
independently measured DRAM energy value. L1D, L2C, and LLC use dynamic energy
only; leakage is excluded. ATP_FPQ dynamic energy and leakage include all three
fake queues, although the per-queue CACTI row models one queue.

The script maps named counters as follows:

| Structure | Read/use count | Write count |
|---|---|---|
| DTLB, ITLB | `TOTAL ACCESS` | 0; writes are not separately exposed |
| STLB | `TOTAL ACCESS` | 0; writes/fills are not separately exposed |
| PSC | `psc_lookups` | 0; lower bound is zero, with optional upper-bound proxy |
| SBFP prefetch queue (PQ) | `pq_lookups` | `pq_inserts` |
| SBFP sampler | `sampler_lookups` | `sampler_inserts` |
| SBFP FDT | tracked updates plus 14 accesses per decay | same as reads |
| ATP fake queues | three lookups per `trigger_misses` (ATP probes its queues only on STLB misses and hits to prefetched entries, see `prototypes/atp/prefetcher/atp/atp.cc`) | 0; insertions are not logged |
| L1D, L2C, LLC | `TRANSLATION ACCESS` | 0; counted as reads |

For the FDT, the log does not count read-only threshold probes, so the estimate
includes only tracked read-modify-write updates and decay shifts. For ATP fake
queues, writes are omitted because the current log has no insertion counter. These
omissions are marked in the result table's `energy_notes` field. The legacy
`energy_nj`, `energy_vs_lru`, and `edp` fields are the PSC=0 lower-bound scenario.
`energy_nj_upper`, `energy_vs_lru_upper`, and `edp_upper` report the upper-bound
scenario when the `PSC_UPPER_PROXY` row or fallback PQ row is populated. A scenario is blank
if another required structure or the DRAM estimate is missing; `known_energy_nj`
remains a partial sum. Missing L1D/L2C/LLC rows do not block totals, but the
excluded cache energy is listed in `energy_coverage` and `energy_notes`.

The CACTI CSV may include a `note` or `notes` column. Its entry for each active
structure is copied into `energy_notes`, including proxy descriptions and notes
for unavailable configurations, so the reported estimates retain their modeling
assumptions.

The PSC prototype reports one aggregate lookup counter. The tested logs report
four PSC lookups per page walk, but CACTI could not model the four PSC geometries
(2, 4, 8, and 32 entries); those runs exited with code 139. Therefore
`psc_energy_nj` is a lower bound of zero. For the upper scenario, the
`PSC_UPPER_PROXY` row should copy the existing 64-entry fully associative PQ
proxy (64 B block, 90 nm). The script uses that explicit row when present, and
falls back to the PQ row itself until the alias is added. The proxy is larger
than every PSC geometry. The script prices aggregate PSC lookups against that
per-access proxy and counts leakage for four PSC structures. The row note is
carried into `energy_notes`; this is a labeled upper-bound estimate, not a
direct measurement of the failed PSCs.

## Prefetch accuracy

- **ATP:** `hits_on_prefetched / issued`. This is reported separately only when
  SBFP direct-fill activity cannot overlap with the same hit counter.
- **SBFP with PQ:** `pq_hits / pq_inserts`. PQ mode is selected from the config
  name, not inferred from whether `pq_inserts` appears in the output.
- **SBFP direct fill:** `free_useful / free_issued`.
- **Combined accuracy:** useful prefetch hits divided by total issued entries.
  In direct-fill mode, `hits_on_prefetched` already includes ATP and SBFP useful
  hits, so it is not added to `free_useful` a second time. In PQ mode, PQ hits
  bypass the STLB prefetch-hit counter and are added separately.

Accuracy is blank when no corresponding prefetches were issued or when the needed
counters are absent. A blank means unavailable, not zero accuracy.
