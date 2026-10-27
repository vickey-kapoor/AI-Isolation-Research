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
from .agenda import Agenda
from .budget import Budget
from .forms import TaskList
from .ledger import Ledger
from .outbox import Reader
from .verifier import check


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
                 quarantine: Quarantine, ledger: Ledger, agenda: Agenda | None = None,
                 verifier=None):
        self.reader = reader
        self.tasks = tasks
        self.budget = budget
        self.quarantine = quarantine
        self.ledger = ledger
        self.agenda = agenda
        # Anything that maps a raw frame to (form, task) or None. By default the
        # check runs in this process; sandboxes/verifier_box.py runs it in its own sandbox.
        self.verifier = verifier or (lambda raw: check(raw, tasks))
        self.pending: dict[tuple[int, int], bytes] = {}  # verified, waiting for their due tick
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
        if self.agenda is None:
            return self._first_come(tick)
        self._hold(tick)
        return self._admit_due(tick)

    def _check(self, tick: int):
        """Read this tick's slot. Returns (key, raw) for a verified answer, else None."""
        raw = self.reader.read(tick % self.reader.slots)
        if frames.is_empty(raw):
            self.stats["empty"] += 1
            return None
        key = self.verifier(raw)
        if key is None:
            self.stats["rejected"] += 1
            return None
        return key, raw

    def _first_come(self, tick: int) -> str | None:
        checked = self._check(tick)
        if checked is None:
            return None
        key, raw = checked
        if key in self.seen:
            self.stats["duplicate"] += 1
            return None
        if not self.budget.try_spend(tick):
            self.stats["over_budget"] += 1
            return None
        return self._quarantine(key, raw)

    def _hold(self, tick: int) -> None:
        checked = self._check(tick)
        if checked is None:
            return
        key, raw = checked
        if key in self.pending or key in self.seen or not self.agenda.is_open(key, tick):
            self.stats["duplicate"] += 1
            return
        self.pending[key] = raw

    def _admit_due(self, tick: int) -> str | None:
        key = self.agenda.due_at(tick)
        if key is None:
            return None
        raw = self.pending.pop(key, None)
        if raw is None:
            self.stats["missed"] += 1
            if self.agenda.on_miss == "close":
                self.budget.close()
                self.ledger.append("closed", {"reason": "an agenda task was not answered in time"})
            return None
        self.seen.add(key)
        if not self.budget.try_spend(tick):
            self.stats["over_budget"] += 1
            return None
        return self._quarantine(key, raw)

    def _quarantine(self, key: tuple[int, int], raw: bytes) -> str:
        self.seen.add(key)
        artefact_id = self.quarantine.add(raw)
        self.ledger.append("quarantined", {"artefact": artefact_id, "form": key[0], "task": key[1]})
        self.stats["quarantined"] += 1
        return artefact_id
