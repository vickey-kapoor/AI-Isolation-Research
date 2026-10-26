#!/usr/bin/env bash
# Install gVisor's runsc and build a minimal root filesystem for the agent.
# Works on any x86_64 or arm64 Linux machine with Docker; no KVM needed.
#
#   ./sandboxes/setup_gvisor.sh [ROOTFS_DIR]
#
# The rootfs is the official python:3.12-slim image, exported to a plain
# folder. runsc uses that folder directly; Docker is only used to fetch it.
set -euo pipefail

ROOTFS="${1:-$HOME/habitat-rootfs}"
ARCH="$(uname -m)"
URL="https://storage.googleapis.com/gvisor/releases/release/latest/${ARCH}"

if ! command -v runsc >/dev/null; then
  tmp="$(mktemp -d)"
  ( cd "$tmp"
    curl -fsSLO "${URL}/runsc"
    curl -fsSLO "${URL}/runsc.sha512"
    sha512sum -c runsc.sha512          # refuse a download that doesn't match
    chmod a+rx runsc
    sudo mv runsc /usr/local/bin/runsc )
  rm -rf "$tmp"
fi
runsc --version | head -1

if [ ! -x "$ROOTFS/usr/local/bin/python3" ]; then
  mkdir -p "$ROOTFS"
  cid="$(docker create python:3.12-slim)"
  docker export "$cid" | sudo tar -x -C "$ROOTFS"
  docker rm "$cid" >/dev/null
fi
echo "rootfs ready at $ROOTFS"
