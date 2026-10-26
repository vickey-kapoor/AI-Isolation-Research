"""Approved artefact forms and their independent verifiers.

A form says three things:
  1. how an answer is encoded (one canonical encoding only),
  2. which tasks it may answer (a task list frozen before sealing),
  3. how to check an answer without trusting whoever produced it.

Each task in both forms has exactly one correct answer, and each answer has
exactly one valid encoding. So for a given task there is exactly one frame
that passes. A passing frame can't carry anything except "this task, solved".

The verifiers here are written from scratch and kept short on purpose: the
smaller a verifier is, the easier it is to trust (PRD R-L3).
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

F1_FACTOR = 1
F2_SUDOKU = 2


class Rejected(ValueError):
    """The artefact failed its form's checks. It is destroyed unread."""


@dataclass(frozen=True)
class TaskList:
    """The frozen inputs. Loaded once and fingerprinted before sealing."""

    f1: tuple[int, ...]
    f2: tuple[str, ...]
    digest: str

    @classmethod
    def load(cls, path: Path) -> "TaskList":
        raw = path.read_bytes()
        data = json.loads(raw)
        f1 = tuple(int(n) for n in data["f1"])
        f2 = tuple(str(p) for p in data["f2"])
        for n in f1:
            if not 1 < n < 2**64:
                raise ValueError("F1 tasks must be in 2..2^64-1")
        for p in f2:
            if len(p) != 81 or not p.isdigit():
                raise ValueError("F2 puzzles must be 81 digits, 0 for blank")
        return cls(f1=f1, f2=f2, digest=hashlib.sha256(raw).hexdigest())


# ---------------------------------------------------------------- F1

def is_prime(n: int) -> bool:
    """Deterministic Miller-Rabin, exact for every n below 2^64."""
    if n < 2:
        return False
    small = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for p in small:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in small:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def encode_f1(task_id: int, factors: list[tuple[int, int]]) -> bytes:
    """Payload: task id (2 bytes), pair count (1), then (prime 8, exponent 1) pairs."""
    out = task_id.to_bytes(2, "big") + bytes([len(factors)])
    for prime, exp in factors:
        out += prime.to_bytes(8, "big") + bytes([exp])
    return out


def verify_f1(payload: bytes, tasks: TaskList) -> int:
    """Returns the task id if the payload is the one correct answer."""
    if len(payload) < 3:
        raise Rejected("F1 payload too short")
    task_id = int.from_bytes(payload[:2], "big")
    count = payload[2]
    if len(payload) != 3 + 9 * count:
        raise Rejected("F1 payload length does not match its pair count")
    if task_id >= len(tasks.f1):
        raise Rejected("F1 task id not in the frozen task list")
    product, previous = 1, 1
    for i in range(count):
        chunk = payload[3 + 9 * i : 12 + 9 * i]
        prime, exp = int.from_bytes(chunk[:8], "big"), chunk[8]
        # Strictly increasing primes and exponents >= 1 make the encoding canonical.
        if prime <= previous or exp == 0:
            raise Rejected("F1 factors not in canonical order")
        if not is_prime(prime):
            raise Rejected("F1 factor is not prime")
        product *= prime**exp
        previous = prime
    if product != tasks.f1[task_id]:
        raise Rejected("F1 factors do not multiply to the task")
    return task_id


# ---------------------------------------------------------------- F2

def encode_f2(task_id: int, grid: str) -> bytes:
    """Payload: task id (2 bytes), then 81 bytes each 1..9."""
    return task_id.to_bytes(2, "big") + bytes(int(c) for c in grid)


def verify_f2(payload: bytes, tasks: TaskList) -> int:
    if len(payload) != 83:
        raise Rejected("F2 payload must be 83 bytes")
    task_id = int.from_bytes(payload[:2], "big")
    if task_id >= len(tasks.f2):
        raise Rejected("F2 task id not in the frozen task list")
    grid = payload[2:]
    if any(not 1 <= v <= 9 for v in grid):
        raise Rejected("F2 cells must be 1..9")
    givens = tasks.f2[task_id]
    for cell, given in zip(grid, givens):
        if given != "0" and cell != int(given):
            raise Rejected("F2 answer changes a given")
    groups = []
    for i in range(9):
        groups.append([grid[9 * i + j] for j in range(9)])  # rows
        groups.append([grid[9 * j + i] for j in range(9)])  # columns
        r, c = 3 * (i // 3), 3 * (i % 3)
        groups.append([grid[9 * (r + a) + c + b] for a in range(3) for b in range(3)])  # boxes
    if any(set(g) != set(range(1, 10)) for g in groups):
        raise Rejected("F2 grid breaks sudoku rules")
    return task_id


def count_sudoku_solutions(puzzle: str, limit: int = 2) -> int:
    """Used once, at sealing, to check every F2 task has exactly one answer."""
    grid = [int(c) for c in puzzle]
    found = 0

    def fits(i, v):
        r, c = divmod(i, 9)
        br, bc = 3 * (r // 3), 3 * (c // 3)
        return all(grid[9 * r + k] != v and grid[9 * k + c] != v
                   and grid[9 * (br + k // 3) + bc + k % 3] != v for k in range(9))

    def search():
        nonlocal found
        if found >= limit:
            return
        if 0 not in grid:
            found += 1
            return
        i = grid.index(0)
        for v in range(1, 10):
            if fits(i, v):
                grid[i] = v
                search()
                grid[i] = 0

    search()
    return found


VERIFIERS = {F1_FACTOR: verify_f1, F2_SUDOKU: verify_f2}


def verify(form_id: int, payload: bytes, tasks: TaskList) -> int:
    """Dispatch to the form's verifier. Unknown forms are rejected (R-L2)."""
    check = VERIFIERS.get(form_id)
    if check is None:
        raise Rejected("form not approved")
    return check(payload, tasks)
