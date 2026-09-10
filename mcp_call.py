"""Call the actual stdio MCP protocol; preserve results for verification."""
import asyncio
import json
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.stdout.reconfigure(encoding='utf-8')

async def run():
    params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('server.py'))])
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as client:
            await client.initialize()
            if len(sys.argv)==1:
                result=await client.list_tools()
            else:
                result=await client.call_tool(sys.argv[1],json.loads(sys.argv[2]) if len(sys.argv)>2 else {})
            print(result.model_dump_json(indent=2))
            if getattr(result,'isError',False): raise RuntimeError('MCP tool failed')

if __name__=='__main__': asyncio.run(run())
