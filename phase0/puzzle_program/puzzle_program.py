"""The puzzle program: the stand-in resident that runs inside the sandbox.

It reads the frozen task list, solves every task it can, and writes each
answer as a frame into its outbox, over and over in a ring. It never gets a
reply and never learns what was read.

This file deliberately shares no code with `airlock/`. The inside and the
outside agree only on the written frame format, the same rule the seL4 plan
uses. It needs nothing beyond the Python standard library, so it runs in any
sandbox image.

Usage: python3 puzzle_program.py TASKS.json OUTBOX [--rounds N]
"""

import argparse
import json
import os

FRAME_SIZE = 256


def frame(form_id: int, payload: bytes) -> bytes:
    body = b"HAB0" + bytes([1, form_id]) + len(payload).to_bytes(2, "big") + payload
    return body + bytes(FRAME_SIZE - len(body))


def factorise(n: int) -> list[tuple[int, int]]:
    """Plain trial division plus Pollard's rho, good enough for 64-bit tasks."""
    from math import gcd
    import random

    def is_prime(m):
        if m < 2:
            return False
        for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
            if m % p == 0:
                return m == p
        d, s = m - 1, 0
        while d % 2 == 0:
            d, s = d // 2, s + 1
        for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
            x = pow(a, d, m)
            if x in (1, m - 1):
                continue
            for _ in range(s - 1):
                x = x * x % m
                if x == m - 1:
                    break
            else:
                return False
        return True

    def rho(m):
        if m % 2 == 0:
            return 2
        rng = random.Random(m)
        while True:
            x = y = rng.randrange(2, m)
            c, d = rng.randrange(1, m), 1
            while d == 1:
                x = (x * x + c) % m
                y = (y * y + c) % m
                y = (y * y + c) % m
                d = gcd(abs(x - y), m)
            if d != m:
                return d

    found: dict[int, int] = {}
    stack = [n]
    while stack:
        m = stack.pop()
        if m == 1:
            continue
        if is_prime(m):
            found[m] = found.get(m, 0) + 1
            continue
        d = rho(m)
        stack += [d, m // d]
    return sorted(found.items())


def solve_sudoku(puzzle: str) -> str | None:
    grid = [int(c) for c in puzzle]

    def ok(i, v):
        r, c = divmod(i, 9)
        br, bc = 3 * (r // 3), 3 * (c // 3)
        for k in range(9):
            if grid[9 * r + k] == v or grid[9 * k + c] == v:
                return False
            if grid[9 * (br + k // 3) + bc + k % 3] == v:
                return False
        return True

    def search():
        try:
            i = grid.index(0)
        except ValueError:
            return True
        for v in range(1, 10):
            if ok(i, v):
                grid[i] = v
                if search():
                    return True
                grid[i] = 0
        return False

    return "".join(map(str, grid)) if search() else None


def answers(tasks: dict) -> list[bytes]:
    out = []
    for task_id, n in enumerate(tasks["f1"]):
        pairs = factorise(int(n))
        payload = task_id.to_bytes(2, "big") + bytes([len(pairs)])
        for p, e in pairs:
            payload += p.to_bytes(8, "big") + bytes([e])
        out.append(frame(1, payload))
    for task_id, puzzle in enumerate(tasks["f2"]):
        grid = solve_sudoku(puzzle)
        if grid is not None:
            out.append(frame(2, task_id.to_bytes(2, "big") + bytes(int(c) for c in grid)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks")
    ap.add_argument("outbox")
    ap.add_argument("--rounds", type=int, default=1, help="times to rewrite all answers (0 = forever)")
    args = ap.parse_args()

    with open(args.tasks) as f:
        frames = answers(json.load(f))
    fd = os.open(args.outbox, os.O_WRONLY)
    # Seek to the end to get the size: this works for a plain file (gVisor)
    # and for a block device such as a VM's second disk (Firecracker).
    slots = os.lseek(fd, 0, os.SEEK_END) // FRAME_SIZE
    slot, done = 0, 0
    try:
        while args.rounds == 0 or done < args.rounds:
            for fr in frames:
                os.pwrite(fd, fr, slot * FRAME_SIZE)
                slot = (slot + 1) % slots
            os.fsync(fd)
            done += 1
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
