"""The one-way outbox: a file of fixed-size slots.

The puzzle program writes slots in a ring, round and round. The gate reads slots on
its own timer and never writes, clears or marks anything. That means the
puzzle program cannot tell whether, when or how often a slot was read (PRD R-L1,
principle 4). It also means the puzzle program can't know when a slot is "free", so
it simply keeps rewriting, and the gate drops duplicates on its side.

What this still relies on: the host kernel and filesystem not leaking reads
back to the writer (for example through access times). The sandbox mounts
are set up to avoid that, but it is an assumption, not a proof.
"""

import os
from pathlib import Path

from .frames import FRAME_SIZE

DEFAULT_SLOTS = 64

# Windows has no pread/pwrite and opens in text mode unless told otherwise.
# Each fd here is opened for a single call, so seek-then-read is equivalent.
_BINARY = getattr(os, "O_BINARY", 0)


def _pwrite(fd: int, data: bytes, offset: int) -> None:
    if hasattr(os, "pwrite"):
        os.pwrite(fd, data, offset)
    else:
        os.lseek(fd, offset, os.SEEK_SET)
        os.write(fd, data)


def _pread(fd: int, size: int, offset: int) -> bytes:
    if hasattr(os, "pread"):
        return os.pread(fd, size, offset)
    os.lseek(fd, offset, os.SEEK_SET)
    return os.read(fd, size)


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
        fd = os.open(self.path, os.O_WRONLY | _BINARY)
        try:
            _pwrite(fd, frame, self.next * FRAME_SIZE)
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
        fd = os.open(self.path, os.O_RDONLY | _BINARY | getattr(os, "O_NOATIME", 0))
        try:
            raw = _pread(fd, FRAME_SIZE, (slot % self.slots) * FRAME_SIZE)
        finally:
            os.close(fd)
        if len(raw) != FRAME_SIZE:
            raise ValueError("short read from outbox")
        return raw
