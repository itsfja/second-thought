    { kind:"category", name:"Pi-hole", categorystyle:"pihole", service:"pihole", contents:[
      B("rb_pihole_summary"), B("rb_pihole_top_domains", { N:N(5) }), B("rb_pihole_top_clients", { N:N(5) }),
      B("rb_pihole_blocking", { N:N(60) }), B("rb_pihole_enable"),
      B("rb_pihole_allow", { DOMAIN:T("ads.example.com") }), B("rb_pihole_deny", { DOMAIN:T("bad.example.com") })
    ]},
