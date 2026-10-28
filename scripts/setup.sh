#!/usr/bin/env bash
# Clone ChampSim and CACTI at pinned commits, fetch ChampSim dependencies with vcpkg, build both.
# Same script for WSL, Linux and macOS (and inside the Docker image).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHAMPSIM_REPO="https://github.com/ChampSim/ChampSim.git"
CHAMPSIM_COMMIT="410cee6"   # pinned so everyone simulates the same code
CACTI_REPO="https://github.com/HewlettPackard/cacti.git"
CACTI_COMMIT="1ffd8df"      # pinned CACTI 7.0 release
CS="$ROOT/third_party/ChampSim"
CACTI="$ROOT/third_party/cacti"
mkdir -p "$ROOT/traces" "$ROOT/results/raw"

if [ ! -d "$CS/.git" ]; then
  mkdir -p "$ROOT/third_party"
  mkdir -p "$ROOT/third_party"
  git clone "$CHAMPSIM_REPO" "$CS"
fi
git -C "$CS" fetch --quiet origin
git -C "$CS" checkout --quiet "$CHAMPSIM_COMMIT"
git -C "$CS" submodule update --init

# vcpkg downloads and builds ChampSim's libraries (fmt, cli11, lzma, ...).
"$CS/vcpkg/bootstrap-vcpkg.sh" -disableMetrics
(cd "$CS" && vcpkg/vcpkg install)

# Generate the Makefile from our config, then compile.
(cd "$CS" && ./config.sh "$ROOT/configs/baseline_lru.json" && make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu)")

# CACTI: energy per access for the TLB / prefetch-queue arrays.
if [ ! -d "$CACTI/.git" ]; then
  git clone "$CACTI_REPO" "$CACTI"
fi
git -C "$CACTI" checkout --quiet "$CACTI_COMMIT"
(cd "$CACTI" && make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu)")

echo "Built: $CS/bin/champsim_baseline_lru"
echo "Built: $CACTI/cacti"
