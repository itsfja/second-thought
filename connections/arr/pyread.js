        case "rb_arr_queue": return "(await R.arr_queue(" + pyStr(b.getFieldValue("WHICH")) + "))";
        case "rb_arr_missing": return "(await R.arr_missing(" + pyStr(b.getFieldValue("WHICH")) + "))";
        case "rb_arr_diskspace": return "(await R.arr_diskspace(" + pyStr(b.getFieldValue("WHICH")) + "))";
