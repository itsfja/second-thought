      case "rb_coinbase_balances": return coinbaseBalances();
      case "rb_coinbase_value": return coinbaseValue();
      case "rb_coinbase_price": return coinbasePrice(b.getFieldValue("WHAT"), await input(b, tc, "PRODUCT"));
      case "rb_coinbase_candles": return coinbaseCandles(b.getFieldValue("SIZE"), await input(b, tc, "PRODUCT"), await input(b, tc, "N", 7));
      case "rb_coinbase_orders": return coinbaseOrders(b.getFieldValue("WHICH"));
      case "rb_coinbase_preview": return coinbasePreview(b.getFieldValue("SIDE"), await input(b, tc, "AMOUNT"), await input(b, tc, "PRODUCT"));
