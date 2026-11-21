        case "rb_homey_value": return "(await R.homey_value(" + I("CAPABILITY", '""') + ", " + I("DEVICE", '""') + "))";
        case "rb_homey_find": return "(await R.homey_find(" + I("TEXT", '"*"') + "))";
        case "rb_homey_variable": return "(await R.homey_variable(" + I("NAME", '""') + "))";
