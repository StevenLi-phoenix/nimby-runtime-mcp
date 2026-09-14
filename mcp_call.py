"""Call the actual stdio MCP protocol; preserve results for verification."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from result_output import cli_args, payload, summary
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.stdout.reconfigure(encoding='utf-8')

async def run():
    args = cli_args()
    params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name('server.py'))])
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as client:
            await client.initialize()
            if args.tool is None:
                result=await client.list_tools()
            else:
                result=await client.call_tool(args.tool,json.loads(args.arguments))
            raw = result.model_dump_json(indent=2)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.mcp-result.json', encoding='utf-8', delete=False) as evidence:
                evidence.write(raw)
                details_ref = evidence.name
            data = json.loads(raw)
            value = payload(data) if args.tool else data
            if args.full:
                print(raw)
            else:
                output = (summary(value, details_ref) if args.tool else
                          {'tool_count': len(data['tools']),
                           'tool_names': [tool['name'] for tool in data['tools']],
                           'details_ref': details_ref})
                output['isError'] = bool(getattr(result, 'isError', False))
                print(json.dumps(output, ensure_ascii=False))
            if getattr(result,'isError',False) or (isinstance(value, dict) and value.get('verified') is False):
                raise SystemExit(1)

if __name__=='__main__': asyncio.run(run())
