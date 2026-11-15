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
`--dram-nj-per-access`. This is a modeling assumption, not an independently
measured DRAM energy value.

The script maps named counters as follows:

| Structure | Read/use count | Write count |
|---|---|---|
| DTLB, ITLB | `TOTAL ACCESS` | 0; writes are not separately exposed |
| STLB | `TOTAL ACCESS` | 0; writes/fills are not separately exposed |
| PSC | `psc_lookups` | 0 |
| SBFP prefetch queue (PQ) | `pq_lookups` | `pq_inserts` |
| SBFP sampler | `sampler_lookups` | `sampler_inserts` |
| SBFP FDT | tracked updates plus 14 accesses per decay | same as reads |
| ATP fake queues | three lookups per `operate_calls` | 0; insertions are not logged |
| L1D, L2C, LLC | `TRANSLATION ACCESS` | 0; counted as reads |

For the FDT, the log does not count read-only threshold probes, so the estimate
includes only tracked read-modify-write updates and decay shifts. For ATP fake
queues, writes are omitted because the current log has no insertion counter. These
omissions are marked in the result table's `energy_notes` field. Total energy,
energy/baseline, and EDP are blank when any active CACTI row or the DRAM estimate
is missing; `known_energy_nj` remains a partial sum.

## Prefetch accuracy

- **ATP:** `hits_on_prefetched / issued`. This is reported separately only when
  SBFP direct-fill activity cannot overlap with the same hit counter.
- **SBFP with PQ:** `pq_hits / pq_inserts`.
- **SBFP direct fill:** `free_useful / free_issued`.
- **Combined accuracy:** useful prefetch hits divided by total issued entries.
  In direct-fill mode, `hits_on_prefetched` already includes ATP and SBFP useful
  hits, so it is not added to `free_useful` a second time. In PQ mode, PQ hits
  bypass the STLB prefetch-hit counter and are added separately.

Accuracy is blank when no corresponding prefetches were issued or when the needed
counters are absent. A blank means unavailable, not zero accuracy.
