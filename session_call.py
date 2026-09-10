"""Submit one request to the persistent MCP protocol harness, without reattaching."""

import json
import sys
import time
import uuid
from pathlib import Path

QUEUE = Path(__file__).resolve().parent / "work" / "session"


def call(tool, **arguments):
    key = f"{time.time_ns()}-{uuid.uuid4().hex[:6]}"
    path = QUEUE / f"{key}.request.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {"tool": tool, "arguments": arguments, "expires_at": time.time() + 25},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    temporary.replace(path)
    out = QUEUE / f"{key}.result.json"
    for _ in range(300):
        if out.exists():
            result = json.loads(out.read_text(encoding="utf-8"))
            if result.get("isError"):
                raise RuntimeError(json.dumps(result, ensure_ascii=False))
            if not result.get("content"):
                return None
            data = json.loads(result["content"][0]["text"])
            if isinstance(data, dict) and data.get("verified") is False:
                raise RuntimeError(f"Unverified {tool}: {data}")
            return data
        time.sleep(0.1)
    raise TimeoutError(f"Response missing: {path}; do not retry a mutation blindly")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(
        json.dumps(
            call(sys.argv[1], **(json.loads(sys.argv[2]) if len(sys.argv) > 2 else {})),
            ensure_ascii=False,
            indent=2,
        )
    )
