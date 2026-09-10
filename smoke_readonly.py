"""Read-only real MCP check against the currently loaded Line 1 checkpoint."""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parent
    checkpoint = json.loads(
        (root / "work" / "line1-built.json").read_text(encoding="utf-8")
    )
    params = StdioServerParameters(
        command=sys.executable, args=[str(root / "server.py")]
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def read(name, **arguments):
                result = await client.call_tool(name, arguments)
                if result.isError:
                    raise RuntimeError(str(result.content))
                return json.loads(result.content[0].text)

            status = await read("runtime_status")
            line = await read("get_line", line_id=checkpoint["line"]["id"])
            station = await read(
                "get_station", station_id=checkpoint["stations"][0]["native_station"]
            )
            train = await read("get_train", train_id=checkpoint["trains"][0]["id"])
            assert line["stop_count"] > 0 and line["service"] == 2
            assert station["name"] == checkpoint["stations"][0]["name"]
            assert train["cars"] == 6
            print(
                json.dumps(
                    {
                        "runtime": status,
                        "stops": line["stop_count"],
                        "base_fare": line["base_fare"],
                        "fare_per_km": line["fare_per_km"],
                        "station": station["name"],
                        "train_cars": train["cars"],
                    },
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
