#!/usr/bin/env bash
# Usage: scripts/run_baseline.sh <trace.champsimtrace.xz> [warmup_M] [sim_M]
# Runs one trace with the LRU baseline and saves the raw ChampSim output.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TRACE="$1"
WARMUP="${2:-10}"   # millions of instructions; small defaults for a first smoke test
SIM="${3:-20}"

mkdir -p "$ROOT/results/raw"
OUT="$ROOT/results/raw/baseline_lru__$(basename "$TRACE" .champsimtrace.xz).txt"

"$ROOT/third_party/ChampSim/bin/champsim_baseline_lru" \
  --warmup-instructions "${WARMUP}000000" \
  --simulation-instructions "${SIM}000000" \
  "$TRACE" | tee "$OUT"

echo "Saved: $OUT"
