#!/usr/bin/env python3
"""Combine ChampSim counters with available CACTI per-access values.

This reports energy for the modeled components with sufficient inputs. It does not
call a partial sum total translation energy: DTLB, ITLB, prefetch structures, or
DRAM may be missing. The optional DRAM input is an explicit per-walk estimate,
not a measured DRAM-reference count.
"""
import argparse
import csv
import re
import sys
from pathlib import Path

DEFAULT_CPU_GHZ = 4.0
CACTI_CSV = Path(__file__).with_name("cacti_per_access.csv")
BASELINE = "baseline_lru"

COLUMNS = [
    "trace", "config", "instructions", "cycles", "ipc", "speedup_vs_lru",
    "stlb_accesses", "stlb_misses", "stlb_mpki", "page_walks", "page_walk_source",
    "ptw_prefetch_walks", "psc_lookups", "psc_hits",
    "stlb_energy_nj", "psc_energy_nj", "known_onchip_energy_nj",
    "dram_energy_nj", "known_components", "energy_coverage",
    # Preserve the existing result-table fields. They stay blank until the full
    # modeled structure set and DRAM accounting are implemented and populated.
    "energy_nj", "energy_vs_lru", "edp",
]

IPC_RE = re.compile(r"cumulative IPC:\s*(\S+)\s+instructions:\s*(\d+)\s+cycles:\s*(\d+)")
STLB_RE = re.compile(
    r"cpu\d+->\S*STLB TOTAL\s+ACCESS:\s*(\d+)\s+HIT:\s*(\d+)\s+MISS:\s*(\d+)"
)
PTW_RE = re.compile(
    r"\[PROTO-PTW\]\s+\S+\s+walks=(\d+)\s+prefetch_walks=(\d+)"
    r"\s+psc_lookups=(\d+)\s+psc_hits=(\d+)"
)


def parse_run(path: Path) -> dict:
    text = path.read_text(errors="replace")
    ipc_match = IPC_RE.search(text)
    stlb_match = STLB_RE.search(text)
    if not (ipc_match and stlb_match):
        sys.exit(f"{path}: could not find IPC / STLB lines; check ChampSim output format")

    instructions, cycles = int(ipc_match.group(2)), int(ipc_match.group(3))
    accesses, _, misses = map(int, stlb_match.groups())
    ptw_match = PTW_RE.search(text)
    config, trace = path.stem.split("__", 1)

    if ptw_match:
        walks, prefetch_walks, psc_lookups, psc_hits = map(int, ptw_match.groups())
        walk_source = "PTW prototype counter"
    else:
        # A useful baseline proxy, but not an independently measured PTW count.
        walks, prefetch_walks, psc_lookups, psc_hits = misses, None, None, None
        walk_source = "STLB misses (proxy)"

    return {
        "trace": trace,
        "config": config,
        "instructions": instructions,
        "cycles": cycles,
        "ipc": instructions / cycles if cycles else 0.0,
        "stlb_accesses": accesses,
        "stlb_misses": misses,
        "stlb_mpki": 1000 * misses / instructions if instructions else 0.0,
        "page_walks": walks,
        "page_walk_source": walk_source,
        "ptw_prefetch_walks": prefetch_walks,
        "psc_lookups": psc_lookups,
        "psc_hits": psc_hits,
    }


def load_cacti(path: Path) -> dict:
    with path.open(newline="") as f:
        return {row["structure"]: row for row in csv.DictReader(f)}


def cacti_row_ready(cacti: dict, structure: str) -> bool:
    row = cacti.get(structure)
    if not row:
        return False
    try:
        return all(float(row[key]) >= 0 for key in ("read_nj", "write_nj", "leakage_mw"))
    except (KeyError, TypeError, ValueError):
        return False


def component_energy_nj(
    structure: str, reads: int, writes: int, runtime_s: float, cacti: dict
) -> float | None:
    """Return dynamic plus leakage energy when CACTI values are available."""
    if not cacti_row_ready(cacti, structure):
        return None
    row = cacti[structure]
    dynamic = reads * float(row["read_nj"]) + writes * float(row["write_nj"])
    # mW * seconds * 1e6 = nJ
    leakage = float(row["leakage_mw"]) * runtime_s * 1e6
    return dynamic + leakage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path, help="raw ChampSim output files")
    parser.add_argument("--out", type=Path, default=Path("results/results_table.csv"))
    parser.add_argument("--cacti-csv", type=Path, default=CACTI_CSV)
    parser.add_argument("--cpu-ghz", type=float, default=DEFAULT_CPU_GHZ)
    parser.add_argument(
        "--dram-nj-per-walk",
        type=float,
        help=("Optional explicit DRAM-energy approximation per page walk. "
              "This is not a measured DRAM-reference count."),
    )
    args = parser.parse_args()

    if args.cpu_ghz <= 0:
        parser.error("--cpu-ghz must be positive")
    if args.dram_nj_per_walk is not None and args.dram_nj_per_walk < 0:
        parser.error("--dram-nj-per-walk cannot be negative")

    cacti = load_cacti(args.cacti_csv)
    runs = [parse_run(path) for path in args.runs]
    baseline = {r["trace"]: r for r in runs if r["config"] == BASELINE}

    for run in runs:
        runtime_s = run["cycles"] / (args.cpu_ghz * 1e9)
        # ChampSim's current TOTAL ACCESS counter does not split reads/writes.
        # Until a write/insert counter exists, it is treated as read-like accesses.
        run["stlb_energy_nj"] = component_energy_nj(
            "STLB", run["stlb_accesses"], 0, runtime_s, cacti
        )

        # The PTW prototype reports PSC lookups; without it, leave PSC energy unknown.
        run["psc_energy_nj"] = (
            component_energy_nj("PSC", run["psc_lookups"], 0, runtime_s, cacti)
            if run["psc_lookups"] is not None
            else None
        )

        known = [run[k] for k in ("stlb_energy_nj", "psc_energy_nj") if run[k] is not None]
        run["known_onchip_energy_nj"] = sum(known) if known else None
        run["known_components"] = ",".join(
            name for name, value in (
                ("STLB", run["stlb_energy_nj"]), ("PSC", run["psc_energy_nj"])
            ) if value is not None
        )
        run["energy_coverage"] = "partial" if run["known_components"] else "no CACTI inputs"
        run["dram_energy_nj"] = (
            run["page_walks"] * args.dram_nj_per_walk
            if args.dram_nj_per_walk is not None
            else None
        )

        base = baseline.get(run["trace"])
        run["speedup_vs_lru"] = run["ipc"] / base["ipc"] if base and base["ipc"] else None

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for run in sorted(runs, key=lambda row: (row["trace"], row["config"])):
            writer.writerow({key: ("" if run.get(key) is None else run.get(key)) for key in COLUMNS})
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
