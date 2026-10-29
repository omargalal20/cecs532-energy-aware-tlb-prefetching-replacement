#!/usr/bin/env bash
# Usage: scripts/fetch_traces.sh [--backups]
# Downloads the selected DPC-3 SPEC traces into traces/ (see README, "Trace selection").
# Existing files that pass `xz -t` are kept; a download is only moved into place after it passes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${TRACE_BASE_URL:-https://dpc3.compas.cs.stonybrook.edu/champsim-traces/speccpu}"
SELECTED=(429.mcf-51B 620.omnetpp_s-874B 623.xalancbmk_s-700B)
BACKUPS=(471.omnetpp-188B 429.mcf-192B 429.mcf-22B)

TRACES=("${SELECTED[@]}")
[[ "${1:-}" == "--backups" ]] && TRACES+=("${BACKUPS[@]}")

mkdir -p "$ROOT/traces"
for t in "${TRACES[@]}"; do
  f="$ROOT/traces/$t.champsimtrace.xz"
  if [[ -f "$f" ]] && xz -t "$f" 2>/dev/null; then
    echo "present: $t"
    continue
  fi
  echo "downloading: $t"
  curl -fL --retry 3 --progress-bar -o "$f.part" "$BASE/$t.champsimtrace.xz"
  xz -t "$f.part"
  mv "$f.part" "$f"
  echo "done: $t"
done
