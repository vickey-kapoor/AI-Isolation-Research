"""Q1 experiment: with an agenda, the inside's write order no longer matters."""

import importlib.util
import json
import random
import tempfile
import unittest
from pathlib import Path

from airlock import frames, outbox
from airlock.agenda import Agenda, first_come_bits
from airlock.budget import Budget
from airlock.gate import Gate, Quarantine
from airlock.ledger import Ledger
from airlock.forms import TaskList

ROOT = Path(__file__).resolve().parent.parent
TASKS_PATH = ROOT / "tasks" / "tasks.json"
TASKS = TaskList.load(TASKS_PATH)

_spec = importlib.util.spec_from_file_location("puzzle_program", ROOT / "puzzle_program" / "puzzle_program.py")
_program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_program)
ANSWERS = _program.answers(json.loads(TASKS_PATH.read_text()))  # one correct frame per task, in task order
N = len(ANSWERS)
SPACING = 4


def run(order: list[int], agenda: Agenda | None, ticks: int = 64) -> list[tuple]:
    """Write the answers in the given order, run the gate, return what entered quarantine and when."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        box = d / "outbox.bin"
        outbox.create(box, 16)
        w = outbox.Writer(box)
        for i in order:
            w.write(ANSWERS[i])
        ledger = Ledger(d / "ledger.jsonl")
        gate = Gate(outbox.Reader(box), TASKS, Budget(2, 16), Quarantine(d / "q"), ledger, agenda=agenda)
        out = []
        for _ in range(ticks):
            if gate.tick():
                e = ledger.entries[-1]["data"]
                out.append((gate.tick_count - 1, e["form"], e["task"]))
        return out


class AgendaTests(unittest.TestCase):
    def setUp(self):
        self.orders = [list(range(N)), list(reversed(range(N)))]
        rng = random.Random(0)
        for _ in range(5):
            o = list(range(N))
            rng.shuffle(o)
            self.orders.append(o)

    def test_without_agenda_write_order_changes_the_output(self):
        outputs = {tuple(run(o, None)) for o in self.orders}
        self.assertGreater(len(outputs), 1)

    def test_with_agenda_write_order_does_not_change_the_output(self):
        agenda = Agenda.from_tasks(TASKS, 16, SPACING)
        outputs = {tuple(run(o, agenda)) for o in self.orders}
        self.assertEqual(len(outputs), 1)
        # Order and timing are the outside's: task i at its fixed due tick.
        out = outputs.pop()
        self.assertEqual([t for t, _, _ in out], [agenda.due_tick((f, k)) for _, f, k in out])

    def test_withheld_answer_is_skipped_others_still_leave(self):
        agenda = Agenda.from_tasks(TASKS, 16, SPACING)
        out = run([i for i in range(N) if i != 1], agenda)
        keys = [(f, t) for _, f, t in out]
        self.assertNotIn(agenda.keys[1], keys)
        self.assertIn(agenda.keys[2], keys)

    def test_close_policy_ends_everything_at_the_first_miss(self):
        agenda = Agenda.from_tasks(TASKS, 16, SPACING, on_miss="close")
        out = run([i for i in range(N) if i != 1], agenda)
        self.assertEqual([(f, t) for _, f, t in out], [agenda.keys[0]])

    def test_answer_after_its_due_tick_is_not_admitted(self):
        agenda = Agenda.from_tasks(TASKS, 16, SPACING)
        due = agenda.due_tick(agenda.keys[0])
        self.assertTrue(agenda.is_open(agenda.keys[0], due))
        self.assertFalse(agenda.is_open(agenda.keys[0], due + 1))

    def test_too_early_first_deadline_lets_slot_placement_matter(self):
        # The finding behind `start`: due before one full sweep, and placement matters again.
        early = Agenda(Agenda.from_tasks(TASKS, 16, SPACING).keys, start=SPACING - 1, spacing=SPACING)
        outputs = {tuple(run(o, early)) for o in self.orders}
        self.assertGreater(len(outputs), 1)

    def test_choice_bounds(self):
        self.assertEqual(Agenda.from_tasks(TASKS, 16, SPACING).choice_bits(), N)
        self.assertAlmostEqual(Agenda.from_tasks(TASKS, 16, SPACING, "close").choice_bits(), 3.0)  # log2(7+1)
        self.assertGreater(first_come_bits(N), 19)  # log2(7!) + 7


if __name__ == "__main__":
    unittest.main()


class VerifierProgramTests(unittest.TestCase):
    """Q2: the verifier as a separate program gives the same verdicts as the in-process check."""

    def test_separate_process_matches_in_process(self):
        import subprocess
        import sys
        from airlock.verifier import check, decode_verdict
        batch = ANSWERS + [bytes(frames.FRAME_SIZE), ANSWERS[0][:-1] + b"\x01"]
        out = subprocess.run([sys.executable, "-m", "airlock.verifier", str(TASKS_PATH)], cwd=ROOT,
                             input=b"".join(batch), capture_output=True, check=True).stdout
        self.assertEqual(len(out), 4 * len(batch))
        verdicts = [decode_verdict(out[i:i + 4]) for i in range(0, len(out), 4)]
        self.assertEqual(verdicts, [check(f, TASKS) for f in batch])
        self.assertEqual(verdicts[-2:], [None, None])

    def test_gate_uses_the_verifier_it_is_given(self):
        # A verifier that refuses everything: nothing reaches quarantine.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            box = d / "outbox.bin"
            outbox.create(box, 16)
            outbox.Writer(box).write(ANSWERS[0])
            q = Quarantine(d / "q")
            gate = Gate(outbox.Reader(box), TASKS, Budget(4, 16), q, Ledger(d / "l.jsonl"),
                        verifier=lambda raw: None)
            for _ in range(16):
                gate.tick()
            self.assertEqual(q.held_ids(), [])
            self.assertEqual(gate.stats["rejected"], 1)
