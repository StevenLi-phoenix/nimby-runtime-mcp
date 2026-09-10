"""OS-released, cross-process lease for a single native adapter owner."""

import msvcrt
import tempfile
from pathlib import Path


class RuntimeLease:
    def __init__(self, path=None):
        self.path = path or Path(tempfile.gettempdir()) / "nimby-runtime-mcp.lock"
        self.file = None

    def acquire(self):
        if self.file is not None:
            return
        file = open(self.path, "a+b")
        try:
            if file.tell() == 0:
                file.write(b"\0")
                file.flush()
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            file.close()
            raise RuntimeError(
                "Another NIMBY MCP adapter is attached; close its session first"
            ) from exc
        self.file = file

    def release(self):
        if self.file is not None:
            self.file.close()
            self.file = None
