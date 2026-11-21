      case "rb_mqtt_publish": await mqttPublish(await input(b, tc, "TOPIC"), await input(b, tc, "TEXT"), b.getFieldValue("RETAIN") === "TRUE", false); break;
