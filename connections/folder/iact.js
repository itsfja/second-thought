      case "rb_file_save": {
        const v = await input(b, tc, "VALUE"), name = str(await input(b, tc, "NAME")).trim() || "output", ext = b.getFieldValue("EXT") || "md";
        const st = addStep("Save file", { mono:true, text:tr("Waiting for you to confirm the download…") }); st.done("waiting", "");
        const msg = await saveTextFile(v, name, ext);
        st.text(msg); st.done(/^Saved/.test(msg) ? tr("saved") : tr("skipped"), /^Saved/.test(msg) ? "ok" : "warn");
        break;
      }
      case "rb_img_save": {
        const pic = needImg(await input(b, tc, "IMG"), "save picture");
        const st = addStep("Save picture", { mono:true, text:tr("Waiting for you to confirm the download…") }); st.done("waiting", "");
        const msg = await savePicture(pic, b.getFieldValue("FORMAT") || "png");
        st.text(msg); st.done(/^Saved/.test(msg) ? tr("saved") : tr("skipped"), /^Saved/.test(msg) ? "ok" : "warn"); break;
      }
