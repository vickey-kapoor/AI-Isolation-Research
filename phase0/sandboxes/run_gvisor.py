"""Run the Phase 0 habitat under gVisor and check it end to end.

Usage (needs root for runsc, and a root filesystem with python3 in it):
    sudo python3 -m sandboxes.run_gvisor --rootfs /path/to/rootfs [--work DIR]

See sandboxes/setup_gvisor.sh for how to install runsc and build the rootfs.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .common import provision, run_habitat
from .gvisor import GVisorHabitat

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
    ap.add_argument("--rootfs", type=Path, required=True)
    ap.add_argument("--work", type=Path)
    ap.add_argument("--runsc", default="runsc")
    args = ap.parse_args()
    work = args.work or Path(tempfile.mkdtemp(prefix="habitat-gvisor-"))

    p = provision(work, backend="gvisor")
    habitat = GVisorHabitat(work, args.rootfs.resolve(), p.outbox_path, runsc=args.runsc)
    print("runsc:", habitat.version())

    probe = habitat.probe()
    print("configuration check:", json.dumps(probe))
    mismatches = {k: (probe.get(k), v) for k, v in EXPECTED.items() if probe.get(k) != v}

    report = run_habitat(p, habitat)
    report["runsc_version"] = habitat.version()
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
