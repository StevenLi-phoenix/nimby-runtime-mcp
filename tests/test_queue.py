import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from mcp_session import dispatch


class QueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_purchase_never_dispatches(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "one.request.json"
            p.write_text(
                json.dumps(
                    {"tool": "purchase_six_car_trains", "expires_at": time.time() - 1}
                )
            )
            client = Mock(call_tool=AsyncMock())
            await dispatch(p, client)
            client.call_tool.assert_not_called()
            self.assertTrue(
                json.loads(p.with_name("one.result.json").read_text())["isError"]
            )

    async def test_request_claimed_before_call_and_not_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "one.request.json"
            p.write_text(
                json.dumps({"tool": "runtime_status", "expires_at": time.time() + 10})
            )

            async def call(*args):
                self.assertFalse(p.exists())
                self.assertTrue(p.with_name("one.processing.json").exists())
                return Mock(model_dump_json=Mock(return_value='{"isError": false}'))

            client = Mock(call_tool=AsyncMock(side_effect=call))
            await dispatch(p, client)
            await dispatch(p, client)
            client.call_tool.assert_called_once()
            self.assertTrue(p.with_name("one.done.json").exists())

    async def test_cancellation_preserves_uncertain_processing_record(self):
        import asyncio

        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "one.request.json"
            p.write_text(
                json.dumps(
                    {"tool": "purchase_six_car_trains", "expires_at": time.time() + 10}
                )
            )
            client = Mock(call_tool=AsyncMock(side_effect=asyncio.CancelledError()))
            with self.assertRaises(asyncio.CancelledError):
                await dispatch(p, client)
            self.assertFalse(p.exists())
            self.assertTrue(p.with_name("one.processing.json").exists())
