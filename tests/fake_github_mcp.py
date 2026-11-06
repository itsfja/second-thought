#!/usr/bin/env python3
"""A stand-in for GitHub's own MCP server (github-mcp-server, run with stdio), for the tests of #333. It speaks the
earlier MCP era over stdio, as tests/fake_mcp.py does, with a few of GitHub's tools as the real server describes them
(checked 2026-11-06): read-only ones (readOnlyHint), an ordinary write (create_issue), one GitHub doesn't mark
destructive but Second Thought always asks about (merge_pull_request), and a destructive one (delete_file). With
FAKE_GITHUB_READ_ONLY set, it offers only the read-only tools, as --read-only does. Every message is logged to
FAKE_MCP_LOG, so a test can see exactly what was sent.

    python fake_github_mcp.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_mcp  # noqa: E402

REPO = {"owner": {"type": "string"}, "repo": {"type": "string"}}
READ = {"readOnlyHint": True}
FILES = {
    "README.md": "# Rye Planner\n\nPlans a week of rye bakes. Run `python plan.py` with your oven's size.\n",
    "plan.py": "import sys\n\n\ndef loaves(oven_litres):\n    return max(1, int(oven_litres) // 20)\n\n\nprint(loaves(sys.argv[1]))\n",
}
TOOLS = [
    {"name": "get_file_contents", "description": "Get the contents of a file or directory from a GitHub repository.", "annotations": READ,
     "inputSchema": {"type": "object", "properties": dict(REPO, path={"type": "string"}), "required": ["owner", "repo"]}},
    {"name": "get_repository_tree", "description": "Get the tree structure (files and directories) of a GitHub repository.", "annotations": READ,
     "inputSchema": {"type": "object", "properties": dict(REPO), "required": ["owner", "repo"]}},
    {"name": "list_issues", "description": "List issues in a GitHub repository.", "annotations": READ,
     "inputSchema": {"type": "object", "properties": dict(REPO, state={"type": "string"}), "required": ["owner", "repo"]}},
    {"name": "create_issue", "description": "Create a new issue in a GitHub repository.", "annotations": {"readOnlyHint": False},
     "inputSchema": {"type": "object", "properties": dict(REPO, title={"type": "string"}, body={"type": "string"}), "required": ["owner", "repo", "title"]}},
    {"name": "merge_pull_request", "description": "Merge a pull request in a GitHub repository.", "annotations": {"readOnlyHint": False},
     "inputSchema": {"type": "object", "properties": dict(REPO, pullNumber={"type": "number"}), "required": ["owner", "repo", "pullNumber"]}},
    {"name": "delete_file", "description": "Delete a file from a GitHub repository.", "annotations": {"readOnlyHint": False, "destructiveHint": True},
     "inputSchema": {"type": "object", "properties": dict(REPO, path={"type": "string"}), "required": ["owner", "repo", "path"]}},
]


def call_tool(name, args):
    text = lambda t, err=False: dict({"content": [{"type": "text", "text": t}]}, **({"isError": True} if err else {}))  # noqa: E731
    if name == "get_repository_tree":
        return text(json.dumps([{"path": p, "type": "blob"} for p in FILES]))
    if name == "get_file_contents":
        path = str(args.get("path") or "").strip("/")
        if not path:
            return text(json.dumps([{"name": p, "type": "file"} for p in FILES]))
        return text(FILES[path]) if path in FILES else text(f"Not Found: {path}", True)
    if name == "list_issues":
        return text(json.dumps([{"number": 3, "title": "Plan for two ovens", "state": "open"}]))
    if name in ("create_issue", "merge_pull_request", "delete_file"):
        return text(f"Done: {name}.")
    return None


fake_mcp.TOOLS = [t for t in TOOLS if not os.environ.get("FAKE_GITHUB_READ_ONLY") or t["annotations"].get("readOnlyHint")]
fake_mcp.call_tool = call_tool

if __name__ == "__main__":
    fake_mcp.stdio("legacy")
