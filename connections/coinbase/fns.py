def coinbase_money(method, path):
    """True for a Coinbase API call that could move real money (#371): anything but reading and previewing an order."""
    method, path = to_str(method).strip().upper(), to_str(path).strip()
    return not any(m == method and re.match(p, path) for m, p in SAFETY["coinbase_free"])
