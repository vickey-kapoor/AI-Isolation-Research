"""What each sandbox relies on, measured on the machine it runs on (plan Q4).

Two kinds of measurement, both read from outside, neither needing anything
from the puzzle program:

  components       the files each wall is built from, with their size and
                   fingerprint. Size is a rough proxy for how much code has
                   to be right. It is not a security score.
  host processes   the processes the habitat shows on the host while it
                   runs, and how each is confined: which user it runs as,
                   whether it has a system call filter (seccomp), whether it
                   can gain privileges, which capabilities it holds, and
                   which namespaces it has apart from the host's.

The host's own Linux kernel sits under every backend. It is recorded by
version only: it is the one thing none of them can do without.
"""

import hashlib
import os
import platform
from pathlib import Path

SECCOMP_MODES = {"0": "none", "1": "strict", "2": "filter"}


def component(role: str, path: Path) -> dict:
    """Size and fingerprint of one file, or the total of a folder of files."""
    path = Path(path).resolve()
    files = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
    digest = hashlib.sha256()
    size = 0
    for f in files:
        data = f.read_bytes()
        size += len(data)
        digest.update(f.relative_to(path).as_posix().encode() if path.is_dir() else b"")
        digest.update(data)
    return {"role": role, "path": str(path), "files": len(files), "bytes": size,
            "sha256": digest.hexdigest()}


def host_kernel() -> str:
    return platform.release()


def _status(pid: str) -> dict:
    fields = {}
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            key, _, value = line.partition(":")
            fields[key] = value.strip()
    return fields


def host_processes(marker: str) -> list[dict]:
    """Every process on the host whose command line mentions the marker, except this one."""
    found = []
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            with open(f"/proc/{entry.name}/cmdline", "rb") as f:
                cmdline = f.read().replace(b"\0", b" ").decode(errors="replace")
            if marker not in cmdline:
                continue
            st = _status(entry.name)
            ns = {k: os.readlink(f"/proc/{entry.name}/ns/{k}") != os.readlink(f"/proc/self/ns/{k}")
                  for k in ("user", "net", "mnt", "pid")}
        except OSError:
            continue  # the process ended while we looked
        found.append({
            "name": st.get("Name", "?"),
            "uid": int(st.get("Uid", "-1").split()[0]),
            "seccomp": SECCOMP_MODES.get(st.get("Seccomp", ""), "unknown"),
            "no_new_privs": st.get("NoNewPrivs") == "1",
            "capabilities": st.get("CapEff", "?"),
            "own_namespaces": sorted(k for k, own in ns.items() if own),
        })
    return sorted(found, key=lambda p: p["name"])
