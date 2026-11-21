          case "rb_ha_call": E("await R.ha_call(" + I("SERVICE", '""') + ", " + I("ENTITY", '""') + ", " + I("DATA", '""') + ")"); break;
          case "rb_ha_notify": E("await R.ha_notify(" + I("TARGET", '"persistent_notification"') + ", " + I("TEXT", '""') + ")"); break;
          case "rb_ha_speak": E("await R.ha_speak(" + I("TEXT", '""') + ", " + I("PLAYER", '""') + ")"); break;
