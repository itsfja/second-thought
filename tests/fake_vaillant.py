#!/usr/bin/env python3
"""A stand-in for the unofficial read-only Vaillant MCP server (#363), unofficialMCP4Vaillant, for the tests. It speaks
the earlier MCP era over stdio, as tests/fake_mcp.py does, with the server's four read-only tools as its v1 describes
them, plus one tool a later version might add, which isn't on the safe list. Every message is logged to FAKE_MCP_LOG,
so a test can see exactly what was sent.

    python fake_vaillant.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_mcp  # noqa: E402

TOOLS = [
    {"name": "vaillant_get_status", "description": "Current temperatures, water pressure, modes, per-zone/DHW state.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {}, "required": []}},
    {"name": "vaillant_get_devices", "description": "Static hardware inventory.", "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {}, "required": []}},
    {"name": "vaillant_get_energy_report", "description": "Energy consumption + COP estimate over a time range.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"time_range": {"type": "string"}}, "required": ["time_range"]}},
    {"name": "vaillant_get_diagnostics", "description": "Trouble codes, heating curve, holiday mode.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {}, "required": []}},
    # Not on the safe list: a tool a later version of the server might add, so it asks first (#363).
    {"name": "vaillant_set_quick_mode", "description": "A tool added after the list was made.",
     "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {}, "required": []}},
]


def call_tool(name, args):
    text = lambda t: {"content": [{"type": "text", "text": t}]}  # noqa: E731
    if name == "vaillant_get_status":
        return text(json.dumps({"outdoor_temperature": 4.5, "room_temperature": 20.1, "water_pressure": 1.8,
                                "dhw_temperature": 48.0, "special_function": "NONE"}))
    if name == "vaillant_get_devices":
        return text(json.dumps({"devices": [{"name": "aroTHERM plus", "serial": "…", "firmware": "v2"}]}))
    if name == "vaillant_get_energy_report":
        return text(json.dumps({"time_range": args.get("time_range", "week"), "consumption_kwh": 78.5,
                                "environment_energy_kwh": 236.0, "heat_generated_kwh": 295.0,
                                "cop_estimate": 3.76, "quality": "good"}))
    if name == "vaillant_get_diagnostics":
        return text(json.dumps({"trouble_codes": [], "heating_curve": 0.9, "holiday_mode": False}))
    if name == "vaillant_set_quick_mode":
        return text("Done (not really: this is the stand-in).")
    return None


fake_mcp.TOOLS = TOOLS
fake_mcp.call_tool = call_tool

if __name__ == "__main__":
    fake_mcp.stdio("legacy")
