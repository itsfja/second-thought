          case "rb_file_save": E("await R.save_file(" + I("VALUE", '""') + ", " + I("NAME", '"output"') + ", " + pyStr(F("EXT") || "md") + ")"); break;
          case "rb_img_save": E("await R.save_picture(" + I("IMG", "None") + ", " + pyStr(F("FORMAT") || "png") + ")"); break;
