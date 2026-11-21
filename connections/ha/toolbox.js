    { kind:"category", name:"Home Assistant", categorystyle:"ha", service:"ha", contents:[
      B("rb_ha_when"), B("rb_ha_trigger"), B("rb_ha_event_when"), B("rb_event"),
      B("rb_ha_state", { ENTITY:K("sensor.living_room_temperature") }), B("rb_ha_attr", { ATTR:K("current_temperature"), ENTITY:K("climate.living_room") }),
      B("rb_ha_summary", { TEXT:K("temperature") }), B("rb_ha_find", { TEXT:K("light") }),
      B("rb_ha_history", { ENTITY:K("sensor.bathroom_humidity"), HOURS:N(24) }), B("rb_ha_snapshot", { CAMERA:K("camera.front_door") }),
      B("rb_ha_call", { SERVICE:K("light.turn_off"), ENTITY:K("light.kitchen"), DATA:T("") }),
      B("rb_ha_notify", { TARGET:K("persistent_notification"), TEXT:L("The back door is still open.") }),
      B("rb_ha_speak", { TEXT:L("Good morning!"), PLAYER:K("media_player.kitchen_speaker") })
    ]},
