"""Firecracker backend: the puzzle program runs inside a small virtual machine.

How Firecracker isolates, in one paragraph: the puzzle program gets its own
Linux kernel running in a virtual machine. The CPU's virtualization features
(driven by KVM, part of the host's Linux kernel) keep that VM's memory and
instructions apart from the host. Firecracker itself is the VMM: a small
program on the host that pretends to be the VM's hardware. It offers very
few devices on purpose: here, two disks and nothing else.

Firecracker runs under the jailer, its companion tool. The jailer starts
Firecracker in an empty folder it can't leave (a chroot), as an unprivileged
user, in its own namespaces, with a system call filter. So even the VMM, if
something went wrong in it, has very little it can reach on the host.

What the VM gets:
  disk 1 (vda)   read-only root filesystem with python3, the puzzle program
                 and the frozen task list baked in at sealing time
  disk 2 (vdb)   the outbox, as a raw block device of fixed-size slots
  nothing else   no network device, no shared folders, no vsock

Unlike gVisor there are no shared folders at all. Firecracker has no way to
share a host folder with the VM, so the inputs have to be baked into a disk
image before the VM starts. That happens to match the PRD's "inputs fixed
before sealing" very closely.
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .common import PROGRAM_DIR, TASKS

SANDBOX_DIR = Path(__file__).resolve().parent
JAIL_UID = JAIL_GID = 65534

INIT = """#!/bin/sh
# PID 1 inside the VM. When this exits, the kernel panics and reboots,
# and Firecracker (started with reboot=k panic=1) exits too.
mount -t proc proc /proc 2>/dev/null
mount -t devtmpfs devtmpfs /dev 2>/dev/null
exec python3 {script}
"""

BOOT_ARGS = "reboot=k panic=1 pci=off ro i8042.noaux i8042.nomux i8042.dumbkbd"


def build_rootfs(base: Path, out: Path, size_mb: int = 512) -> None:
    """Bake the frozen inputs into a read-only ext4 image (PRD R-O1)."""
    staging = out.with_suffix(".d")
    shutil.rmtree(staging, ignore_errors=True)
    subprocess.run(["cp", "-a", f"{base}/.", str(staging)], check=True)
    hab = staging / "habitat"
    (hab / "program").mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROGRAM_DIR / "puzzle_program.py", hab / "program" / "puzzle_program.py")
    shutil.copy2(TASKS, hab / "tasks.json")
    shutil.copy2(SANDBOX_DIR / "probe.py", hab / "probe.py")
    for name, script in {
        "init": "/habitat/program/puzzle_program.py /habitat/tasks.json /dev/vdb --rounds 0",
        "probe-init": "/habitat/probe.py /dev/vdb",
    }.items():
        (hab / name).write_text(INIT.format(script=script))
        (hab / name).chmod(0o755)
    out.unlink(missing_ok=True)
    subprocess.run(["truncate", "-s", f"{size_mb}M", str(out)], check=True)
    subprocess.run(["mkfs.ext4", "-q", "-F", "-d", str(staging), str(out)], check=True)
    shutil.rmtree(staging)


class FirecrackerHabitat:
    name = "firecracker"

    def __init__(self, work: Path, kernel: Path, base_rootfs: Path, outbox_path: Path,
                 firecracker: str = "firecracker", jailer: str = "jailer"):
        self.work = work
        self.kernel = kernel
        self.outbox_path = outbox_path
        self.firecracker = shutil.which(firecracker) or firecracker
        self.jailer = shutil.which(jailer) or jailer
        self.rootfs = work / "rootfs.ext4"
        build_rootfs(base_rootfs, self.rootfs)
        self.jail_base = work / "jail"
        self.proc: subprocess.Popen | None = None
        self.vm_id = ""

    def version(self) -> str:
        out = subprocess.run([self.firecracker, "--version"], capture_output=True, text=True)
        return out.stdout.splitlines()[0] if out.stdout else "unknown"

    def _chroot(self, vm_id: str) -> Path:
        return self.jail_base / Path(self.firecracker).name / vm_id / "root"

    def _stage(self, vm_id: str, init: str, console: bool) -> Path:
        """Put everything the VM needs inside the jail folder, owned by the jail user."""
        root = self._chroot(vm_id)
        root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.kernel, root / "vmlinux")
        os.link(self.rootfs, root / "rootfs.ext4")
        # A hard link: the VM's second disk and the file the gate reads are the same file.
        os.link(self.outbox_path, root / "outbox.bin")
        boot_args = BOOT_ARGS + f" init=/habitat/{init}"
        boot_args += " console=ttyS0 quiet" if console else " 8250.nr_uarts=0"
        config = {
            "boot-source": {"kernel_image_path": "vmlinux", "boot_args": boot_args},
            "drives": [
                {"drive_id": "rootfs", "path_on_host": "rootfs.ext4", "is_root_device": True, "is_read_only": True},
                {"drive_id": "outbox", "path_on_host": "outbox.bin", "is_root_device": False, "is_read_only": False},
            ],
            "machine-config": {"vcpu_count": 1, "mem_size_mib": 256},
            "network-interfaces": [],
        }
        (root / "config.json").write_text(json.dumps(config, indent=2))
        for p in (root / "vmlinux", root / "rootfs.ext4", root / "outbox.bin", root / "config.json"):
            os.chown(p, JAIL_UID, JAIL_GID)
        return root

    def _jailer_cmd(self, vm_id: str) -> list[str]:
        return [self.jailer, "--id", vm_id, "--exec-file", self.firecracker,
                "--uid", str(JAIL_UID), "--gid", str(JAIL_GID),
                "--chroot-base-dir", str(self.jail_base),
                "--", "--config-file", "config.json", "--no-api"]

    def probe(self) -> dict:
        """Boot a VM with the habitat's settings that runs the configuration check and exits."""
        vm_id = f"probe-{os.getpid()}"
        self._stage(vm_id, "probe-init", console=True)
        try:
            out = subprocess.run(self._jailer_cmd(vm_id), capture_output=True, text=True, timeout=120)
        finally:
            self._destroy(vm_id)
        for line in reversed(out.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                return json.loads(line)
        raise RuntimeError(f"probe printed no result: {out.stdout[-2000:]} {out.stderr[-2000:]}")

    def start(self) -> None:
        self.vm_id = f"habitat-{os.getpid()}"
        self._stage(self.vm_id, "init", console=False)
        # No console and no stdio: the VM has no serial path to the outside.
        self.proc = subprocess.Popen(self._jailer_cmd(self.vm_id), stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Wait until the puzzle program has written its first slot, or give up.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and self.proc.poll() is None:
            with open(self.outbox_path, "rb") as f:
                if any(f.read(256)):
                    return
            time.sleep(0.02)
        raise RuntimeError("the VM did not start writing its outbox")

    def _destroy(self, vm_id: str) -> None:
        shutil.rmtree(self.jail_base / Path(self.firecracker).name / vm_id, ignore_errors=True)
        for cg in Path("/sys/fs/cgroup").glob(f"**/{vm_id}"):
            try:
                cg.rmdir()
            except OSError:
                pass

    def kill_and_destroy(self) -> None:
        """Outside-only. Stops the VMM process; the VM has no say in it."""
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        self._destroy(self.vm_id)
        self.rootfs.unlink(missing_ok=True)
        self.outbox_path.unlink(missing_ok=True)

    def leftovers(self) -> list[str]:
        left = []
        if (self.jail_base / Path(self.firecracker).name / self.vm_id).exists():
            left.append("jail folder")
        if self.rootfs.exists():
            left.append("rootfs image")
        if self.outbox_path.exists():
            left.append("outbox file")
        if any(Path("/sys/fs/cgroup").glob(f"**/{self.vm_id}")):
            left.append("cgroup")
        procs = subprocess.run(["pgrep", "-f", self.vm_id], capture_output=True, text=True).stdout.split()
        procs = [p for p in procs if int(p) != os.getpid()]
        if procs:
            left.append(f"processes {procs}")
        with open("/proc/self/mountinfo") as f:
            mounts = [line.split()[4] for line in f if str(self.work) in line.split()[4]]
        left += [f"mount {m}" for m in mounts]
        return left
