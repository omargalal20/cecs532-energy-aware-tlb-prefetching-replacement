# Optional: identical toolchain for everyone (WSL, macOS, Linux).
# Build:  docker build -t tlb-sim -f docker/Dockerfile .
# Run:    docker run --rm -it -v "$PWD":/work -w /work tlb-sim
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build git curl zip unzip tar pkg-config \
    ca-certificates python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*
CMD ["bash"]
