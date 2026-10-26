"""Backend-independent checks, using the no-sandbox control backend."""

import tempfile
import unittest
from pathlib import Path

from sandboxes.common import provision, run_habitat
from sandboxes.gvisor import _spec
from sandboxes.process import ProcessHabitat


class ControlBackendTests(unittest.TestCase):
    def test_full_run_quarantines_and_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            p = provision(Path(d), backend="process")
            report = run_habitat(p, ProcessHabitat(p.outbox_path), ticks=32, tick_seconds=0.01)
            self.assertGreater(report["quarantined"], 0)
            self.assertEqual(report["leftovers"], [])
            self.assertIn("released", report)


class GVisorSpecTests(unittest.TestCase):
    """The gVisor config itself, checked without needing runsc installed."""

    def setUp(self):
        self.spec = _spec(Path("/rootfs"), ["python3"], Path("/work/outbox.bin"))

    def test_root_is_read_only_and_unprivileged(self):
        self.assertTrue(self.spec["root"]["readonly"])
        self.assertEqual(self.spec["process"]["user"]["uid"], 65534)
        self.assertTrue(all(v == [] for v in self.spec["process"]["capabilities"].values()))
        self.assertFalse(self.spec["process"]["terminal"])

    def test_outbox_is_the_only_writable_bind(self):
        writable = [m["destination"] for m in self.spec["mounts"]
                    if m["type"] == "bind" and "rw" in m.get("options", [])]
        self.assertEqual(writable, ["/habitat/outbox.bin"])

    def test_own_network_namespace(self):
        self.assertIn({"type": "network"}, self.spec["linux"]["namespaces"])


if __name__ == "__main__":
    unittest.main()
