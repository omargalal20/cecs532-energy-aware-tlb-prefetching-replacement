#!/usr/bin/env bash
# Usage: scripts/run_all.sh [warmup_M] [sim_M] [config ...]
# Runs every config on every trace in traces/ (or only TRACES="a.champsimtrace.xz b..." if set).
# Raw output goes to results/raw/<config>__<trace>.txt, the naming energy_fusion.py expects.
# Runs up to JOBS at once (default 2). Existing outputs are skipped, so it can be restarted.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WARMUP="${1:-10}"; SIM="${2:-20}"; shift $(( $# > 2 ? 2 : $# ))
CONFIGS=("${@:-baseline_lru itp atp atp_itp atp_sbfp atp_sbfp_itp}")
read -ra CONFIGS <<< "${CONFIGS[*]}"
JOBS="${JOBS:-2}"
TRACES_DEFAULT="429.mcf-51B 620.omnetpp_s-874B 623.xalancbmk_s-700B"

mkdir -p "$ROOT/results/raw"
run_one() {
  local cfg="$1" trace="$2" out="$ROOT/results/raw/${1}__${2}.txt"
  [ -s "$out" ] && grep -q "Region of Interest" "$out" && { echo "skip $out"; return; }
  echo "run  $cfg $trace"
  "$ROOT/third_party/ChampSim/bin/champsim_$cfg" \
    --warmup-instructions "${WARMUP}000000" --simulation-instructions "${SIM}000000" \
    "$ROOT/traces/$trace.champsimtrace.xz" > "$out.tmp" 2>&1 && mv "$out.tmp" "$out"
}
export -f run_one; export ROOT WARMUP SIM

for t in ${TRACES:-$TRACES_DEFAULT}; do
  t="${t%.champsimtrace.xz}"
  for c in "${CONFIGS[@]}"; do echo "$c $t"; done
done | xargs -P "$JOBS" -L1 bash -c 'run_one "$0" "$1"'
echo "Done. Next: python3 energy/energy_fusion.py results/raw/*.txt --out results/results_table.csv"
