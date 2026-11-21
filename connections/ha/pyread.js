        case "rb_ha_state": return "(await R.ha_state(" + I("ENTITY", '""') + "))";
        case "rb_ha_attr": return "(await R.ha_attr(" + I("ATTR", '""') + ", " + I("ENTITY", '""') + "))";
        case "rb_ha_find": return "(await R.ha_find(" + I("TEXT", '"*"') + "))";
        case "rb_ha_summary": return "(await R.ha_summary(" + I("TEXT", '"*"') + "))";
        case "rb_ha_history": return "(await R.ha_history(" + I("ENTITY", '""') + ", " + I("HOURS", "24") + "))";
        case "rb_ha_snapshot": return "(await R.ha_snapshot(" + I("CAMERA", '""') + "))";
        case "rb_ha_trigger": return "R.ha_trigger()";
