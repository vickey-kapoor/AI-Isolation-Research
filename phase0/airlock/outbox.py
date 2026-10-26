"""The one-way outbox: a file of fixed-size slots.

The agent writes slots in a ring, round and round. The gate reads slots on
its own timer and never writes, clears or marks anything. That means the
agent cannot tell whether, when or how often a slot was read (PRD R-L1,
principle 4). It also means the agent can't know when a slot is "free", so
it simply keeps rewriting, and the gate drops duplicates on its side.

What this still relies on: the host kernel and filesystem not leaking reads
back to the writer (for example through access times). The sandbox mounts
are set up to avoid that, but it is an assumption, not a proof.
"""

import os
from pathlib import Path

from .frames import FRAME_SIZE

DEFAULT_SLOTS = 64


def create(path: Path, slots: int = DEFAULT_SLOTS) -> None:
    """Outside creates the outbox before sealing, all zeros, fixed size."""
    with path.open("wb") as f:
        f.write(bytes(FRAME_SIZE * slots))


def slot_count(path: Path) -> int:
    size = path.stat().st_size
    if size % FRAME_SIZE:
        raise ValueError("outbox size is not a whole number of slots")
    return size // FRAME_SIZE


class Writer:
    """Inside side. Only ever writes whole slots, in a ring."""

    def __init__(self, path: Path):
        self.path = path
        self.slots = slot_count(path)
        self.next = 0

    def write(self, frame: bytes) -> None:
        if len(frame) != FRAME_SIZE:
            raise ValueError("frames must be exactly FRAME_SIZE bytes")
        fd = os.open(self.path, os.O_WRONLY)
        try:
            os.pwrite(fd, frame, self.next * FRAME_SIZE)
            os.fsync(fd)
        finally:
            os.close(fd)
        self.next = (self.next + 1) % self.slots


class Reader:
    """Outside side. Opens read-only, reads one whole slot at a time."""

    def __init__(self, path: Path):
        self.path = path
        self.slots = slot_count(path)

    def read(self, slot: int) -> bytes:
        fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_NOATIME", 0))
        try:
            raw = os.pread(fd, FRAME_SIZE, (slot % self.slots) * FRAME_SIZE)
        finally:
            os.close(fd)
        if len(raw) != FRAME_SIZE:
            raise ValueError("short read from outbox")
        return raw
