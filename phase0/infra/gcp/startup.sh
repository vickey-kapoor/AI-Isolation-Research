#!/bin/bash
# Runs as root on first boot. Installs what Phase 0 needs, nothing else.
set -euo pipefail
if [ -f /var/lib/phase0-ready ]; then exit 0; fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y git docker.io python3-venv e2fsprogs
systemctl enable --now docker
touch /var/lib/phase0-ready
