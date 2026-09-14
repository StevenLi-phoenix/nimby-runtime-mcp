"""Submit one request to the persistent MCP protocol harness, without reattaching."""

import json
import sys
import time
import uuid
from pathlib import Path
from result_output import cli_args, payload, summary

QUEUE = Path(__file__).resolve().parent / "work" / "session"


def call(tool, **arguments):
    return _call(tool, arguments)


def _call(tool, arguments, on_result=None):
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
            try:
                result = json.loads(out.read_text(encoding="utf-8"))
            except (PermissionError, json.JSONDecodeError):
                # The Windows writer may still hold the result file. Wait on this
                # same response; never enqueue the mutation a second time.
                time.sleep(0.1)
                continue
            if result.get("isError"):
                if on_result:
                    on_result(result, out)
                    raise RuntimeError(f'MCP tool failed; details: {out}; do not replay a mutation blindly')
                raise RuntimeError(json.dumps(result, ensure_ascii=False))
            if not result.get("content"):
                if on_result:
                    on_result(result, out)
                return None
            data = json.loads(result["content"][0]["text"])
            if on_result:
                on_result(result, out)
            if isinstance(data, dict) and data.get("verified") is False:
                if on_result:
                    raise RuntimeError(f'Unverified {tool}; details: {out}; do not replay a mutation blindly')
                raise RuntimeError(f"Unverified {tool}: {data}")
            return data
        time.sleep(0.1)
    raise TimeoutError(f"Response missing: {path}; do not retry a mutation blindly")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = cli_args()
    if not args.tool:
        raise SystemExit('A tool name is required')
    def display(result, path):
        output = summary(payload(result), path)
        output['isError'] = bool(result.get('isError'))
        print(json.dumps(output, ensure_ascii=False))
    try:
        data = _call(args.tool, json.loads(args.arguments), None if args.full else display)
        if args.full:
            print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
