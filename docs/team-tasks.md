# Team tasks to finish the implementation (due Wed 2026-11-18)

Goal: the full pipeline `traces → ChampSim (6 configs) → counters → energy → table → plots` runs end to end, so the
Nov 21 presentation and the final report can use real numbers. Omar and Claude run all simulations locally; the tasks
below need no simulation, only the repo, CACTI and the output files described here.

**Everyone, first:** `git pull`, then `scripts/setup.sh` (once) and `scripts/build_all.sh`. To work without waiting for
the real traces, `scripts/run_all.sh` needs traces in `traces/`; a synthetic test trace is made with
`python3 /path/to/gen_synthetic_trace.py 2500000 traces/syn.champsimtrace && xz traces/syn.champsimtrace`
(script is in the project folder `champsim-prototype/`). Raw outputs go to `results/raw/<config>__<trace>.txt`.

Each task ends with a short **Difficulties and learnings** section in your PR description (what blocked you, what you
decided and why). Say plainly what is an assumption.

## Ayushi: CACTI rows for the structures we simulate (`energy/cacti_per_access.csv`)
Start from your merged `configs/stlb_128x8.cfg` and `configs/cacti_stlb_notes.md`.
1. Sizes to model (from ChampSim `champsim_config.json` and the SBFP paper, Sec. IV-B): DTLB and ITLB 16 sets x 4 ways;
   STLB 128 x 12 (see Sanket's task for the non-power-of-two issue); PSC levels (PSCL5 1x2, PSCL4 1x4, PSCL3 2x4, PSCL2 4x8);
   SBFP FDT = 14 counters x 10 bit; Sampler = 64 entries x (36-bit page + 4-bit distance), fully associative;
   ATP fake prefetch queues = 3 x 16 entries (page number only).
2. One CACTI config per structure under `configs/`, same technology node as the STLB runs. Record the node, entry width and
   anything CACTI forced you to approximate (minimum block size, associativity).
3. Fill `read_nj`, `write_nj`, `leakage_mw` in `energy/cacti_per_access.csv` and cite the config file in the `source` column.
Done when: no `TBD` remains in the CSV.

## Sanket: sensitivity of the STLB model
1. The real STLB is 1536 entries (128 x 12), which CACTI cannot model directly. Run the 128x8 and 128x16 configs plus
   a 1024- and a 2048-entry variant, and compare read energy, write energy and leakage.
2. Choose and justify one rule (for example interpolate between the two neighbours, or scale by entries) and state its error range.
3. Check the 90 nm assumption (it came from the CACTI sample config): repeat the STLB with a more recent node and report how much
   the ratios between configs change (ratios matter more than absolute values for our research question).
Done when: a half-page table in `docs/cacti-sensitivity.md` and a recommended STLB value for the CSV.

## Niyati: energy fusion (`energy/energy_fusion.py`)
Run it first on `results/raw/*.txt` produced from a synthetic trace to see the table.
1. **Demand-only misses.** `STLB TOTAL` includes prefetch accesses, so `stlb_mpki` is inflated for prefetching configs.
   Subtract the `STLB PREFETCH` line (or use LOAD + TRANSLATION lines) to report demand MPKI; keep the total for energy.
2. **New counters** printed by the simulator: `[PROTO-PTW] ... free_prefetches=N` (SBFP fills that cost no walk),
   `[SBFP] free_issued, sampler_inserts, sampler_lookups, fdt_updates`, `[ATP] operate_calls`. Parse them into columns.
3. **Energy per structure:** STLB reads = lookups, STLB writes = fills (demand fills + prefetch fills + free prefetches);
   FDT updates and Sampler lookups/inserts use the `SBFP_FDT` row; ATP uses the `PQ` row per operate call.
4. **DRAM walk energy.** Pick one cited per-access DRAM energy and multiply by page-walk memory accesses; state it is an estimate.
5. Fill `energy_nj`, `energy_vs_lru` and `edp` (EDP = energy x runtime, runtime = cycles / 4 GHz).
Done when: `python3 scripts/plot_results.py` draws `pareto.png` from your table.

## Johnny: extra workloads and trace checks
1. Once the 6 configs exist (`scripts/build_all.sh`), run all of them on the three GAP traces from your screening
   (`bc.kron-2608B`, `bc.road-131B`, `bc.twitter-1658B`) with `TRACES="..." scripts/run_all.sh 10 20`.
2. Report in `README.md`'s GAP section: per trace and config, speedup and demand STLB MPKI (reuse `energy_fusion.py` output).
3. Confirm the final trace list for the third workload (`623.xalancbmk_s-700B` vs a GAP trace) and why.
Done when: `results/raw/` files for the GAP runs and a short table, shared with Omar.

## Omar and Claude
Merge the SBFP PR, run the 6 configs x 3 traces (about 2.5 h at 10M + 20M), produce the first table and plots, start the
slide and paper skeletons, then reruns with longer windows if time allows.
