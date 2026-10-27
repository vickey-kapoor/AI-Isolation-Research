"""The verifier in a gVisor sandbox of its own (Q2).

The gate hands each frame to a separate verifier process and gets back a
4-byte verdict (see airlock/verifier.py). Here that process runs under
gVisor with:

  no network            --network=none, loopback only
  nothing writable      read-only root, no writable mounts at all, not even /tmp
  only what it needs    the four airlock files it uses and the task list, read-only
  uid 65534, no caps    as for the puzzle program
  one pipe in, one out  standard input for frames, standard output for verdicts

If a crafted frame ever got the better of the verifier, it would be inside
this box, with nothing to reach and nothing to write. What it could still do
is give a wrong verdict, which only a second, independent verifier can catch.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from airlock import frames
from airlock.verifier import decode_verdict

from . import inventory
from .common import PHASE0, TASKS
from .gvisor import SANDBOX_DIR

VERIFIER_FILES = ("__init__.py", "frames.py", "forms.py", "verifier.py")


def _spec(rootfs: Path, code: Path, args: list[str]) -> dict:
    return {
        "ociVersion": "1.0.0",
        "process": {
            "terminal": False,
            "user": {"uid": 65534, "gid": 65534},
            "args": args,
            "env": ["PATH=/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE=1"],
            "cwd": "/verifier",
            "capabilities": {k: [] for k in ("bounding", "effective", "inheritable", "permitted", "ambient")},
            "noNewPrivileges": True,
        },
        "root": {"path": str(rootfs), "readonly": True},
        "hostname": "verifier",
        "mounts": [
            {"destination": "/proc", "type": "proc", "source": "proc"},
            {"destination": "/dev", "type": "tmpfs", "source": "tmpfs", "options": ["nosuid", "mode=755", "ro"]},
            {"destination": "/verifier/airlock", "type": "bind", "source": str(code), "options": ["rbind", "ro"]},
            {"destination": "/verifier/tasks.json", "type": "bind", "source": str(TASKS), "options": ["bind", "ro"]},
            {"destination": "/verifier/probe.py", "type": "bind", "source": str(SANDBOX_DIR / "probe.py"),
             "options": ["bind", "ro"]},
        ],
        "linux": {"namespaces": [{"type": t} for t in ("pid", "ipc", "uts", "mount", "network")]},
    }


class SandboxedVerifier:
    def __init__(self, work: Path, rootfs: Path, runsc: str = "runsc"):
        self.work = work
        self.state = work / "verifier-state"
        self.code = work / "verifier-code"
        self.bundles = work / "verifier-bundles"
        self.id = f"verifier-{os.getpid()}"
        self.base = [runsc, f"--root={self.state}", "--network=none"]
        self.rootfs = rootfs
        self.code.mkdir(parents=True, exist_ok=True)
        for name in VERIFIER_FILES:  # only what the verifier imports
            shutil.copy2(PHASE0 / "airlock" / name, self.code / name)
        self.proc = False

    def _bundle(self, name: str, args: list[str]) -> Path:
        bundle = self.bundles / name
        bundle.mkdir(parents=True, exist_ok=True)
        (bundle / "config.json").write_text(json.dumps(_spec(self.rootfs, self.code, args), indent=2))
        return bundle

    def code_lines(self) -> int:
        return sum(len((self.code / n).read_text().splitlines()) for n in VERIFIER_FILES)

    def probe(self) -> dict:
        bundle = self._bundle("probe", ["python3", "/verifier/probe.py", "/verifier/tasks.json"])
        out = subprocess.run([*self.base, "run", f"--bundle={bundle}", f"{self.id}-probe"],
                             capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            raise RuntimeError(f"probe failed: {out.stderr.strip()}")
        return json.loads(out.stdout.strip().splitlines()[-1])

    def start(self) -> None:
        bundle = self._bundle("verifier", ["python3", "-m", "airlock.verifier", "/verifier/tasks.json"])
        # create + start, as for the habitat, so no unconfined runsc process stays
        # around to relay the pipes: they're handed straight to the sandbox.
        r_in, self.w_in = os.pipe()
        self.r_out, w_out = os.pipe()
        subprocess.run([*self.base, "create", f"--bundle={bundle}", self.id], check=True,
                       stdin=r_in, stdout=w_out, stderr=subprocess.DEVNULL)
        os.close(r_in)
        os.close(w_out)
        subprocess.run([*self.base, "start", self.id], check=True)
        self.proc = True

    def __call__(self, raw: bytes) -> tuple[int, int] | None:
        assert len(raw) == frames.FRAME_SIZE
        os.write(self.w_in, raw)
        reply = b""
        while len(reply) < 4:
            chunk = os.read(self.r_out, 4 - len(reply))
            if not chunk:
                break
            reply += chunk
        return decode_verdict(reply)

    def leftovers(self) -> list[str]:
        left = [str(d) for d in (self.state, self.code, self.bundles) if d.exists()]
        if inventory.host_processes(self.id):
            left.append("processes")
        return left

    def host_processes(self) -> list[dict]:
        return inventory.host_processes(self.id)

    def stop(self) -> None:
        if self.proc:
            os.close(self.w_in)
            os.close(self.r_out)
        subprocess.run([*self.base, "kill", self.id, "KILL"], capture_output=True)
        subprocess.run([*self.base, "delete", "--force", self.id], capture_output=True)
        with open("/proc/self/mountinfo") as f:
            mounts = [line.split()[4] for line in f if line.split()[4].startswith(str(self.state))]
        for m in sorted(mounts, reverse=True):
            subprocess.run(["umount", "-l", m], capture_output=True)
        for d in (self.state, self.code, self.bundles):
            shutil.rmtree(d, ignore_errors=True)
