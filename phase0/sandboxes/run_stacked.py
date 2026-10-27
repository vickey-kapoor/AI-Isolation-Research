"""Run the Phase 0 habitat with gVisor inside a Firecracker VM, and check it end to end.

Usage (needs root and /dev/kvm, plus both setups):
    ./sandboxes/setup_gvisor.sh ~/habitat-rootfs
    ./sandboxes/setup_firecracker.sh ~/habitat-fc
    sudo python3 -m sandboxes.run_stacked --kernel ~/habitat-fc/vmlinux --rootfs ~/habitat-fc/rootfs
"""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from .common import provision, run_habitat
from .stacked import StackedHabitat

# The probe runs inside gVisor inside the VM, so it should see what it saw
# under plain gVisor: loopback only, read-only root, unprivileged user.
EXPECTED = {
    "interfaces": ["lo"],
    "network_reachable": False,
    "root_writable": False,
    "tasks_writable": False,
    "outbox_writable": True,
    "uid": 65534,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel", type=Path, required=True)
    ap.add_argument("--rootfs", type=Path, required=True, help="base root filesystem folder with python3")
    ap.add_argument("--gvisor-dir", type=Path, default=Path("/usr/local/lib/gvisor"),
                    help="the unpacked gVisor release (runsc plus gvisor-bin/)")
    ap.add_argument("--work", type=Path)
    ap.add_argument("--firecracker", default="firecracker")
    ap.add_argument("--jailer", default="jailer")
    args = ap.parse_args()
    work = args.work or Path(tempfile.mkdtemp(prefix="habitat-stacked-"))

    p = provision(work, backend="stacked")
    habitat = StackedHabitat(work, args.kernel.resolve(), args.rootfs.resolve(), args.gvisor_dir.resolve(),
                             p.outbox_path, firecracker=args.firecracker, jailer=args.jailer)
    print("firecracker:", habitat.version())
    p.ledger.append("images", {
        "kernel_sha256": hashlib.sha256(args.kernel.read_bytes()).hexdigest(),
        "rootfs_sha256": hashlib.sha256(habitat.rootfs.read_bytes()).hexdigest(),
        "outbox_offset": habitat.outbox_offset,
    })

    probe = habitat.probe()
    print("configuration check:", json.dumps(probe))
    mismatches = {k: (probe.get(k), v) for k, v in EXPECTED.items() if probe.get(k) != v}

    report = run_habitat(p, habitat)
    report["firecracker_version"] = habitat.version()
    report["probe"] = probe
    (work / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print("results folder:", work)

    problems = []
    if mismatches:
        problems.append(f"configuration differs from plan (got, wanted): {mismatches}")
    if report["quarantined"] == 0:
        problems.append("no artefact reached quarantine")
    if report["leftovers"]:
        problems.append(f"state survived termination: {report['leftovers']}")
    for line in problems:
        print("PROBLEM:", line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
