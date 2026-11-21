    # Coinbase (#371)
    # Coinbase's Advanced Trade API, with a CDP API key: COINBASE_KEY_FILE is the key file you download when you make
    # one at portal.cdp.coinbase.com (or COINBASE_KEY, that file's contents, say from the keychain). Make it View only,
    # for one portfolio, unless the program trades; never give it Transfer. Each request carries a short-lived token the
    # key signs (ES256), which needs the cryptography package. Placing and cancelling orders always ask, even with
    # (no asking), and never run with nobody there to ask; nothing else that changes the account is offered at all
    # (coinbase_free in SAFETY, core.py). Spot trading pairs only: no derivatives or equities.
    COINBASE_ORDER_KINDS = {"buy": "BUY", "sell": "SELL"}

    @staticmethod
    def _cents(v):
        """Rounded to two places, as the page's Math.round(v * 100) / 100 does."""
        return _clean_num(math.floor(num(v) * 100 + 0.5) / 100)

    def _coinbase_key(self):
        """(key name, PEM private key) from COINBASE_KEY or the file COINBASE_KEY_FILE names."""
        raw, path = os.environ.get("COINBASE_KEY", "").strip(), os.environ.get("COINBASE_KEY_FILE", "").strip().strip('"')
        if not raw and path:
            path = os.path.expanduser(path)
            if not os.path.isabs(path):
                path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0] or ".")), path)
            try:
                with open(path, encoding="utf-8-sig") as f:
                    raw = f.read()
            except OSError as e:
                raise RunError(tr("Couldn't read the Coinbase key file {path} ({reason}).", path=path, reason=e.strerror or e)) from None
        if not raw:
            raise RunError(tr("Coinbase needs COINBASE_KEY_FILE {where_keys}: the key file you download when you make an API key at portal.cdp.coinbase.com. Make it View only unless the program trades.", where_keys=WHERE_KEYS))
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        name = to_str(data.get("name") or data.get("id")).strip() if isinstance(data, dict) else ""
        pem = to_str(data.get("privateKey")).replace("\\n", "\n").strip() if isinstance(data, dict) else ""
        if not name or not pem:
            raise RunError(tr("The Coinbase key should be the JSON file Coinbase gave you, with name and privateKey in it."))
        return name, pem

    def _coinbase_token(self, method, where):
        """The JWT for one request (Coinbase wants a new one each time): signed with the key, ES256, for two minutes."""
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec, utils
        except ImportError:
            raise RunError(tr("Coinbase needs the cryptography package to sign its requests: pip install cryptography")) from None
        name, pem = self._coinbase_key()
        if "BEGIN" not in pem:  # a newer CDP key's bare Ed25519 secret, which Advanced Trade doesn't take
            raise RunError(tr("This Coinbase key is an Ed25519 key, and Advanced Trade needs an ECDSA one. Make a new key at portal.cdp.coinbase.com and choose ECDSA under its advanced settings."))
        try:
            key = serialization.load_pem_private_key(pem.encode(), password=None)
        except (ValueError, TypeError):
            raise RunError(tr("The Coinbase key's privateKey couldn't be read. Use the key file as Coinbase gave it.")) from None
        if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
            raise RunError(tr("This Coinbase key is an Ed25519 key, and Advanced Trade needs an ECDSA one. Make a new key at portal.cdp.coinbase.com and choose ECDSA under its advanced settings."))
        now = int(time.time())
        part = lambda d: base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).rstrip(b"=").decode()  # noqa: E731
        signed = part({"alg": "ES256", "typ": "JWT", "kid": name, "nonce": secrets.token_hex(16)}) + "." + \
            part({"sub": name, "iss": "cdp", "nbf": now, "exp": now + 120, "uri": f"{method} {where}"})
        r, s = utils.decode_dss_signature(key.sign(signed.encode(), ec.ECDSA(hashes.SHA256())))
        return signed + "." + base64.urlsafe_b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")).rstrip(b"=").decode()

    async def _coinbase(self, method, path, query=None, body=None, approved=False):
        """One Advanced Trade API call. One that could move money (anything but reading and previewing) only goes with
        approved=True, which only _coinbase_ask gives, after a yes; so nothing else can move money, whatever calls this."""
        if coinbase_money(method, path) and not approved:
            raise RunError(tr("That Coinbase action could move real money, so it only runs after you say yes."))
        base = os.environ.get("COINBASE_API_URL", "").strip().rstrip("/") or "https://api.coinbase.com"
        whole = urllib.parse.urlparse(base + path)
        token = self._coinbase_token(method, whole.netloc + whole.path)
        url = base + path + ("?" + urllib.parse.urlencode(query, doseq=True) if query else "")
        req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json"})

        def go():
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    raw = r.read()
                    return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as e:
                try:
                    said = json.loads(e.read() or b"{}")
                except ValueError:
                    said = {}
                said = to_str(said.get("message") or said.get("error") or "") if isinstance(said, dict) else ""
                why = {401: tr("it refused the key. Check COINBASE_KEY_FILE: it must be a CDP key with an ECDSA private key"),
                       403: tr("the key isn't allowed to do that. Check its permissions and portfolio at portal.cdp.coinbase.com"),
                       404: tr("not found"), 429: tr("too many requests just now; try again in a minute")}.get(e.code, tr("it answered {code}", code=e.code))
                raise RunError(tr("Coinbase: {why}.", why=why) + (f" ({_short(said, 160)})" if said else "")) from None
            except urllib.error.URLError as e:
                raise RunError(tr("Couldn't reach Coinbase ({reason}).", reason=e.reason)) from None
        return await asyncio.to_thread(go)

    @staticmethod
    def _coinbase_currency():
        """The program's currency (currency in second-thought.ini), for values: GBP, USD, EUR and so on."""
        return (os.environ.get("RB_CURRENCY") or "usd").strip().upper()

    @staticmethod
    def _coinbase_product_id(product):
        p = to_str(product).strip().upper().replace("/", "-")
        if not re.fullmatch(r"[A-Z0-9]{2,12}-[A-Z0-9]{2,12}", p):
            raise RunError(tr("“{product}” isn't a Coinbase trading pair. Use one like BTC-GBP.", product=to_str(product).strip()))
        return p

    async def _coinbase_product(self, product):
        """A spot trading pair, like BTC-GBP: derivatives and equities aren't offered."""
        p = await self._coinbase("GET", "/api/v3/brokerage/products/" + self._coinbase_product_id(product))
        if to_str(p.get("product_type") or "SPOT").upper() != "SPOT":
            raise RunError(tr("Only spot trading pairs, like BTC-GBP, are offered here."))
        return p

    async def _coinbase_portfolio(self):
        """The key's portfolio, valued in the program's currency."""
        uid = to_str((await self._coinbase("GET", "/api/v3/brokerage/key_permissions")).get("portfolio_uuid")).strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", uid):
            raise RunError(tr("Coinbase didn't say which portfolio this key is for."))
        got = await self._coinbase("GET", "/api/v3/brokerage/portfolios/" + uid, {"currency": self._coinbase_currency()})
        return got.get("breakdown") or {}

    async def coinbase_balances(self):
        """One record per asset in the portfolio, biggest value first: asset, amount, value (in the program's currency)
        and currency."""
        cur = self._coinbase_currency()
        out = [{"asset": to_str(p.get("asset")), "amount": num(p.get("total_balance_crypto")), "value": self._cents(p.get("total_balance_fiat")), "currency": cur}
               for p in (await self._coinbase_portfolio()).get("spot_positions") or [] if num(p.get("total_balance_crypto")) or num(p.get("total_balance_fiat"))]
        out.sort(key=lambda r: -r["value"])
        lines = "\n".join(f"{r['asset']}: {r['amount']} ({r['value']} {cur})" for r in out)
        self.log(tr("Coinbase balances"), lines or tr("(nothing)"), tr("{n} assets", n=len(out)))
        return out

    async def coinbase_value(self):
        """The whole portfolio's value in the program's currency."""
        total = ((await self._coinbase_portfolio()).get("portfolio_balances") or {}).get("total_balance") or {}
        return self._cents(total.get("value"))

    async def coinbase_price(self, what, product):
        """A trading pair's price, or its change over 24 hours in percent."""
        p = await self._coinbase_product(product)
        return self._cents(p.get("price_percentage_change_24h")) if what == "change" else num(p.get("price"))

    async def coinbase_candles(self, size, product, count):
        """The last few days' (or hours') prices, oldest first: time, open, high, low, close and volume."""
        pid, hours = self._coinbase_product_id(product), size == "hour"
        n, step = max(1, min(350, int(num(count) or 1))), 3600 if hours else 86400
        end = int(time.time())
        got = await self._coinbase("GET", f"/api/v3/brokerage/products/{pid}/candles",
                                   {"start": str(end - n * step), "end": str(end), "granularity": "ONE_HOUR" if hours else "ONE_DAY", "limit": str(n)})
        rows = sorted(got.get("candles") or [], key=lambda c: num(c.get("start")))[-n:]
        when = lambda c: datetime.datetime.fromtimestamp(num(c.get("start"))).strftime("%Y-%m-%d %H:00" if hours else "%Y-%m-%d")  # noqa: E731
        return [dict({"time": when(c)}, **{k: num(c.get(k)) for k in ("open", "high", "low", "close", "volume")}) for c in rows]

    async def coinbase_orders(self, which):
        """Open orders (which = "open") or the latest fills (which = "fills"), newest first, as records."""
        if which == "fills":
            got = await self._coinbase("GET", "/api/v3/brokerage/orders/historical/fills", {"limit": "50"})
            return [{"time": to_str(f.get("trade_time"))[:19].replace("T", " "), "product": to_str(f.get("product_id")), "side": to_str(f.get("side")).lower(),
                     "size": num(f.get("size")), "price": num(f.get("price")), "fee": num(f.get("commission")), "order": to_str(f.get("order_id"))}
                    for f in got.get("fills") or []]
        got = await self._coinbase("GET", "/api/v3/brokerage/orders/historical/batch", {"order_status": "OPEN", "limit": "100"})
        out = []
        for o in got.get("orders") or []:
            cfg = next(iter((o.get("order_configuration") or {}).values()), {}) or {}
            out.append({"id": to_str(o.get("order_id")), "product": to_str(o.get("product_id")), "side": to_str(o.get("side")).lower(),
                        "size": num(cfg.get("base_size") or cfg.get("quote_size")), "price": num(cfg.get("limit_price")) if cfg.get("limit_price") else "",
                        "filled": num(o.get("filled_size")), "created": to_str(o.get("created_time"))[:19].replace("T", " ")})
        return out

    def _coinbase_order_body(self, side, amount, pid):
        """A market order: buy spends an amount of the second currency (50 GBP of BTC-GBP), sell sells an amount of the first."""
        side = to_str(side).strip().lower()
        if side not in self.COINBASE_ORDER_KINDS:
            raise RunError(tr("A Coinbase order is buy or sell."))
        if not _num_like(amount) or num(amount) <= 0:
            raise RunError(tr("The amount should be a number above 0, like 50."))
        size = format(decimal.Decimal(to_str(num(amount))), "f")
        return {"product_id": pid, "side": self.COINBASE_ORDER_KINDS[side],
                "order_configuration": {"market_market_ioc": {"quote_size" if side == "buy" else "base_size": size}}}

    async def coinbase_preview(self, side, amount, product):
        """What an order would come to, without placing it: product, side, size (of the first currency), spend (of the
        second), fee, total, slippage and warnings. Nothing changes."""
        return (await self._coinbase_previewed(side, amount, product))[0]

    async def _coinbase_previewed(self, side, amount, product):
        """The preview's record, and its id for placing the order."""
        p = await self._coinbase_product(product)
        pid = to_str(p.get("product_id")) or self._coinbase_product_id(product)
        body = self._coinbase_order_body(side, amount, pid)
        got = await self._coinbase("POST", "/api/v3/brokerage/orders/preview", body=body)
        errs = [to_str(e).replace("PREVIEW_", "").replace("_", " ").lower() for e in got.get("errs") or []]
        if errs:
            raise RunError(tr("Coinbase wouldn't place that order: {why}.", why=", ".join(errs)))
        return {"product": pid, "side": to_str(side).strip().lower(), "size": num(got.get("base_size")), "spend": num(got.get("quote_size")),
                "fee": num(got.get("commission_total")), "total": num(got.get("order_total")), "slippage": num(got.get("slippage")),
                "warnings": [to_str(w) for w in got.get("warning") or []]}, to_str(got.get("preview_id"))

    async def _coinbase_ask(self, what):
        """Asks before anything that could move money on Coinbase: always, live, and never with nobody there (#371)."""
        if self._skip_action(what):
            return False
        return await self.confirm_money(what)

    async def coinbase_order(self, side, amount, product):
        """Places a market order, after previewing it and asking you with the preview's numbers. Gives back the order's id,
        or "" if it wasn't placed."""
        pre, preview_id = await self._coinbase_previewed(side, amount, product)
        base, quote = pre["product"].split("-")
        what = (f"{pre['side']} {pre['size']} {base} for {pre['spend']} {quote} on Coinbase (fee {pre['fee']} {quote}, "
                f"total {pre['total']} {quote})")
        if not await self._coinbase_ask(what):
            return ""
        body = dict(self._coinbase_order_body(side, amount, pre["product"]), client_order_id=str(uuid.uuid4()))
        if preview_id:
            body["preview_id"] = preview_id
        got = await self._coinbase("POST", "/api/v3/brokerage/orders", body=body, approved=True)
        if not got.get("success"):
            err = got.get("error_response") or {}
            raise RunError(tr("Coinbase didn't place the order: {why}.", why=to_str(err.get("message") or err.get("error_details") or err.get("error") or "no reason given")))
        oid = to_str((got.get("success_response") or {}).get("order_id"))
        self.log(tr("Coinbase order placed"), f"{what} · {oid}", tr("done"))
        return oid

    async def coinbase_cancel(self, order):
        """Cancels one of your open orders, by its id, after asking."""
        oid = to_str(order).strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{6,64}", oid):
            raise RunError(tr("Which Coinbase order? Give its id, from 'Coinbase open orders'."))
        if not await self._coinbase_ask(f"cancel the Coinbase order {oid}"):
            return False
        got = await self._coinbase("POST", "/api/v3/brokerage/orders/batch_cancel", body={"order_ids": [oid]}, approved=True)
        res = next(iter(got.get("results") or []), {})
        if not res.get("success"):
            raise RunError(tr("Coinbase didn't cancel the order: {why}.", why=to_str(res.get("failure_reason") or "no reason given").replace("_", " ").lower()))
        self.log(tr("Coinbase order cancelled"), oid, tr("done"))
        return True
