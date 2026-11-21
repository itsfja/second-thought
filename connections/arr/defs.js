    /* Radarr and Sonarr (#398): reads, and a search that always asks */
    V("rb_arr_queue", "%1 queue", [{ type:"field_dropdown", name:"WHICH", options:[["Radarr","radarr"],["Sonarr","sonarr"]] }], "Array", { style:"arr",
      tooltip:"A list of records, one for each download in the queue: title, status (Downloading, Importing, Failed, ...), size_mb, left_mb, quality and eta (time left, like 0:12:34). On this page it uses a sample queue." }),
    V("rb_arr_missing", "%1 wanted list", [{ type:"field_dropdown", name:"WHICH", options:[["Radarr","radarr"],["Sonarr","sonarr"]] }], "Array", { style:"arr",
      tooltip:"A list of records, one for each movie or episode with no file: title, added (when it was added) and id." }),
    V("rb_arr_diskspace", "%1 diskspace", [{ type:"field_dropdown", name:"WHICH", options:[["Radarr","radarr"],["Sonarr","sonarr"]] }], "Array", { style:"arr",
      tooltip:"A list of records, one for each of its folders: path, label, free_gb and total_gb." }),
    S("rb_arr_search", "search %1 for what's missing", [{ type:"field_dropdown", name:"WHICH", options:[["Radarr","radarr"],["Sonarr","sonarr"]] }],
      { style:"arr", inputsInline:true, tooltip:"Searches the whole wanted list for what has no file. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really searches." }),
