#!/usr/bin/env python3
"""Fuse ChampSim counters with CACTI per-access energy into energy, speedup and EDP.

Usage:
    python3 energy/energy_fusion.py results/raw/*.txt --out results/results_table.csv

Raw files are named <config>__<trace>.txt (see scripts/run_baseline.sh). The config
named "baseline_lru" is the reference for speedup and energy ratios.

Energy model (nJ):
    E_dynamic = sum_s (reads_s * read_nj_s + writes_s * write_nj_s)
    E_leakage = sum_s leakage_mw_s * runtime_s          (runtime = cycles / frequency)
    E_total   = E_dynamic + E_leakage
    EDP       = E_total * runtime_s

Status: stub. Only STLB counters are wired in; extend COUNTER_MAP as new structures
(PQ, SBFP free-distance table, page-structure caches) expose counters.
"""
import argparse
import csv
import re
import sys
from pathlib import Path

CPU_GHZ = 4.0  # matches ooo_cpu frequency (4000 MHz) in ChampSim's default config
CACTI_CSV = Path(__file__).with_name("cacti_per_access.csv")
BASELINE = "baseline_lru"

COLUMNS = ["trace", "config", "instructions", "cycles", "ipc", "speedup_vs_lru",
           "stlb_accesses", "stlb_misses", "stlb_mpki", "page_walks",
           "energy_nj", "energy_vs_lru", "edp"]

IPC_RE = re.compile(r"cumulative IPC: (\S+) instructions: (\d+) cycles: (\d+)")
STLB_RE = re.compile(r"cpu\d+->\S*STLB TOTAL\s+ACCESS:\s*(\d+)\s+HIT:\s*(\d+)\s+MISS:\s*(\d+)")


def parse_run(path: Path) -> dict:
    text = path.read_text()
    ipc = IPC_RE.search(text)
    stlb = STLB_RE.search(text)
    if not (ipc and stlb):
        sys.exit(f"{path}: could not find IPC / STLB lines; check ChampSim output format")
    instr, cycles = int(ipc.group(2)), int(ipc.group(3))
    accesses, misses = int(stlb.group(1)), int(stlb.group(3))
    config, trace = path.stem.split("__", 1)
    return {"trace": trace, "config": config, "instructions": instr, "cycles": cycles,
            "ipc": instr / cycles, "stlb_accesses": accesses, "stlb_misses": misses,
            "stlb_mpki": 1000 * misses / instr,
            "page_walks": misses}  # TODO: replace with the PTW counter once confirmed


def load_cacti() -> dict:
    with CACTI_CSV.open() as f:
        return {r["structure"]: r for r in csv.DictReader(f)}


def energy_nj(run: dict, cacti: dict) -> float | None:
    row = cacti.get("STLB")
    if row is None or "TBD" in (row["read_nj"], row["write_nj"], row["leakage_mw"]):
        return None  # CACTI numbers not filled in yet
    runtime_s = run["cycles"] / (CPU_GHZ * 1e9)
    dynamic = run["stlb_accesses"] * float(row["read_nj"])  # TODO: split reads/writes, add PQ/SBFP/PSC
    leakage = float(row["leakage_mw"]) * 1e-3 * runtime_s * 1e9  # mW -> W -> J -> nJ
    return dynamic + leakage


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", type=Path, help="raw ChampSim output files")
    ap.add_argument("--out", type=Path, default=Path("results/results_table.csv"))
    args = ap.parse_args()

    cacti = load_cacti()
    runs = [parse_run(p) for p in args.runs]
    base = {r["trace"]: r for r in runs if r["config"] == BASELINE}

    for r in runs:
        e = energy_nj(r, cacti)
        runtime_s = r["cycles"] / (CPU_GHZ * 1e9)
        b = base.get(r["trace"])
        r["energy_nj"] = e
        r["edp"] = e * runtime_s if e is not None else None
        r["speedup_vs_lru"] = r["ipc"] / b["ipc"] if b else None
        be = energy_nj(b, cacti) if b else None
        r["energy_vs_lru"] = e / be if (e is not None and be) else None

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in sorted(runs, key=lambda r: (r["trace"], r["config"])):
            w.writerow({c: ("" if r[c] is None else r[c]) for c in COLUMNS})
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
