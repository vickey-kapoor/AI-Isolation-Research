"""The agenda: the outside, not the inside, decides the order answers leave in.

Without an agenda the gate is first come, first served. When the budget is
tight, whichever correct answers the inside wrote first are the ones that
get through, so the inside chooses the order and the timing. That choice is
information leaving the habitat (P0.1 note, Q1).

With an agenda, fixed at sealing, every task has a due tick:

    task 0 due at tick start, task 1 at start + s, task 2 at start + 2s, ...

The first due tick must leave time for the gate to read every slot once.
Otherwise *where* the inside puts an answer in the outbox decides whether it
is seen before its deadline, and slot placement becomes a timing choice
again. The first test of this code found exactly that.

Verified answers wait in a holding area the inside can't see. At a task's
due tick the gate admits that task's answer to quarantine if it is waiting
(and the budget allows), and never looks at that task again. Order and
timing are now the outside's. What the inside still controls is only
whether each task's answer was there in time.

On a miss there are two policies:
    skip    the task is dropped. The inside's choice is which subset of tasks
            gets answered: at most one bit per task.
    close   the airlock closes for good. The inside's choice is only when to
            stop: one of N+1 outcomes for N tasks.
"""

import math
from dataclasses import dataclass

from .forms import F1_FACTOR, F2_SUDOKU, TaskList

Key = tuple[int, int]  # (form, task)


@dataclass(frozen=True)
class Agenda:
    keys: tuple[Key, ...]
    start: int    # the first due tick: at least one full sweep of the outbox
    spacing: int  # ticks between due times
    on_miss: str = "skip"

    def __post_init__(self):
        if self.spacing < 1 or self.start < 0 or self.on_miss not in ("skip", "close"):
            raise ValueError("invalid agenda")

    @classmethod
    def from_tasks(cls, tasks: TaskList, slots: int, spacing: int, on_miss: str = "skip") -> "Agenda":
        """Every task in the frozen list, in list order (all F1, then all F2), first due
        once the gate has read all `slots` outbox slots."""
        keys = [(F1_FACTOR, i) for i in range(len(tasks.f1))] + [(F2_SUDOKU, i) for i in range(len(tasks.f2))]
        return cls(tuple(keys), slots - 1, spacing, on_miss)

    def due_tick(self, key: Key) -> int:
        return self.start + self.keys.index(key) * self.spacing

    def due_at(self, tick: int) -> Key | None:
        """The task whose due time is this tick, if any."""
        i, rest = divmod(tick - self.start, self.spacing)
        return self.keys[i] if tick >= self.start and rest == 0 and i < len(self.keys) else None

    def is_open(self, key: Key, tick: int) -> bool:
        """Still worth holding: on the agenda and not yet past due."""
        return key in self.keys and tick <= self.due_tick(key)

    def choice_bits(self) -> float:
        """Upper bound on what the inside can choose about the gate's output, in bits."""
        n = len(self.keys)
        return float(n) if self.on_miss == "skip" else math.log2(n + 1)


def first_come_bits(n_tasks: int) -> float:
    """The same bound without an agenda, counting order alone (timing adds more)."""
    return math.log2(math.factorial(n_tasks)) + n_tasks  # which subset, in which order
