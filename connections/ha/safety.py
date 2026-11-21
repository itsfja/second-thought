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
    # Home Assistant services an agent can't run without asking, even with 'control devices (no asking)': they run
    # scripts, scenes or automations, or press buttons, and so could do anything, unlocking included.
    "agent_ha_indirect": [r"^script\.", r"^scene\.", r"^automation\.trigger$", r"^(input_)?button\.press$"],
