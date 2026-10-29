# Trace Sources

A ChampSim trace is a recording of a program's instructions and memory addresses. ChampSim replays the recording instead of running the program, so every configuration sees exactly the same workload.

```
benchmark program ──► SimPoint picks representative slices ──► <benchmark>-<slice>B.champsimtrace.xz ──► ChampSim
```

This page lists the trace sources we know of, what we verified about each, and how to screen a new one. The measured results for the sources we have run are in the *Trace selection* section of the [README](../README.md#trace-selection).

## DPC-3 SPEC traces (used in this study)

The Third Data Prefetching Championship (DPC-3) published SPEC CPU2006 (`4xx`) and SPEC CPU2017 (`6xx_s`) traces at <https://dpc3.compas.cs.stonybrook.edu/champsim-traces/speccpu/>. Each file is one SimPoint slice of a benchmark. The slice numbers and weights are in `weights-and-simpoints-speccpu.tar.gz` on the same page; the site does not define the "B" suffix in the file names.

Why we use it: it is public, already in ChampSim format, comes with SimPoint weights, and runs with the pinned ChampSim commit. We measured it directly: 14 traces screened, 3 selected. The traces were built for data prefetching, which is why most of them barely touch the STLB.

Download the selected traces with `scripts/fetch_traces.sh` (about 2.2 GB; `--backups` adds three more).

## Qualcomm server traces (identified, not used yet)

A Zenodo record, [Qualcomm Server ChampSim Traces](https://zenodo.org/records/14045186) (DOI 10.5281/zenodo.14045186, CC BY 4.0), by D. Chasapis (first author of reference [2] in the README), holds ChampSim traces from the CVP-1 and IPC-1 Qualcomm server workloads. It is 38.3 GB in two archives (`qualcomm_srv.tar`, 31.1 GB; `smt_qualcomm_srv.tar`, 7.2 GB) and links the repository `dchasap/itp_asplos25_AE`.

The record does not list the traces inside the archives or describe their TLB behaviour, so we have not checked their STLB MPKI or instruction share. The DPC-3 set has almost no instruction pressure on the STLB (at most 7.7%), so these are the first candidates to screen for iTP.

## GAP and XSBench traces (identified, not used yet)

A Zenodo record, [ChampSim Traces for GAP and XSBench](https://zenodo.org/records/20043527) (DOI 10.5281/zenodo.20043527, CC BY 4.0, published May 2026), by Jamet, Alvarez, Jiménez and Casas, holds traces of the GAP graph kernels (`bc`, `bfs`, `cc`, `pr`, `sssp`, `tc`) and four XSBench inputs (`xs_XL64`, `xs_XL100`, `xs_XXL64`, `xs_XXL100`), plus a `weights.tar.gz`. It is 62.3 GB in total; individual archives are 2.9 to 10.0 GB. The record asks users to cite "Characterizing the impact of last-level cache replacement policies on big-data workloads" (IISWC 2020).

It says the traces "can be used in the ChampSim simulator" but does not state the trace format, the tool that produced them or their length, and it says nothing about TLB behaviour. We have not checked that they load in our pinned ChampSim commit or measured their STLB MPKI. Because they are large and graph-like, they are a reasonable candidate for TLB pressure, but that is a hypothesis to test with the screening below.

## Screening a new source

For any new trace:

1. Download it into `traces/`. Keep large archives outside git.
2. Run a short check to confirm ChampSim accepts the format:
   `third_party/ChampSim/bin/champsim_baseline_lru --warmup-instructions 1000000 --simulation-instructions 2000000 traces/<trace>.champsimtrace.xz`
3. Run the screening run: `scripts/run_baseline.sh traces/<trace>.champsimtrace.xz 10 20`. The raw output is saved to `results/raw/baseline_lru__<trace>.txt`.
4. Compute STLB MPKI (STLB misses / 20M instructions × 1000) and the instruction share of STLB accesses, as defined in the README's Trace selection section.
5. Add a row to the table below and, if the trace looks useful, to the README table.

## Sources found by the team

| Source | Link | Tested by | Subset tested | Result |
|---|---|---|---|---|
| DPC-3 SPEC (Stony Brook) | <https://dpc3.compas.cs.stonybrook.edu/champsim-traces/speccpu/> | Omar | 14 traces | 3 selected (README) |
| Qualcomm server (Zenodo) | <https://zenodo.org/records/14045186> | | | |
| GAP and XSBench (Zenodo) | <https://zenodo.org/records/20043527> | | | |
