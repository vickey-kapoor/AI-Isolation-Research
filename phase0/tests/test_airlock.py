"""Tests for the Phase 0 airlock. Run from phase0/: python3 -m unittest -v"""

import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from airlock import frames, outbox
from airlock.budget import Budget, BudgetError
from airlock.forms import (F1_FACTOR, F2_SUDOKU, Rejected, TaskList, count_sudoku_solutions,
                           encode_f1, encode_f2, verify)
from airlock.gate import Gate, Quarantine
from airlock.governance import Governance, GovernanceError, Proposal, public_key_hex, sign
from airlock.ledger import Ledger, LedgerError

ROOT = Path(__file__).resolve().parent.parent
TASKS = TaskList.load(ROOT / "tasks" / "tasks.json")
SUDOKU_0 = "534678912672195348198342567859761423426853791713924856961537284287419635345286179"


class TempDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class FrameTests(unittest.TestCase):
    def test_round_trip(self):
        raw = frames.encode(frames.Frame(1, b"abc"))
        self.assertEqual(len(raw), frames.FRAME_SIZE)
        self.assertEqual(frames.decode(raw), frames.Frame(1, b"abc"))

    def test_padding_must_be_zero(self):
        raw = bytearray(frames.encode(frames.Frame(1, b"abc")))
        raw[-1] = 1
        with self.assertRaises(frames.FrameError):
            frames.decode(bytes(raw))

    def test_wrong_size_rejected(self):
        with self.assertRaises(frames.FrameError):
            frames.decode(b"HAB0" + bytes(10))


class FormTests(unittest.TestCase):
    def test_f1_correct_answer_passes(self):
        self.assertEqual(verify(F1_FACTOR, encode_f1(0, [(2, 3), (3, 2), (5, 1)]), TASKS), 0)

    def test_f1_wrong_product_rejected(self):
        with self.assertRaises(Rejected):
            verify(F1_FACTOR, encode_f1(0, [(2, 3), (3, 2), (7, 1)]), TASKS)

    def test_f1_non_canonical_order_rejected(self):
        # Same factors, different order: only one encoding may pass.
        with self.assertRaises(Rejected):
            verify(F1_FACTOR, encode_f1(0, [(3, 2), (2, 3), (5, 1)]), TASKS)

    def test_f1_split_exponent_rejected(self):
        with self.assertRaises(Rejected):
            verify(F1_FACTOR, encode_f1(0, [(2, 1), (2, 2), (3, 2), (5, 1)]), TASKS)

    def test_f1_composite_factor_rejected(self):
        with self.assertRaises(Rejected):
            verify(F1_FACTOR, encode_f1(0, [(4, 1), (90, 1)]), TASKS)

    def test_f1_unknown_task_rejected(self):
        with self.assertRaises(Rejected):
            verify(F1_FACTOR, encode_f1(99, [(2, 1)]), TASKS)

    def test_f1_trailing_bytes_rejected(self):
        with self.assertRaises(Rejected):
            verify(F1_FACTOR, encode_f1(0, [(2, 3), (3, 2), (5, 1)]) + b"\x00", TASKS)

    def test_f2_correct_answer_passes(self):
        self.assertEqual(verify(F2_SUDOKU, encode_f2(0, SUDOKU_0), TASKS), 0)

    def test_f2_broken_rules_rejected(self):
        bad = "4" + SUDOKU_0[1:]
        with self.assertRaises(Rejected):
            verify(F2_SUDOKU, encode_f2(0, bad), TASKS)

    def test_unapproved_form_rejected(self):
        with self.assertRaises(Rejected):
            verify(7, b"anything", TASKS)

    def test_frozen_puzzles_have_one_answer(self):
        for p in TASKS.f2:
            self.assertEqual(count_sudoku_solutions(p), 1)


class BudgetTests(unittest.TestCase):
    def test_limit_per_period(self):
        b = Budget(2, period_ticks=10)
        self.assertEqual([b.try_spend(t) for t in (0, 1, 2)], [True, True, False])
        self.assertTrue(b.try_spend(10))

    def test_cannot_raise(self):
        b = Budget(2, 10)
        with self.assertRaises(BudgetError):
            b.lower(3)

    def test_close_is_permanent(self):
        b = Budget(2, 10)
        b.close()
        self.assertFalse(b.try_spend(100))
        with self.assertRaises(BudgetError):
            b.lower(1)


class LedgerTests(TempDir):
    def test_chain_verifies_and_detects_edits(self):
        path = self.dir / "l.jsonl"
        led = Ledger(path)
        led.append("a", {"x": 1})
        led.append("b", {"x": 2})
        Ledger(path)  # verifies on load
        lines = path.read_text().splitlines()
        entry = json.loads(lines[0])
        entry["data"]["x"] = 9
        lines[0] = json.dumps(entry)
        path.write_text("\n".join(lines) + "\n")
        with self.assertRaises(LedgerError):
            Ledger(path)

    def test_detects_removed_entry(self):
        path = self.dir / "l.jsonl"
        led = Ledger(path)
        for i in range(3):
            led.append("a", {"i": i})
        lines = path.read_text().splitlines()
        path.write_text(lines[0] + "\n" + lines[2] + "\n")
        with self.assertRaises(LedgerError):
            Ledger(path)


class GateTests(TempDir):
    def make(self, slots=8, budget=Budget(10, 100)):
        box = self.dir / "outbox.bin"
        outbox.create(box, slots)
        q = Quarantine(self.dir / "q")
        led = Ledger(self.dir / "ledger.jsonl")
        return box, Gate(outbox.Reader(box), TASKS, budget, q, led), q, led

    def test_valid_artefact_quarantined_once(self):
        box, gate, q, led = self.make()
        w = outbox.Writer(box)
        good = frames.encode(frames.Frame(F2_SUDOKU, encode_f2(0, SUDOKU_0)))
        w.write(good)
        w.write(good)
        for _ in range(8):
            gate.tick()
        self.assertEqual(len(q.held_ids()), 1)
        self.assertEqual(gate.stats["duplicate"], 1)

    def test_rejections_leave_no_trace(self):
        box, gate, q, led = self.make()
        outbox.Writer(box).write(frames.encode(frames.Frame(F1_FACTOR, encode_f1(0, [(2, 1)]))))
        for _ in range(8):
            gate.tick()
        self.assertEqual(q.held_ids(), [])
        self.assertEqual(led.entries, [])
        self.assertEqual(gate.stats["rejected"], 1)

    def test_gate_never_writes_outbox(self):
        box, gate, q, led = self.make()
        w = outbox.Writer(box)
        w.write(frames.encode(frames.Frame(F2_SUDOKU, encode_f2(0, SUDOKU_0))))
        before = box.read_bytes()
        for _ in range(16):
            gate.tick()
        self.assertEqual(box.read_bytes(), before)

    def test_closed_gate_reads_nothing(self):
        budget = Budget(10, 100)
        budget.close()
        box, gate, q, led = self.make(budget=budget)
        outbox.Writer(box).write(frames.encode(frames.Frame(F2_SUDOKU, encode_f2(0, SUDOKU_0))))
        for _ in range(8):
            gate.tick()
        self.assertEqual(gate.stats["closed"], 8)
        self.assertEqual(q.held_ids(), [])

    def test_agent_end_to_end(self):
        box, gate, q, led = self.make(slots=16)
        agent = ROOT / "agent" / "toy_agent.py"
        subprocess.run([sys.executable, str(agent), str(ROOT / "tasks" / "tasks.json"), str(box)],
                       check=True)
        for _ in range(16):
            gate.tick()
        self.assertEqual(len(q.held_ids()), len(TASKS.f1) + len(TASKS.f2))


class GovernanceTests(TempDir):
    def setUp(self):
        super().setUp()
        self.keys = [Ed25519PrivateKey.generate() for _ in range(3)]
        self.budget = Budget(5, 10)
        self.q = Quarantine(self.dir / "q")
        self.ledger = Ledger(self.dir / "ledger.jsonl")
        self.killed = []
        self.gov = self.governance()

    def governance(self):
        return Governance(
            stewards={public_key_hex(k.public_key()): k.public_key() for k in self.keys},
            threshold=2, budget=self.budget, quarantine=self.q, ledger=self.ledger,
            kill_switch=lambda: self.killed.append(1))

    def proposal(self, action, **params):
        return Proposal(action, params, nonce=uuid.uuid4().hex)

    def test_one_signature_is_not_enough(self):
        p = self.proposal("close_airlock")
        with self.assertRaises(GovernanceError):
            self.gov.execute(p, [sign(p, self.keys[0])])
        self.assertFalse(self.budget.closed)

    def test_same_steward_twice_counts_once(self):
        p = self.proposal("close_airlock")
        with self.assertRaises(GovernanceError):
            self.gov.execute(p, [sign(p, self.keys[0]), sign(p, self.keys[0])])

    def test_outsider_key_does_not_count(self):
        p = self.proposal("close_airlock")
        outsider = Ed25519PrivateKey.generate()
        with self.assertRaises(GovernanceError):
            self.gov.execute(p, [sign(p, self.keys[0]), sign(p, outsider)])

    def test_signature_bound_to_proposal(self):
        p = self.proposal("lower_budget", max_per_period=4)
        other = Proposal("lower_budget", {"max_per_period": 0}, nonce=p.nonce)
        sigs = [sign(other, self.keys[0]), sign(other, self.keys[1])]
        with self.assertRaises(GovernanceError):
            self.gov.execute(p, sigs)

    def test_replay_rejected_even_after_restart(self):
        p = self.proposal("lower_budget", max_per_period=4)
        sigs = [sign(p, self.keys[0]), sign(p, self.keys[1])]
        self.gov.execute(p, sigs)
        with self.assertRaises(GovernanceError):
            self.gov.execute(p, sigs)
        self.ledger = Ledger(self.dir / "ledger.jsonl")
        with self.assertRaises(GovernanceError):
            self.governance().execute(p, sigs)

    def test_unknown_action_rejected(self):
        p = self.proposal("raise_budget", max_per_period=100)
        with self.assertRaises(GovernanceError):
            self.gov.execute(p, [sign(p, k) for k in self.keys])

    def test_terminate_calls_kill_switch_and_closes(self):
        p = self.proposal("terminate")
        self.gov.execute(p, [sign(p, self.keys[1]), sign(p, self.keys[2])])
        self.assertEqual(self.killed, [1])
        self.assertTrue(self.budget.closed)
        self.assertEqual(self.ledger.entries[-1]["data"]["action"], "terminate")


if __name__ == "__main__":
    unittest.main()
