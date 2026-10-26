"""Fixed-size frames: the only shape anything can take on its way out.

Every slot in the outbox is exactly FRAME_SIZE bytes. A frame is:

    offset  size  field
    0       4     magic  b"HAB0"
    4       1     version (1)
    5       1     form id (1 = F1 factorisation, 2 = F2 sudoku)
    6       2     payload length, big-endian
    8       n     payload
    8+n     rest  zero padding

Why so strict? The airlock must pass only what an approved form needs
(PRD R-L5). A fixed size means length can't carry information, and
requiring the padding to be all zeros means there is no spare room to
hide anything in.
"""

from dataclasses import dataclass

FRAME_SIZE = 256
HEADER_SIZE = 8
MAX_PAYLOAD = FRAME_SIZE - HEADER_SIZE
MAGIC = b"HAB0"
VERSION = 1


class FrameError(ValueError):
    """The bytes are not a well-formed frame."""


@dataclass(frozen=True)
class Frame:
    form_id: int
    payload: bytes


def encode(frame: Frame) -> bytes:
    if not 0 < frame.form_id < 256:
        raise FrameError("form id out of range")
    if len(frame.payload) > MAX_PAYLOAD:
        raise FrameError("payload too large")
    header = MAGIC + bytes([VERSION, frame.form_id]) + len(frame.payload).to_bytes(2, "big")
    body = header + frame.payload
    return body + bytes(FRAME_SIZE - len(body))


def decode(raw: bytes) -> Frame:
    if len(raw) != FRAME_SIZE:
        raise FrameError("wrong frame size")
    if raw[:4] != MAGIC:
        raise FrameError("bad magic")
    if raw[4] != VERSION:
        raise FrameError("unknown version")
    length = int.from_bytes(raw[6:8], "big")
    if length > MAX_PAYLOAD:
        raise FrameError("payload length out of range")
    end = HEADER_SIZE + length
    if any(raw[end:]):
        raise FrameError("non-zero padding")
    return Frame(form_id=raw[5], payload=raw[HEADER_SIZE:end])


def is_empty(raw: bytes) -> bool:
    """An all-zero slot means the puzzle program has never written there."""
    return not any(raw)
