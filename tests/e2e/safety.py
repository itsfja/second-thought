"""The safety rules (SAFETY in python/second_thought/core.py) give the same answers on the page and in exported
programs: what always asks, for Home Assistant, Homey, MQTT and the agent's tools."""
from e2e.common import *  # noqa: F401,F403

sys.path.insert(0, str(ROOT / "python"))
from second_thought.agent import AgentTools  # noqa: E402
from second_thought.connectors import Connections  # noqa: E402
from second_thought.core import SAFETY, ha_sensitive  # noqa: E402

HA = [("lock.unlock", "lock.front_door"), ("lock.lock", "lock.front_door"), ("lock.open", ""), ("cover.open_cover", "cover.garage"),
      ("cover.close_cover", "cover.garage"), ("cover.set_cover_position", "cover.blinds"), ("cover.stop_cover", ""),
      ("valve.open_valve", "valve.water"), ("valve.close_valve", ""), ("alarm_control_panel.alarm_disarm", ""),
      ("alarm_control_panel.alarm_arm_away", ""), ("garage_door.open", ""), ("homeassistant.toggle", "lock.front_door"),
      ("homeassistant.turn_off", "light.kitchen, cover.garage"), ("homeassistant.turn_on", "light.kitchen"), ("light.turn_on", "light.kitchen"),
      ("  lock.unlock  ", ""), ("switch.turn_on", "switch.alarm_control_panel")]
TOOLS = [("call_service", {"service": "script.morning"}), ("call_service", {"service": "scene.movie"}),
         ("call_service", {"service": "automation.trigger"}), ("call_service", {"service": "input_button.press"}),
         ("call_service", {"service": "button.press"}), ("call_service", {"service": "light.turn_on"}),
         ("call_service", {"service": "automation.turn_off"}), ("run_homey_flow", {"flow": "Away"}),
         ("publish_mqtt", {"topic": "zigbee2mqtt/front_door/set", "message": '{"state": "UNLOCK"}'}),
         ("publish_mqtt", {"topic": "garage/Open", "message": "1"}), ("publish_mqtt", {"topic": "lights/kitchen", "message": "on"}),
         ("publish_mqtt", {"topic": "a", "message": "reopening soon"}), ("read_page", {"url": "https://example.com/?d=secret"})]


async def safety_tests():
    print("Safety rules: the page and exported programs agree")
    cases = [{"kind": "ha", "service": s, "entity": e} for s, e in HA]
    cases += [{"kind": "homey", "capability": c, "value": v} for c, v in [("locked", False), ("locked", True), ("garagedoor_closed", False),
                                                                          ("garagedoor_closed", True), ("homealarm_state", "disarmed"),
                                                                          ("homealarm_state", "armed"), ("onoff", False)]]
    kinds = sorted(set(SAFETY["agent_private"]) | set(SAFETY["agent_asks"]) | {"web", "calc", "time", "review", "feeds", "telegram_send_free"})
    cases += [{"kind": "asks", "tool": k} for k in kinds] + [{"kind": "private", "tool": k} for k in kinds]
    for private in (False, True):
        for seen in ("", "https://example.com/?d=secret"):
            cases += [{"kind": "must", "tool": t, "input": i, "private": private, "seen": seen} for t, i in TOOLS]
    want = []
    for c in cases:
        if c["kind"] == "ha":
            want.append(ha_sensitive(c["service"], c["entity"]))
        elif c["kind"] == "homey":
            want.append((c["capability"], c["value"]) in Connections.HOMEY_SENSITIVE)
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
