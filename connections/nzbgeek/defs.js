    /* NZBGeek (#400): a search that only reads, and a fetch that always asks */
    V("rb_nzbgeek_search", "search NZBGeek for %1", [val("QUERY")], "Array", { style:"nzbgeek",
      tooltip:"A list of records, one for each release the indexer has for these words: title, id, size_mb, grabs, posted (when it was posted) and group. It only reads: nothing is ever downloaded. Needs NZBGEEK_API_KEY in second-thought.ini. On this page it uses a sample search." }),
    S("rb_nzbgeek_fetch", "fetch the NZB for %1", [val("ID")],
      { style:"nzbgeek", inputsInline:true, tooltip:"Fetches one release's NZB file and saves it as <id>.nzb. It always asks you first, even when nothing else asks, and with nobody there to say yes it doesn't run. It never hands anything to a downloader: the file is saved, that's all. On this page nothing really fetches." }),
