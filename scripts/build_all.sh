#!/usr/bin/env bash
# Usage: scripts/build_all.sh
# Applies our ChampSim patches and modules to third_party/ChampSim (run scripts/setup.sh first),
# then builds one executable per configuration in configs/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CS="$ROOT/third_party/ChampSim"
CONFIGS=(${CONFIGS_OVERRIDE:-baseline_lru itp atp atp_itp atp_sbfp atp_sbfp_itp})   # add sbfp configs here once they exist

[ -d "$CS/.git" ] || { echo "Run scripts/setup.sh first"; exit 1; }

# Start from the pinned commit so re-running is safe.
git -C "$CS" checkout --quiet -- .
git -C "$CS" clean -fdq inc src prefetcher replacement

git -C "$CS" apply "$ROOT/prototypes/ptw-counters.patch"
git -C "$CS" apply "$ROOT/prototypes/itp/instr-flag.patch"
git -C "$CS" apply "$ROOT/prototypes/sbfp/sbfp-free-walk.patch"
cp -r "$ROOT/prototypes/itp/replacement/itp" "$CS/replacement/"
cp -r "$ROOT"/prototypes/atp/prefetcher/* "$CS/prefetcher/"

for c in "${CONFIGS[@]}"; do
  echo "== building $c"
  (cd "$CS" && ./config.sh "$ROOT/configs/$c.json" && make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu)")
done
ls "$CS"/bin
