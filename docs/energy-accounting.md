# Energy accounting and prefetch accuracy

`energy/energy_fusion.py` combines ChampSim activity counters, per-access CACTI
values, and an explicit DRAM-read estimate. All energy results are estimates.

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
| ATP fake queues | three lookups per `operate_calls` | 0; insertions are not logged |
| L1D, L2C, LLC | `TRANSLATION ACCESS` | 0; counted as reads |

For the FDT, the log does not count read-only threshold probes, so the estimate
includes only tracked read-modify-write updates and decay shifts. For ATP fake
queues, writes are omitted because the current log has no insertion counter. These
omissions are marked in the result table's `energy_notes` field. The legacy
`energy_nj`, `energy_vs_lru`, and `edp` fields are the PSC=0 lower-bound scenario.
`energy_nj_upper`, `energy_vs_lru_upper`, and `edp_upper` report the upper-bound
scenario when the `PSC_UPPER_PROXY` CACTI row is populated. A scenario is blank
if another active structure or the DRAM estimate is missing; `known_energy_nj`
remains a partial sum.

The CACTI CSV may include a `note` or `notes` column. Its entry for each active
structure is copied into `energy_notes`, including proxy descriptions and notes
for unavailable configurations, so the reported estimates retain their modeling
assumptions.

The PSC prototype reports one aggregate lookup counter. The tested logs report
four PSC lookups per page walk, but CACTI could not model the four geometries
directly. Therefore `psc_energy_nj` is a lower bound of zero. If the team supplies
a supported, documented proxy in a `PSC_UPPER_PROXY` row, the script prices all
aggregate PSC lookups against that per-access proxy and counts leakage for four
PSC caches. The proxy note is copied to `energy_notes`; it must be described as
an upper-bound estimate, not a direct measurement of the failed geometries.

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
