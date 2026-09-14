import unittest
from threading import Event, Timer
from unittest.mock import Mock, patch

import frida

from runtime_connection import RuntimeConnection


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        # Drive idle expiry explicitly; no background callbacks escape tests.
        timer = patch('runtime_connection.threading.Timer')
        self.timer = timer.start()
        self.addCleanup(timer.stop)

    def connection(self):
        runtime = RuntimeConnection()
        runtime.session = Mock(is_detached=False)
        runtime.script = Mock()
        return runtime

    def test_unverified_native_result_is_error(self):
        runtime = self.connection()
        runtime.script.exports_sync.request.return_value = {"verified": False}
        with self.assertRaisesRegex(RuntimeError, "did not verify"):
            runtime.request("purchase")

    def test_failed_mutation_is_never_replayed(self):
        runtime = self.connection()
        script = runtime.script
        script.exports_sync.request.side_effect = frida.InvalidOperationError(
            "detached"
        )
        with self.assertRaisesRegex(RuntimeError, "outcome unknown"):
            runtime.request("purchase")
        script.exports_sync.request.assert_called_once()

    def test_next_request_reconnects_after_game_exit(self):
        runtime = self.connection()
        runtime.session.is_detached = True
        replacement = Mock()
        replacement.exports_sync.request.return_value = {"speed": 1}

        def attach():
            runtime.session = Mock(is_detached=False)
            runtime.script = replacement

        with patch.object(runtime, "_attach", side_effect=attach) as connect:
            self.assertEqual(runtime.request("status"), {"speed": 1})
            connect.assert_called_once()

    def test_shutdown_failure_does_not_unload_live_callbacks(self):
        runtime = self.connection()
        script, session = runtime.script, runtime.session
        script.exports_sync.shutdown.side_effect = frida.RPCException("in flight")
        with self.assertRaises(frida.RPCException):
            runtime.close()
        script.unload.assert_not_called()
        session.detach.assert_not_called()
        self.assertIs(runtime.script, script)

    def test_close_is_idempotent_and_ordered(self):
        runtime = self.connection()
        calls = Mock()
        calls.attach_mock(runtime.script, "script")
        calls.attach_mock(runtime.session, "session")
        runtime.close()
        runtime.close()
        self.assertEqual(
            [c[0] for c in calls.mock_calls],
            ["script.exports_sync.shutdown", "script.unload", "session.detach"],
        )
        self.assertIsNone(runtime.session)

    def test_failed_load_does_not_leave_partial_connection(self):
        runtime = RuntimeConnection()
        device = Mock()
        device.enumerate_processes.return_value = [Mock(name="process", pid=7)]
        device.enumerate_processes.return_value[0].name = "NimbyRails.exe"
        device.attach.return_value.create_script.return_value.load.side_effect = (
            RuntimeError("bad bridge")
        )
        with (
            patch.object(runtime.lease, "acquire"),
            patch("runtime_connection.DEFAULT_EXE") as exe,
            patch("runtime_connection.hashlib.sha256") as digest,
            patch("runtime_connection.frida.get_local_device", return_value=device),
        ):
            from game_version import SUPPORTED_SHA256

            exe.read_bytes.return_value = b"game"
            digest.return_value.hexdigest.return_value = SUPPORTED_SHA256
            with self.assertRaisesRegex(RuntimeError, "bad bridge"):
                runtime.request("status")
        device.attach.return_value.detach.assert_called_once()
        self.assertIsNone(runtime.script)

    def test_idle_release_then_next_request_reattaches(self):
        runtime = self.connection()
        runtime.lease = Mock()
        runtime.script.exports_sync.request.return_value = {'speed': 0}
        runtime.request('status')
        self.timer.assert_called_once_with(30, runtime._release_idle, (runtime._idle_generation,))
        runtime._release_idle(runtime._idle_generation)
        runtime.lease.release.assert_called_once()
        self.assertIsNone(runtime.session)
        replacement = Mock()
        replacement.exports_sync.request.return_value = {'speed': 1}
        def attach():
            runtime.session = Mock(is_detached=False)
            runtime.script = replacement
        with patch.object(runtime, '_attach', side_effect=attach) as connect:
            self.assertEqual(runtime.request('status'), {'speed': 1})
            connect.assert_called_once()

    def test_new_request_invalidates_old_idle_callback(self):
        runtime = self.connection()
        runtime.request('status')
        generation = runtime._idle_generation
        runtime.request('status')
        runtime._release_idle(generation)
        runtime.script.exports_sync.shutdown.assert_not_called()

    def test_idle_shutdown_failure_retains_lease_and_retries_cleanup_only(self):
        runtime = self.connection()
        runtime.lease = Mock()
        runtime.script.exports_sync.shutdown.side_effect = frida.RPCException('in flight')
        runtime.request('purchase')
        script = runtime.script
        with self.assertLogs('runtime_connection', level='ERROR'):
            runtime._release_idle(runtime._idle_generation)
        script.unload.assert_not_called()
        runtime.lease.release.assert_not_called()
        script.exports_sync.request.assert_called_once()
        self.assertIs(runtime.script, script)
        self.assertIsNotNone(runtime._idle_timer)

    def test_inflight_request_invalidates_timer_before_dispatch(self):
        runtime = self.connection()
        runtime.request('status')
        generation = runtime._idle_generation
        def dispatch(*args):
            runtime._release_idle(generation)
            runtime.script.exports_sync.shutdown.assert_not_called()
            return {'verified': True}
        runtime.script.exports_sync.request.side_effect = dispatch
        self.assertEqual(runtime.request('purchase'), {'verified': True})

    def test_explicit_close_invalidates_timer(self):
        runtime = self.connection()
        runtime.request('status')
        generation = runtime._idle_generation
        script = runtime.script
        runtime.close()
        runtime._release_idle(generation)
        script.exports_sync.shutdown.assert_called_once()

    def test_real_timer_releases_idle_connection(self):
        runtime = self.connection()
        runtime.idle_timeout = 0.02
        released = Event()
        runtime.lease = Mock()
        runtime.lease.release.side_effect = released.set
        try:
            with patch('runtime_connection.threading.Timer', Timer):
                runtime.request('status')
                self.assertTrue(released.wait(2), 'Idle timer did not release lease')
            self.assertIsNone(runtime.session)
            self.assertIsNone(runtime.script)
        finally:
            runtime.close()


if __name__ == "__main__":
    unittest.main()
