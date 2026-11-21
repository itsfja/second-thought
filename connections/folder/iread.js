      case "rb_file_choose": { const f = await chooseTextFile(); run.lastFile = f.name; return f.text; }
      case "rb_folder_files": {
        const folder = str(await input(b, tc, "FOLDER", "")).trim() || "inbox", match = str(await input(b, tc, "MATCH", "")).trim() || "*";
        const re = new RegExp("^" + match.toLowerCase().replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".") + "$");
        const two = n => String(n).padStart(2, "0"), stamp = d => d.getFullYear() + "-" + two(d.getMonth() + 1) + "-" + two(d.getDate()) + " " + two(d.getHours()) + ":" + two(d.getMinutes());
        return ((CONN.folder || {}).files || []).filter(f => re.test(f.name.toLowerCase())).sort((a, c) => a.days_ago - c.days_ago)
          .map(f => ({ name:f.name, path:folder + "/" + f.name, modified:stamp(new Date(Date.now() - f.days_ago * 86400000)), size:f.size }));
      }
      case "rb_img_choose": {
        return choosePicture();
      }
