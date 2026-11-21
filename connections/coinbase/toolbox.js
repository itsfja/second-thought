    { kind:"category", name:"Coinbase", categorystyle:"coinbase", service:"coinbase", contents:[
      B("rb_coinbase_balances"), B("rb_coinbase_value"), B("rb_coinbase_price", { PRODUCT:K("BTC-GBP") }),
      B("rb_coinbase_candles", { PRODUCT:K("BTC-GBP"), N:N(7) }), B("rb_coinbase_orders"),
      B("rb_coinbase_preview", { AMOUNT:N(50), PRODUCT:K("BTC-GBP") }), B("rb_coinbase_order", { AMOUNT:N(50), PRODUCT:K("BTC-GBP") }),
      B("rb_coinbase_cancel", { ORDER:K("") })
    ]},
