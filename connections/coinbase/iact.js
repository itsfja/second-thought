      case "rb_coinbase_order": await coinbaseOrder(b.getFieldValue("SIDE"), await input(b, tc, "AMOUNT"), await input(b, tc, "PRODUCT")); break;
      case "rb_coinbase_cancel": await coinbaseCancel(await input(b, tc, "ORDER")); break;
