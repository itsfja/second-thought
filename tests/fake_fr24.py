#!/usr/bin/env python3
"""A stand-in for Flightradar24's MCP server (npx @flightradar24/fr24api-mcp), for the tests of #364. It speaks the
earlier MCP era over stdio, as tests/fake_mcp.py does, with a few of the server's own tools as fr24api-mcp 1.0.2
describes them: live positions, a flight summary and airport details, all read-only, plus one tool the server might
add later, which isn't on the safe list. Every message is logged to FAKE_MCP_LOG, so a test can see exactly what was
sent.

    python fake_fr24.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_mcp  # noqa: E402

TOOLS = [
    {"name": "get_live_flights_positions_light", "description": "Get real-time aircraft positions with basic information.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"flights": {"type": "string"}, "bounds": {"type": "string"}}}},
    {"name": "get_flight_summary_light", "description": "Get essential flight takeoff/landing information.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"flights": {"type": "string"},
                                                    "flight_datetime_from": {"type": "string"},
                                                    "flight_datetime_to": {"type": "string"}},
                    "required": ["flight_datetime_from", "flight_datetime_to"]}},
    {"name": "get_airport_info_light", "description": "Get basic airport information.", "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
    # Not on the safe list: a tool a later fr24api-mcp might add, so it asks first (#364).
    {"name": "get_future_thing", "description": "A tool added after the list was made.", "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {}}, "required": []},
]


def call_tool(name, args):
    text = lambda t: {"content": [{"type": "text", "text": t}]}  # noqa: E731
    if name == "get_live_flights_positions_light":
        flight = (args.get("flights") or "BA123").split(",")[0]
        return text(json.dumps({"flights": [{"flight": flight, "latitude": 51.4700, "longitude": -0.4543,
                                             "altitude_ft": 35000, "groundspeed_kts": 450,
                                             "estimated_landing_time_utc": "2026-11-07T14:30:00Z"}]}))
    if name == "get_flight_summary_light":
        return text(json.dumps({"flights": [{"flight": args.get("flights") or "BA123", "origin": "LHR",
                                             "destination": "JFK", "scheduled_landing_utc": "2026-11-07T14:30:00Z"}]}))
    if name == "get_airport_info_light":
        return text(json.dumps({"code": args.get("code", "LHR"), "name": "London Heathrow", "timezone": "Europe/London"}))
    return None


fake_mcp.TOOLS = TOOLS
fake_mcp.call_tool = call_tool

if __name__ == "__main__":
    fake_mcp.stdio("legacy")
