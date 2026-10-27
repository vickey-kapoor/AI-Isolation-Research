"""Q2 experiment: run the verifier in its own gVisor sandbox and compare it with the in-process one.

Usage (needs root for runsc):
    sudo python3 -m sandboxes.run_verifier_box --rootfs /path/to/rootfs [--work DIR]

It feeds the same frames to both: every correct answer, plus frames that
must fail (empty, wrong size of padding, wrong answer, unknown form). The
verdicts must match exactly. It also times both and runs the configuration
check inside the verifier's box.
"""

import argparse
import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path

from airlock import frames
from airlock.forms import F1_FACTOR, TaskList, encode_f1
from airlock.verifier import check

from .common import PHASE0, PROGRAM_DIR, TASKS
from .verifier_box import SandboxedVerifier

EXPECTED = {"interfaces": ["lo"], "network_reachable": False, "root_writable": False,
            "outbox_writable": False, "uid": 65534}


def test_frames() -> list[bytes]:
    spec = importlib.util.spec_from_file_location("puzzle_program", PROGRAM_DIR / "puzzle_program.py")
    program = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(program)
    good = program.answers(json.loads(TASKS.read_text()))
    bad = [
        bytes(frames.FRAME_SIZE),                                                 # empty
        good[0][:-1] + b"\x01",                                                   # padding not zero
        frames.encode(frames.Frame(F1_FACTOR, encode_f1(0, [(2, 1)]))),            # wrong answer
        frames.encode(frames.Frame(9, b"\x00\x00")),                               # unapproved form
    ]
    return good + bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rootfs", type=Path, required=True)
    ap.add_argument("--work", type=Path)
    ap.add_argument("--runsc", default="runsc")
    ap.add_argument("--rounds", type=int, default=20, help="times to feed the whole set, for timing")
    args = ap.parse_args()
    work = args.work or Path(tempfile.mkdtemp(prefix="habitat-verifier-"))
    tasks = TaskList.load(TASKS)
    batch = test_frames()

    box = SandboxedVerifier(work, args.rootfs.resolve(), runsc=args.runsc)
    probe = box.probe()
    print("configuration check:", json.dumps(probe))
    mismatches = {k: (probe.get(k), v) for k, v in EXPECTED.items() if probe.get(k) != v}

    t0 = time.monotonic()
    local = [check(f, tasks) for _ in range(args.rounds) for f in batch]
    local_us = (time.monotonic() - t0) / len(local) * 1e6

    t0 = time.monotonic()
    box.start()
    boxed = [box(batch[0])]
    start_s = time.monotonic() - t0
    procs = box.host_processes()
    t0 = time.monotonic()
    boxed = [box(f) for _ in range(args.rounds) for f in batch]
    boxed_us = (time.monotonic() - t0) / len(boxed) * 1e6
    lines = box.code_lines()
    box.stop()

    report = {
        "verifier_code_lines": lines,
        "frames_checked": len(boxed),
        "verdicts_match": local == boxed,
        "passed": sum(v is not None for v in boxed[:len(batch)]),
        "failed": sum(v is None for v in boxed[:len(batch)]),
        "in_process_us_per_frame": round(local_us, 1),
        "boxed_us_per_frame": round(boxed_us, 1),
        "box_start_seconds": round(start_s, 3),
        "host_processes": procs,
        "leftovers": box.leftovers(),
        "probe": probe,
    }
    print(json.dumps(report, indent=2))
    (work / "verifier-report.json").write_text(json.dumps(report, indent=2))
    print("results folder:", work)

    problems = []
    if mismatches:
        problems.append(f"configuration differs from plan (got, wanted): {mismatches}")
    if not report["verdicts_match"]:
        problems.append("the boxed verifier disagreed with the in-process one")
    if report["leftovers"]:
        problems.append(f"state survived: {report['leftovers']}")
    for line in problems:
        print("PROBLEM:", line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
