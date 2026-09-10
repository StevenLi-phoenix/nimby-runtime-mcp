"""Serialized lazy attachment. Failed mutations are never automatically replayed."""

import hashlib
import threading
from pathlib import Path

import frida

from game_version import DEFAULT_EXE, SUPPORTED_SHA256
from runtime_lease import RuntimeLease


class RuntimeConnection:
    def __init__(self):
        self.lock = threading.RLock()
        self.session = None
        self.script = None
        self.lease = RuntimeLease()

    def close(self):
        with self.lock:
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
