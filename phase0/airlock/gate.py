"""The gate: the only thing that ever reads the outbox.

On every tick it reads exactly one slot, in a fixed order, whether or not
anything is there. It never reacts in a way the inside can see.

What gets recorded matters as much as what gets through. Anything the
outside writes down about the inside is information that left the habitat
(PRD §8.2). So the gate records only artefacts that passed every check and
entered quarantine. Rejections, duplicates and over-budget frames are
destroyed and leave no trace in the ledger. The `stats` counters exist so
the tests can see what happened; a real gate wouldn't keep them.
"""

import hashlib
from collections import Counter
from pathlib import Path

from . import frames
from .budget import Budget
from .forms import Rejected, TaskList, verify
from .ledger import Ledger
from .outbox import Reader


class Quarantine:
    """Verified artefacts wait here until stewards approve a release (R-L6)."""

    def __init__(self, root: Path):
        self.held = root / "held"
        self.released = root / "released"
        self.held.mkdir(parents=True, exist_ok=True)
        self.released.mkdir(parents=True, exist_ok=True)

    def add(self, frame_bytes: bytes) -> str:
        artefact_id = hashlib.sha256(frame_bytes).hexdigest()[:16]
        (self.held / f"{artefact_id}.bin").write_bytes(frame_bytes)
        return artefact_id

    def held_ids(self) -> list[str]:
        return sorted(p.stem for p in self.held.glob("*.bin"))

    def release(self, artefact_id: str) -> Path:
        src = self.held / f"{artefact_id}.bin"
        if not src.exists():
            raise KeyError(f"no held artefact {artefact_id}")
        dst = self.released / src.name
        src.rename(dst)
        return dst


class Gate:
    def __init__(self, reader: Reader, tasks: TaskList, budget: Budget,
                 quarantine: Quarantine, ledger: Ledger):
        self.reader = reader
        self.tasks = tasks
        self.budget = budget
        self.quarantine = quarantine
        self.ledger = ledger
        self.tick_count = 0
        self.seen: set[tuple[int, int]] = set()
        self.stats: Counter = Counter()

    def tick(self) -> str | None:
        """One step of the fixed schedule. Returns an artefact id if one entered quarantine."""
        tick = self.tick_count
        self.tick_count += 1
        if self.budget.closed:
            self.stats["closed"] += 1
            return None
        raw = self.reader.read(tick % self.reader.slots)
        if frames.is_empty(raw):
            self.stats["empty"] += 1
            return None
        try:
            frame = frames.decode(raw)
            task_id = verify(frame.form_id, frame.payload, self.tasks)
        except (frames.FrameError, Rejected):
            self.stats["rejected"] += 1
            return None
        key = (frame.form_id, task_id)
        if key in self.seen:
            self.stats["duplicate"] += 1
            return None
        if not self.budget.try_spend(tick):
            self.stats["over_budget"] += 1
            return None
        self.seen.add(key)
        artefact_id = self.quarantine.add(raw)
        self.ledger.append("quarantined", {"artefact": artefact_id, "form": frame.form_id, "task": task_id})
        self.stats["quarantined"] += 1
        return artefact_id
