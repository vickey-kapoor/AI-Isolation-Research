"""Run the Phase 0 habitat inside a Firecracker microVM and check it end to end.

Usage (needs root and /dev/kvm):
    sudo python3 -m sandboxes.run_firecracker --kernel VMLINUX --rootfs DIR [--work DIR]

See sandboxes/setup_firecracker.sh for how to get Firecracker, a guest kernel
and the base root filesystem.
"""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from .common import provision, run_habitat
from .firecracker import FirecrackerHabitat

# Inside the VM the program runs as root: the wall is the VM itself, and the
# VMM outside runs as an unprivileged user in a jail. The outbox is the VM's
# second disk.
EXPECTED = {
    "interfaces": ["lo"],
    "network_reachable": False,
    "root_writable": False,
    "tasks_writable": False,
    "outbox_writable": True,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel", type=Path, required=True)
    ap.add_argument("--rootfs", type=Path, required=True, help="base root filesystem folder with python3")
    ap.add_argument("--work", type=Path)
    ap.add_argument("--firecracker", default="firecracker")
    ap.add_argument("--jailer", default="jailer")
    args = ap.parse_args()
    work = args.work or Path(tempfile.mkdtemp(prefix="habitat-firecracker-"))

    p = provision(work, backend="firecracker")
    habitat = FirecrackerHabitat(work, args.kernel.resolve(), args.rootfs.resolve(), p.outbox_path,
                                 firecracker=args.firecracker, jailer=args.jailer)
    print("firecracker:", habitat.version())
    p.ledger.append("images", {
        "kernel_sha256": hashlib.sha256(args.kernel.read_bytes()).hexdigest(),
        "rootfs_sha256": hashlib.sha256(habitat.rootfs.read_bytes()).hexdigest(),
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
