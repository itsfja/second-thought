#!/usr/bin/env python3
"""A stand-in for Kraken's MCP server (kraken mcp, in kraken-cli), for the tests of #262. It speaks the earlier MCP
era over stdio, as tests/fake_mcp.py does, with a few of Kraken's own tools as kraken-cli 0.5.1 describes them:
read-only ones (annotated readOnlyHint), a paper trade (local: no annotation, no acknowledged), and live-money ones
(destructiveHint, with Kraken's "acknowledged" input). Like Kraken, a live-money call without acknowledged: true is
refused. Every message is logged to FAKE_MCP_LOG, so a test can see exactly what was sent.

    python fake_kraken.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_mcp  # noqa: E402

ACK = {"acknowledged": {"type": "boolean", "description": "Set true to confirm this call reaches the real account."}}
MONEY = {"readOnlyHint": False, "destructiveHint": True}
TOOLS = [
    {"name": "kraken_ticker", "description": "Get ticker information.", "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"pair": {"type": "string"}}, "required": ["pair"]}},
    {"name": "kraken_balance", "description": "Get all cash balances.", "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "kraken_auth_test", "description": "Test authentication by calling the Balance endpoint.", "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "kraken_paper_buy", "description": "Paper buy order.", "annotations": {"readOnlyHint": False},
     "inputSchema": {"type": "object", "properties": {"pair": {"type": "string"}, "volume": {"type": "string"}}, "required": ["pair", "volume"]}},
    {"name": "kraken_order_buy", "description": "Place a buy order.", "annotations": MONEY,
     "inputSchema": {"type": "object", "properties": dict({"pair": {"type": "string"}, "volume": {"type": "string"}}, **ACK),
                     "required": ["pair", "volume", "acknowledged"]}},
    {"name": "kraken_withdraw", "description": "Make a withdrawal.", "annotations": MONEY,
     "inputSchema": {"type": "object", "properties": dict({"asset": {"type": "string"}, "key": {"type": "string"}, "amount": {"type": "string"}}, **ACK),
                     "required": ["asset", "key", "amount", "acknowledged"]}},
    # Not on Kraken's list, but it takes "acknowledged", so it counts as moving money too.
    {"name": "kraken_future_thing", "description": "A tool added after the list was made.", "annotations": MONEY,
     "inputSchema": {"type": "object", "properties": dict(ACK)}},
]


def call_tool(name, args):
    text = lambda t, err=False: dict({"content": [{"type": "text", "text": t}]}, **({"isError": True} if err else {}))  # noqa: E731
    if name == "kraken_ticker":
        return text(json.dumps({args.get("pair", "XBTGBP"): {"c": ["51234.5", "0.01"]}}))
    if name in ("kraken_balance", "kraken_auth_test"):
        if os.environ.get("KRAKEN_API_KEY", "") == "bad":
            return text("EAPI:Invalid key", True)
        return text(json.dumps({"ZGBP": "1200.00", "XXBT": "0.0500"}))
    if name == "kraken_paper_buy":
        return text(f"Paper: bought {args.get('volume')} {args.get('pair')}.")
    if name in ("kraken_order_buy", "kraken_withdraw", "kraken_future_thing"):
        if args.get("acknowledged") is not True:
            return text("This call reaches the real account. Ask the user, then call again with acknowledged: true.", True)
        return text(f"Done for real: {name}.")
    return None


fake_mcp.TOOLS = TOOLS
fake_mcp.call_tool = call_tool

if __name__ == "__main__":
    fake_mcp.stdio("legacy")
