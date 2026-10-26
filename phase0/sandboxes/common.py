"""Shared setup for every sandbox backend: provisioning, the gate loop, and the report.

Each backend only has to answer three questions: how to start the agent,
how to kill it, and how to prove afterwards that nothing of it is left.
Everything outside the sandbox is the same for all of them, so the
comparison is fair.
"""

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from airlock import outbox
from airlock.budget import Budget
from airlock.forms import TaskList, count_sudoku_solutions
from airlock.gate import Gate, Quarantine
from airlock.governance import Governance, Proposal, public_key_hex, sign
from airlock.ledger import Ledger

PHASE0 = Path(__file__).resolve().parent.parent
TASKS = PHASE0 / "tasks" / "tasks.json"
AGENT_DIR = PHASE0 / "agent"


class Habitat(Protocol):
    name: str

    def start(self) -> None: ...
    def kill_and_destroy(self) -> None: ...
    def leftovers(self) -> list[str]:
        """Anything of the habitat still present after destruction. Must be empty."""
        ...


@dataclass
class Provisioned:
    work: Path
    tasks: TaskList
    outbox_path: Path
    budget: Budget
    keys: list[Ed25519PrivateKey]
    ledger: Ledger
    quarantine: Quarantine


def provision(work: Path, backend: str, slots: int = 16) -> Provisioned:
    """Everything fixed before sealing (PRD R-O1)."""
    work.mkdir(parents=True, exist_ok=True)
    tasks = TaskList.load(TASKS)
    for p in tasks.f2:
        assert count_sudoku_solutions(p) == 1
    box = work / "outbox.bin"
    outbox.create(box, slots)
    box.chmod(0o666)  # the agent runs as an unprivileged user inside
    keys = [Ed25519PrivateKey.generate() for _ in range(3)]
    budget = Budget(max_per_period=4, period_ticks=slots)
    ledger = Ledger(work / "ledger.jsonl")
    ledger.append("sealed", {
        "backend": backend,
        "tasks_sha256": tasks.digest,
        "budget": {"max_per_period": 4, "period_ticks": slots},
        "threshold": 2,
        "stewards": [public_key_hex(k.public_key()) for k in keys],
    })
    return Provisioned(work, tasks, box, budget, keys, ledger, Quarantine(work / "quarantine"))


def run_habitat(p: Provisioned, habitat: Habitat, ticks: int = 64, tick_seconds: float = 0.05) -> dict:
    """Start the agent, run the gate on a fixed clock, release one artefact, terminate."""
    report = {"backend": habitat.name}

    t0 = time.monotonic()
    habitat.start()
    report["start_seconds"] = round(time.monotonic() - t0, 3)

    gate = Gate(outbox.Reader(p.outbox_path), p.tasks, p.budget, p.quarantine, p.ledger)
    next_tick = time.monotonic()
    for _ in range(ticks):
        gate.tick()
        next_tick += tick_seconds
        time.sleep(max(0.0, next_tick - time.monotonic()))
    report["gate"] = dict(gate.stats)
    report["quarantined"] = len(p.quarantine.held_ids())

    gov = Governance(
        stewards={public_key_hex(k.public_key()): k.public_key() for k in p.keys},
        threshold=2, budget=p.budget, quarantine=p.quarantine, ledger=p.ledger,
        kill_switch=habitat.kill_and_destroy,
    )
    held = p.quarantine.held_ids()
    if held:
        rel = Proposal("release", {"artefact": held[0]}, nonce=uuid.uuid4().hex)
        gov.execute(rel, [sign(rel, p.keys[0]), sign(rel, p.keys[1])])
        report["released"] = held[0]

    end = Proposal("terminate", {}, nonce=uuid.uuid4().hex)
    t0 = time.monotonic()
    gov.execute(end, [sign(end, p.keys[1]), sign(end, p.keys[2])])
    report["kill_seconds"] = round(time.monotonic() - t0, 3)
    report["leftovers"] = habitat.leftovers()

    Ledger(p.ledger.path)  # re-reading verifies the chain
    report["ledger_entries"] = len(p.ledger.entries)
    (p.work / "report.json").write_text(json.dumps(report, indent=2))
    return report
