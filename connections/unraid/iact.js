      case "rb_unraid_container_power": await unraidPower("container", b.getFieldValue("ACTION"), await input(b, tc, "NAME")); break;
      case "rb_unraid_vm_power": await unraidPower("vm", b.getFieldValue("ACTION"), await input(b, tc, "NAME")); break;
      case "rb_unraid_parity": await unraidParity(); break;
