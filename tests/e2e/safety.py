"""The safety rules (SAFETY in python/second_thought/core.py) give the same answers on the page and in exported
programs: what always asks, for Home Assistant, Homey, MQTT, Coinbase, MikroTik, UniFi, Proxmox and the agent's tools."""
from e2e.common import *  # noqa: F401,F403

sys.path.insert(0, str(ROOT / "python"))
from second_thought.agent import AgentTools  # noqa: E402
from second_thought.connectors import Connections  # noqa: E402
from second_thought.core import SAFETY, coinbase_money, ha_sensitive, mikrotik_allowed, proxmox_call, unifi_allowed  # noqa: E402

HA = [("lock.unlock", "lock.front_door"), ("lock.lock", "lock.front_door"), ("lock.open", ""), ("cover.open_cover", "cover.garage"),
      ("cover.close_cover", "cover.garage"), ("cover.set_cover_position", "cover.blinds"), ("cover.stop_cover", ""),
      ("valve.open_valve", "valve.water"), ("valve.close_valve", ""), ("alarm_control_panel.alarm_disarm", ""),
      ("alarm_control_panel.alarm_arm_away", ""), ("garage_door.open", ""), ("homeassistant.toggle", "lock.front_door"),
      ("homeassistant.turn_off", "light.kitchen, cover.garage"), ("homeassistant.turn_on", "light.kitchen"), ("light.turn_on", "light.kitchen"),
      ("  lock.unlock  ", ""), ("switch.turn_on", "switch.alarm_control_panel")]
# The target in the data (#303): (service, entity, data), as text or as the agent's own object.
HA_DATA = [("homeassistant.toggle", "", '{"entity_id": "lock.front_door"}'), ("homeassistant.turn_on", "", {"entity_id": ["light.a", "cover.b"]}),
           ("homeassistant.turn_off", "", '{"area_id": "hallway"}'), ("homeassistant.turn_on", "", {"target": {"device_id": "abc"}}),
           ("homeassistant.turn_on", "", {"floor_id": "ground"}), ("homeassistant.toggle", "", '{"label_id": ["doors"]}'),
           ("homeassistant.turn_on", "", '{"entity_id": "all"}'), ("homeassistant.turn_on", "", ""), ("homeassistant.turn_on", "", "{not json"),
           ("homeassistant.turn_on", "light.kitchen", '{"brightness": 120}'), ("homeassistant.turn_on", "", {"entity_id": "light.kitchen"}),
           ("homeassistant.turn_on", "", {"target": {"entity_id": "switch.fan"}, "area_id": ""}), ("light.turn_on", "", '{"area_id": "hallway"}'),
           ("homeassistant.turn_on", "light.hall", {"target": {"entity_id": "valve.water"}})]
TOOLS = [("call_service", {"service": "script.morning"}), ("call_service", {"service": "scene.movie"}),
         ("call_service", {"service": "automation.trigger"}), ("call_service", {"service": "input_button.press"}),
         ("call_service", {"service": "button.press"}), ("call_service", {"service": "light.turn_on"}),
         ("call_service", {"service": "automation.turn_off"}), ("run_homey_flow", {"flow": "Away"}),
         ("publish_mqtt", {"topic": "zigbee2mqtt/front_door/set", "message": '{"state": "UNLOCK"}'}),
         ("publish_mqtt", {"topic": "garage/Open", "message": "1"}), ("publish_mqtt", {"topic": "lights/kitchen", "message": "on"}),
         ("publish_mqtt", {"topic": "a", "message": "reopening soon"}), ("read_page", {"url": "https://example.com/?d=secret"}),
         ("read_page", {"url": "https://example.com/?d=sec"}), ("read_page", {"url": "https://example.com"}),
         ("read_feed", {"url": "https://example.com/?d=secret/"}), ("read_page", {"url": "https://example.com/wiki/A_(b)"})]


async def safety_tests():
    print("Safety rules: the page and exported programs agree")
    cases = [{"kind": "ha", "service": s, "entity": e} for s, e in HA]
    cases += [{"kind": "ha", "service": s, "entity": e, "data": d} for s, e, d in HA_DATA]
    cases += [{"kind": "homey", "capability": c, "value": v} for c, v in [("locked", False), ("locked", True), ("garagedoor_closed", False),
                                                                          ("garagedoor_closed", True), ("homealarm_state", "disarmed"),
                                                                          ("homealarm_state", "armed"), ("onoff", False)]]
    cases += [{"kind": "coinbase", "method": m, "path": "/api/v3/brokerage/" + p} for m, p in [
        ("GET", "accounts"), ("GET", "products/BTC-GBP/candles"), ("get", "key_permissions"), ("POST", "orders/preview"), ("POST", "orders"),
        ("POST", "orders/batch_cancel"), ("POST", "orders/edit"), ("POST", "convert/quote"), ("POST", "portfolios/move_funds"),
        ("DELETE", "portfolios/x"), ("GET", "products?x=1"), ("POST", "orders/preview/x")]]
    cases += [{"kind": "mikrotik", "method": m, "path": "/rest/" + p} for m, p in [
        ("GET", "interface"), ("get", "system/health"), ("POST", "interface/ethernet/monitor"), ("POST", "system/reboot"),
        ("PATCH", "interface/*1"), ("GET", "interface/*1"), ("GET", "export"), ("DELETE", "ip/address/*2")]]
    cases += [{"kind": "unifi", "method": m, "path": "/proxy/network/integration/v1/" + p} for m, p in [
        ("GET", "sites"), ("get", "sites/a-1/clients"), ("GET", "sites/a-1/devices/d-2/statistics/latest"), ("POST", "sites/a-1/clients/c/actions"),
        ("POST", "sites/a-1/devices/d-2/actions"), ("GET", "sites/a-1/hotspot/vouchers"), ("DELETE", "sites/a-1/hotspot/vouchers/v")]]
    cases += [{"kind": "proxmox", "method": m, "path": "/api2/json/" + p} for m, p in [
        ("GET", "nodes"), ("get", "cluster/tasks"), ("GET", "nodes/pve1/lxc/104/config"), ("POST", "nodes/pve1/lxc/104/status/start"),
        ("POST", "nodes/pve1/qemu/100/status/stop"), ("DELETE", "nodes/pve1/qemu/100"), ("POST", "nodes/pve1/qemu/100/agent/exec"), ("PUT", "access/acl")]]
    kinds = sorted(set(SAFETY["agent_private"]) | set(SAFETY["agent_asks"]) | {"web", "calc", "time", "review", "feeds", "telegram_send_free"})
    cases += [{"kind": "asks", "tool": k} for k in kinds] + [{"kind": "private", "tool": k} for k in kinds]
    for private in (False, True):
        for seen in ("", "https://example.com/?d=secret", "See https://example.com/?d=secret. Or (https://example.com/wiki/A_(b))."):
            cases += [{"kind": "must", "tool": t, "input": i, "private": private, "seen": seen} for t, i in TOOLS]
    want = []
    for c in cases:
        if c["kind"] == "ha":
            want.append(ha_sensitive(c["service"], c["entity"], c.get("data")))
        elif c["kind"] == "homey":
            want.append((c["capability"], c["value"]) in Connections.HOMEY_SENSITIVE)
        elif c["kind"] == "proxmox":
            want.append(proxmox_call(c["method"], c["path"]))
        elif c["kind"] == "unifi":
            want.append(unifi_allowed(c["method"], c["path"]))
        elif c["kind"] == "mikrotik":
            want.append(mikrotik_allowed(c["method"], c["path"]))
        elif c["kind"] == "coinbase":
            want.append(coinbase_money(c["method"], c["path"]))
        elif c["kind"] == "asks":
            want.append(c["tool"] in AgentTools.AGENT_ASKS)
        elif c["kind"] == "private":
            want.append(c["tool"] in AgentTools.AGENT_PRIVATE)
        else:
            want.append(AgentTools._agent_must_ask(AgentTools, c["tool"], c["input"], c["seen"], c["private"]))
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page()
        await pg.route("**/*", route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1000)
        got = await pg.evaluate("c => window.__safety(c)", cases)
        await browser.close()
    differ = [(c, w, g) for c, w, g in zip(cases, want, got) if w != g]
    check(not differ, f"the page and the runtime give the same answer to all {len(cases)} safety questions"
          + (f"; they differ on {differ[:3]}" if differ else ""))
    check(sum(1 for w in want if w) > 20 and sum(1 for w in want if not w) > 20, "the questions include both kinds of answer")
