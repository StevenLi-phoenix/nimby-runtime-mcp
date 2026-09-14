"""Serialized lazy attachment. Failed mutations are never automatically replayed."""

import hashlib
import logging
import threading
from pathlib import Path

import frida

from game_version import DEFAULT_EXE, SUPPORTED_SHA256
from runtime_lease import RuntimeLease


class RuntimeConnection:
    def __init__(self, idle_timeout=30):
        if idle_timeout <= 0:
            raise ValueError('idle_timeout must be positive')
        self.lock = threading.RLock()
        self.session = None
        self.script = None
        self.lease = RuntimeLease()
        self.idle_timeout = idle_timeout
        self._idle_timer = None
        self._idle_generation = 0

    def _cancel_idle(self):
        self._idle_generation += 1
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

    def _arm_idle(self):
        self._cancel_idle()
        if self.session is None:
            return
        self._idle_timer = threading.Timer(
            self.idle_timeout, self._release_idle, (self._idle_generation,))
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _release_idle(self, generation):
        with self.lock:
            if generation != self._idle_generation:
                return
            try:
                self.close()
            except Exception:
                # shutdown() refuses to unload an active native callback. Keep
                # the lease and retry cleanup later, never replay the command.
                logging.getLogger(__name__).exception('Idle runtime release failed; retaining lease')
                self._arm_idle()

    def close(self):
        with self.lock:
            self._cancel_idle()
            session, script = self.session, self.script
            if session is None:
                return
            if not session.is_detached and script is not None:
                # If draining fails, retain the live references. Unloading an
                # in-flight native callback can crash the game.
                try:
                    script.exports_sync.shutdown()
                except frida.InvalidOperationError:
                    if not session.is_detached:
                        raise
                if not session.is_detached:
                    script.unload()
            if not session.is_detached:
                session.detach()
            self.session = self.script = None
            self.lease.release()

    def _attach(self):
        if hashlib.sha256(DEFAULT_EXE.read_bytes()).hexdigest() != SUPPORTED_SHA256:
            raise RuntimeError("Unsupported NIMBY Rails build")
        device = frida.get_local_device()
        games = [
            p
            for p in device.enumerate_processes()
            if p.name.lower() == "nimbyrails.exe"
        ]
        if len(games) != 1:
            raise RuntimeError("Expected exactly one NIMBY Rails process")
        self.lease.acquire()
        session = None
        try:
            session = device.attach(games[0].pid)
            script = session.create_script(
                Path(__file__).with_name("bridge.js").read_text(encoding="utf-8")
                + "\n"
                + Path(__file__).with_name("operations.js").read_text(encoding="utf-8")
            )
            script.load()
        except Exception:
            try:
                if session is not None:
                    session.detach()
            finally:
                self.lease.release()
            raise
        self.session, self.script = session, script

    def request(self, kind, args=None):
        with self.lock:
            self._cancel_idle()
            try:
                return self._request_locked(kind, args)
            finally:
                self._arm_idle()

    def _request_locked(self, kind, args=None):
        with self.lock:
            if self.session is not None and self.session.is_detached:
                self.session = self.script = None
                self.lease.release()
            if self.script is None:
                self._attach()
            try:
                result = self.script.exports_sync.request(kind, args or {})
            except (frida.InvalidOperationError, frida.TransportError) as exc:
                if self.session.is_detached:
                    self.session = self.script = None
                    self.lease.release()
                raise RuntimeError(
                    "Runtime connection lost; outcome unknown. Inspect state before retrying a mutation."
                ) from exc
            if isinstance(result, dict) and result.get("verified") is False:
                raise RuntimeError(
                    f"Native operation {kind} did not verify; inspect state before retrying: {result}"
                )
            return result
