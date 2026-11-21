  /* Coinbase on the page (#371): a sample portfolio, in pounds. Exported Python talks to Coinbase's Advanced Trade API
     with your key. Matches the runtime's coinbase_ methods (and tests/fake_coinbase.py, which serves the same sample).
     Placing and cancelling orders always ask, even when nothing else does; here nothing is bought or sold. */
  const cbSample = () => { connNote("Coinbase"); return CONN.coinbase || {}; };
  const cents = v => Math.round(num(v) * 100) / 100;
  function cbProductId(product){
    const p = str(product).trim().toUpperCase().replace(/\//g, "-");
    if (!/^[A-Z0-9]{2,12}-[A-Z0-9]{2,12}$/.test(p)) fail(tr("“{product}” isn't a Coinbase trading pair. Use one like BTC-GBP.", { product:str(product).trim() }));
    return p;
  }
  function cbProduct(product){
    const p = (cbSample().products || {})[cbProductId(product)];
    if (!p) fail(tr("Coinbase: {why}.", { why:tr("not found") }));
    if ((p.product_type || "SPOT").toUpperCase() !== "SPOT") fail(tr("Only spot trading pairs, like BTC-GBP, are offered here."));
    return p;
  }
  function coinbaseBalances(){
    const c = cbSample(), cur = c.currency || "GBP";
    const out = (c.positions || []).filter(p => num(p.total_balance_crypto) || num(p.total_balance_fiat))
      .map(p => ({ asset:str(p.asset), amount:num(p.total_balance_crypto), value:cents(p.total_balance_fiat), currency:cur }));
    out.sort((a, b) => b.value - a.value);
    addStep("Coinbase balances", { mono:true, text:out.map(r => r.asset + ": " + r.amount + " (" + r.value + " " + cur + ")").join("\n") || tr("(nothing)") })
      .done(tr("{n} assets", { n:out.length }), "ok");
    return out;
  }
  const coinbaseValue = () => cents((cbSample().positions || []).reduce((t, p) => t + num(p.total_balance_fiat), 0));
  function coinbasePrice(what, product){
    const p = cbProduct(product);
    return what === "change" ? cents(p.price_percentage_change_24h) : num(p.price);
  }
  function coinbaseCandles(size, product, count){
    const id = cbProductId(product), hours = size === "hour", n = Math.max(1, Math.min(350, Math.trunc(num(count)) || 1)), step = hours ? 3600 : 86400;
    const rows = ((cbSample().candles || {})[id] || {})[hours ? "hour" : "day"];
    if (!rows) fail(tr("Coinbase: {why}.", { why:tr("not found") }));
    const top = Math.floor(Date.now() / 1000 / step) * step, some = rows.slice(-n);
    return some.map((r, i) => {
      const d = new Date((top - (some.length - 1 - i) * step) * 1000);
      return { time:d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()) + (hours ? " " + pad2(d.getHours()) + ":00" : ""),
               open:r[0], high:r[1], low:r[2], close:r[3], volume:r[4] };
    });
  }
  const cbWhen = t => str(t).slice(0, 19).replace("T", " ");
  function coinbaseOrders(which){
    const c = cbSample();
    if (which === "fills") return (c.fills || []).map(f => ({ time:cbWhen(f.trade_time), product:str(f.product_id), side:str(f.side).toLowerCase(),
      size:num(f.size), price:num(f.price), fee:num(f.commission), order:str(f.order_id) }));
    return (c.orders || []).map(o => {
      const cfg = Object.values(o.order_configuration || {})[0] || {};
      return { id:str(o.order_id), product:str(o.product_id), side:str(o.side).toLowerCase(), size:num(cfg.base_size || cfg.quote_size),
               price:cfg.limit_price ? num(cfg.limit_price) : "", filled:num(o.filled_size), created:cbWhen(o.created_time) };
    });
  }
  // What the sample account would charge: a 0.6% fee, no slippage. tests/fake_coinbase.py works it out the same way.
  function coinbasePreview(side, amount, product){
    const p = cbProduct(product), id = p.product_id, [base, quote] = id.split("-");
    side = str(side).trim().toLowerCase();
    if (side !== "buy" && side !== "sell") fail(tr("A Coinbase order is buy or sell."));
    if (!isNumLike(amount) || num(amount) <= 0) fail(tr("The amount should be a number above 0, like 50."));
    const a = num(amount), price = num(p.price), have = asset => num(((cbSample().positions || []).find(x => x.asset === asset) || {}).total_balance_crypto);
    let rec;
    if (side === "buy") { const fee = cents(a * 0.006); rec = { size:Math.floor((a - fee) / price * 1e8) / 1e8, spend:a, fee, total:a }; }
    else { const gross = cents(a * price), fee = cents(gross * 0.006); rec = { size:a, spend:gross, fee, total:cents(gross - fee) }; }
    if (side === "buy" ? a > have(quote) : a > have(base)) fail(tr("Coinbase wouldn't place that order: {why}.", { why:"insufficient fund" }));
    return Object.assign({ product:id, side }, rec, { slippage:0, warnings:[] });
  }
  async function confirmMoney(what){ return confirmAction(what + " (it could move real money, so it always asks)"); }
  async function coinbaseOrder(side, amount, product){
    const pre = coinbasePreview(side, amount, product), [base, quote] = pre.product.split("-");
    const what = pre.side + " " + pre.size + " " + base + " for " + pre.spend + " " + quote + " on Coinbase (fee " + pre.fee + " " + quote + ", total " + pre.total + " " + quote + ")";
    if (!(await confirmMoney(what))) return "";
    addStep("Coinbase order placed", { mono:true, text:what + " · sample-order" }).done("sample account", "ok");
    return "sample-order";
  }
  async function coinbaseCancel(order){
    const id = str(order).trim();
    if (!/^[A-Za-z0-9-]{6,64}$/.test(id)) fail(tr("Which Coinbase order? Give its id, from 'Coinbase open orders'."));
    if (!(await confirmMoney("cancel the Coinbase order " + id))) return false;
    if (!(cbSample().orders || []).some(o => o.order_id === id)) fail(tr("Coinbase didn't cancel the order: {why}.", { why:"unknown cancel order" }));
    addStep("Coinbase order cancelled", { mono:true, text:id }).done("sample account", "ok");
    return true;
  }
