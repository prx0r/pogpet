"""Writing room client: pogtown joke MCP, called server-side.

Perform lives in oddhobb (one tab). The words come from pogtown's writer.
Same box: localhost:8801. If the room is down the tab still renders —
writing help just reports unavailable, never blocks the stage.
"""
from __future__ import annotations

import json
import os
import urllib.request

PORT = int(os.environ.get("POG_MCP_PORT", "8801"))
URL = f"http://127.0.0.1:{PORT}/mcp"


class JokeRoomDown(Exception):
    pass


def _rpc(method: str, params: dict | None = None, timeout: int = 120) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params or {}}).encode()
    req = urllib.request.Request(
        URL, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            sid = r.headers.get("mcp-session-id")
            raw = r.read().decode()
    except Exception as e:  # noqa: BLE001
        raise JokeRoomDown(f"writing room unreachable: {str(e)[:100]}")
    import re
    m = re.search(r"data: (\{.*\})", raw)
    if not m:
        raise JokeRoomDown("writing room gave no answer")
    data = json.loads(m.group(1))
    if data.get("error"):
        raise JokeRoomDown(str(data["error"])[:150])
    if method == "initialize":
        return {"sid": sid}
    return data.get("result", {})


def call(tool: str, args: dict, timeout: int = 120) -> dict:
    """One MCP round-trip: init + notify + call. Returns parsed JSON."""
    import re
    sid, _ = _raw({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                   "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "oddhobb", "version": "1"}}},
                  timeout)
    _raw({"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout, sid)
    _, out = _raw({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                   "params": {"name": tool, "arguments": args}}, timeout, sid)
    m = re.search(r"data: (\{.*\})", out)
    res = json.loads(m.group(1))["result"]
    return json.loads(res["content"][0]["text"])


def _raw(body: dict, timeout: int, sid: str | None = None) -> tuple:
    data = json.dumps(body).encode()
    h = {"Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid:
        h["mcp-session-id"] = sid
    req = urllib.request.Request(URL, data=data, method="POST", headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.headers.get("mcp-session-id"), r.read().decode()
    except Exception as e:  # noqa: BLE001
        raise JokeRoomDown(f"writing room unreachable: {str(e)[:100]}")
