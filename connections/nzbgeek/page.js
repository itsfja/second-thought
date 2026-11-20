  /* NZBGeek on the page (#400): a sample search. Exported Python talks to its Newznab API: a search that only
     reads, and a fetch that always asks. */
  const nzbgeekSample = () => { connNote("NZBGeek"); return (CONN.nzbgeek || {})["search"] || []; };
  function nzbgeekSearch(query){
    const out = nzbgeekSample().map(r => { const a = {};
      (r["newznab:attr"] || []).forEach(x => { const v = x["@attributes"] || x; a[v.name] = v.value; });
      return { title:str(r.title), id:str(r.guid || "").split("/").pop(),
        size_mb:a.size ? cents(num(a.size) / 1048576) : "", grabs:a.grabs ? Math.trunc(num(a.grabs)) : "",
        posted:str(a.usenetdate || r.pubDate || "").slice(0, 16), group:str(a.group || "") }; });
    addStep("NZBGeek search", { mono:true, text:out.map(r => r.title + (r.size_mb ? " (" + r.size_mb + " MB)" : "")).join("\n") || tr("(nothing)") })
      .done(tr("{n} found", { n:out.length }), "ok");
    return out;
  }
  async function nzbgeekFetch(id){
    const what = "fetch the NZB for " + id + " from NZBGeek";
    if (!(await confirmAction(what + " (it always asks)"))) return false;
    addStep("NZBGeek", { mono:true, text:what }).done(tr("done"), "ok");
    return true;
  }
