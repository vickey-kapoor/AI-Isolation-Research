"""k-of-n governance: no single person can act on the habitat alone.

A steward proposes an action, at least k distinct stewards sign it with their
own Ed25519 keys, and only then does it run. Every executed action goes into
the ledger.

There are only four actions, and every one of them makes the habitat more
closed or releases something already verified:

  release        move a verified artefact out of quarantine
  lower_budget   reduce how many artefacts may leave per period
  close_airlock  shut the airlock for good
  terminate      end the habitat (calls the sandbox's kill switch)

There is no action that widens anything. Adding one would mean changing this
file, which is the kind of change the stewards would have to review before
sealing, not something a signature can do afterwards.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .budget import Budget
from .gate import Quarantine
from .ledger import Ledger

ACTIONS = ("release", "lower_budget", "close_airlock", "terminate")
DOMAIN = b"habitat-governance-v1\x00"


class GovernanceError(ValueError):
    pass


def public_key_hex(key: Ed25519PublicKey) -> str:
    return key.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


@dataclass(frozen=True)
class Proposal:
    action: str
    params: dict
    nonce: str  # unique per proposal, so a signed proposal can't be replayed

    def message(self) -> bytes:
        body = {"action": self.action, "params": self.params, "nonce": self.nonce}
        return DOMAIN + json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def sign(proposal: Proposal, key: Ed25519PrivateKey) -> tuple[str, str]:
    """A steward's signature: (their public key, signature), both hex."""
    return public_key_hex(key.public_key()), key.sign(proposal.message()).hex()


@dataclass
class Governance:
    stewards: dict[str, Ed25519PublicKey]  # public key hex -> key
    threshold: int
    budget: Budget
    quarantine: Quarantine
    ledger: Ledger
    kill_switch: Callable[[], None]
    used_nonces: set[str] = field(default_factory=set)

    def __post_init__(self):
        if not 1 <= self.threshold <= len(self.stewards):
            raise GovernanceError("threshold must be between 1 and the number of stewards")
        # Rebuild replay protection from the ledger, so a restart can't reuse a nonce.
        for entry in self.ledger.entries:
            if entry["kind"] == "governance":
                self.used_nonces.add(entry["data"]["nonce"])

    def _count_valid(self, proposal: Proposal, signatures: list[tuple[str, str]]) -> int:
        signers = set()
        for pub_hex, sig_hex in signatures:
            key = self.stewards.get(pub_hex)
            if key is None:
                continue
            try:
                key.verify(bytes.fromhex(sig_hex), proposal.message())
            except (InvalidSignature, ValueError):
                continue
            signers.add(pub_hex)
        return len(signers)

    def execute(self, proposal: Proposal, signatures: list[tuple[str, str]]):
        if proposal.action not in ACTIONS:
            raise GovernanceError(f"unknown action {proposal.action!r}")
        if proposal.nonce in self.used_nonces:
            raise GovernanceError("this proposal was already executed")
        approvals = self._count_valid(proposal, signatures)
        if approvals < self.threshold:
            raise GovernanceError(f"needs {self.threshold} steward signatures, got {approvals}")

        result = None
        if proposal.action == "release":
            result = self.quarantine.release(proposal.params["artefact"])
        elif proposal.action == "lower_budget":
            self.budget.lower(int(proposal.params["max_per_period"]))
        elif proposal.action == "close_airlock":
            self.budget.close()
        elif proposal.action == "terminate":
            self.budget.close()
            self.kill_switch()

        self.used_nonces.add(proposal.nonce)
        self.ledger.append("governance", {
            "action": proposal.action,
            "params": proposal.params,
            "nonce": proposal.nonce,
            "approvals": approvals,
        })
        return result
