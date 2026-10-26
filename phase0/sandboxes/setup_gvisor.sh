#!/usr/bin/env bash
# Install gVisor's runsc and build a minimal root filesystem for the agent.
# Works on any x86_64 or arm64 Linux machine; no KVM needed.
#
#   ./sandboxes/setup_gvisor.sh [ROOTFS_DIR]
#
# gVisor now ships as one tarball: runsc plus a gvisor-bin/ folder of helper
# binaries (the Sentry, the user-space kernel, is gvisor-bin/gvisor_sentry).
# runsc looks for gvisor-bin/ next to its own real path, so we install the
# whole tarball into one folder and symlink runsc onto the PATH.
#
# The rootfs is the official python:3.12-slim image, exported to a plain
# folder. runsc uses that folder directly; Docker is only used to fetch it.
set -euo pipefail

ROOTFS="${1:-$HOME/habitat-rootfs}"
RELEASE="${GVISOR_RELEASE:-20261019.0}"   # pinned, so every run uses the same build
ARCH="$(uname -m)"
URL="https://storage.googleapis.com/gvisor/releases/release/${RELEASE}/${ARCH}"
DEST=/usr/local/lib/gvisor

if ! command -v runsc >/dev/null; then
  tmp="$(mktemp -d)"
  ( cd "$tmp"
    curl -fsSLO "${URL}/gvisor.tar.bz2"
    curl -fsSLO "${URL}/gvisor.tar.bz2.sha512"
    sha512sum -c gvisor.tar.bz2.sha512      # refuse a download that doesn't match
    sudo mkdir -p "$DEST"
    sudo tar -xjf gvisor.tar.bz2 -C "$DEST"
    sudo ln -sf "$DEST/runsc" /usr/local/bin/runsc )
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
