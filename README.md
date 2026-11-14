# Energy-Aware Evaluation of TLB Prefetching and Replacement

**CECS 532 — Memory Design Implementation | CSULB Fall 2026 | Group 6**

This repository contains the simulation infrastructure and results for a trace-driven study of TLB prefetching (ATP with SBFP) and second-level TLB (STLB) replacement (iTP). ChampSim has no energy model, so we add access-level energy accounting based on CACTI and compare configurations by speedup and estimated translation energy.

---

## Research Question

> Which TLB prefetching and STLB replacement policies provide the best trade-off between execution speed and estimated translation energy?

**Objectives**
1. Measure speedup and estimated translation energy for each configuration.
2. Identify Pareto-optimal configurations.
3. Characterize which workload types (for example irregular versus regular access patterns) favor which policy, to inform TLB design choices. This follows from the proposal's expected workload dependence.

We answer it by simulating a baseline (LRU replacement, no TLB prefetching), ATP/SBFP, iTP and, if integration is feasible, their combination in ChampSim. Speedup and estimated energy are compared to identify Pareto-optimal configurations.

**Expected outcome (hypotheses, not results).** The trade-off should vary by workload: aggressive prefetching should raise speed but also energy on irregular workloads, and free prefetching (SBFP) should be among the most efficient. The experiments may instead show one policy to be best on both measures, which is also a useful result.

## Background

Every memory access needs a virtual-to-physical translation. Translations are cached in the TLB hierarchy (DTLB/ITLB, then a shared STLB). An STLB miss triggers a page-table walk, which issues dependent memory references and can stall the core for hundreds of cycles. Two lines of work reduce this cost:

- **Agile TLB Prefetching (ATP) with Sampling-Based Free TLB Prefetching (SBFP).** ATP selects among several TLB prefetchers at run time. SBFP exploits the fact that a page-table walk fetches a cache line holding neighbouring PTEs and keeps the useful ones as "free" prefetches [1].
- **iTP (instruction-aware STLB replacement).** iTP biases STLB replacement toward instruction translations, which are more costly to miss, and is designed to cooperate with cache replacement [2].

Both can reduce page walks, but speculative prefetches consume energy and affect which translations remain in the STLB. Published TLB work mostly reports speedup, and energy is evaluated for only some designs; the ISCA 2021 paper estimates energy with CACTI for its prefetcher [1]. This project compares the policies in one common setup, with speed and estimated energy side by side. Our implementations are simplified versions of the published designs, and every simplification is documented alongside the code.

## Evaluated Configurations

| ID | STLB prefetching | STLB replacement | Status |
|---|---|---|---|
| `baseline_lru` | none | LRU | Required |
| `itp` | none | iTP | Required |
| `atp_sbfp_pq` | ATP + SBFP (free PTEs go to a separate 64-entry prefetch queue, as in the paper) | LRU | Required |
| `atp_sbfp_pq_itp` | ATP + SBFP with prefetch queue | iTP | Required, if integration is feasible |
| `atp` , `atp_itp` | ATP only (no SBFP) | LRU / iTP | Diagnostic: isolates SBFP's contribution |
| `atp_sbfp` , `atp_sbfp_itp` | ATP + SBFP, free PTEs fill the STLB directly (no prefetch queue) | LRU / iTP | Ablation: shows the cost of STLB pollution |
| STLB-capacity and page-size sensitivity, 4-core runs | — | — | Stretch |

## Methodology

```
 trace ──► ChampSim (modified) ──► counters ──┐
                                              ├──► energy_fusion.py ──► results_table.csv
 CACTI ──► per-access energy, leakage ────────┘                         (speedup, energy, EDP)
```

**Simulator.** [ChampSim](https://github.com/ChampSim/ChampSim), pinned to commit `410cee6` (see `scripts/setup.sh`). It models a TLB hierarchy and a hardware page-table walker with page-structure caches. It ships no TLB-specific prefetcher and no iTP, so these are implemented as ChampSim modules in this project.

**Energy model.** Dynamic energy is access counts times per-access energy, plus leakage over the simulated runtime:

```
E_dynamic = Σ_s ( reads_s · e_read,s + writes_s · e_write,s )     s ∈ {DTLB, ITLB, STLB, PQ, SBFP tables, PSC}
E_leakage = Σ_s P_leak,s · t_run                                   t_run = cycles / frequency
E_total   = E_dynamic + E_leakage + E_pagewalk_memory
EDP       = E_total · t_run
```

Per-access energies and leakage come from [CACTI](https://github.com/HewlettPackard/cacti) models of each structure (`energy/cacti_per_access.csv`). Page-walk accesses to DRAM use a separate energy estimate. CACTI requires power-of-two sizes, so the 1536-entry STLB (128 sets × 12 ways) is modeled at nearby power-of-two sizes. This approximation is stated wherever results are reported.

**Metrics.** IPC and speedup over `baseline_lru`; STLB misses (MPKI); page-walk memory references; prefetch accuracy; estimated translation energy; EDP as a derived comparison.

## Experimental Setup

| Item | Value |
|---|---|
| Simulator | ChampSim `410cee6`, single core (4-core as stretch) |
| Core / TLBs | ChampSim defaults: 4 GHz core, STLB 128 sets × 12 ways, 4 KB pages |
| STLB prefetch queue | `pq_size = 8` (default is 0, which disables STLB prefetching) |
| Traces | `429.mcf-51B`, `620.omnetpp_s-874B`, `623.xalancbmk_s-700B`, selected by STLB MPKI (see Trace selection below) |
| Warmup / simulation | Smoke tests: 10M / 20M instructions. Reported runs: to be set once runtime is measured |

### Trace selection

**Why screen traces.** The DPC-3 SPEC traces were assembled for data-cache prefetching, not for TLB behaviour, so we do not assume they stress the STLB. Each candidate is run once with `baseline_lru` (10M warmup + 20M simulated instructions) and ranked by its STLB misses per thousand instructions (MPKI). Traces with high MPKI are kept, because a TLB policy cannot show a difference on a trace that barely misses.

**Result.** 14 traces were screened (the heaviest published SimPoint slice of 12 benchmarks, plus two more mcf slices). Eight of the 14 have an STLB MPKI below 1.

| Trace | SimPoint weight | STLB MPKI | STLB miss latency (cycles) | Instruction share of STLB accesses | Decision |
|---|---|---|---|---|---|
| `429.mcf-51B` | 0.323 | 11.23 | 110.4 | 0.0% | **Selected** |
| `471.omnetpp-188B` | 0.945 | 4.30 | 65.8 | 2.1% | Backup |
| `620.omnetpp_s-874B` | 0.828 | 4.26 | 93.2 | 7.7% | **Selected** |
| `429.mcf-192B` | 0.185 | 2.56 | 144.5 | 0.0% | Backup |
| `429.mcf-22B` | 0.114 | 2.42 | 261.8 | 0.0% | Backup |
| `623.xalancbmk_s-700B` | 0.413 | 1.86 | 23.6 | 0.7% | **Selected** |
| `450.soplex-247B` | 0.487 | 0.94 | 123.9 | 0.0% | Dropped (MPKI < 1) |
| `619.lbm_s-4268B` | 0.418 | 0.73 | 212.5 | 0.0% | Dropped |
| `605.mcf_s-665B` | 0.441 | 0.27 | 146.2 | 0.0% | Dropped |
| `602.gcc_s-734B` | 0.641 | 0.20 | 274.5 | 0.0% | Dropped |
| `483.xalancbmk-716B` | 0.375 | 0.18 | 305.1 | 0.0% | Dropped |
| `649.fotonik3d_s-1176B` | 0.497 | 0.14 | 242.8 | 0.0% | Dropped |
| `473.astar-153B` | 0.611 | 0.07 | 39.8 | 0.0% | Dropped |
| `654.roms_s-842B` | 0.431 | 0.00 | 250.8 | 0.0% | Dropped |

**How to read the table.**
- *STLB MPKI* is STLB misses divided by simulated instructions, times 1000. Miss rate alone is misleading: `429.mcf-22B` misses on 63% of its STLB accesses but has far fewer misses per instruction than `429.mcf-51B`.
- *Instruction share* is the fraction of STLB accesses that come from instruction fetches, computed as (ITLB misses − ITLB merged misses) / STLB accesses. It matters for iTP, which treats instruction translations specially.
- *SimPoint weight* is how much of the full program the slice represents. The number in a trace name is its SimPoint slice index, taken from `weights-and-simpoints-speccpu.tar.gz` on the DPC-3 trace server; the site does not define the "B" suffix.
- Each value comes from a single 20M-instruction measurement window per trace.

**Selected set and why.**
- `429.mcf-51B` has by far the highest STLB pressure, which is what ATP and SBFP act on.
- `620.omnetpp_s-874B` is the second program with high MPKI and the only selected trace with a meaningful instruction share (7.7%).
- `623.xalancbmk_s-700B` has moderate MPKI but cheap walks (23.6 cycles per miss against 93 to 110 for the other two), which gives a contrasting regime. Choosing it for that contrast is a design decision, not a measured result.

**Limitations.**
- None of the 14 traces has substantial instruction pressure on the STLB (maximum 7.7%), and the three mcf traces have none. iTP can therefore only be tested meaningfully on `620.omnetpp_s-874B` (weakly on `471.omnetpp-188B`), so iTP results should be read with this in mind.
- We have not investigated why the traces differ in STLB behaviour; the table reports measurements only.
- GAP (graph) was successfully screened using ChampSim; they show substantial STLB activity but 0% instruction share.
- XSBench (scientific proxy) traces may stress the TLB more, but their availability in ChampSim format is not verified.

**Reproducing a row.** Download the trace from the DPC-3 server into `traces/` (sources and the screening steps for new traces are in [docs/trace-sources.md](docs/trace-sources.md)), then run `scripts/run_baseline.sh traces/<trace>.champsimtrace.xz 10 20`. The raw output goes to `results/raw/baseline_lru__<trace>.txt`. The MPKI, latency and instruction share are computed from the `STLB`, `DTLB` and `ITLB` lines of that file.

### GAP trace screening

In addition to the DPC-3 SPEC traces, we obtained three GAP graph-processing traces and evaluated them using ChampSim's existing baseline configuration.

**Experimental setup**

- Warmup: 10 million instructions
- Simulation: 20 million instructions
- Configuration: Existing ChampSim baseline
- Workload: GAP graph-processing traces
- Purpose: Evaluate STLB pressure and identify additional workloads for TLB prefetching and replacement experiments.

**Baseline results**

| Metric | bc.kron-2608B | bc.road-131B | bc.twitter-1658B |
|---|---:|---:|---:|
| IPC | 0.2279 | 0.1215 | 0.2072 |
| Instructions | 20,000,002 | 20,000,000 | 20,000,003 |
| Cycles | 87,763,757 | 164,555,250 | 96,513,323 |
| STLB accesses | 369,860 | 308,901 | 382,395 |
| STLB hits | 6,989 | 136,673 | 8,364 |
| STLB misses | 362,871 | 172,228 | 374,031 |
| STLB MPKI | 18.14 | 8.61 | 18.70 |
| STLB average miss latency (cycles) | 232.9 | 74.94 | 191.7 |
| Runtime | 4m 26s | 9m 49s | 5m 8s |

**Additional observations**

- All three traces recorded zero ITLB misses and zero ITLB merged misses.
- Consequently, all three have 0% instruction share of STLB accesses, using the project's instruction-share formula.
- The traces exhibit substantial STLB miss activity, particularly Kron and Twitter.
- Road has fewer STLB misses and a shorter average STLB miss latency than the other two traces.

**Conclusion**

The GAP traces are successfully processed by ChampSim and provide additional workloads with substantial STLB activity. They may be useful for evaluating data-side TLB prefetching and translation behavior. However, their zero instruction share makes them less suitable for evaluating the instruction-aware benefits of iTP.

These traces supplement the original DPC-3 screening results rather than replacing the previously selected SPEC traces. Further experiments are needed to evaluate their behavior under ATP/SBFP and iTP configurations.

## Repository Structure

```
.
├── configs/*.json                ChampSim configuration per policy (baseline_lru, itp, atp, atp_sbfp, ...), CACTI .cfg files
├── scripts/
│   ├── setup.sh                  Clone pinned ChampSim, install libraries, build
│   ├── fetch_traces.sh           Download the selected traces into traces/
│   ├── build_all.sh              Apply our patches and modules, build one binary per config
│   ├── run_all.sh                Run configs x traces into results/raw/
│   ├── plot_results.py           Plots from results_table.csv
│   └── run_baseline.sh           Run one trace and save raw output
├── docs/trace-sources.md         Trace sources, what we verified, how to screen a new trace
├── prototypes/                   ChampSim patches and modules: ptw-counters, itp (+instruction flag), atp, sbfp
├── energy/
│   ├── energy_fusion.py          Counters × CACTI energy → energy, speedup, EDP
│   └── cacti_per_access.csv      Per-access energy and leakage per structure
├── docker/Dockerfile             Optional reproducible toolchain
└── third_party/ , traces/ , results/raw/   Generated locally, not tracked by git
```

## Getting Started

### 1. Prerequisites

A C++17 toolchain, CMake, `git`, `curl`, `zip`, `unzip`, `tar`, `pkg-config` and Python 3.10+.

| Platform | Install |
|---|---|
| **Windows** | Install WSL 2 with Ubuntu 24.04 (`wsl --install -d Ubuntu-24.04`), then work inside the Linux filesystem (`~/`), not under `/mnt/c`, which is much slower. Follow the Linux line below. |
| **Ubuntu / Debian** | `sudo apt update && sudo apt install -y build-essential cmake ninja-build git curl zip unzip tar pkg-config python3` |
| **macOS** | `xcode-select --install && brew install cmake ninja git pkg-config python` |
| **Docker (any OS)** | `docker build -t tlb-sim -f docker/Dockerfile .` then `docker run --rm -it -v "$PWD":/work -w /work tlb-sim` |

### 2. Build the simulator

```bash
git clone https://github.com/omargalal20/cecs532-energy-aware-tlb-prefetching-replacement.git
cd cecs532-energy-aware-tlb-prefetching-replacement
scripts/setup.sh
```

This clones ChampSim and CACTI into `third_party/` at pinned commits, builds ChampSim's dependencies with vcpkg (first run takes several minutes) and produces `third_party/ChampSim/bin/champsim_baseline_lru` and `third_party/cacti/cacti`. Check CACTI with `cd third_party/cacti && ./cacti -infile cache.cfg`.

### 3. Obtain a trace

Run `scripts/fetch_traces.sh` to download the three selected traces into `traces/` (about 2.2 GB; add `--backups` for three more). Traces are large and are not stored in git. Other trace sources are described in [docs/trace-sources.md](docs/trace-sources.md).

### 4. Run the baseline

```bash
scripts/run_baseline.sh traces/<trace>.champsimtrace.xz 10 20   # warmup 10M, simulate 20M instructions
```

Raw output is saved to `results/raw/baseline_lru__<trace>.txt`.

### 5. Read the counters

| Output line | Meaning |
|---|---|
| `cumulative IPC: … instructions: … cycles: …` | Performance of the core |
| `cpu0->cpu0_STLB TOTAL ACCESS / HIT / MISS` | STLB demand behaviour; MISS drives page walks |
| `cpu0->cpu0_STLB PREFETCH REQUESTED / ISSUED / USEFUL / USELESS` | Prefetch accuracy (zero for the baseline) |
| `cpu0->cpu0_PTW …` | Page-table-walker activity |

### 6. Run all configurations

```bash
scripts/build_all.sh                    # apply patches, build one binary per configuration
scripts/run_all.sh 10 20                # all 8 configurations x 3 traces, 10M warmup + 20M simulated
JOBS=12 scripts/run_all.sh 20 100 baseline_lru itp atp_sbfp_pq atp_sbfp_pq_itp   # required four, longer window
TRACES="<trace> <trace>" scripts/run_all.sh 10 20 baseline_lru itp   # other traces or a subset of configurations
```

`run_all.sh` takes `[warmup_M] [sim_M] [config ...]`, runs `JOBS` simulations in parallel (default 2, each about 190 MB of memory) and writes `results/raw/<config>__<trace>.txt`. Finished files are skipped, so an interrupted run can be restarted. Do not rename `results/raw/` while it runs.

### 7. Compute energy, speedup and EDP

```bash
python3 energy/energy_fusion.py results/raw/*.txt --out results/results_table.csv
python3 scripts/plot_results.py
```

Energy columns stay empty until `energy/cacti_per_access.csv` contains CACTI values.

## Results

Measured on single-core ChampSim, 20M warmup + 100M simulated instructions, for the four required configurations. Raw outputs: `results/raw_20_100/`. Speedup is cycles of `baseline_lru` divided by cycles of the configuration. Page walks are the walks counted by the page-table walker (for the baseline they equal the STLB misses; with the prefetch queue, STLB misses served from the queue do not start a walk, so walks can be lower than STLB misses). STLB MPKI is taken from the STLB miss counter, which still counts prefetch accesses until the fusion script uses demand-only counters. Energy and EDP are filled in once the CACTI values and the energy-fusion update are merged.

| Trace | Config | IPC | Speedup vs LRU | STLB MPKI | Page walks | Walks vs LRU | Energy vs LRU | EDP |
|---|---|---|---|---|---|---|---|---|
| `429.mcf-51B` | `baseline_lru` | 0.1460 | 1.0000 | 10.77 | 1,076,833 | — | TBD | TBD |
| | `itp` | 0.1448 | 0.9923 | 20.79 | 2,078,715 | +93% | TBD | TBD |
| | `atp_sbfp_pq` | 0.1461 | 1.0008 | 10.77 | 959,014 | −11% | TBD | TBD |
| | `atp_sbfp_pq_itp` | 0.1450 | 0.9937 | 19.81 | 1,817,148 | +69% | TBD | TBD |
| `620.omnetpp_s-874B` | `baseline_lru` | 0.4166 | 1.0000 | 4.29 | 429,352 | — | TBD | TBD |
| | `itp` | 0.4154 | 0.9972 | 5.14 | 513,990 | +20% | TBD | TBD |
| | `atp_sbfp_pq` | 0.4167 | 1.0003 | 4.29 | 392,281 | −9% | TBD | TBD |
| | `atp_sbfp_pq_itp` | 0.4158 | 0.9981 | 5.14 | 478,429 | +11% | TBD | TBD |
| `623.xalancbmk_s-700B` | `baseline_lru` | 0.9183 | 1.0000 | 1.71 | 171,437 | — | TBD | TBD |
| | `itp` | 0.8993 | 0.9793 | 3.78 | 378,434 | +121% | TBD | TBD |
| | `atp_sbfp_pq` | 0.9185 | 1.0002 | 1.71 | 163,586 | −5% | TBD | TBD |
| | `atp_sbfp_pq_itp` | 0.9004 | 0.9804 | 3.69 | 349,054 | +104% | TBD | TBD |

**What the measurements show so far (speed only).**
- iTP is slower than LRU on all three traces and increases page walks. Its data-translation insertion policy is a poor fit for traces with little instruction share (`429.mcf-51B` has none).
- ATP with SBFP and a separate prefetch queue is neutral on speed (+0.02% to +0.08%) and removes 5 to 11% of page walks.
- Combining the two is slightly better than iTP alone on every trace, and still slower than LRU.
- ATP's throttling counter keeps it disabled except together with iTP on `429.mcf-51B`, where it issues 15,199 prefetch walks.
- A shorter 10M warmup + 20M run gave the same ranking, except that `623.xalancbmk_s-700B` with iTP looked nearly neutral there (speedup 0.997) and is clearly worse at 100M (0.979). The two windows cover different parts of the trace (the 20M run measures instructions 10M to 30M, the 100M run 20M to 120M). Where they overlap (instructions 20M to 30M) iTP is about 1.0% slower in both runs, and it falls further behind later (1.5% to 3.1% slower per 10M-instruction slice). Walks more than double, yet speed drops only about 2%, because walks on this trace are cheap (about 21 cycles per STLB miss) and partly overlapped by the core. Instruction share of STLB accesses is only 1.6%, so iTP's instruction priority gains little. We read this as phase dependence; the instruction-share explanation is consistent with the counters but not tested separately.
- The `atp`, `atp_itp`, `atp_sbfp` and `atp_sbfp_itp` ablations were run at 10M + 20M only. Without the prefetch queue, free prefetches pollute the STLB (`623.xalancbmk_s-700B`: 0.989 speedup, +51% walks).

**Still to come:** energy and EDP per configuration, the Pareto comparison, and GAP workloads. Each trace will be tagged with a workload type for objective 3.

## Project Status

| Milestone | Status |
|---|---|
| Proposal | Complete |
| Repository, build, baseline run and trace screening | Complete (14 traces screened, 3 selected) |
| ATP/SBFP and iTP implementation, counters | Complete; all configurations run on the three selected traces (10M + 20M, and 20M + 100M for the four required configurations) |
| CACTI models of TLB, PQ and SBFP structures | In progress |
| Full experiment set and energy fusion | Speed results complete; energy columns waiting on CACTI values and the fusion-script update |
| Final report | Not started |

## Limitations

- ATP/SBFP and iTP are simplified re-implementations, not the authors' code.
- CACTI requires power-of-two array sizes; the STLB is approximated.
- Energy covers translation-related structures and page-walk memory references only, not whole-core energy.
- Results come from a limited trace set and single-core runs unless the stretch goals are reached.

## References

1. G. Vavouliotis et al., "Exploiting page table locality for agile TLB prefetching," in *Proc. 48th Annu. Int. Symp. Comput. Archit. (ISCA)*, 2021, pp. 85–98.
2. D. Chasapis, G. Vavouliotis, D. A. Jiménez, and M. Casas, "Instruction-aware cooperative TLB and cache replacement policies," in *Proc. 30th ACM Int. Conf. Archit. Support Program. Lang. Oper. Syst. (ASPLOS)*, 2025, pp. 619–636.
3. N. Gober et al., "The Championship Simulator: Architectural Simulation for Education and Competition," arXiv:2210.14324, 2022.
4. CACTI, Hewlett Packard Labs, <https://github.com/HewlettPackard/cacti>.

## Authors

Niyati Nikunj Kapadia, Johnny Van, Omar Elhanafy, Ayushi Mistry and Sanketkumar Rakeshbhai Patel — CECS 532, California State University, Long Beach.
