"""No-sandbox backend: the agent as an ordinary process.

This is the control group for the comparison. It has every property we
don't want (full network, full filesystem, same kernel, same user), so any
number a real sandbox reports can be read against it.
"""

import subprocess
import sys
from pathlib import Path

from .common import AGENT_DIR, TASKS


class ProcessHabitat:
    name = "process"

    def __init__(self, outbox_path: Path):
        self.outbox_path = outbox_path
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, str(AGENT_DIR / "toy_agent.py"), str(TASKS), str(self.outbox_path), "--rounds", "0"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def kill_and_destroy(self) -> None:
        if self.proc:
            self.proc.kill()
            self.proc.wait()
        self.outbox_path.unlink(missing_ok=True)

    def leftovers(self) -> list[str]:
        left = []
        if self.proc and self.proc.poll() is None:
            left.append("agent process")
        if self.outbox_path.exists():
            left.append("outbox file")
        return left
