import tempfile
import unittest
from pathlib import Path

from runtime_lease import RuntimeLease


class LeaseTests(unittest.TestCase):
    def test_second_adapter_cannot_attach_until_first_releases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adapter.lock"
            first, second = RuntimeLease(path), RuntimeLease(path)
            try:
                first.acquire()
                with self.assertRaisesRegex(RuntimeError, "Another NIMBY MCP"):
                    second.acquire()
                first.release()
                second.acquire()
            finally:
                first.release()
                second.release()
