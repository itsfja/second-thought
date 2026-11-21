          case "rb_mqtt_publish": E("await R.mqtt_publish(" + I("TOPIC", '""') + ", " + I("TEXT", '""') + ", " + (F("RETAIN") === "TRUE" ? "True" : "False") + ")"); break;
