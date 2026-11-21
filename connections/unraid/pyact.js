        case "rb_unraid_container_power": E("await R.unraid_power(\"container\", " + pyStr(b.getFieldValue("ACTION")) + ", " + I("NAME", "plex") + ")"); break;
        case "rb_unraid_vm_power": E("await R.unraid_power(\"vm\", " + pyStr(b.getFieldValue("ACTION")) + ", " + I("NAME", "windows") + ")"); break;
        case "rb_unraid_parity": E("await R.unraid_parity()"); break;
