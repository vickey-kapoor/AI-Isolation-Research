"""Tamper-evident ledger: an append-only hash chain.

Each entry stores the hash of the entry before it. Changing, removing or
reordering any past entry breaks every hash after it, so verify() catches it.
This doesn't stop someone rewriting the whole file; it makes the rewrite
detectable by anyone who kept an earlier head hash.
"""

import hashlib
import json
from pathlib import Path

GENESIS = "0" * 64


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _entry_hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(_canonical(body)).hexdigest()


class LedgerError(ValueError):
    pass


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.entries: list[dict] = []
        if path.exists():
            for line in path.read_text().splitlines():
                self.entries.append(json.loads(line))
            self.verify()

    @property
    def head(self) -> str:
        return self.entries[-1]["hash"] if self.entries else GENESIS

    def append(self, kind: str, data: dict) -> dict:
        entry = {"seq": len(self.entries), "kind": kind, "data": data, "prev": self.head}
        entry["hash"] = _entry_hash(entry)
        with self.path.open("a") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        self.entries.append(entry)
        return entry

    def verify(self) -> None:
        prev = GENESIS
        for i, entry in enumerate(self.entries):
            if entry.get("seq") != i or entry.get("prev") != prev:
                raise LedgerError(f"chain broken at entry {i}")
            if entry.get("hash") != _entry_hash(entry):
                raise LedgerError(f"entry {i} was altered")
            prev = entry["hash"]
