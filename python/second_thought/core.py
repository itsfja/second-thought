"""Limits, errors, and the value helpers that mirror the block editor exactly.

Part of the second_thought package. tools/sync.py joins these files, in order, into
python/runtime.py, which is what ships inside every exported program and the page.
"""
import asyncio
import base64
import contextlib
import contextvars
import datetime
import hashlib
import json
import math
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from .settings import SETTING_NAMES, WHERE_KEYS
from .settings import tr  # noqa: F401
# ---- package only: tools/sync.py leaves everything above this line out of python/runtime.py ----


MAX_TOKENS = 4096


def _number_setting(name, default, what, whole=False):
    """A number from the settings (second-thought.ini or the environment). A mistake stops the program and says
    which setting is wrong, as a mistake anywhere else in second-thought.ini does, rather than being ignored."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    friendly = next((k for k, v in SETTING_NAMES.items() if v == name), name)
    try:
        n = float(raw)
        if not math.isfinite(n) or n < 0 or (whole and not n.is_integer()):
            raise ValueError
    except ValueError:
        sys.exit((tr("{friendly} must be {what}, not “{raw}”. Fix it {where_keys} (or the {name} environment variable). 0 means no limit.", friendly=friendly, what=what, raw=raw, where_keys=WHERE_KEYS, name=name)
                  if friendly != name else tr("{friendly} must be {what}, not “{raw}”. Fix it {where_keys}. 0 means no limit.", friendly=friendly, what=what, raw=raw, where_keys=WHERE_KEYS)))
    return int(n) if whole else n


# 0 means no limit for all three (call_timeout used to mean 300 at 0; now 0 is no timeout, like the others).
CALL_TIMEOUT = _number_setting("RB_CALL_TIMEOUT", 300, "a number of seconds, like 120") or None  # one model call gives up after this long
MAX_SECONDS = _number_setting("RB_MAX_SECONDS", 0, "a number of seconds, like 900")             # any run stops after this long
BUDGET = _number_setting("RB_BUDGET", 0, "a whole number of tokens, like 50000", whole=True)      # tokens per run
BUDGET_DOLLARS = _number_setting("RB_BUDGET_DOLLARS", 0, "an amount in US dollars, like 0.50")  # US dollars per run, at list prices
BUDGET_MONEY = _number_setting("RB_BUDGET_MONEY", 0, "an amount in your currency, like 0.40")  # the same in the program's currency
MAX_AI_CALLS = 60       # per run, to protect your usage
MAX_STEPS = 20000       # stops loops that never end
MAX_SCRIPTS = 100       # scripts started by broadcasts in one run
MAX_DEPTH = 60          # My Blocks calling themselves
OUTPUT_DIR = "outputs"  # where pictures are saved
LOG_DIR = "logs"        # where run logs go when save_log = yes in second-thought.ini
# 'forever' and timed memories live in this file, next to the program.
MEMORY_FILE = os.environ.get("RB_MEMORY_FILE") or os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "memory.json")


# Home Assistant: the address of your Home Assistant and a long-lived access token
# (your Home Assistant profile, Security tab, "Long-lived access tokens").
HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
HA_TTS_ENTITY = os.environ.get("HA_TTS_ENTITY", "tts.home_assistant_cloud")  # used by the 'say … on' block
HA_WATCH_SECONDS = 15  # how often 'when … changes' scripts check Home Assistant
# ----- The safety rules: what always asks -----
# One list, read by exported programs and (copied in by tools/sync.py) by the page, so both ask before the same things.
# The patterns are regular expressions that mean the same in Python and JavaScript. tests/unit/test_safety.py checks
# both sides give the same answers.
SAFETY = {
    # Home Assistant actions that unlock, open or disarm: they always ask, even with 'control devices (no asking)'. Locks,
    # covers (garage doors, gates, blinds) and valves: everything but locking, closing and stopping, since toggling or
    # setting a position can open them too.
    "ha_sensitive": [r"^lock\.(?!lock$)", r"^cover\.(?!(close_cover|close_cover_tilt|stop_cover|stop_cover_tilt)$)",
                     r"^valve\.(?!(close_valve|stop_valve)$)", r"^alarm_control_panel\.alarm_disarm$", r"^garage_door\.open"],
    # homeassistant.turn_on, turn_off and toggle reach any device, so they ask when aimed at one of these.
    "ha_generic": r"^homeassistant\.(turn_on|turn_off|toggle)$",
    "ha_sensitive_entity": r"^(lock|cover|valve|alarm_control_panel)\.",
    # Targets other than entities (in a service call's data, or its "target"): with the generic services above, we can't
    # see which devices they reach, so they ask too (#303). So does entity_id "all", or no target at all.
    "ha_wide_targets": ["area_id", "device_id", "floor_id", "label_id"],
    # Homey changes that unlock, open or disarm: [capability, value].
    "homey_sensitive": [["locked", False], ["garagedoor_closed", False], ["homealarm_state", "disarmed"]],
    # Coinbase's Advanced Trade API (#371): the calls that run without asking, [method, path]. Reading, and previewing an
    # order. Any other call (placing, editing or cancelling an order, converting, moving funds) can move real money: it
    # always asks, even with (no asking), and never runs with nobody there to ask, like Kraken's money tools (#262).
    "coinbase_free": [["GET", r"^/api/v3/brokerage/[A-Za-z0-9_/.-]+$"], ["POST", r"^/api/v3/brokerage/orders/preview$"]],
    # MikroTik's RouterOS REST API (#360): the only calls made, [method, path]. Reading, and the monitor command, which
    # only reads but is a POST. Nothing else is ever sent: no changes, no reboot. A switch that loses its config takes
    # the network with it, and nothing here is worth that.
    # UniFi's Network API (#359), the Integration API on a UniFi OS console: the only calls made. Reading clients and
    # devices; nothing that blocks, reconnects or restarts, and nothing near the firewall, VLANs or WiFi.
    # Proxmox VE's REST API (#357): the reads the runtime makes, and the power actions it may make after a yes. Nothing
    # else is ever sent: no destroying, no snapshots rolled back, no commands run in a guest, no storage, permissions or
    # firewall changes. A power action always asks, live, and never runs with nobody there; PROXMOX_PROTECT lists
    # guests it never touches at all.
    "proxmox_free": [["GET", r"^/api2/json/(version|nodes|cluster/resources|cluster/tasks|access/permissions|nodes/[A-Za-z0-9.-]+/(qemu|lxc)/\d+/config)$"]],
    "proxmox_asks": [["POST", r"^/api2/json/nodes/[A-Za-z0-9.-]+/(qemu|lxc)/\d+/status/(start|shutdown|reboot)$"]],
    # Docker's Engine API (#358): the reads the runtime makes, and what it may do to a container after a yes. Nothing
    # else is ever sent: no exec, run, rm, pull or build (each can run anything on the machine as root), and nothing
    # to do with images, volumes or networks. Restart, stop and start always ask, live, and never run with nobody there.
    "docker_free": [["GET", r"^/(version|containers/json|containers/[A-Za-z0-9][A-Za-z0-9_.-]*/(json|stats|logs))$"]],
    "docker_asks": [["POST", r"^/containers/[A-Za-z0-9][A-Za-z0-9_.-]*/(restart|stop|start)$"]],
    # SABnzbd's API (#397): one endpoint whose mode says what's asked for, so the gate matches the mode. The reads the
    # runtime makes, and pause and resume, which need a live yes. Nothing else is ever sent: no adding or deleting jobs,
    # no retry, no speedlimit, no config, no shutdown, and nothing that touches servers or categories.
    "sabnzbd_free": [["GET", r"^(queue|history|diskspace)$"]],
    "sabnzbd_asks": [["GET", r"^(pause|resume)$"]],
    # Radarr and Sonarr's Servarr API (#398): the reads the runtime makes, and the one command it may send after a yes.
    # The command's name is in the body, checked separately against ARR_SEARCH; nothing else is ever sent: no adding or
    # deleting, no editing profiles or root folders, nothing in the indexer or download-client settings, no refresh.
    "arr_free": [["GET", r"^/api/v3/(queue|wanted/missing|diskspace|system/status)$"]],
    "arr_asks": [["POST", r"^/api/v3/command$"]],
    # Unraid's own GraphQL API (#399), all of it one POST to /graphql, so the gate reads the query text: a query is a
    # read, and only these mutations are ever sent, after a live yes: starting or stopping one container or VM by
    # name, and a parity read-check. Anything else (stopping the array, adding or removing disks, updating
    # containers, plugins, terminal commands) is never sent.
    "unraid_free": [["POST", r"^(?![\s\S]*mutation)\s*(query|\{)"]],
    "unraid_asks": [["POST", r'^mutation\{docker\{(start|stop)\(id:"container:[^"]+"\)\{id\}\}\}$'],
                    ["POST", r'^mutation\{vm\{(start|stop)\(id:"vm:[^"]+"\)\}\}$'],
                    ["POST", r"^mutation\{parity\{start\(correct:false\)\}\}$"]],
    # NZBGeek's Newznab API (#400): one GET to /api, so the gate reads the query. The searches and t=caps are reads;
    # the one fetch (t=get, an NZB file, with a paid account's key) always asks, live. Nothing else is ever sent:
    # no account changes, no VIP time, no payments, and a search that smuggles t=get is refused.
    "nzbgeek_free": [["GET", r"^(?!.*(^|&)t=get(&|$))t=(search|tvsearch|movie|caps)(&|$)"]],
    "nzbgeek_asks": [["GET", r"^(?!.*(^|&)t=(search|tvsearch|movie|caps)(&|$))t=get&id=[^&]+$"]],
    "unifi_free": [["GET", r"^/proxy/network/integration/v1/(info|sites|sites/[A-Za-z0-9-]+/(clients|devices|devices/[A-Za-z0-9-]+/statistics/latest))$"]],
    # Tesla's Powerwall gateway (#362): the reads the runtime makes, and the one thing it may change after a yes. Nothing
    # else is ever sent: no firmware, no storm watch, no operation mode, no grid charging or export setting.
    "powerwall_free": [["GET", r"^/api/(meters/aggregates|system_status/soe|system_status/grid_status|operation)$"]],
    "powerwall_asks": [["POST", r"^/api/operation$"]],
    "mikrotik_free": [["GET", r"^/rest/(interface|system/resource|system/health|log|user|user/group)$"],
                      ["POST", r"^/rest/interface/ethernet/monitor$"]],
    # Built-in agent tools that ask before each use.
    "agent_asks": ["ha_act", "github_act", "telegram_send", "email_send", "mqtt_act", "homey_act", "discord_send", "slack_send"],
    # Tools that let an agent see private things. An agent with any of them can't read a page or feed whose address it
    # made up (one that wasn't in its goal or in anything it read) without asking: the address itself could carry the
    # private things away, like https://example.com/?d=<your emails>.
    "agent_private": ["email", "email_send", "calendar", "telegram", "telegram_send", "telegram_send_free", "discord", "discord_send",
                      "discord_send_free", "slack", "slack_send", "slack_send_free", "github", "github_act", "ha_read", "ha_act",
                      "ha_act_free", "homey_read", "homey_act", "homey_act_free", "mqtt", "mqtt_act", "mqtt_act_free", "memory", "file", "mcp"],
    # Home Assistant services an agent can't run without asking, even with 'control devices (no asking)': they run
    # scripts, scenes or automations, or press buttons, and so could do anything, unlocking included.
    "agent_ha_indirect": [r"^script\.", r"^scene\.", r"^automation\.trigger$", r"^(input_)?button\.press$"],
    # MQTT messages an agent can't publish without asking (matched in the topic and message, any case).
    "mqtt_unlock": r"\b(unlock|open|disarm)",
    # An address in what the agent was given or read (#304): whole addresses are compared, never a piece of one. Ends in
    # . , ; : ! ? and a ) that closes nothing are punctuation, not part of the address.
    "agent_seen_address": r"https?://[^\s\"'<>\[\]{}]+",
    # MCP tools that can reach real money (#262): they always ask, even with (no asking), never run with nobody there
    # to ask (a schedule, GitHub Actions, --mcp), and the agent can't answer for the person. Kraken's own list: every tool
    # its agents/tool-catalog.json marks dangerous, paper_safe or local_or_live (kraken-cli 0.5.1, checked 2026-11-03).
    # Any MCP tool that takes an "acknowledged" input counts too: that's how Kraken marks one, so a new tool is covered.
    "mcp_money": ["kraken_earn_allocate", "kraken_earn_deallocate", "kraken_export_delete", "kraken_export_retrieve",
                  "kraken_futures_batch_order", "kraken_futures_cancel", "kraken_futures_cancel_after", "kraken_futures_cancel_all",
                  "kraken_futures_edit_order", "kraken_futures_order_buy", "kraken_futures_order_sell", "kraken_futures_set_leverage",
                  "kraken_futures_set_pnl_preference", "kraken_futures_set_subaccount_status", "kraken_futures_transfer",
                  "kraken_futures_wallet_transfer", "kraken_order_amend", "kraken_order_batch", "kraken_order_buy", "kraken_order_cancel",
                  "kraken_order_cancel_after", "kraken_order_cancel_all", "kraken_order_cancel_batch", "kraken_order_edit",
                  "kraken_order_sell", "kraken_paper_reset", "kraken_subaccount_create", "kraken_subaccount_transfer",
                  "kraken_wallet_transfer", "kraken_withdraw", "kraken_withdrawal_cancel", "kraken_workspace_create",
                  "kraken_workspace_promote", "kraken_workspace_reset"],
    # Inputs that say "yes, really" to a money tool: Kraken's acknowledged, and Trust Wallet's autoApprove (x402
    # payments, #320). The agent is never offered them; only the person's yes sets them.
    "mcp_money_inputs": ["acknowledged", "autoApprove"],
    # Trust Wallet's Agent Kit (twak serve, #320), judged the safe way round like Kraken: only these tools run without
    # the money question (balances, prices, history, quotes, risk checks, price alerts); any other counts as money,
    # including transfer, swap, token approvals and x402 payments, and any tool a later twak adds. twak 0.24.3, checked
    # 2026-11-06. Its tools carry no MCP annotations, so this list is all there is.
    "mcp_twak_safe": ["check_alerts", "check_allowance", "check_token_risk", "competition_status", "create_alert", "delete_alert",
                      "delete_automation", "erc8004_get_metadata", "erc8004_show", "erc8183_policy_info", "erc8183_status",
                      "get_address", "get_asset_info", "get_balance", "get_offramp_quote", "get_offramp_url", "get_onramp_quote",
                      "get_onramp_url", "get_swap_history", "get_swap_quote", "get_token_holdings", "get_token_price",
                      "get_transaction_details", "get_transaction_history", "get_trending_tokens", "get_wallet_status",
                      "list_addresses", "list_alerts", "list_automations", "search_assets", "token_balance", "validate_transaction",
                      "wallet_balance", "wallet_portfolio", "x402_quote"],
    # Never offered to an agent (#320): an automation trades later, inside twak, where nothing here can ask first.
    "mcp_twak_never": ["create_automation"],
    # The other way round, so it fails safe (#309): Kraken's tools known not to move money, the ones its catalog marks
    # read_only or local (paper trading, notes); kraken-cli 0.5.1, checked 2026-11-06. Any other kraken_ tool, such as
    # one a later kraken-cli adds, counts as money and asks.
    # MCP tools that ask first even under (no asking), like those marked destructiveHint (#333): GitHub's that change a
    # repository's code or history, or make, remove or fork one, which its own server doesn't mark destructive
    # (github-mcp-server, checked 2026-11-06). Any server's tool by these names counts; read-only marks still win.
    "mcp_always_ask": ["create_or_update_file", "create_repository", "create_repository_ruleset", "delete_file", "delete_repository",
                       "fork_repository", "merge_pull_request", "push_files", "update_pull_request_branch"],
    "mcp_kraken_safe": ["kraken_assets", "kraken_auth_show", "kraken_auth_test", "kraken_balance",
                     "kraken_closed_orders", "kraken_credit_lines", "kraken_deposit_addresses",
                     "kraken_deposit_methods", "kraken_deposit_status", "kraken_earn_allocate_status",
                     "kraken_earn_allocations", "kraken_earn_deallocate_status", "kraken_earn_strategies",
                     "kraken_explain_pnl", "kraken_export_report", "kraken_export_status", "kraken_extended_balance",
                     "kraken_feedback", "kraken_futures_accounts", "kraken_futures_assignment_programs",
                     "kraken_futures_fee_schedule_volumes", "kraken_futures_feeschedules", "kraken_futures_fills",
                     "kraken_futures_historical_funding_rates", "kraken_futures_history",
                     "kraken_futures_history_account_log_csv", "kraken_futures_history_executions",
                     "kraken_futures_history_orders", "kraken_futures_history_triggers",
                     "kraken_futures_instrument_status", "kraken_futures_instruments", "kraken_futures_leverage",
                     "kraken_futures_notifications", "kraken_futures_open_orders", "kraken_futures_order_status",
                     "kraken_futures_orderbook", "kraken_futures_paper_balance", "kraken_futures_paper_batch_order",
                     "kraken_futures_paper_buy", "kraken_futures_paper_cancel", "kraken_futures_paper_cancel_all",
                     "kraken_futures_paper_edit_order", "kraken_futures_paper_fills", "kraken_futures_paper_history",
                     "kraken_futures_paper_init", "kraken_futures_paper_leverage",
                     "kraken_futures_paper_order_status", "kraken_futures_paper_orders",
                     "kraken_futures_paper_positions", "kraken_futures_paper_reset", "kraken_futures_paper_sell",
                     "kraken_futures_paper_set_leverage", "kraken_futures_paper_status",
                     "kraken_futures_pnl_preferences", "kraken_futures_positions", "kraken_futures_subaccount_status",
                     "kraken_futures_subaccounts", "kraken_futures_ticker", "kraken_futures_tickers",
                     "kraken_futures_trading_instruments", "kraken_futures_transfers", "kraken_futures_unwind_queue",
                     "kraken_lab_compare", "kraken_lab_curve", "kraken_lab_new", "kraken_lab_next",
                     "kraken_lab_score", "kraken_lab_show", "kraken_ledgers", "kraken_ohlc", "kraken_open_orders",
                     "kraken_orderbook", "kraken_orderbook_grouped", "kraken_orderbook_l3", "kraken_pairs",
                     "kraken_paper_balance", "kraken_paper_buy", "kraken_paper_cancel", "kraken_paper_cancel_all",
                     "kraken_paper_history", "kraken_paper_init", "kraken_paper_orders", "kraken_paper_sell",
                     "kraken_paper_status", "kraken_plugin_init", "kraken_plugin_list", "kraken_positions",
                     "kraken_query_ledgers", "kraken_query_orders", "kraken_query_trades", "kraken_recipe_create",
                     "kraken_recipe_list", "kraken_recipe_show", "kraken_server_time", "kraken_session_decisions",
                     "kraken_session_list", "kraken_session_note", "kraken_session_show", "kraken_session_state_get",
                     "kraken_session_state_set", "kraken_session_stop", "kraken_spreads", "kraken_status",
                     "kraken_tape_list", "kraken_ticker", "kraken_trade_balance", "kraken_trades",
                     "kraken_trades_history", "kraken_volume", "kraken_withdrawal_addresses",
                     "kraken_withdrawal_info", "kraken_withdrawal_methods", "kraken_withdrawal_status",
                     "kraken_workspace_balance", "kraken_workspace_list", "kraken_workspace_report",
                     "kraken_workspace_show", "kraken_workspace_status"],
    # Flightradar24's own MCP server (#364): every tool it offers only reads — live and historic flight positions,
    # flight summaries, tracks, and airline and airport details (fr24api-mcp 1.0.2, checked 2026-11-06). A tool a
    # later server adds, or one that leaves this list, asks first: the safe way round, like Kraken's (#309).
    "mcp_fr24_safe": ["get_airline_info", "get_airport_info_full", "get_airport_info_light", "get_flight_summary_count",
                      "get_flight_summary_full", "get_flight_summary_light", "get_flight_tracks",
                      "get_historic_flights_count", "get_historic_flights_positions_full",
                      "get_historic_flights_positions_light", "get_live_flights_count",
                      "get_live_flights_positions_full", "get_live_flights_positions_light"],
    # The unofficial read-only Vaillant MCP server (#363): unofficialMCP4Vaillant v1 is read-only by design — status,
    # devices, the energy report and diagnostics, each cached (status 60s, energy 5 min) so the myVAILLANT account
    # behind it is polled gently. The API is unofficial and reverse-engineered, so it can change whenever Vaillant
    # changes the app: a tool this list has never seen asks first, the safe way round like Kraken's (#309).
    "mcp_vaillant_safe": ["vaillant_get_devices", "vaillant_get_diagnostics", "vaillant_get_energy_report",
                          "vaillant_get_status"],
}
HA_SENSITIVE = tuple(SAFETY["ha_sensitive"])
HA_SENSITIVE_ENTITY = SAFETY["ha_sensitive_entity"]


def coinbase_money(method, path):
    """True for a Coinbase API call that could move real money (#371): anything but reading and previewing an order."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    return not any(m == method and re.match(p, path) for m, p in SAFETY["coinbase_free"])


def powerwall_allowed(method, path, approved=False):
    """True for one of the few Tesla gateway calls the runtime makes (#362): the reads in powerwall_free, and the
    backup reserve change in powerwall_asks, only after the person's yes."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    return any(m == method and re.match(p, path) for m, p in SAFETY["powerwall_free"]) \
        or (approved and any(m == method and re.match(p, path) for m, p in SAFETY["powerwall_asks"]))


def mikrotik_allowed(method, path):
    """True for one of the few RouterOS REST calls the runtime makes (#360): reading, never changing."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    return any(m == method and re.match(p, path) for m, p in SAFETY["mikrotik_free"])


def proxmox_call(method, path):
    """"free" for a Proxmox call the runtime makes without asking, "asks" for a power action that needs a live yes,
    and None for anything else, which is never sent (#357)."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, path) for m, p in SAFETY["proxmox_" + kind]):
            return kind
    return None


def docker_call(method, path):
    """"free" for a Docker call the runtime makes without asking, "asks" for restart, stop and start, which need a live
    yes, and None for anything else, which is never sent (#358)."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, path) for m, p in SAFETY["docker_" + kind]):
            return kind
    return None


def sabnzbd_call(method, mode):
    """"free" for a SABnzbd call the runtime makes without asking, "asks" for pause and resume, which need a live yes,
    and None for anything else, which is never sent (#397)."""
    method, mode = to_str(method).strip().upper(), to_str(mode).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, mode) for m, p in SAFETY["sabnzbd_" + kind]):
            return kind
    return None


ARR_SEARCH = {"radarr": "MissingMovieSearch", "sonarr": "MissingEpisodeSearch"}


def arr_call(method, path):
    """"free" for a Radarr or Sonarr call the runtime makes without asking, "asks" for the one search command, which
    needs a live yes, and None for anything else, which is never sent (#398)."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, path) for m, p in SAFETY["arr_" + kind]):
            return kind
    return None


def nzbgeek_call(method, query):
    """"free" for one of NZBGeek's Newznab reads (a search, or t=caps), "asks" for the one fetch (t=get, an NZB
    file, with a paid account's key), and None for anything else, which is never sent (#400). The query is read as
    a whole: a search that smuggles t=get is refused, and so is a fetch that smuggles a search."""
    method, query = to_str(method).strip().upper(), to_str(query).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, query) for m, p in SAFETY["nzbgeek_" + kind]):
            return kind
    return None


def unraid_call(method, query):
    """"free" for a Unraid GraphQL query the runtime makes without asking (a query is a read), "asks" for the few
    mutations that need a live yes (starting or stopping one container or VM, a parity read-check), and None for
    anything else, which is never sent (#399)."""
    method, query = to_str(method).strip().upper(), to_str(query).strip()
    for kind in ("free", "asks"):
        if any(m == method and re.match(p, query) for m, p in SAFETY["unraid_" + kind]):
            return kind
    return None


def unifi_allowed(method, path):
    """True for one of the few UniFi Network API calls the runtime makes (#359): reading, never changing."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    return any(m == method and re.match(p, path) for m, p in SAFETY["unifi_free"])


def same_problem(a, b):
    """Whether two review problems say the same thing (#331): the same words, or mostly the same longer words, since a
    reviewer asked to repeat a problem doesn't always manage it word for word."""
    words = lambda t: {w for w in re.findall(r"[a-z0-9]+", to_str(t).lower()) if len(w) > 3}  # noqa: E731
    if to_str(a).strip().lower() == to_str(b).strip().lower():
        return True
    wa, wb = words(a), words(b)
    return bool(wa and wb) and len(wa & wb) >= 0.6 * min(len(wa), len(wb))


def seen_addresses(text):
    """Every web address in text, whole, without trailing punctuation or slashes: what an agent was given or read (#304)."""
    out = set()
    for m in re.findall(SAFETY["agent_seen_address"], to_str(text)):
        while m and (m[-1] in ".,;:!?" or (m[-1] == ")" and m.count("(") < m.count(")"))):
            m = m[:-1]
        out.add(m.rstrip("/"))
    return out


def ha_sensitive(service, entity="", data=None):
    """True for an action that could unlock, open or disarm: a sensitive service, or homeassistant.turn_on, turn_off or
    toggle that could reach a lock, cover, valve or alarm (they reach the same devices). That's judged on the call as
    sent: the entity and any entity_id in the data (JSON text or a dict); an area, device, floor or label target,
    entity_id "all" or no target at all count too, since we can't see what they reach (#303)."""
    service = to_str(service).strip()
    if any(re.match(p, service) for p in HA_SENSITIVE):
        return True
    if not re.match(SAFETY["ha_generic"], service):
        return False
    if not isinstance(data, dict):
        try:
            data = json.loads(to_str(data)) if to_str(data).strip() else {}
        except ValueError:
            data = {}
        data = data if isinstance(data, dict) else {}
    parts = [data] + ([data["target"]] if isinstance(data.get("target"), dict) else [])
    if any(p.get(k) not in (None, "", []) for p in parts for k in SAFETY["ha_wide_targets"]):
        return True
    ids = [to_str(entity)] + [i for p in parts for i in (p.get("entity_id") if isinstance(p.get("entity_id"), list) else [p.get("entity_id")])
                              if i is not None]
    ids = [e for i in ids for e in re.split(r"[\s,]+", to_str(i).strip()) if e]
    return not ids or any(e.lower() == "all" or re.match(HA_SENSITIVE_ENTITY, e) for e in ids)

# Connections. Each one is only needed if your program uses it; put the keys in second-thought.ini.
# GitHub: a token from https://github.com/settings/tokens (read access to your repositories is enough to look;
# to comment on pull requests it also needs pull request write access).
GITHUB_API = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
# Telegram: make a bot by talking to @BotFather in Telegram; it gives you the token. TELEGRAM_CHAT_ID is your own chat
# with the bot: the bot only listens to, and searches, the chats listed there (anyone can message a bot).
TELEGRAM_API = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org").rstrip("/")
TELEGRAM_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "telegram-messages.json")
# The last text of each page a 'when the web page … changes' block watches, so a restart doesn't count every page as changed.
PAGES_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "watched-pages.json")
# Discord: a bot token (Discord Developer Portal, your application, Bot, Reset Token) with the Message Content intent
# turned on, and DISCORD_CHANNEL_ID: the channels it reads and posts in (anyone in a server can post, so only these count).
# Slack: a bot token (api.slack.com/apps, your app, OAuth & Permissions; scopes channels:history, groups:history,
# chat:write) and SLACK_CHANNEL_ID, the channels it reads and posts in. Invite the bot to each channel.
DISCORD_API = os.environ.get("DISCORD_API_URL", "https://discord.com/api/v10").rstrip("/")
SLACK_API = os.environ.get("SLACK_API_URL", "https://slack.com/api").rstrip("/")
# Email: your address and an app password (Gmail: Google account, Security, App passwords). The mail servers are
# worked out for Gmail, iCloud, Yahoo, Fastmail and mailbox.org; for anything else set EMAIL_IMAP_HOST and EMAIL_SMTP_HOST.
# MQTT: MQTT_HOST is your broker (for example homeassistant.local, if it runs Mosquitto), with MQTT_USERNAME and
# MQTT_PASSWORD if it needs them. MQTT_TLS = yes for an encrypted connection (port 8883). Needs  pip install paho-mqtt.
# Web requests: WEBHOOK_SECRET is a password every request must carry (?key=... or an X-Second-Thought-Key header);
# WEBHOOK_PORT is the port to listen on (8765 if you don't say). Only this computer can reach it unless
# WEBHOOK_HOST = 0.0.0.0, which opens it to every network the computer is on (Home Assistant elsewhere, your phone).
# Calendar: CALENDAR_URL is your calendar's private iCal address (Google Calendar: Settings, your calendar,
# "Secret address in iCal format"; Outlook: Settings, Calendar, Shared calendars, Publish; iCloud: share as public).
# Several addresses can be separated by spaces.

MESSAGE_VALUE = contextvars.ContextVar("message_value", default="")
MODEL_OVERRIDE = contextvars.ContextVar("model_override", default=None)  # set by 'with model' blocks
# Server-side web search for the 'search the web' block. Your API organisation must allow it.
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}


class Reply(str):
    """A model's reply text that also says whether it was cut off by the length limit."""
    def __new__(cls, text, truncated=False):
        r = str.__new__(cls, text)
        r.truncated = bool(truncated)
        return r


CONTINUE_PROMPT = "Continue exactly where you stopped. Don't repeat anything you've already written."


class Finish(Exception):
    """Raised by 'finish' and 'stop the run' blocks."""


class RunError(Exception):
    """A problem in the program itself."""


class Retryable(RunError):
    """A failure a second try could fix (a garbled or empty reply)."""


# ----- pictures -----

class BadJSON(Retryable):
    """The model's reply wasn't readable JSON."""


class Picture:
    """A picture: a file you chose, or an SVG illustration Claude drew."""
    _count = 0

    def __init__(self, data, media_type, name=None, svg=None):
        Picture._count += 1
        self.data, self.media_type, self.svg = data, media_type, svg
        self.name = name or f"picture-{Picture._count}"
        self.path = None

    def __str__(self):
        return f"[picture: {self.name}]"


_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml"}
_EXT = {v: k for k, v in _MEDIA.items() if k != ".jpeg"}


def clean_svg(text):
    m = re.search(r"<svg[\s\S]*</svg>", to_str(text), re.I)
    if not m:
        return None
    svg = m.group(0)
    svg = re.sub(r"<(script|foreignObject|iframe)\b[\s\S]*?</\1\s*>", "", svg, flags=re.I)
    svg = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg, flags=re.I)
    svg = re.sub(r"\s(xlink:)?href\s*=\s*(\"(?!#|data:image/)[^\"]*\"|'(?!#|data:image/)[^']*')", "", svg, flags=re.I)
    if "xmlns=" not in svg[:300]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return svg


def _need_picture(v, where):
    if not isinstance(v, Picture):
        raise RunError(tr("The '{where}' block needs a picture in its picture slot.", where=where))
    return v


# ----- value helpers (they mirror the block editor exactly) -----

def _clean_num(n):
    if isinstance(n, float) and n.is_integer() and abs(n) < 1e15:
        return int(n)
    return n


def num(v):
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return v
    try:
        s = str(v).strip()
        return _clean_num(float(s)) if s else 0
    except (TypeError, ValueError):
        return 0


def to_str(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "\n".join(to_str(x) for x in v)
    if isinstance(v, dict):
        return "\n".join(f"{k}: " + (", ".join(to_str(x) for x in val) if isinstance(val, list) else to_str(val)) for k, val in v.items())
    if isinstance(v, float):
        return str(_clean_num(v))
    return str(v)  # Picture.__str__ gives "[picture: name]"


def to_bool(v):
    if isinstance(v, str):
        return not (v == "" or v.lower() == "false" or v == "0")
    if isinstance(v, list):
        return True
    return bool(v)


# A list item's marker: "- " or "* ", "•", or a number with . or ) after it ("1.", "3)", "(2)"). Only those, so
# "10 green bottles", "2024 plan", "1.5 kg flour" and "-5 °C" keep their numbers. The page's list() is the same.
_BULLET = re.compile(r"^\s*(?:[-*](?=\s)|•|\(?\d+[.)](?!\d))\s*")


def to_list(v):
    if isinstance(v, list):
        return v
    if v is None or v == "":
        return []
    out = []
    for line in re.split(r"\n+", to_str(v)):
        item = _BULLET.sub("", line).strip()
        if item:
            out.append(item)
    return out


def _num_like(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str) and v.strip():
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False


def compare(a, op, b):
    if _num_like(a) and _num_like(b):
        x, y = num(a), num(b)
    else:
        x, y = to_str(a).lower(), to_str(b).lower()
    return {"EQ": x == y, "NEQ": x != y, "LT": x < y, "LTE": x <= y, "GT": x > y, "GTE": x >= y}[op]


def arith(a, op, b):
    a, b = num(a), num(b)
    if op == "ADD":
        r = a + b
    elif op == "MINUS":
        r = a - b
    elif op == "MULTIPLY":
        r = a * b
    elif op == "DIVIDE":
        if b == 0:
            raise RunError(tr("Can't divide by zero."))
        r = a / b
    else:
        r = math.pow(a, b)
    return _clean_num(r)


def random_int(a, b):
    a, b = round_js(num(a)), round_js(num(b))
    if a > b:
        a, b = b, a
    return random.randint(a, b)


def round_js(n):
    return int(math.floor(n + 0.5))


def round_op(n, op):
    n = num(n)
    return {"ROUND": round_js(n), "ROUNDUP": int(math.ceil(n)), "ROUNDDOWN": int(math.floor(n))}[op]


def modulo(a, b):
    a, b = num(a), num(b)
    if b == 0:
        raise RunError(tr("Can't divide by zero."))
    return _clean_num(math.fmod(a, b))


def join(*parts):
    return "".join(to_str(p) for p in parts)


def length(v):
    return len(v) if isinstance(v, list) else len(to_str(v))


def is_empty(v):
    return len(to_str(v)) == 0


def change_case(v, mode):
    t = to_str(v)
    if mode == "UPPERCASE":
        return t.upper()
    if mode == "LOWERCASE":
        return t.lower()
    return re.sub(r"\S+", lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(), t)


def contains(a, b):
    return to_str(b).lower() in to_str(a).lower()


def word_count(v):
    t = to_str(v).strip()
    return len(t.split()) if t else 0


def count(start, end, by):
    start, end, by = num(start), num(end), abs(num(by)) or 1
    if start > end:
        by = -by
    i = start
    while (i <= end) if by > 0 else (i >= end):
        yield _clean_num(i)
        i += by


def times(n):
    return range(max(0, int(math.floor(num(n)))))


def field_list(f):
    return [x.strip() for x in re.split(r"[,\n]+", to_str(f)) if x.strip()]


def to_record(o, fields=()):
    r = {}
    if isinstance(o, dict):
        for k, v in o.items():
            r[k] = json.dumps(v) if isinstance(v, dict) else v
    for f in fields:
        r.setdefault(f, "")
    return r


def rec_get(rec, key):
    if not isinstance(rec, dict):
        raise RunError(tr("'{key} of' needs a record in its second slot.", key=to_str(key)))
    return rec.get(to_str(key).strip(), "")


def rec_set(rec, key, value):
    key = to_str(key).strip()
    if not key:
        raise RunError(tr("The 'set … of record' block needs a field name."))
    if not isinstance(rec, dict):
        raise RunError(tr("The 'set {key} of' block needs a record in its middle slot.", key=key))
    rec[key] = value


def rec_has(rec, key):
    return isinstance(rec, dict) and to_str(key).strip() in rec


def rec_keys(rec):
    return list(rec.keys()) if isinstance(rec, dict) else []


def sort_by(items, key, order):
    items, key = list(to_list(items)), to_str(key).strip()
    get = (lambda it: it.get(key, "") if isinstance(it, dict) else "") if key else (lambda it: it)
    nums = all(_num_like(get(it)) for it in items)
    items.sort(key=(lambda it: num(get(it))) if nums else (lambda it: to_str(get(it)).lower()), reverse=(order != "asc"))
    return items


def _parse_json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except ValueError:
            pass
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    end = max(text.rfind("}"), text.rfind("]"))
    if starts and end > min(starts):
        try:
            return json.loads(text[min(starts):end + 1])
        except ValueError:
            pass
    raise BadJSON(tr("Claude's reply came back in an unreadable format. Run again."))


# ----- Structured replies -----
# Every block that wants JSON names the shape it expects. Claude is held to that shape while it writes (constrained
# decoding). Every other model is checked after it replies, and asked once to fix a reply that doesn't fit.
# The page keeps a copy of these shapes (SCHEMAS in second-thought.html); keep the two the same.
_ANY = {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "boolean"}]}


class Shape(dict):
    """A reply shape sent to Claude, with a looser one (check) to judge the reply by afterwards. The agent's step is held
    to its tools' input types while Claude writes, but a wrong-typed input is still the tool's to refuse, as 'bad input'
    with the reason, not a reply to repair."""
    def __init__(self, shape, check):
        super().__init__(shape)
        self.check = check


def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


SCHEMAS = {
    "yesno": _obj({"answer": {"type": "boolean"}}, ["answer"]),
    "number": _obj({"number": {"type": "number"}}, ["number"]),
    "list": _obj({"items": {"type": "array", "items": {"type": "string"}}}, ["items"]),
    "score": _obj({"score": {"type": "number"}}, ["score"]),
    "pick": _obj({"pick": {"type": "integer", "enum": [1, 2]}, "reason": {"type": "string"}}, ["pick"]),
    "review": _obj({"approved": {"type": "boolean"}, "problems": {"type": "array", "items": {"type": "string"}}}, ["approved"]),
    "agent": _obj({"tool": {"type": "string"}, "input": {"type": "object"}, "why": {"type": "string"},
                   "done": {"type": "boolean"}, "answer": {"type": "string"},
                   "plan": {"type": "array", "items": {"type": "string"}}}),
}


# ----- What a program can do -----
# Everything a program can do beyond asking its model services, in the order it's listed. The page reads this list too
# (tools/sync.py copies it in): it works out which of these a program uses from its blocks, shows them when you import a
# program, and writes them into the exported program, which lists them and asks before its first run if any of them
# acts on the world (the third value). Each is (id, what it lets the program do, whether that acts on the world).
CAPABILITIES = [
    ("email_send", "send email", True),
    ("telegram_send", "send Telegram messages", True),
    ("discord_send", "send Discord messages", True),
    ("slack_send", "send Slack messages", True),
    ("github_comment", "comment on GitHub, and open and label issues", True),
    ("ha_act", "control your Home Assistant devices", True),
    ("homey_act", "control your Homey devices and start Homey flows", True),
    ("mqtt_publish", "publish MQTT messages", True),
    ("webhook", "accept web requests from other computers", True),
    ("mcp", "use the tools of the MCP servers you set up (they can do whatever those servers can)", True),
    ("kraken_trade", "trade on your Kraken account with real money (asking you before every order)", True),
    ("coinbase_trade", "trade on your Coinbase account with real money (asking you before every order)", True),
    ("proxmox_control", "start, shut down and reboot your Proxmox guests (asking you each time)", True),
    ("docker_control", "restart, stop and start your Docker containers (asking you each time)", True),
    ("sabnzbd_control", "pause and resume your SABnzbd downloads (asking you each time)", True),
    ("arr_control", "search your Radarr and Sonarr for what's missing (asking you each time)", True),
    ("unraid_control", "start and stop your Unraid's containers and VMs, and check its parity (asking you each time)", True),
    ("nzbgeek_fetch", "fetch an NZB file from NZBGeek and save it (asking you each time)", True),
    ("powerwall_control", "set your Powerwall's backup reserve (asking you each time)", True),
    ("kraken_read", "read your Kraken balances and orders, market prices, and trade on paper", False),
    ("flightradar_read", "read Flightradar24's flight data: live and historic positions, summaries, tracks, and airline and airport details", False),
    ("coinbase_read", "read your Coinbase balances and orders, and market prices", False),
    ("mikrotik_read", "read your MikroTik router or switch: its ports, modules, health and log", False),
    ("unifi_read", "read your UniFi network: who's connected, and how your UniFi devices are", False),
    ("proxmox_read", "read your Proxmox cluster: nodes, guests, storage and tasks", False),
    ("docker_read", "read your Docker containers: their health, memory and logs", False),
    ("sabnzbd_read", "read your SABnzbd: the download queue, its history and the download disk's free space", False),
    ("arr_read", "read your Radarr and Sonarr: the download queue, the wanted list and disk space", False),
    ("unraid_read", "read your Unraid server: the array, its disks, its shares, its containers and its VMs", False),
    ("nzbgeek_read", "search NZBGeek, the Usenet indexer, and read what it has: titles, sizes, ages and groups", False),
    ("solax_read", "read your Solax inverter's figures from SolaxCloud: solar generation, battery charge, import and export", False),
    ("powerwall_read", "read your Powerwall's figures: battery charge, solar, grid import and export, and the reserve it keeps", False),
    ("web", "read public web pages and search the web", False),
    ("email_read", "read your email", False),
    ("calendar", "read your calendars", False),
    ("feeds", "read news feeds", False),
    ("github_read", "look at your GitHub projects", False),
    ("telegram_read", "read your Telegram messages", False),
    ("discord_read", "read your Discord channels", False),
    ("slack_read", "read your Slack channels", False),
    ("ha_read", "look at your Home Assistant devices", False),
    ("homey_read", "look at your Homey devices, flows and variables", False),
    ("mqtt_read", "read MQTT messages", False),
    ("folder", "look at the files in a folder, and watch it for new ones", False),
    ("files_read", "read files you choose", False),
    ("files_save", "save files in its outputs folder", False),
    ("memory", "keep notes between runs, in memory.json", False),
]


def record_schema(fields, many=False):
    one = _obj({f: _ANY for f in fields})
    return _obj({"items": {"type": "array", "items": one}}, ["items"]) if many else one


def _shape_problem(v, schema, where="the reply"):
    """What's wrong with v for this schema, in a sentence, or None. Numbers written as text count as numbers."""
    if "anyOf" in schema:
        return None if any(_shape_problem(v, o, where) is None for o in schema["anyOf"]) else f"{where} has the wrong kind of value"
    t = schema.get("type")
    if t == "object":
        if not isinstance(v, dict):
            return f"{where} should be a JSON object"
        for k in schema.get("required", []):
            if k not in v:
                return f"{where} is missing \"{k}\""
        for k, sub_ in schema.get("properties", {}).items():
            if k in v:
                bad = _shape_problem(v[k], sub_, f"\"{k}\"")
                if bad:
                    return bad
        return None
    if t == "array":
        if not isinstance(v, list):
            return f"{where} should be a list"
        for i, x in enumerate(v):
            bad = _shape_problem(x, schema.get("items", {}), f"item {i + 1} of {where}")
            if bad:
                return bad
        return None
    if t == "boolean" and not isinstance(v, bool):
        return f"{where} should be true or false"
    if t in ("number", "integer") and (isinstance(v, bool) or not _num_like(v)):
        return f"{where} should be a number"
    if t == "string" and not isinstance(v, str):
        return f"{where} should be text"
    if "enum" in schema and (num(v) if t in ("number", "integer") else v) not in schema["enum"]:
        return f"{where} should be one of {', '.join(json.dumps(e) for e in schema['enum'])}"
    return None


def _fit(v, schema):
    """Small, safe fixes before checking: a bare list where {"items": [...]} is wanted, one record sent as a list of one."""
    props = schema.get("properties", {})
    if isinstance(v, list) and list(props) == ["items"]:
        return {"items": v}
    if isinstance(v, list) and len(v) == 1 and isinstance(v[0], dict) and schema.get("type") == "object":
        return v[0]
    return v


def _short(s, n):
    s = re.sub(r"\s+", " ", to_str(s)).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ----- Files that several programs can share (memory.json, the Telegram messages) -----
# Two programs can point at the same file (RB_MEMORY_FILE). Each change to one is a read, a change and a write, done
# while holding a lock on "<file>.lock", so two programs saving at once take turns instead of one losing the other's
# change. Writes go to a temporary file first, which then replaces the real one, so a crash mid-save can't leave half a file.
_FILE_LOCKS = {}                 # path -> [open lock file, how many times this program holds it]
_FILE_LOCKS_GUARD = threading.RLock()


@contextlib.contextmanager
def _locked(path):
    """Holds the lock for a shared file. This program can take it again while holding it (memory blocks nest)."""
    key = os.path.abspath(path)
    with _FILE_LOCKS_GUARD:
        held = _FILE_LOCKS.get(key)
        if held:
            held[1] += 1
        else:
            try:
                f = open(key + ".lock", "a+b")
            except OSError:  # a folder we can't write to: carry on without the lock rather than fail
                f = None
            if f is not None:
                if os.name == "nt":
                    import msvcrt
                    give_up = time.monotonic() + 120
                    while True:
                        try:
                            f.seek(0)
                            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)  # retries for 10 s, then raises
                            break
                        except OSError:
                            if time.monotonic() > give_up:
                                f.close()
                                raise RunError(tr("Another program has been using {x} for over two minutes, so this one gave up waiting.", x=os.path.basename(key)))
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            held = _FILE_LOCKS[key] = [f, 1]
        try:
            yield
        finally:
            held[1] -= 1
            if not held[1]:
                del _FILE_LOCKS[key]
                f = held[0]
                if f is not None:
                    try:
                        if os.name == "nt":
                            import msvcrt
                            f.seek(0)
                            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    finally:
                        f.close()


class _WebSocket:
    """Just enough of a WebSocket client (RFC 6455) for Home Assistant's API, using only the standard library."""

    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer

    @classmethod
    async def connect(cls, url, timeout=20):
        import ssl
        u = urllib.parse.urlparse(url)
        secure = u.scheme in ("wss", "https")
        port = u.port or (443 if secure else 80)
        reader, writer = await asyncio.wait_for(asyncio.open_connection(
            u.hostname, port, ssl=ssl.create_default_context() if secure else None, limit=2 ** 24), timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        host = u.hostname + (f":{u.port}" if u.port else "")
        writer.write((f"GET {u.path or '/'}{'?' + u.query if u.query else ''} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                      f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        await writer.drain()
        head = (await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout)).decode("latin-1")
        want = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if " 101 " not in head.split("\r\n", 1)[0] or want not in head:
            writer.close()
            raise RunError(tr("{hostname} didn't accept a WebSocket connection at {path} ({x}).", hostname=u.hostname, path=u.path, x=head.split(chr(13), 1)[0]))
        return cls(reader, writer)

    async def _send(self, opcode, payload):
        n, mask = len(payload), os.urandom(4)
        head = bytes([0x80 | opcode]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + n.to_bytes(2, "big") if n < 65536
                                          else bytes([0x80 | 127]) + n.to_bytes(8, "big"))
        self.writer.write(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
        await self.writer.drain()

    async def send_json(self, obj):
        await self._send(1, json.dumps(obj).encode())

    async def recv_json(self):
        """The next message, as JSON. A connection that ends part-way, or a message that isn't JSON, is a RunError (#313)."""
        try:
            return await self._recv_json()
        except asyncio.IncompleteReadError:
            raise RunError(tr("Home Assistant closed the connection.")) from None
        except ValueError as e:
            raise RunError(tr("Home Assistant sent something that isn't JSON ({e}).", e=_short(str(e), 80))) from None

    async def _recv_json(self):
        parts = []
        while True:
            b0, b1 = await self.reader.readexactly(2)
            n = b1 & 0x7F
            if n == 126:
                n = int.from_bytes(await self.reader.readexactly(2), "big")
            elif n == 127:
                n = int.from_bytes(await self.reader.readexactly(8), "big")
            mask = await self.reader.readexactly(4) if b1 & 0x80 else None
            data = await self.reader.readexactly(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            op = b0 & 0x0F
            if op == 8:
                raise RunError(tr("Home Assistant closed the connection."))
            if op == 9:
                await self._send(10, data)  # a ping: answer it
                continue
            if op in (1, 2, 0):
                parts.append(data)
                if b0 & 0x80:  # the last piece of the message
                    return json.loads(b"".join(parts))

    def close(self):
        try:
            self.writer.close()
        except Exception:  # noqa: BLE001
            pass


def _private_open(path, mode="w"):
    """Opens a file for writing that only you can read (#307): on Linux and Mac it's made with 0600, and one already
    there is changed to it. These hold prompts, answers, messages and spending, and other people on the computer
    shouldn't see them. Windows keeps a file to its user already."""
    if os.name != "posix":
        return open(path, mode, encoding="utf-8")
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if mode == "a" else os.O_TRUNC)
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
    except OSError:
        pass  # a file system without modes
    return os.fdopen(fd, mode, encoding="utf-8")


def _write_json(path, data, **dump_args):
    """Writes JSON so the file is either all old or all new, even if the program stops part-way. Only you can read it
    (#307): these are memory, messages, spending and approvals."""
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with _private_open(tmp) as f:
            json.dump(data, f, ensure_ascii=False, **dump_args)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ----- The agent's ready-made helpers: sums, clock times and web pages (the page has the same sums and clock times) -----

class _Calc:
    """Works out a sum like (350 / 500) * 100 exactly, without running any code: numbers, + - * / ^, brackets and a few functions."""
    FUNCS = ("round", "min", "max", "sqrt", "abs", "floor", "ceil")

    def __init__(self, text):
        self.toks = re.findall(r"\d+(?:\.\d*)?|\.\d+|[A-Za-z_]+|\S", to_str(text).replace("×", "*").replace("÷", "/"))
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, want=None):
        t = self.peek()
        if t is None:
            raise ValueError("it ends too soon")
        if want is not None and t != want:
            raise ValueError(f"expected “{want}” but found “{t}”")
        self.i += 1
        return t

    def run(self):
        if not self.toks:
            raise ValueError("it's empty")
        v = self.expr()
        if self.peek() is not None:
            raise ValueError(f"I don't understand “{self.peek()}” there")
        if not math.isfinite(v):
            raise ValueError("the answer isn't a number")
        return v

    def expr(self):
        v = self.term()
        while self.peek() in ("+", "-"):
            v = v + self.term() if self.take() == "+" else v - self.term()
        return v

    def term(self):
        v = self.unary()
        while self.peek() in ("*", "/"):
            op, r = self.take(), self.unary()
            if op == "/" and r == 0:
                raise ValueError("it divides by zero")
            v = v * r if op == "*" else v / r
        return v

    def unary(self):
        if self.peek() in ("-", "+"):
            return -self.unary() if self.take() == "-" else self.unary()
        return self.power()

    def power(self):
        v = self.primary()
        if self.peek() == "^":
            self.take()
            try:
                v = math.pow(v, self.unary())
            except (ValueError, OverflowError):
                raise ValueError("the answer isn't a number") from None
        return v

    def primary(self):
        t = self.take()
        if t == "(":
            v = self.expr()
            self.take(")")
            return v
        if re.match(r"[\d.]", t):
            return float(t)
        name = t.lower()
        if name == "pi":
            return math.pi
        if name not in self.FUNCS:
            raise ValueError(f"I don't know “{t}” (it can use {', '.join(self.FUNCS)} and pi)")
        self.take("(")
        args = [self.expr()]
        while self.peek() == ",":
            self.take()
            args.append(self.expr())
        self.take(")")
        if name in ("min", "max"):
            return min(args) if name == "min" else max(args)
        if name == "round":
            places = max(0, min(10, int(round_js(args[1])))) if len(args) > 1 else 0
            f = 10 ** places
            return math.floor(args[0] * f + 0.5) / f
        if len(args) != 1:
            raise ValueError(f"{name} takes one number")
        if name == "sqrt" and args[0] < 0:
            raise ValueError("it takes the square root of a negative number")
        return {"sqrt": math.sqrt, "abs": abs, "floor": math.floor, "ceil": math.ceil}[name](args[0])


def read_text_file(path):
    """The words in a PDF, a .docx or a text file. Anything that can't be read becomes a plain RunError."""
    try:
        return _read_text_file(path)
    except RunError:
        raise
    except Exception as e:  # noqa: BLE001 - a damaged, locked or mislabelled file: say so, don't crash
        kind = "Word file" if path.lower().endswith(".docx") else "PDF" if path.lower().endswith(".pdf") else "file"
        raise RunError(tr("That {kind} couldn't be read ({name}: {e}). It may be damaged, locked, or not really a {kind}.", kind=kind, name=type(e).__name__, e=_short(e, 120))) from None


def _read_text_file(path):
    low = path.lower()
    if low.endswith(".pdf"):
        try:
            from pypdf import PdfReader  # pip install pypdf
        except ImportError:
            raise RunError(tr("Reading PDFs needs the pypdf package: pip install pypdf")) from None
        return "\n\n".join((p.extract_text() or "") for p in PdfReader(path).pages[:300])
    if low.endswith(".docx"):
        import zipfile
        with zipfile.ZipFile(path) as z, z.open("word/document.xml") as f:
            xml = f.read(25 * 1024 * 1024).decode("utf-8", "replace")  # at most 25 MB unpacked, however small the file (#304)
        xml = re.sub(r"<w:tab/>", "\t", xml)
        xml = re.sub(r"</w:p>|<w:br[^>]*/>", "\n", xml)
        text = re.sub(r"<[^>]+>", "", xml)
        for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&")):
            text = text.replace(a, b)
        return text
    with open(path, "rb") as f:
        raw = f.read(25 * 1024 * 1024)
    if b"\x00" in raw[:4000]:
        raise RunError(tr("That file isn't text. Use a PDF, a .docx or a text file."))
    return raw.decode("utf-8", "replace")


def calc_text(expression):
    """'(350 / 500) * 100' -> '(350 / 500) * 100 = 70'."""
    expression = to_str(expression).strip()
    try:
        v = _Calc(expression).run()
    except ValueError as e:
        raise RunError(tr("calculate couldn't work out “{expression}”: {e}.", expression=_short(expression, 80), e=e)) from None
    v = float(f"{v:.12g}")
    shown = str(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v)
    return f"{expression} = {shown}"


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def time_plus_text(when, minutes):
    """'09:30' plus 270 -> '14:00'; '2026-10-10 22:00' plus 600 -> '2026-10-11 08:00 (Sunday)'. Negative minutes go back."""
    m = re.match(r"^\s*(?:(\d{4})-(\d{1,2})-(\d{1,2})[ T]+)?(\d{1,2})[:.](\d{2})\s*(am|pm)?\s*$", to_str(when), re.I)
    if not m:
        raise RunError(tr("time_plus needs a time like 09:30 or 2026-10-10 09:30, not “{when}”.", when=_short(when, 40)))
    h, mi, ampm = int(m.group(4)), int(m.group(5)), (m.group(6) or "").lower()
    if ampm:
        if not 1 <= h <= 12:
            raise RunError(tr("“{x}” isn't a time.", x=to_str(when).strip()))
        h = h % 12 + (12 if ampm == "pm" else 0)
    if h > 23 or mi > 59:
        raise RunError(tr("“{x}” isn't a time.", x=to_str(when).strip()))
    add = round_js(num(minutes))
    if m.group(1):
        try:
            start = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), h, mi)
        except ValueError:
            raise RunError(tr("“{x}” isn't a real date.", x=to_str(when).strip())) from None
        t = start + datetime.timedelta(minutes=add)
        return t.strftime("%Y-%m-%d %H:%M") + f" ({WEEKDAYS[t.weekday()]})"
    total = h * 60 + mi + add
    days, t = total // 1440, total % 1440
    note = {0: "", 1: " (next day)", -1: " (the day before)"}.get(days, f" ({days} days later)" if days > 0 else f" ({-days} days earlier)")
    return f"{t // 60:02d}:{t % 60:02d}" + note


def current_time_text():
    d = datetime.datetime.now()
    return f"{WEEKDAYS[d.weekday()]} {d:%Y-%m-%d %H:%M}"
