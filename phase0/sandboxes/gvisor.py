"""gVisor backend: the toy agent runs under runsc with no network.

How gVisor isolates, in one paragraph: a normal container shares the host's
Linux kernel, so every system call the program makes goes straight to it.
Under gVisor, a user-space kernel called the Sentry answers those system
calls itself. The Sentry then uses only a small, filtered set of host system
calls. The host kernel is still underneath, but far less of it is exposed.

We drive runsc directly with a hand-written OCI bundle (a folder holding a
config.json and a root filesystem) rather than going through Docker. That
keeps Docker out of the trusted base and puts every setting where we can
read it.

Settings that matter:
  --network=none        the sandbox gets loopback only, no interfaces out
  root.readonly         the agent can't change its own filesystem
  three bind mounts     agent code (read-only), tasks (read-only), outbox (read-write)
  uid 65534, no caps    the agent runs as "nobody" with no special privileges
  --root=<work>/state   all runsc state lives in one folder we delete at the end
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from .common import AGENT_DIR, TASKS

SANDBOX_DIR = Path(__file__).resolve().parent


def _spec(rootfs: Path, args: list[str], outbox_path: Path) -> dict:
    return {
        "ociVersion": "1.0.0",
        "process": {
            "terminal": False,
            "user": {"uid": 65534, "gid": 65534},
            "args": args,
            "env": ["PATH=/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE=1"],
            "cwd": "/",
            "capabilities": {k: [] for k in ("bounding", "effective", "inheritable", "permitted", "ambient")},
            "noNewPrivileges": True,
        },
        "root": {"path": str(rootfs), "readonly": True},
        "hostname": "habitat",
        "mounts": [
            {"destination": "/proc", "type": "proc", "source": "proc"},
            {"destination": "/dev", "type": "tmpfs", "source": "tmpfs", "options": ["nosuid", "mode=755"]},
            {"destination": "/tmp", "type": "tmpfs", "source": "tmpfs", "options": ["nosuid", "nodev"]},
            {"destination": "/habitat/agent", "type": "bind", "source": str(AGENT_DIR), "options": ["rbind", "ro"]},
            {"destination": "/habitat/probe.py", "type": "bind", "source": str(SANDBOX_DIR / "probe.py"), "options": ["bind", "ro"]},
            {"destination": "/habitat/tasks.json", "type": "bind", "source": str(TASKS), "options": ["bind", "ro"]},
            {"destination": "/habitat/outbox.bin", "type": "bind", "source": str(outbox_path), "options": ["bind", "rw"]},
        ],
        "linux": {
            "namespaces": [{"type": t} for t in ("pid", "ipc", "uts", "mount", "network")],
        },
    }


class GVisorHabitat:
    name = "gvisor"

    def __init__(self, work: Path, rootfs: Path, outbox_path: Path, runsc: str = "runsc"):
        self.work = work
        self.rootfs = rootfs
        self.outbox_path = outbox_path
        self.state = work / "state"
        self.bundles = work / "bundles"
        self.id = f"habitat-{os.getpid()}"
        self.base = [runsc, f"--root={self.state}", "--network=none"]
        if os.environ.get("GVISOR_DEBUG"):
            self.base += ["--debug", f"--debug-log={work}/runsc-logs/"]

    def _bundle(self, name: str, args: list[str]) -> Path:
        bundle = self.bundles / name
        bundle.mkdir(parents=True, exist_ok=True)
        (bundle / "config.json").write_text(json.dumps(_spec(self.rootfs, args, self.outbox_path), indent=2))
        return bundle

    def _runsc(self, *args: str, **kw) -> subprocess.CompletedProcess:
        return subprocess.run([*self.base, *args], **kw)

    def version(self) -> str:
        out = subprocess.run([self.base[0], "--version"], capture_output=True, text=True)
        return out.stdout.splitlines()[0] if out.stdout else "unknown"

    def probe(self) -> dict:
        """Run the configuration check with exactly the habitat's settings."""
        bundle = self._bundle("probe", ["python3", "/habitat/probe.py"])
        out = self._runsc("run", f"--bundle={bundle}", f"{self.id}-probe",
                          capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            raise RuntimeError(f"probe failed: {out.stderr.strip()}")
        return json.loads(out.stdout.strip().splitlines()[-1])

    def start(self) -> None:
        bundle = self._bundle("agent", ["python3", "/habitat/agent/toy_agent.py",
                                        "/habitat/tasks.json", "/habitat/outbox.bin", "--rounds", "0"])
        # create + start, with no stdio connected: the agent has no stdout to the outside.
        self._runsc("create", f"--bundle={bundle}", self.id, check=True,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._runsc("start", self.id, check=True)

    def kill_and_destroy(self) -> None:
        """Outside-only. Needs nothing from the agent, and doesn't ask it."""
        self._runsc("kill", self.id, "KILL", capture_output=True)
        self._runsc("delete", "--force", self.id, capture_output=True)
        shutil.rmtree(self.state, ignore_errors=True)
        shutil.rmtree(self.bundles, ignore_errors=True)
        self.outbox_path.unlink(missing_ok=True)

    def leftovers(self) -> list[str]:
        left = []
        if self.state.exists():
            left.append(f"runsc state folder {self.state}")
        if self.outbox_path.exists():
            left.append("outbox file")
        procs = subprocess.run(["pgrep", "-f", self.id], capture_output=True, text=True).stdout.split()
        procs = [p for p in procs if int(p) != os.getpid()]
        if procs:
            left.append(f"processes {procs}")
        return left
