    /* SABnzbd (#397): reads, and pause and resume that always ask */
    V("rb_sabnzbd_queue", "SABnzbd queue", [], "Array", { style:"sabnzbd",
      tooltip:"A list of records, one for each job in the download queue: name, size_mb, left_mb, percent, eta (time left, like 0:12:34) and status (Downloading, Queued, Paused). On this page it uses a sample queue." }),
    V("rb_sabnzbd_history", "SABnzbd history, last %1 hours", [val("N")], "Array", { style:"sabnzbd",
      tooltip:"A list of records, one for each job that finished in that time: name, status (Completed or Failed), size_mb, when it finished and, for a failure, why it failed." }),
    V("rb_sabnzbd_diskspace", "SABnzbd diskspace", [], "Array", { style:"sabnzbd",
      tooltip:"A list of records, one for each of SABnzbd's folders (the download folder first): folder and free_gb." }),
    S("rb_sabnzbd_pause", "%1 SABnzbd", [{ type:"field_dropdown", name:"ACTION", options:[["pause","pause"],["resume","resume"]] }],
      { style:"sabnzbd", inputsInline:true, tooltip:"Pauses or resumes the whole download queue. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. On this page nothing really pauses." }),
