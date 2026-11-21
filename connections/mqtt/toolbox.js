    { kind:"category", name:"MQTT", categorystyle:"mqtt", service:"mqtt", contents:[
      B("rb_mqtt_when"), B("rb_event"),
      B("rb_mqtt_read", { TOPIC:K("home/kitchen/temperature") }), B("rb_mqtt_publish", { TEXT:K("ON"), TOPIC:K("zigbee2mqtt/oven_plug/set") })
    ]},
