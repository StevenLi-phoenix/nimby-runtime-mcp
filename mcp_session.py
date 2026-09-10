"""Persistent standard MCP client for local batch scripts.

The disk queue is a client harness, not the server transport. Expired requests
are rejected; processing records left by a crash are never automatically replayed.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "work" / "session"


def publish_result(path, text):
    """Readers see either no result or a complete JSON document."""
    temporary = path.with_suffix('.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(path)


async def dispatch(path, client):
    out = path.with_name(path.name.replace(".request.", ".result."))
    if out.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("stop"):
        path.rename(path.with_name(path.name.replace(".request.", ".done.")))
        return True
    if data.get("expires_at", 0) <= time.time():
        publish_result(out,
            json.dumps(
                {
                    "isError": True,
                    "error": "Request expired before dispatch; nothing submitted",
                }
            ),
        )
        path.rename(path.with_name(path.name.replace(".request.", ".done.")))
        return False
    processing = path.with_name(path.name.replace(".request.", ".processing."))
    path.rename(processing)
    try:
        result = await client.call_tool(data["tool"], data.get("arguments", {}))
        output = result.model_dump_json(indent=2)
    except Exception as exc:
        output = json.dumps({"isError": True, "error": str(exc)})
    publish_result(out, output)
    processing.rename(path.with_name(path.name.replace(".request.", ".done.")))
    return False


async def run():
    QUEUE.mkdir(parents=True, exist_ok=True)
    params = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "server.py")]
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            print("MCP session ready", flush=True)
            while True:
                for path in sorted(QUEUE.glob("*.request.json")):
                    if await dispatch(path, client):
                        return
                await asyncio.sleep(0.2)


if __name__ == "__main__":
    asyncio.run(run())
