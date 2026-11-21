      case "rb_tg_message": {
        const m = tc.payload && typeof tc.payload === "object" && "text" in tc.payload ? tc.payload : null;
        if (!m) return "";
        return { text:m.text, sender:m.sender || "", chat:m.chat || "" }[b.getFieldValue("PART") || "text"];
      }
