# Home Assistant: the address of your Home Assistant and a long-lived access token
# (your Home Assistant profile, Security tab, "Long-lived access tokens").
HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
HA_TTS_ENTITY = os.environ.get("HA_TTS_ENTITY", "tts.home_assistant_cloud")  # used by the 'say … on' block
HA_WATCH_SECONDS = 15  # how often 'when … changes' scripts check Home Assistant

HA_SENSITIVE = tuple(SAFETY["ha_sensitive"])
HA_SENSITIVE_ENTITY = SAFETY["ha_sensitive_entity"]


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
