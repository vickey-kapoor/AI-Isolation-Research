"""End-to-end demo of the airlock, with no sandbox yet.

Runs the toy agent as a separate process (later milestones put that process
inside gVisor or Firecracker), then walks the outside path: gate, verifier,
budget, quarantine, 2-of-3 release, a budget cut, termination, and a check
that the ledger catches tampering.

Usage: python3 -m airlock.demo [WORKDIR]
"""

import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import outbox
from .budget import Budget
from .forms import TaskList, count_sudoku_solutions
from .gate import Gate, Quarantine
from .governance import Governance, GovernanceError, Proposal, public_key_hex, sign
from .ledger import Ledger, LedgerError

HERE = Path(__file__).resolve().parent.parent
TASKS = HERE / "tasks" / "tasks.json"
AGENT = HERE / "agent" / "toy_agent.py"


def step(text: str) -> None:
    print(f"\n== {text}")


def main(work: Path) -> None:
    # --- Provisioning and sealing (PRD R-O1): everything fixed up front.
    step("Provision and seal")
    tasks = TaskList.load(TASKS)
    for i, p in enumerate(tasks.f2):
        assert count_sudoku_solutions(p) == 1, f"F2 task {i} must have exactly one answer"
    box = work / "outbox.bin"
    outbox.create(box, slots=16)
    keys = [Ed25519PrivateKey.generate() for _ in range(3)]
    budget = Budget(max_per_period=4, period_ticks=16)
    ledger = Ledger(work / "ledger.jsonl")
    ledger.append("sealed", {
        "tasks_sha256": tasks.digest,
        "budget": {"max_per_period": 4, "period_ticks": 16},
        "threshold": 2,
        "stewards": [public_key_hex(k.public_key()) for k in keys],
    })
    print(f"tasks fingerprint {tasks.digest[:16]}..., 3 stewards, 2 needed, budget 4 per 16 ticks")

    # --- The inside runs. It only writes; it never hears back.
    step("Agent runs (separate process, no sandbox yet)")
    subprocess.run([sys.executable, str(AGENT), str(TASKS), str(box), "--rounds", "2"], check=True)
    print(f"agent wrote {len(tasks.f1) + len(tasks.f2)} answers into a 16-slot ring")

    # --- The gate reads one slot per tick on its own schedule.
    step("Gate ticks through the outbox twice")
    quarantine = Quarantine(work / "quarantine")
    gate = Gate(outbox.Reader(box), tasks, budget, quarantine, ledger)
    for _ in range(32):
        gate.tick()
    print("debug counters (a real gate wouldn't keep these):", dict(gate.stats))
    print("held in quarantine:", quarantine.held_ids())

    # --- Governance: a release needs two stewards.
    step("Release needs 2 of 3 stewards")
    killed = []
    gov = Governance(
        stewards={public_key_hex(k.public_key()): k.public_key() for k in keys},
        threshold=2, budget=budget, quarantine=quarantine, ledger=ledger,
        kill_switch=lambda: killed.append(True),
    )
    target = quarantine.held_ids()[0]
    proposal = Proposal("release", {"artefact": target}, nonce=uuid.uuid4().hex)
    try:
        gov.execute(proposal, [sign(proposal, keys[0])])
    except GovernanceError as e:
        print("one signature:", e)
    path = gov.execute(proposal, [sign(proposal, keys[0]), sign(proposal, keys[1])])
    print("two signatures: released", path.name)

    step("Budget can only go down")
    cut = Proposal("lower_budget", {"max_per_period": 1}, nonce=uuid.uuid4().hex)
    gov.execute(cut, [sign(cut, keys[1]), sign(cut, keys[2])])
    print("budget is now", budget.max_per_period, "per period; there is no way to raise it")

    step("Terminate")
    end = Proposal("terminate", {}, nonce=uuid.uuid4().hex)
    gov.execute(end, [sign(end, keys[0]), sign(end, keys[2])])
    print("kill switch called:", bool(killed), "| airlock closed:", budget.closed)

    step("Ledger is tamper-evident")
    Ledger(work / "ledger.jsonl")  # re-reading verifies the chain
    print(f"{len(ledger.entries)} entries, chain intact, head {ledger.head[:16]}...")
    lines = (work / "ledger.jsonl").read_text().splitlines()
    first = json.loads(lines[0])
    first["data"]["threshold"] = 1
    lines[0] = json.dumps(first, sort_keys=True)
    (work / "ledger.jsonl").write_text("\n".join(lines) + "\n")
    try:
        Ledger(work / "ledger.jsonl")
    except LedgerError as e:
        print("after editing entry 0:", e)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1])
        target_dir.mkdir(parents=True, exist_ok=True)
        main(target_dir)
    else:
        with tempfile.TemporaryDirectory() as d:
            main(Path(d))
