    { kind:"category", name:"Homey", categorystyle:"homey", service:"homey", contents:[
      B("rb_homey_when"), B("rb_event"),
      B("rb_homey_find", { TEXT:K("light") }), B("rb_homey_value", { CAPABILITY:K("measure_temperature"), DEVICE:K("Proofing box") }),
      B("rb_homey_set", { DEVICE:K("Kitchen light"), CAPABILITY:K("onoff"), VALUE:K("off") }), B("rb_homey_flow", { NAME:K("Good night") }),
      B("rb_homey_variable", { NAME:K("Loaves this week") }), B("rb_homey_set_variable", { NAME:K("Loaves this week"), VALUE:N(4) })
    ]},
