    # Coinbase's Advanced Trade API (#371): the calls that run without asking, [method, path]. Reading, and previewing an
    # order. Any other call (placing, editing or cancelling an order, converting, moving funds) can move real money: it
    # always asks, even with (no asking), and never runs with nobody there to ask, like Kraken's money tools (#262).
    "coinbase_free": [["GET", r"^/api/v3/brokerage/[A-Za-z0-9_/.-]+$"], ["POST", r"^/api/v3/brokerage/orders/preview$"]],
