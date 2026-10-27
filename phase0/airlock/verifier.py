"""The verifier as its own small program, so it can run in a box of its own (Q2).

The verifier is the one piece of outside code that reads bytes the inside
chose. If it had a flaw, a crafted frame would meet it first. So it should be
small, and it should be isolated from everything else outside, or it becomes
a weaker second habitat with the gate's privileges.

Run as a program, it reads 256-byte frames on standard input and answers
each with exactly 4 bytes on standard output:

    01 FF TT TT    passed: form FF, task TTTT
    00 00 00 00    failed (no reason given, so a failure says nothing)

It needs nothing else: no files beyond the task list, no network, no clock.
It uses only frames.py and forms.py, which use only Python's standard library.
"""

import sys
from pathlib import Path

from . import frames
from .forms import Rejected, TaskList, verify

FAILED = bytes(4)


def check(raw: bytes, tasks: TaskList) -> tuple[int, int] | None:
    """In-process check: (form, task) for a frame that passes every check, else None."""
    if frames.is_empty(raw):
        return None
    try:
        frame = frames.decode(raw)
        return frame.form_id, verify(frame.form_id, frame.payload, tasks)
    except (frames.FrameError, Rejected):
        return None


def encode_verdict(key: tuple[int, int] | None) -> bytes:
    return FAILED if key is None else bytes([1, key[0]]) + key[1].to_bytes(2, "big")


def decode_verdict(reply: bytes) -> tuple[int, int] | None:
    if len(reply) != 4 or reply[0] != 1:
        return None
    return reply[1], int.from_bytes(reply[2:], "big")


def main() -> int:
    tasks = TaskList.load(Path(sys.argv[1]))
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    while True:
        raw = stdin.read(frames.FRAME_SIZE)
        if len(raw) < frames.FRAME_SIZE:
            return 0
        stdout.write(encode_verdict(check(raw, tasks)))
        stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
