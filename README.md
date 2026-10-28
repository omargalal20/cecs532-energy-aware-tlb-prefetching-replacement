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
| Traces | Accessible memory-intensive traces; final list to be fixed |
| Warmup / simulation | Smoke tests: 10M / 20M instructions. Reported runs: to be set once runtime is measured |

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

This clones ChampSim into `third_party/`, builds its dependencies with vcpkg (first run takes several minutes) and produces `third_party/ChampSim/bin/champsim_baseline_lru`.

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
| Repository, build and baseline run | In progress |
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
