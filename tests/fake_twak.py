#!/usr/bin/env python3
"""A stand-in for Trust Wallet's Agent Kit MCP server (twak serve, from @trustwallet/cli), for the tests of #320. It
speaks the earlier MCP era over stdio, as tests/fake_mcp.py does, with a few of twak 0.24.3's own tools as it lists
them (schemas copied, descriptions shortened), plus one it doesn't have, to stand for a tool a later twak adds. Like
twak, none carries MCP annotations. Every message is logged to FAKE_MCP_LOG, so a test can see exactly what was sent.

    python fake_twak.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_mcp  # noqa: E402

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_twak_tools.json"), encoding="utf-8") as f:
    TOOLS = json.load(f)  # as twak 0.24.3 lists them (descriptions shortened)
TOOLS.append({"name": "stake_everything", "description": "A tool added after the list was made.", "inputSchema": {"type": "object", "properties": {}}})


def call_tool(name, args):
    text = lambda t, err=False: dict({"content": [{"type": "text", "text": t}]}, **({"isError": True} if err else {}))  # noqa: E731
    if name == "get_wallet_status":
        return text(json.dumps({"exists": True, "mode": "agent", "address": "0x1111111111111111111111111111111111111111"}))
    if name == "wallet_portfolio":
        return text(json.dumps({"totalUsd": 1234.5, "assets": [{"symbol": "ETH", "amount": "0.4", "usd": 1100.0},
                                                               {"symbol": "PEPE", "amount": "1000000", "usd": 134.5}]}))
    if name == "get_token_price":
        return text(json.dumps({"symbol": args.get("token", "ETH"), "usd": 2750.0}))
    if name == "check_token_risk":
        return text(json.dumps({"risk": "high", "reasons": ["low liquidity"]}))
    if name == "create_alert":
        return text("Alert created.")
    if name in ("transfer", "swap", "x402_request", "stake_everything", "create_automation"):
        return text(f"Done on chain: {name} {json.dumps(args, sort_keys=True)}")
    return None


fake_mcp.TOOLS = TOOLS
fake_mcp.call_tool = call_tool

if __name__ == "__main__":
    fake_mcp.stdio("legacy")
