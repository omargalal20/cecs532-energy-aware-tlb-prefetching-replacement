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
| `atp_sbfp` | ATP + SBFP | LRU | Required |
| `atp_sbfp_itp` | ATP + SBFP | iTP | Required, if integration is feasible |
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
- GAP (graph) and XSBench (scientific proxy) traces may stress the TLB more, but their availability in ChampSim format is not verified.

**Reproducing a row.** Download the trace from the DPC-3 server into `traces/`, then run `scripts/run_baseline.sh traces/<trace>.champsimtrace.xz 10 20`. The raw output goes to `results/raw/baseline_lru__<trace>.txt`. The MPKI, latency and instruction share are computed from the `STLB`, `DTLB` and `ITLB` lines of that file.

## Repository Structure

```
.
├── configs/baseline_lru.json     ChampSim configuration of the LRU baseline
├── scripts/
│   ├── setup.sh                  Clone pinned ChampSim, install libraries, build
│   └── run_baseline.sh           Run one trace and save raw output
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

Place `*.champsimtrace.xz` files in `traces/`. The DPC-3 SPEC traces are available from <https://dpc3.compas.cs.stonybrook.edu/champsim-traces/speccpu/>. Traces are large and are not stored in git.

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

### 6. Compute energy, speedup and EDP

```bash
python3 energy/energy_fusion.py results/raw/*.txt --out results/results_table.csv
```

Energy columns stay empty until `energy/cacti_per_access.csv` contains CACTI values.

## Results

Populated as runs complete. Each trace is tagged with a workload type so results can be read per scenario (objective 3).

| Trace | Workload type | Config | IPC | Speedup vs LRU | STLB MPKI | Page walks | Energy vs LRU | EDP |
|---|---|---|---|---|---|---|---|---|
| — | — | `baseline_lru` | — | 1.00 | — | — | 1.00 | — |
| — | — | `itp` | — | — | — | — | — | — |
| — | — | `atp_sbfp` | — | — | — | — | — | — |
| — | — | `atp_sbfp_itp` | — | — | — | — | — | — |

## Project Status

| Milestone | Status |
|---|---|
| Proposal | Complete |
| Repository, build, baseline run and trace screening | Complete (14 traces screened, 3 selected) |
| ATP/SBFP and iTP integration, counters | Not started |
| CACTI models of TLB, PQ and SBFP structures | In progress |
| Full experiment set and energy fusion | Not started |
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
