        case "rb_coinbase_balances": return "(await R.coinbase_balances())";
        case "rb_coinbase_value": return "(await R.coinbase_value())";
        case "rb_coinbase_price": return "(await R.coinbase_price(" + pyStr(b.getFieldValue("WHAT")) + ", " + I("PRODUCT", '""') + "))";
        case "rb_coinbase_candles": return "(await R.coinbase_candles(" + pyStr(b.getFieldValue("SIZE")) + ", " + I("PRODUCT", '""') + ", " + I("N", "7") + "))";
        case "rb_coinbase_orders": return "(await R.coinbase_orders(" + pyStr(b.getFieldValue("WHICH")) + "))";
        case "rb_coinbase_preview": return "(await R.coinbase_preview(" + pyStr(b.getFieldValue("SIDE")) + ", " + I("AMOUNT", "0") + ", " + I("PRODUCT", '""') + "))";
