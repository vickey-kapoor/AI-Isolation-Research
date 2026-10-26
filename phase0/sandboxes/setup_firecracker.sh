#!/usr/bin/env bash
# Install Firecracker and its jailer, fetch a guest kernel, and build the
# base root filesystem. Needs a Linux x86_64 or arm64 machine with /dev/kvm.
#
#   ./sandboxes/setup_firecracker.sh [OUT_DIR]
#
# Writes OUT_DIR/vmlinux (the guest kernel) and OUT_DIR/rootfs/ (a folder
# with python3). The habitat's own disk image is built from that folder at
# sealing time, with the puzzle program and tasks baked in.
set -euo pipefail

OUT="${1:-$HOME/habitat-firecracker}"
ARCH="$(uname -m)"
FC_VERSION="${FC_VERSION:-v1.15.0}"      # pinned
KERNEL_KEY="${KERNEL_KEY:-firecracker-ci/v1.15/${ARCH}/vmlinux-6.1.155}"
mkdir -p "$OUT"

if [ ! -e /dev/kvm ]; then
  echo "No /dev/kvm here. Firecracker needs a machine with KVM (see PLAN.md section 5)." >&2
  exit 1
fi

if ! command -v firecracker >/dev/null; then
  tmp="$(mktemp -d)"
  ( cd "$tmp"
    base="https://github.com/firecracker-microvm/firecracker/releases/download/${FC_VERSION}"
    tgz="firecracker-${FC_VERSION}-${ARCH}.tgz"
    curl -fsSLO "${base}/${tgz}"
    curl -fsSLO "${base}/${tgz}.sha256.txt"
    sha256sum -c "${tgz}.sha256.txt"        # refuse a download that doesn't match
    tar -xzf "$tgz"
    sudo install -m 0755 "release-${FC_VERSION}-${ARCH}/firecracker-${FC_VERSION}-${ARCH}" /usr/local/bin/firecracker
    sudo install -m 0755 "release-${FC_VERSION}-${ARCH}/jailer-${FC_VERSION}-${ARCH}" /usr/local/bin/jailer )
  rm -rf "$tmp"
fi
firecracker --version | head -1

# The guest kernel: a minimal build published by the Firecracker project for its own CI.
if [ ! -s "$OUT/vmlinux" ]; then
  curl -fsSL -o "$OUT/vmlinux" "https://s3.amazonaws.com/spec.ccfc.min/${KERNEL_KEY}"
fi
sha256sum "$OUT/vmlinux"

if [ ! -x "$OUT/rootfs/usr/local/bin/python3" ]; then
  mkdir -p "$OUT/rootfs"
  cid="$(sudo docker create python:3.12-slim)"
  sudo docker export "$cid" | sudo tar -x -C "$OUT/rootfs"
  sudo docker rm "$cid" >/dev/null
fi
echo "ready: kernel $OUT/vmlinux, rootfs $OUT/rootfs"
