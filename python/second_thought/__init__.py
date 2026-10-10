"""Second Thought's Python runtime, as a package.

Each module is one part of the runtime:

    settings    reading second-thought.ini and the environment
    providers   the model services and how each is called (the ModelCalls part of Runtime)
    core        limits, errors and the value helpers that mirror the block editor
    connectors  web pages, feeds, calendars, Home Assistant, messaging, MQTT and Homey (the Connections part)
    mcp         MCP servers and their tools, for the agent (the MCPTools part)
    agent       the agent block (the AgentTools part)
    doctor      --doctor: checking a program's setup without spending anything (the Doctor part)
    runtime     Runtime itself: run state, logging, memory, drafts, output, scripts and schedules

Exported programs don't use this package. tools/sync.py joins these modules into python/runtime.py, one file
with nothing to install, and that file goes inside every exported program and the page. So: edit here, then
run `python tools/sync.py`.

Importing the package is for reading and unit-testing the parts. Settings are read from second-thought.ini and
the environment when the package is first imported, exactly as an exported program reads them when it starts.
"""
from .runtime import Runtime  # noqa: F401
