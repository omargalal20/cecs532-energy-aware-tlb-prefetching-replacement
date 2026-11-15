#!/usr/bin/env python3
"""Plot results/results_table.csv (made by energy/energy_fusion.py).

Usage: python3 scripts/plot_results.py [results/results_table.csv] [--out results/plots]
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ORDER = ["baseline_lru", "itp", "atp_sbfp_pq", "atp_sbfp_pq_itp", "atp", "atp_itp", "atp_sbfp", "atp_sbfp_itp"]


def num(x):
    return float(x) if x not in ("", None) else None


def grouped_bars(rows, key, ylabel, title, path, baseline_line=None, ylim=None):
    traces = sorted({r["trace"] for r in rows})
    configs = [c for c in ORDER if any(r["config"] == c for r in rows)]
    width = 0.8 / max(len(configs), 1)
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, c in enumerate(configs):
        vals = []
        for t in traces:
            v = next((num(r[key]) for r in rows if r["trace"] == t and r["config"] == c), None)
            vals.append(v if v is not None else 0)
        ax.bar([x + i * width for x in range(len(traces))], vals, width, label=c)
    ax.set_xticks([x + width * (len(configs) - 1) / 2 for x in range(len(traces))])
    ax.set_xticklabels(traces, rotation=15, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if baseline_line is not None:
        ax.axhline(baseline_line, color="gray", lw=0.8, ls="--")
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="results/results_table.csv")
    ap.add_argument("--out", default="results/plots")
    args = ap.parse_args()
    rows = list(csv.DictReader(open(args.csv)))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sp = [num(r["speedup_vs_lru"]) for r in rows if num(r["speedup_vs_lru"]) is not None]
    lo, hi = min(min(sp), 1.0) - 0.005, max(max(sp), 1.0) + 0.005
    grouped_bars(rows, "speedup_vs_lru", "speedup vs baseline_lru", f"Speedup (y-axis starts at {lo:.3f})", out / "speedup.png", 1.0, ylim=(lo, hi))
    grouped_bars(rows, "stlb_mpki", "STLB MPKI", "STLB misses per kilo-instruction", out / "stlb_mpki.png")

    base = {r["trace"]: num(r["page_walks"]) for r in rows if r["config"] == "baseline_lru"}
    for r in rows:
        w, b = num(r["page_walks"]), base.get(r["trace"])
        r["walks_rel"] = w / b if w is not None and b else ""
    grouped_bars(rows, "walks_rel", "page walks relative to baseline_lru", "Page walks (demand + prefetch)", out / "page_walks.png", 1.0)

    pts = defaultdict(list)
    for r in rows:
        if num(r["energy_vs_lru"]) is not None and num(r["speedup_vs_lru"]) is not None:
            pts[r["config"]].append((num(r["energy_vs_lru"]), num(r["speedup_vs_lru"]), r["trace"]))
    if pts:
        fig, ax = plt.subplots(figsize=(10, 5))
        traces = sorted({trace for points in pts.values() for _, _, trace in points})
        marker_cycle = ["o", "s", "^", "D", "v", "P", "X", "*"]
        trace_markers = {trace: marker_cycle[i % len(marker_cycle)] for i, trace in enumerate(traces)}
        trace_names = {trace: trace.split("-")[0] for trace in traces}
        colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        config_handles = []
        for i, (config, points) in enumerate(pts.items()):
            color = colors[i % len(colors)]
            config_handles.append(Line2D([], [], marker="o", linestyle="None", color=color, label=config))
            for trace, marker in trace_markers.items():
                matches = [(x, y) for x, y, name in points if name == trace]
                if matches:
                    ax.scatter([x for x, _ in matches], [y for _, y in matches], color=color, marker=marker)
        ax.axhline(1, color="gray", lw=0.8, ls="--")
        ax.axvline(1, color="gray", lw=0.8, ls="--")
        ax.set_xlabel("estimated translation energy vs baseline_lru (lower is better)")
        ax.set_ylabel("speedup vs baseline_lru (higher is better)")
        trace_handles = [
            Line2D([], [], marker=marker, linestyle="None", color="black", label=name)
            for trace, marker in trace_markers.items()
            for name in [trace_names[trace]]
        ]
        ax.legend(handles=config_handles, title="Config", fontsize=7, loc="upper left", bbox_to_anchor=(1.02, 1))
        fig.legend(handles=trace_handles, title="Trace marker", fontsize=7, loc="upper left", bbox_to_anchor=(0.72, 0.48))
        fig.tight_layout(rect=(0, 0, 0.70, 1))
        fig.savefig(out / "pareto.png", dpi=200)
        plt.close(fig)
    else:
        print("No energy_vs_lru values yet: skipped pareto.png")
    print(f"Plots in {out}/")


if __name__ == "__main__":
    main()
