"""Resume native MCP line setup from the successfully built checkpoint."""

import json
from pathlib import Path

from session_call import call


def main():
    p = Path(__file__).resolve().parent / "work" / "line1-built.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    if d["status"] not in [
        "built",
        "configuring-line",
        "built-awaiting-path-validation",
    ]:
        raise RuntimeError("Expected built infrastructure")

    def save():
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    if "line" not in d:
        d["line"] = call("create_line")["line"]
        d["status"] = "configuring-line"
        save()
    lid = d["line"]["id"]
    call("set_line_name", line_id=lid, name="北京地铁1号线八通线", code="bj-1")
    expected = [s["east_stop"] for s in d["stations"]] + [
        s["west_stop"] for s in reversed(d["stations"])
    ]
    current = call("get_line", line_id=lid)
    if [s["node_id"] for s in current["stops"]] != expected[: current["stop_count"]]:
        raise RuntimeError("Unexpected stop order")
    for n in expected[current["stop_count"] :]:
        d["line"] = call("add_line_stop", line_id=lid, platform_node_id=n)["line"]
        save()
        print(f"Stops {d['line']['stop_count']}/72", flush=True)
    if not d.get("trains"):
        d["trains"] = call("purchase_six_car_trains", line_id=lid, count=1)["trains"]
        save()
    d["line"] = call(
        "set_line_service",
        line_id=lid,
        service=2,
        reference_train_id=d["trains"][0]["id"],
    )["line"]
    d["status"] = "built-awaiting-path-validation"
    save()
    print("Line ready for path validation", flush=True)


if __name__ == "__main__":
    main()
