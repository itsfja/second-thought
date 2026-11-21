        case "rb_folder_files": return "(await R.folder_files(" + I("FOLDER", '""') + ", " + I("MATCH", '""') + "))";
        case "rb_img_choose": return "(await R.choose_picture())";
        case "rb_file_choose": return "(await R.choose_file())";
