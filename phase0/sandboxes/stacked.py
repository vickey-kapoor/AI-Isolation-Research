"""Stacked backend: gVisor inside a Firecracker VM, with the puzzle program inside gVisor.

    host machine (Linux)
    └─ Firecracker, in its jail                      wall 1: hardware virtualization
       └─ small VM with its own Linux kernel
          └─ gVisor (runsc), no network              wall 2: a user-space kernel
             └─ puzzle program

The two walls are different kinds of thing. Firecracker relies on KVM and
the CPU; gVisor relies on its own kernel (the Sentry) and a filtered set of
the VM kernel's system calls. A flaw in one doesn't automatically carry
over to the other, which is what PRD R-B4 (independent layers) asks for.

Everything is baked in at sealing time, as in the plain Firecracker backend.
The VM's root disk now also holds runsc and a ready-made gVisor config.

The outbox needs one extra step. gVisor can only hand the puzzle program
ordinary files, not a raw disk, so the VM's second disk holds a tiny ext2
filesystem with a single file, outbox.bin, in one contiguous run of blocks.
The VM mounts that disk and gVisor passes the file in. Outside, the gate
reads those blocks straight from the disk image at a fixed offset, found
once at sealing. ext2 has no journal and the file is preallocated, so
writes land in place.
"""

import json
import shutil
import subprocess
from pathlib import Path

from airlock import outbox

from .firecracker import FirecrackerHabitat, build_rootfs
from .gvisor import _spec

BLOCK = 4096

STACKED_INIT = """#!/bin/sh
# PID 1 inside the VM: prepare the few mounts runsc needs, then hand over to gVisor.
mount -t proc proc /proc 2>/dev/null
mount -t devtmpfs devtmpfs /dev 2>/dev/null
mount -t sysfs sysfs /sys 2>/dev/null
mount -t tmpfs tmpfs /tmp
mount -t ext2 -o noatime /dev/vdb /mnt/outbox
{run}
"""

# The habitat run has no console, so it simply hands over to runsc. The
# configuration check has a console, so if runsc fails there it also prints
# the end of runsc's own logs, which is the only way to see why from outside.
RUNSC = "runsc --root=/tmp/runsc --network=none --ignore-cgroups"
RUN = {
    "init": f"exec {RUNSC} run --bundle /habitat/bundles/init init",
    "probe-init": f"""mkdir -p /tmp/runsc-logs
{RUNSC} --debug --debug-log=/tmp/runsc-logs/ run --bundle /habitat/bundles/probe-init probe-init \\
  || for f in /tmp/runsc-logs/*; do echo "== $f"; tail -n 25 "$f"; done""",
}

INNER_ARGS = {
    "init": ["python3", "/habitat/program/puzzle_program.py", "/habitat/tasks.json",
             "/habitat/outbox.bin", "--rounds", "0"],
    "probe-init": ["python3", "/habitat/probe.py"],
}


def build_outbox_disk(slots: int, out: Path) -> int:
    """Make the ext2 disk holding outbox.bin. Returns the byte offset of its first slot."""
    size = slots * outbox.FRAME_SIZE
    staging = out.with_suffix(".d")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    # Filled with 0xFF, not zeros: newer mkfs.ext2 stores an all-zero file as
    # a hole with no blocks at all. The real zeros are written in below.
    (staging / "outbox.bin").write_bytes(b"\xff" * size)
    (staging / "outbox.bin").chmod(0o666)  # gVisor runs the puzzle program as user 65534
    out.unlink(missing_ok=True)
    subprocess.run(["truncate", "-s", "4M", str(out)], check=True)
    subprocess.run(["mkfs.ext2", "-q", "-F", "-b", str(BLOCK), "-d", str(staging), str(out)], check=True)
    shutil.rmtree(staging)

    blocks = []
    for i in range((size + BLOCK - 1) // BLOCK):
        res = subprocess.run(["debugfs", "-R", f"bmap /outbox.bin {i}", str(out)],
                             capture_output=True, text=True, check=True)
        blocks.append(int(res.stdout.split()[-1]))
    if blocks != list(range(blocks[0], blocks[0] + len(blocks))) or blocks[0] == 0:
        raise RuntimeError(f"outbox.bin is not one contiguous run of blocks: {blocks}")
    offset = blocks[0] * BLOCK
    with open(out, "r+b") as f:  # every slot starts empty
        f.seek(offset)
        f.write(bytes(size))
    return offset


class StackedHabitat(FirecrackerHabitat):
    name = "stacked"

    def __init__(self, work: Path, kernel: Path, base_rootfs: Path, gvisor_dir: Path,
                 outbox_path: Path, **kw):
        self.gvisor_dir = gvisor_dir
        self.slots = outbox.slot_count(outbox_path)
        outbox_path.unlink()  # replaced by the disk below
        disk = work / "outbox-disk.img"
        super().__init__(work, kernel, base_rootfs, disk, **kw)
        self.outbox_offset = build_outbox_disk(self.slots, disk)
        self.mem_mib = 1024  # gVisor plus Python needs more than the plain VM

    def reader(self) -> outbox.Reader:
        return outbox.Reader(self.outbox_path, offset=self.outbox_offset, slots=self.slots)

    def _build_rootfs(self, base: Path) -> None:
        build_rootfs(base, self.rootfs, size_mb=1024, extra=self._add_gvisor)

    def _add_gvisor(self, staging: Path) -> None:
        dest = staging / "usr/local/lib/gvisor"
        shutil.copytree(self.gvisor_dir, dest, symlinks=True, dirs_exist_ok=True)
        link = staging / "usr/local/bin/runsc"
        link.unlink(missing_ok=True)
        link.symlink_to("/usr/local/lib/gvisor/runsc")
        (staging / "mnt/outbox").mkdir(parents=True, exist_ok=True)
        hab = staging / "habitat"
        # gVisor mounts the outbox file over this spot. The VM's root disk is
        # read-only, so the spot has to exist before sealing.
        (hab / "outbox.bin").touch()
        for name, args in INNER_ARGS.items():
            bundle = hab / "bundles" / name
            bundle.mkdir(parents=True, exist_ok=True)
            spec = _spec(Path("/"), args, Path("/mnt/outbox/outbox.bin"),
                         program_dir=Path("/habitat/program"), tasks=Path("/habitat/tasks.json"),
                         probe=Path("/habitat/probe.py"))
            (bundle / "config.json").write_text(json.dumps(spec, indent=2))
            (hab / name).write_text(STACKED_INIT.format(run=RUN[name]))
            (hab / name).chmod(0o755)
