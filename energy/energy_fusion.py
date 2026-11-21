#!/usr/bin/env python3
"""Fuse ChampSim translation counters with CACTI per-access energy.

Usage:
    python3 energy/energy_fusion.py results/raw/*.txt \\
        --cacti-csv energy/cacti_per_access.csv \\
        --dram-nj-per-access VALUE --out results/results_table.csv

The CSV must provide read_nj, write_nj, and leakage_mw rows for each modeled
on-chip structure. Cache rows (L1D, L2C, LLC) are optional; missing cache rows
are excluded and identified in energy_coverage and energy_notes. PSC uses a
zero lower bound and the existing PQ row (or its PSC_UPPER_PROXY alias) for its
upper scenario. The DRAM value is the estimated energy of one LLC translation miss.

Counter-to-energy assumptions are recorded in energy_notes. ChampSim does not
separate TLB lookup writes/fills, so TLB accesses are priced as read-like accesses.
Current SBFP/ATP logs do not count every FDT read or fake-queue insertion; their
energy is an estimate based on the available counters, not a complete gate-level
accounting. A missing required CACTI value leaves total energy, energy_vs_lru,
and EDP blank; missing optional cache rows do not block totals but are excluded.
"""

import argparse
import csv
import math
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_CPU_GHZ = 4.0
CACTI_CSV = Path(__file__).with_name("cacti_per_access.csv")
BASELINE = "baseline_lru"

COLUMNS = [
    "trace", "config", "instructions", "cycles", "runtime_s", "ipc",
    "speedup_vs_lru", "stlb_total_accesses", "stlb_demand_misses",
    "stlb_mpki", "page_walks", "page_walk_source",
    "l1d_translation_accesses", "l2c_translation_accesses",
    "llc_translation_accesses", "llc_translation_misses",
    "ptw_prefetch_walks", "psc_lookups", "psc_hits", "pq_lookups",
    "pq_hits", "pq_inserts", "sbfp_free_issued", "sbfp_free_useful",
    "sbfp_sampler_lookups", "sbfp_sampler_hits", "sbfp_sampler_inserts",
    "sbfp_fdt_updates", "sbfp_fdt_decays", "atp_issued",
    "atp_useful_hits", "atp_prefetch_accuracy", "sbfp_prefetch_accuracy",
    "prefetch_accuracy", "dtlb_energy_nj", "itlb_energy_nj",
    "stlb_energy_nj", "psc_energy_nj", "pq_energy_nj",
    "sbfp_fdt_energy_nj", "sbfp_sampler_energy_nj", "atp_fpq_energy_nj",
    "l1d_translation_energy_nj", "l2c_translation_energy_nj",
    "llc_translation_energy_nj", "dram_energy_nj", "known_energy_nj",
    "psc_energy_nj_upper", "energy_nj", "energy_nj_upper",
    "energy_vs_lru", "energy_vs_lru_upper", "edp", "edp_upper",
    "energy_coverage", "energy_notes",
]

IPC_RE = re.compile(
    r"CPU\s+\d+\s+cumulative IPC:\s*(\S+)\s+instructions:\s*(\d+)\s+cycles:\s*(\d+)"
)
STAT_RE = re.compile(
    r"^cpu\d+->(?P<target>\S+)\s+(?P<kind>TOTAL|LOAD|TRANSLATION)\s+"
    r"ACCESS:\s*(?P<access>\d+)\s+HIT:\s*(?P<hit>\d+)\s+MISS:\s*(?P<miss>\d+)",
    re.MULTILINE,
)
KV_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*)=(\d+)")

PSC_STRUCTURES = ("PSC_1X2", "PSC_1X4", "PSC_2X4", "PSC_4X8")
ONCHIP_STRUCTURES = (
    "DTLB", "ITLB", "STLB", "PSC", *PSC_STRUCTURES, "PQ", "SBFP_FDT",
    "SBFP_SAMPLER", "ATP_FPQ"
)
CACHE_STRUCTURES = ("L1D", "L2C", "LLC")


def sum_counter_lines(text: str, prefix: str) -> dict[str, int]:
    """Sum named key=value counters from every matching per-core line."""
    totals: dict[str, int] = {}
    for line in text.splitlines():
        if line.startswith(prefix):
            for key, value in KV_RE.findall(line):
                totals[key] = totals.get(key, 0) + int(value)
    return totals


def sum_atp_lines(text: str) -> dict[str, int]:
    """Collect ATP counters, including the parenthesized useful-prefetch count."""
    totals: dict[str, int] = {}
    for line in text.splitlines():
        if not line.startswith("[ATP]"):
            continue
        for key, value in KV_RE.findall(line):
            # Parsed separately below because the parenthesized counter is also
            # matched by the generic key=value expression.
            if key == "hits_on_prefetched":
                continue
            totals[key] = totals.get(key, 0) + int(value)
        match = re.search(r"hits_on_prefetched=(\d+)", line)
        if match:
            totals["hits_on_prefetched"] = totals.get("hits_on_prefetched", 0) + int(match.group(1))
    return totals


def parse_stats(text: str) -> dict[str, dict[str, dict[str, int]]]:
    stats: dict[str, dict[str, dict[str, int]]] = {}
    for match in STAT_RE.finditer(text):
        target = match.group("target")
        structure = next((name for name in (*ONCHIP_STRUCTURES, *CACHE_STRUCTURES)
                          if target.endswith(name)), None)
        if structure is None:
            continue
        kind = match.group("kind")
        row = stats.setdefault(structure, {}).setdefault(kind, {"access": 0, "hit": 0, "miss": 0})
        row["access"] += int(match.group("access"))
        row["hit"] += int(match.group("hit"))
        row["miss"] += int(match.group("miss"))
    return stats


def parse_run(path: Path) -> dict[str, Any]:
    text = path.read_text(errors="replace")
    ipc_matches = IPC_RE.findall(text)
    if not ipc_matches:
        sys.exit(f"{path}: could not find final CPU cumulative IPC line")
    # Current project runs are single-core. Summing final lines also supports a
    # future multi-core output if ChampSim prints one final summary per CPU.
    instructions = sum(int(row[1]) for row in ipc_matches)
    cycles = sum(int(row[2]) for row in ipc_matches)
    stats = parse_stats(text)

    stlb = stats.get("STLB", {})
    if "LOAD" not in stlb or "TOTAL" not in stlb:
        sys.exit(f"{path}: missing STLB LOAD or TOTAL counters; cannot separate demand misses")
    stlb_demand_misses = stlb["LOAD"]["miss"]

    ptw = sum_counter_lines(text, "[PROTO-PTW]")
    sbfp = sum_counter_lines(text, "[SBFP]")
    atp = sum_atp_lines(text)

    config, trace = path.stem.split("__", 1) if "__" in path.stem else ("unknown", path.stem)
    page_walks = ptw.get("walks")
    walk_source = "PROTO-PTW walks" if page_walks is not None else "STLB LOAD misses (proxy)"
    if page_walks is None:
        page_walks = stlb_demand_misses

    def stat_access(structure: str, kind: str) -> int:
        return stats.get(structure, {}).get(kind, {}).get("access", 0)

    return {
        "trace": trace,
        "config": config,
        "instructions": instructions,
        "cycles": cycles,
        "runtime_s": cycles / (DEFAULT_CPU_GHZ * 1e9),
        "ipc": instructions / cycles if cycles else 0.0,
        "stlb_total_accesses": stat_access("STLB", "TOTAL"),
        "stlb_demand_misses": stlb_demand_misses,
        "stlb_mpki": 1000 * stlb_demand_misses / instructions if instructions else 0.0,
        "page_walks": page_walks,
        "page_walk_source": walk_source,
        "l1d_translation_accesses": stat_access("L1D", "TRANSLATION"),
        "l2c_translation_accesses": stat_access("L2C", "TRANSLATION"),
        "llc_translation_accesses": stat_access("LLC", "TRANSLATION"),
        "llc_translation_misses": stats.get("LLC", {}).get("TRANSLATION", {}).get("miss", 0),
        "ptw_prefetch_walks": ptw.get("prefetch_walks"),
        "psc_lookups": ptw.get("psc_lookups"),
        "psc_hits": ptw.get("psc_hits"),
        "pq_lookups": ptw.get("pq_lookups"),
        "pq_hits": ptw.get("pq_hits"),
        "pq_inserts": ptw.get("pq_inserts"),
        "sbfp_free_issued": sbfp.get("free_issued"),
        "sbfp_free_useful": sbfp.get("free_useful"),
        "sbfp_sampler_lookups": sbfp.get("sampler_lookups"),
        "sbfp_sampler_hits": sbfp.get("sampler_hits"),
        "sbfp_sampler_inserts": sbfp.get("sampler_inserts"),
        "sbfp_fdt_updates": sbfp.get("fdt_updates"),
        "sbfp_fdt_decays": sbfp.get("decays"),
        "atp_issued": atp.get("issued"),
        "atp_useful_hits": atp.get("hits_on_prefetched"),
        "_stats": stats,
        "_ptw": ptw,
        "_sbfp": sbfp,
        "_atp": atp,
    }


def load_cacti(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"structure", "read_nj", "write_nj", "leakage_mw"}.issubset(reader.fieldnames):
            raise ValueError(f"{path}: expected structure, read_nj, write_nj, leakage_mw columns")
        return {row["structure"].strip().upper(): row for row in reader if row.get("structure")}


def cacti_ready(
    cacti: dict[str, dict[str, str]], structure: str, *, include_leakage: bool = True,
) -> bool:
    row = cacti.get(structure)
    if not row:
        return False
    try:
        keys = ["read_nj", "write_nj"]
        if include_leakage:
            keys.append("leakage_mw")
        return all(math.isfinite(float(row[key])) and float(row[key]) >= 0 for key in keys)
    except (KeyError, TypeError, ValueError):
        return False


def component_energy_nj(
    structure: str, reads: int, writes: int, runtime_s: float,
    cacti: dict[str, dict[str, str]], *, include_leakage: bool = True,
    leakage_instances: int = 1,
) -> float | None:
    if not cacti_ready(cacti, structure, include_leakage=include_leakage):
        return None
    row = cacti[structure]
    energy = reads * float(row["read_nj"]) + writes * float(row["write_nj"])
    if include_leakage:
        energy += leakage_instances * float(row["leakage_mw"]) * runtime_s * 1e6
    return energy


def ratio(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def active_structures(config: str) -> set[str]:
    tokens = set(config.lower().split("_"))
    active = {"DTLB", "ITLB", "STLB", "L1D", "L2C", "LLC"}
    if "atp" in tokens:
        active.add("ATP_FPQ")
    if "sbfp" in tokens:
        active.update({"SBFP_FDT", "SBFP_SAMPLER"})
    if "pq" in tokens:
        active.add("PQ")
    return active


def add_energy(
    run: dict[str, Any], cacti: dict[str, dict[str, str]],
    dram_nj: float | None, cpu_ghz: float,
) -> None:
    ptw, sbfp, atp = run["_ptw"], run["_sbfp"], run["_atp"]
    config_tokens = set(run["config"].lower().split("_"))
    # Determine the implementation from its selected config. Counter presence
    # is not a reliable mode signal because a zero-valued field may still print.
    pq_mode = "pq" in config_tokens
    atp_issued = atp.get("issued")
    atp_useful = atp.get("hits_on_prefetched")
    sbfp_issued = ptw.get("pq_inserts") if pq_mode else sbfp.get("free_issued")
    sbfp_useful = ptw.get("pq_hits") if pq_mode else sbfp.get("free_useful")

    has_atp = "atp" in config_tokens
    has_sbfp = "sbfp" in config_tokens
    has_pq = "pq" in config_tokens
    # In direct-fill SBFP configurations, hits_on_prefetched already includes
    # useful SBFP fills, so ATP-only accuracy cannot be separated from this log.
    run["atp_prefetch_accuracy"] = (
        ratio(atp_useful, atp_issued) if has_atp and (not has_sbfp or has_pq) else None
    )
    run["sbfp_prefetch_accuracy"] = ratio(sbfp_useful, sbfp_issued)
    if not has_atp and not has_sbfp:
        run["prefetch_accuracy"] = None
    else:
        total_issued = (atp_issued or 0) + (sbfp_issued or 0)
        if has_sbfp and not has_pq:
            # Direct-fill SBFP useful hits are already included in ATP's
            # hits_on_prefetched counter; do not add sbfp_free_useful again.
            total_useful = atp_useful or 0
        else:
            # In PQ mode, queue hits bypass the STLB prefetch-hit counter.
            total_useful = (atp_useful or 0) + (sbfp_useful or 0)
        run["prefetch_accuracy"] = ratio(total_useful, total_issued)

    runtime_s = run["cycles"] / (cpu_ghz * 1e9)
    stats = run["_stats"]

    # ChampSim's counters do not expose separate TLB writes/fills. Count all
    # accesses as read-like; the STLB TOTAL is used for energy, while STLB LOAD
    # misses are retained separately as demand misses (excluding prefetches).
    # The PTW counter is aggregate across the four page-structure caches.
    # Current logs show exactly four lookups per walk. Keep the aggregate so
    # one documented CACTI proxy can provide a PSC upper-bound estimate.
    psc_lookups_each = (ptw.get("psc_lookups", 0) or 0) / len(PSC_STRUCTURES)
    access_counts: dict[str, tuple[float, float]] = {
        "DTLB": (stats.get("DTLB", {}).get("TOTAL", {}).get("access", 0), 0),
        "ITLB": (stats.get("ITLB", {}).get("TOTAL", {}).get("access", 0), 0),
        "STLB": (run["stlb_total_accesses"], 0),
        "PQ": (ptw.get("pq_lookups", 0), ptw.get("pq_inserts", 0)),
        # Each tracked FDT update is read-modify-write; a decay shifts all 14
        # counters. Read-only threshold probes are not present in the log.
        "SBFP_FDT": (
            sbfp.get("fdt_updates", 0) + 14 * sbfp.get("decays", 0),
            sbfp.get("fdt_updates", 0) + 14 * sbfp.get("decays", 0),
        ),
        # Sampler hits are included in lookups; inserts are writes.
        "SBFP_SAMPLER": (sbfp.get("sampler_lookups", 0), sbfp.get("sampler_inserts", 0)),
        # ATP checks three fake queues per operate call. The current log does
        # not count fake-queue insertions, so writes are omitted and documented.
        "ATP_FPQ": (3 * atp.get("operate_calls", 0), 0),
        "L1D": (run["l1d_translation_accesses"], 0),
        "L2C": (run["l2c_translation_accesses"], 0),
        "LLC": (run["llc_translation_accesses"], 0),
    }
    energies: dict[str, float | None] = {}
    active = active_structures(run["config"])
    for structure, (reads, writes) in access_counts.items():
        if structure not in active:
            energies[structure] = 0.0
        else:
            cache_dynamic_only = structure in CACHE_STRUCTURES
            energies[structure] = component_energy_nj(
                structure, reads, writes, runtime_s, cacti,
                include_leakage=not cache_dynamic_only,
                leakage_instances=3 if structure == "ATP_FPQ" else 1,
            )

    # PSC CACTI failures are represented as an interval: zero is the lower
    # bound, while the PQ row (or its PSC_UPPER_PROXY alias) supplies the upper
    # bound. If the four geometry-specific rows eventually become usable, use
    # their sum instead of the generic proxy.
    psc_lower = 0.0
    psc_upper: float | None = None
    psc_proxy_source: str | None = None
    psc_total_lookups = ptw.get("psc_lookups", 0) or 0
    if all(cacti_ready(cacti, name) for name in PSC_STRUCTURES):
        psc_proxy_source = "PSC geometry-specific rows"
        psc_parts = [
            component_energy_nj(name, psc_lookups_each, 0, runtime_s, cacti)
            for name in PSC_STRUCTURES
        ]
        if all(value is not None for value in psc_parts):
            psc_upper = sum(value for value in psc_parts if value is not None)
    else:
        # Use the explicit alias row when present. Until then, PQ itself is the
        # specified 64-entry, fully associative proxy at the same CACTI node.
        psc_proxy_source = next(
            (name for name in ("PSC_UPPER_PROXY", "PQ") if cacti_ready(cacti, name)),
            None,
        )
    if psc_upper is None and psc_proxy_source is not None:
        psc_upper = component_energy_nj(
            psc_proxy_source, psc_total_lookups, 0, runtime_s, cacti,
            leakage_instances=len(PSC_STRUCTURES),
        )

    dram_energy = None if dram_nj is None else run["llc_translation_misses"] * dram_nj
    missing = sorted(
        name for name in active
        if energies.get(name) is None and name not in CACHE_STRUCTURES
    )
    missing_caches = sorted(
        name for name in CACHE_STRUCTURES
        if name in active and energies.get(name) is None
    )
    if dram_nj is None:
        missing.append("DRAM")

    # known_energy_nj is the modeled partial sum and excludes PSC; PSC is
    # separately exposed as a lower/upper bound.
    known = sum(energies[name] for name in active if energies.get(name) is not None)
    if dram_energy is not None:
        known += dram_energy
    complete_lower = not missing
    total_lower = known if complete_lower else None
    total_upper = (
        known + psc_upper
        if complete_lower and psc_upper is not None else None
    )

    for structure, column in (
        ("DTLB", "dtlb_energy_nj"), ("ITLB", "itlb_energy_nj"),
        ("STLB", "stlb_energy_nj"),
        ("PQ", "pq_energy_nj"), ("SBFP_FDT", "sbfp_fdt_energy_nj"),
        ("SBFP_SAMPLER", "sbfp_sampler_energy_nj"),
        ("ATP_FPQ", "atp_fpq_energy_nj"),
        ("L1D", "l1d_translation_energy_nj"),
        ("L2C", "l2c_translation_energy_nj"),
        ("LLC", "llc_translation_energy_nj"),
    ):
        run[column] = energies[structure]
    run["dram_energy_nj"] = dram_energy
    run["known_energy_nj"] = known
    # The legacy energy_nj/edp columns now explicitly hold the lower-bound
    # scenario (PSC=0); upper-bound proxy results are in separate columns.
    run["psc_energy_nj"] = psc_lower
    run["psc_energy_nj_upper"] = psc_upper
    run["energy_nj"] = total_lower
    run["energy_nj_upper"] = total_upper
    run["edp"] = total_lower * runtime_s if total_lower is not None else None
    run["edp_upper"] = total_upper * runtime_s if total_upper is not None else None
    if complete_lower:
        coverage = (
            "PSC lower/upper scenarios available (PQ proxy upper bound)"
            if total_upper is not None else "PSC=0 lower-bound estimate; upper proxy unavailable"
        )
    else:
        coverage = "partial; missing " + ", ".join(missing)
    if missing_caches:
        coverage += "; cache energy excluded: " + ", ".join(missing_caches)
    run["energy_coverage"] = coverage
    notes = []
    if "ATP_FPQ" in active:
        notes.append("ATP_FPQ energy includes 3 queues; writes uncounted and excluded")
    if "SBFP_FDT" in active:
        notes.append("FDT read-only threshold probes uncounted")
    if "DTLB" in active or "ITLB" in active or "STLB" in active:
        notes.append("TLB fills priced as read-like accesses; STLB writes not split")
    # Preserve CACTI proxy/failure documentation from either accepted CSV
    # heading so the assumption remains visible in every affected result row.
    for structure in sorted(active):
        row = cacti.get(structure, {})
        cacti_note = (row.get("note") or row.get("notes") or "").strip()
        if cacti_note:
            notes.append(f"{structure}: {cacti_note}")
    for structure in (*PSC_STRUCTURES, "PSC_UPPER_PROXY", "PQ"):
        row = cacti.get(structure, {})
        cacti_note = (row.get("note") or row.get("notes") or "").strip()
        if cacti_note:
            notes.append(f"{structure}: {cacti_note}")
    if psc_proxy_source == "PSC geometry-specific rows":
        psc_upper_note = "upper scenario sums the four geometry-specific CACTI rows"
    elif psc_proxy_source:
        psc_upper_note = (
            "upper scenario uses the 64-entry fully associative, 64 B PQ proxy at the "
            f"selected node (CACTI row {psc_proxy_source})"
        )
    else:
        psc_upper_note = "upper proxy CACTI value unavailable"
    notes.append(
        "PSC lower bound assumes 0 nJ; " + psc_upper_note
        + "; real PSC geometries (2, 4, 8, and 32 entries) failed in CACTI (exit 139)"
    )
    if missing_caches:
        notes.append(
            "Cache energy for page-walk accesses is excluded because CACTI rows are unavailable: "
            + ", ".join(missing_caches)
        )
    run["energy_notes"] = "; ".join(notes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path, help="raw ChampSim output files")
    parser.add_argument("--out", type=Path, default=Path("results/results_table.csv"))
    parser.add_argument("--cacti-csv", type=Path, default=CACTI_CSV)
    parser.add_argument("--cpu-ghz", type=float, default=DEFAULT_CPU_GHZ)
    parser.add_argument(
        "--dram-nj-per-access", type=float, default=56.0,
        help="Estimated energy for one DRAM read caused by an LLC translation miss (nJ)",
    )
    args = parser.parse_args()
    if args.cpu_ghz <= 0:
        parser.error("--cpu-ghz must be positive")
    if args.dram_nj_per_access is not None and args.dram_nj_per_access < 0:
        parser.error("--dram-nj-per-access cannot be negative")

    try:
        cacti = load_cacti(args.cacti_csv)
        runs = [parse_run(path) for path in args.runs]
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    # runtime uses the selected CPU clock, not a hard-coded frequency.
    for run in runs:
        run["runtime_s"] = run["cycles"] / (args.cpu_ghz * 1e9)
        add_energy(run, cacti, args.dram_nj_per_access, args.cpu_ghz)

    baselines = {run["trace"]: run for run in runs if run["config"] == BASELINE}
    for run in runs:
        base = baselines.get(run["trace"])
        run["speedup_vs_lru"] = (
            base["cycles"] / run["cycles"]
            if base and run["cycles"] > 0 and base["cycles"] > 0
            else None
        )
        run["energy_vs_lru"] = (
            run["energy_nj"] / base["energy_nj"]
            if base and run["energy_nj"] is not None and base["energy_nj"]
            else None
        )
        run["energy_vs_lru_upper"] = (
            run["energy_nj_upper"] / base["energy_nj_upper"]
            if base and run["energy_nj_upper"] is not None and base["energy_nj_upper"]
            else None
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=COLUMNS)
        writer.writeheader()
        for run in sorted(runs, key=lambda row: (row["trace"], row["config"])):
            writer.writerow({key: ("" if run.get(key) is None else run.get(key)) for key in COLUMNS})
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
