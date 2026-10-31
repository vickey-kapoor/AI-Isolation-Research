"""Put several backends' reports side by side, as one Markdown page.

Usage:
    python3 -m sandboxes.compare REPORT.json [REPORT.json ...] [--out comparison.md]

Each REPORT.json is the report.json a run_* script leaves in its results
folder. With --control, the no-sandbox control backend is run first, here
and now, and put in the first column.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROWS = [
    ("Network interfaces inside", lambda r: ", ".join(r.get("probe", {}).get("interfaces", [])) or "not checked"),
    ("Internet reachable", lambda r: _yn(r.get("probe", {}).get("network_reachable"))),
    ("Root filesystem writable", lambda r: _yn(r.get("probe", {}).get("root_writable"))),
    ("Outbox writable", lambda r: _yn(r.get("probe", {}).get("outbox_writable"))),
    ("User inside", lambda r: str(r.get("probe", {}).get("uid", "not checked"))),
    ("Start until first answer (s)", lambda r: str(r["start_seconds"])),
    ("Kill and destroy (s)", lambda r: str(r["kill_seconds"])),
    ("Answers reaching quarantine", lambda r: str(r["quarantined"])),
    ("Leftovers after destroy", lambda r: ", ".join(r["leftovers"]) or "none"),
    ("Host kernel", lambda r: r["trusts"]["host_kernel"]),
    ("Code the walls are built from", lambda r: _size(sum(c["bytes"] for c in r["trusts"]["components"]))
     if r["trusts"]["components"] else "none (no wall)"),
    ("Host processes while running", lambda r: str(len(r["host_processes"]))),
    ("... with a system call filter", lambda r: _count(r, lambda p: p["seccomp"] == "filter")),
    ("... running as host user 0", lambda r: _count(r, lambda p: p["uid"] == 0)),
    ("... in their own network namespace", lambda r: _count(r, lambda p: "net" in p["own_namespaces"])),
]


def _yn(v) -> str:
    return "not checked" if v is None else ("yes" if v else "no")


def _size(n: int) -> str:
    return f"{n / 1_000_000:.1f} MB"


def _count(r: dict, pred) -> str:
    procs = r["host_processes"]
    return f"{sum(1 for p in procs if pred(p))} of {len(procs)}"


def render(reports: list[dict]) -> str:
    names = [r["backend"] for r in reports]
    out = ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for label, get in ROWS:
        out.append(f"| {label} | " + " | ".join(get(r) for r in reports) + " |")
    out += ["", "### What each one's walls are built from", ""]
    out += ["| Backend | Part | Size | sha256 (first 16) |", "|---|---|---|---|"]
    for r in reports:
        for c in r["trusts"]["components"]:
            out.append(f"| {r['backend']} | {c['role']} | {_size(c['bytes'])} | `{c['sha256'][:16]}` |")
    out += ["", "### Host processes while the habitat runs", ""]
    out += ["| Backend | Process | Host user | System call filter | Can gain privileges | Own namespaces |",
            "|---|---|---|---|---|---|"]
    for r in reports:
        for p in r["host_processes"]:
            out.append(f"| {r['backend']} | {p['name']} | {p['uid']} | {p['seccomp']} | "
                       f"{'no' if p['no_new_privs'] else 'yes'} | {', '.join(p['own_namespaces']) or 'none'} |")
    out += ["", "One run of each. Times are rough, not a benchmark. Sizes are of the files on disk, "
            "a rough measure of how much code has to be right, not a security score. Every backend "
            "also relies on the host kernel listed above."]
    return "\n".join(out) + "\n"


def run_control() -> dict:
    from .common import provision, run_habitat
    from .process import ProcessHabitat
    p = provision(Path(tempfile.mkdtemp(prefix="habitat-process-")), backend="process")
    return run_habitat(p, ProcessHabitat(p.outbox_path))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reports", nargs="*", type=Path)
    ap.add_argument("--control", action="store_true", help="also run the no-sandbox control here")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    reports = ([run_control()] if args.control else []) + [json.loads(p.read_text()) for p in args.reports]
    if not reports:
        ap.error("no reports given")
    page = render(reports)
    print(page)
    if args.out:
        args.out.write_text(page)
    return 0


if __name__ == "__main__":
    sys.exit(main())
