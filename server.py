"""Local stdio MCP backed by the running game's native command processor."""

import atexit
import math
import re

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from runtime_connection import RuntimeConnection

mcp = FastMCP("NIMBY Rails Runtime")
runtime = RuntimeConnection()
request = runtime.request
close = runtime.close
atexit.register(close)


def valid_id(value):
    """Require canonical ASCII uint64 strings; preserve precision across JSON."""
    return (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and 0 < int(value) < 2**64
        and str(int(value)) == value
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, openWorldHint=False
    )
)
def runtime_status() -> dict:
    """Read current simulation speed and normal cash balance at the live core boundary."""
    return request("status")


@mcp.tool()
def connect_station_walk_link(station_a: str, station_b: str) -> dict:
    """Add a native bidirectional walking interchange; game's distance limit applies."""
    if not valid_id(station_a) or not valid_id(station_b) or station_a == station_b:
        raise ValueError("Expected two distinct station IDs")
    return request("walk_link", {"a": station_a, "b": station_b})


@mcp.tool()
def set_simulation_speed(speed: int) -> dict:
    """Queue a native simulation-speed command; zero pauses. Read back execution."""
    if not 0 <= speed <= 10000:
        raise ValueError("Speed must be 0..10000")
    return request("set_speed", {"speed": speed})


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, openWorldHint=False
    )
)
def get_track_node(node_id: str) -> dict | None:
    """Read a track node by its native ID from the current runtime database."""
    if not valid_id(node_id):
        raise ValueError("Invalid node ID")
    return request("get_node", {"id": node_id})


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False))
def get_track_network(seed_node_ids: list[str]) -> dict:
    """Read current connected tracks including branches, bounded to 5000 nodes."""
    if not seed_node_ids or any(not valid_id(i) for i in seed_node_ids):
        raise ValueError("Invalid seed IDs")
    return request("get_network", {"ids": seed_node_ids})


@mcp.tool()
def get_nearby_track_nodes(x: float, y: float, radius: float = 500) -> dict:
    """Read all nearby native track objects, including detached platform structures."""
    if not all(math.isfinite(v) for v in (x, y, radius)) or not 0 < radius <= 2000:
        raise ValueError("Invalid search area")
    return request("nearby_nodes", {"x": x, "y": y, "radius": radius})


@mcp.tool()
def rebuild_track_blueprints(node_ids: list[str]) -> dict:
    """Convert selected built nodes back to blueprints using native ReBP, preserving geometry."""
    if not node_ids or len(node_ids) > 5000 or any(not valid_id(i) for i in node_ids):
        raise ValueError("Invalid node IDs")
    return request("rebp", {"ids": list(dict.fromkeys(node_ids))})


@mcp.tool()
def set_medium_track(node_ids: list[str]) -> dict:
    """Change blueprint nodes to Medium speed. Built nodes must first pass native ReBP."""
    if not node_ids or len(node_ids) > 5000 or any(not valid_id(i) for i in node_ids):
        raise ValueError("Invalid node IDs")
    return request("edit_kind", {"ids": list(dict.fromkeys(node_ids)), "track_type": 3})


@mcp.tool()
def set_line_name(
    line_id: str,
    name: str,
    code: str = "bj-1",
    base_fare: float | None = None,
    fare_per_km: float | None = None,
    color: str | None = None,
) -> dict:
    """Set line name/code, optional #RRGGBB color and game-unit fares; preserve omitted fields."""
    if not valid_id(line_id):
        raise ValueError("Invalid line ID")
    for s in [name, code]:
        if not s or "\x00" in s or len(s.encode("utf-8")) > 1024:
            raise ValueError("Invalid text")
    if not re.fullmatch(r"[a-z][a-z0-9]*-[a-z0-9]+", code):
        raise ValueError("Line code must include city and line, e.g. bj-1 or nyc-a")
    for v in [base_fare, fare_per_km]:
        if v is not None and (not math.isfinite(v) or not 0 <= v <= 10000):
            raise ValueError("Invalid fare")
    if fare_per_km is not None and fare_per_km > 10:
        raise ValueError("Price per km must not exceed the game's limit of 10")
    if color is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("Color must be #RRGGBB")
    native_color = None if color is None else int.from_bytes(bytes.fromhex(color[1:]) + b'\xff', 'little')
    return request(
        "line_meta",
        {
            "id": line_id,
            "name": name,
            "code": code,
            "base_fare": base_fare,
            "fare_per_km": fare_per_km,
            "color": native_color,
        },
    )


@mcp.tool()
def set_line_service(
    line_id: str, service: int = 2, reference_train_id: str | None = None
) -> dict:
    """Configure service level (0 closed, 1 technical, 2 passenger) and reference train."""
    if not valid_id(line_id):
        raise ValueError("Invalid line ID")
    if service not in [0, 1, 2]:
        raise ValueError("Service must be 0..2")
    if reference_train_id is not None and get_train(reference_train_id) is None:
        raise ValueError("Reference train not found")
    return request(
        "line_service",
        {"id": line_id, "service": service, "reference_train": reference_train_id},
    )


@mcp.tool()
def purchase_six_car_trains(line_id: str, count: int = 1) -> dict:
    """Purchase built-in Kayou 231 six-car, 120m trains and assign auto-run to a line.

    This is an operational substitute, not an exact Beijing rolling-stock model.
    """
    if not valid_id(line_id):
        raise ValueError("Invalid line ID")
    if not 1 <= count <= 40:
        raise ValueError("Count must be 1..40")
    line = get_line(line_id)
    if line is None or not re.fullmatch(r"[a-z][a-z0-9]*-[a-z0-9]+", line["code"]):
        raise ValueError("Set a city-prefixed line code before purchase")
    prefix = line["code"] + "-"
    used = [int(t["serial"][len(prefix):]) for t in list_trains()["trains"]
            if t["serial"].startswith(prefix) and t["serial"][len(prefix):].isascii()
            and t["serial"][len(prefix):].isdecimal()]
    start = max(used, default=0) + 1
    result = request("purchase", {"line_id": line_id, "count": count})
    # A failed rename must never repeat the purchase. Expose IDs for recovery.
    try:
        result["trains"] = [rename_train(t["id"], f'{line["name"]} {i:04d}',
                                         f'{prefix}{i:04d}')["train"]
                            for i, t in enumerate(result["trains"], start)]
    except Exception as error:
        raise RuntimeError(f"Purchase succeeded; naming incomplete. Do not purchase again. "
                           f"Train IDs: {[t['id'] for t in result['trains']]}") from error
    return result


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False))
def list_trains() -> dict:
    """Read all purchased trains, including their city-prefixed display serials."""
    return request("get_trains")


@mcp.tool()
def rename_train(train_id: str, name: str, serial: str) -> dict:
    """Set display name/serial via native Edit; preserve all other train settings."""
    if not valid_id(train_id):
        raise ValueError("Invalid train ID")
    if not name or "\x00" in name or len(name.encode("utf-8")) > 1024:
        raise ValueError("Invalid train name")
    if not re.fullmatch(r"[a-z][a-z0-9]*-[a-z0-9]+-[0-9]{4,}", serial):
        raise ValueError("Serial must include city, line and sequence, e.g. bj-1-0001")
    return request("rename_train", {"id": train_id, "name": name, "serial": serial})


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, openWorldHint=False
    )
)
def get_train(train_id: str) -> dict | None:
    """Read a purchased train's model, dimensions and capacity from the runtime."""
    if not valid_id(train_id):
        raise ValueError("Invalid train ID")
    return request("get_train", {"id": train_id})


@mcp.tool()
def add_line_stop(line_id: str, platform_node_id: str) -> dict:
    """Append an oriented platform stop to an operating line using native EditStop."""
    for i in [line_id, platform_node_id]:
        if not valid_id(i):
            raise ValueError("Invalid object ID")
    return request("add_stop", {"line_id": line_id, "node_id": platform_node_id})


@mcp.tool()
def create_line() -> dict:
    """Create an empty operating line through the game's native NewLine command."""
    return request("new_line")


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, openWorldHint=False
    )
)
def get_line(line_id: str) -> dict | None:
    """Read an operating line name, code and stop count."""
    if not valid_id(line_id):
        raise ValueError("Invalid line ID")
    return request("get_line", {"id": line_id})


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, openWorldHint=False
    )
)
def get_station(station_id: str) -> dict | None:
    """Read a station name and world position from the running game."""
    if not valid_id(station_id):
        raise ValueError("Invalid station ID")
    return request("get_station", {"id": station_id})


@mcp.tool()
def rename_station(station_id: str, name: str) -> dict:
    """Rename a station through the native command processor, preserving other settings."""
    if not valid_id(station_id):
        raise ValueError("Invalid station ID")
    if not name or "\x00" in name or len(name.encode("utf-8")) > 1024:
        raise ValueError("Invalid name")
    return request("rename_station", {"id": station_id, "name": name})


@mcp.tool()
def set_station_label_name_and_pax(station_id: str) -> dict:
    """Set the native station label to Name and pax, preserving other settings."""
    if not valid_id(station_id):
        raise ValueError("Invalid station ID")
    return request("station_label", {"id": station_id, "label": 1})


@mcp.tool()
def build_all_blueprints(verify_node_ids: list[str]) -> dict:
    """Build ALL pending blueprints in the active world, then verify supplied nodes are built."""
    if not verify_node_ids:
        raise ValueError("Provide nodes to verify")
    for i in verify_node_ids:
        if not valid_id(i):
            raise ValueError("Invalid node ID")
    return request("build", {"ids": verify_node_ids})


@mcp.tool()
def connect_track_endpoints(
    start_node_id: str, end_node_id: str, dual: bool = True
) -> dict:
    """Connect two existing free endpoints through a native track command."""
    for i in [start_node_id, end_node_id]:
        n = get_track_node(i)
        if n is None or (n["previous"] != "0" and n["next"] != "0"):
            raise ValueError("Expected free endpoints")
    return request(
        "create_track",
        {"start": {"id": start_node_id}, "end": {"id": end_node_id}, "dual": dual},
    )


@mcp.tool()
def create_platform(
    start_x: float, start_y: float, end_x: float, end_y: float, depth: int = -1
) -> dict:
    """Create Medium twin platforms with Name and pax labels, at depth -1, 0 or 1."""
    values = [start_x, start_y, end_x, end_y]
    if not all(math.isfinite(x) and abs(x) <= 21_000_000 for x in values):
        raise ValueError("Invalid world coordinates")
    if not 50 <= math.hypot(end_x - start_x, end_y - start_y) <= 500:
        raise ValueError("Platform must be 50..500 world metres")
    if depth not in [-1, 0, 1]:
        raise ValueError("Depth must be -1, 0 or 1")
    result = request(
        "create_platform",
        {
            "start": {"x": start_x, "y": start_y},
            "end": {"x": end_x, "y": end_y},
            "depth": depth,
        },
    )
    station_ids = sorted({n["station_id"] for n in result["nodes"] if n["station_id"] != "0"})
    try:
        if not station_ids:
            raise RuntimeError("No created station ID returned")
        result["stations"] = [set_station_label_name_and_pax(i)["station"] for i in station_ids]
    except Exception as exc:
        raise RuntimeError(
            f"Platforms created but default label failed. Do not repeat construction. "
            f"Station IDs: {station_ids}; node IDs: {[n['id'] for n in result['nodes']]}"
        ) from exc
    return result


@mcp.tool()
def extend_track(node_id: str, end_x: float, end_y: float, depth: int = -1) -> dict:
    """Experimental: extend an existing track endpoint, including its paired track."""
    n = get_track_node(node_id)
    if n is None:
        raise ValueError("Node not found")
    if n["previous"] != "0" and n["next"] != "0":
        raise ValueError("Node is not an endpoint")
    if not all(math.isfinite(x) for x in [end_x, end_y]):
        raise ValueError("Invalid endpoint")
    if not 1 <= math.hypot(end_x - n["x"], end_y - n["y"]) <= 10000:
        raise ValueError("Segment must be 1..10000 world metres")
    if depth not in [-1, 0, 1]:
        raise ValueError("Depth must be -1, 0 or 1")
    return request(
        "create_track",
        {
            "start": {"id": node_id},
            "end": {"x": end_x, "y": end_y, "depth": depth},
            "dual": True,
        },
    )


@mcp.tool()
def create_track_branch(
    start_edge_id: str,
    start_position: float,
    end_edge_id: str,
    end_position: float,
    depth: int = -1,
) -> dict:
    """Experimental single-track crossover between points on two existing edges."""
    for i in [start_edge_id, end_edge_id]:
        if get_track_node(i) is None:
            raise ValueError("Edge node not found")
    if not all(
        math.isfinite(v) and 0.01 <= v <= 0.99 for v in [start_position, end_position]
    ):
        raise ValueError("Position must be 0.01..0.99")
    if depth not in [-1, 0, 1]:
        raise ValueError("Invalid depth")
    return request(
        "create_track",
        {
            "start": {
                "edge_id": start_edge_id,
                "position": start_position,
                "depth": depth,
            },
            "end": {"edge_id": end_edge_id, "position": end_position, "depth": depth},
            "dual": False,
        },
    )


@mcp.tool()
def create_track_segment(
    start_x: float, start_y: float, end_x: float, end_y: float, dual: bool = True
) -> dict:
    """Experimental: create underground Medium track in game world metres. Returns native nodes.

    Endpoints create new nodes; geographic intersection alone does not connect existing tracks.
    Only use in the dedicated construction sandbox until adapter validation is complete.
    """
    values = [start_x, start_y, end_x, end_y]
    if not all(math.isfinite(x) and abs(x) <= 21_000_000 for x in values):
        raise ValueError("Invalid world coordinates")
    if not 1 <= math.hypot(end_x - start_x, end_y - start_y) <= 10_000:
        raise ValueError("Segment must be 1..10000 world metres")
    return request(
        "create_track",
        {
            "start": {"x": start_x, "y": start_y},
            "end": {"x": end_x, "y": end_y},
            "dual": dual,
        },
    )


@mcp.tool()
def create_single_track_connection(start: dict, end: dict) -> dict:
    """Create a Medium single track using free endpoints, branch positions or coordinates."""
    for point in (start, end):
        if set(point) == {"id"}:
            if not valid_id(point['id']):
                raise ValueError("Invalid endpoint ID")
        elif set(point) == {"edge_id", "position", "depth"}:
            if not valid_id(point['edge_id']) or not 0.01 <= point['position'] <= 0.99:
                raise ValueError("Invalid branch endpoint")
        elif set(point) == {"x", "y", "depth"}:
            if any(not math.isfinite(point[k]) or abs(point[k]) > 21000000 for k in ('x', 'y')):
                raise ValueError("Invalid coordinates")
        else:
            raise ValueError("Invalid endpoint fields")
        if 'depth' in point and (type(point['depth']) is not int or not -3 <= point['depth'] <= 3):
            raise ValueError("Invalid depth")
    return request("create_track", {"start": start, "end": end, "dual": False})


@mcp.tool()
def remove_track_branches(node_ids: list[str]) -> dict:
    """Remove only complete isolated branch pairs via native Delete; preserve parent tracks."""
    if not node_ids or len(node_ids) > 500 or any(not valid_id(i) for i in node_ids):
        raise ValueError("Invalid branch IDs")
    return request("delete_branches", {"ids": list(dict.fromkeys(node_ids))})


@mcp.tool()
def sync_platform_building_depth(node_ids: list[str]) -> dict:
    """Match attached platform buildings to each track node's layer using native Edit."""
    if not node_ids or len(node_ids) > 500 or any(not valid_id(i) for i in node_ids):
        raise ValueError("Expected 1..500 native node IDs")
    return request("sync_building_depth", {"ids": list(dict.fromkeys(node_ids))})


@mcp.tool()
def set_track_depth(node_ids: list[str], depth: int) -> dict:
    """Change track and attached building layers through native tn::Edit and verify both."""
    if not node_ids or len(node_ids) > 500:
        raise ValueError("Provide 1..500 nodes")
    if type(depth) is not int or depth not in [-3, -2, -1, 0, 1, 2, 3]:
        raise ValueError("Invalid depth")
    for i in node_ids:
        if not valid_id(i):
            raise ValueError("Invalid node ID")
    return request("edit_depth", {"ids": list(dict.fromkeys(node_ids)), "depth": depth})


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    finally:
        close()
