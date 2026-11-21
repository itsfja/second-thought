          case "rb_coinbase_order": E("await R.coinbase_order(" + pyStr(b.getFieldValue("SIDE")) + ", " + I("AMOUNT", "0") + ", " + I("PRODUCT", '""') + ")"); break;
          case "rb_coinbase_cancel": E("await R.coinbase_cancel(" + I("ORDER", '""') + ")"); break;
