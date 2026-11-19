// 23-gallery-share.js: Offering the program on the canvas to the community gallery (#437). Share… opens a form
// that shows the card as it will look in Browse examples — with what the program can do worked out from its blocks,
// as now — and opens a prefilled "Share a program" issue form on GitHub with the #p= link (#436) in it. Nothing is
// sent until Open is pressed. A maintainer accepts the issue with the gallery-accepted label, and
// .github/workflows/gallery-share.yml turns it into the pull request that adds gallery/<name>.json.
  const REPO_URL = "https://github.com/itsfja/second-thought";
  const SHARE_TEMPLATE = "share-a-program.yml";
  const SHARE_FIELDS = ["sh-title", "sh-category", "sh-desc", "sh-tip", "sh-author"];

  function shareFields(){
    return { title:$("sh-title").value.trim(), category:$("sh-category").value,
             desc:$("sh-desc").value.trim(), tip:$("sh-tip").value.trim(), author:$("sh-author").value.trim() };
  }
  function fillShareCategory(){
    const sel = $("sh-category"); sel.innerHTML = "";
    Object.keys(GALLERY_GROUPS).forEach(k => {
      const o = document.createElement("option"); o.value = k; o.textContent = tr(GALLERY_GROUPS[k]); sel.appendChild(o);
    });
    if (!GALLERY_GROUPS[sel.value]) sel.value = "odds";
  }
  // The community card as it will look (08-workspace.js's fillGallery builds the same), updated as the form is filled.
  function shareCard(){
    const f = shareFields(), card = $("sh-card"); card.innerHTML = "";
    const t = document.createElement("h4"); t.textContent = f.title || $("io-name").value.trim() || "my-program"; card.appendChild(t);
    const by = document.createElement("p"); by.className = "by";
    by.textContent = tr("Shared by {author}, made with runtime {runtime}.", { author:f.author, runtime:RUNTIME_VERSION }); card.appendChild(by);
    const d = document.createElement("p"); d.textContent = f.desc; card.appendChild(d);
    const can = document.createElement("p"); can.className = "can";
    can.textContent = capabilitySentence(programCapabilities()) || tr("It only uses your models: it doesn't connect to anything else."); card.appendChild(can);
    const tip = document.createElement("p"); tip.className = "tip"; tip.textContent = tr("Try: {tip}", { tip:f.tip }); card.appendChild(tip);
    const btn = document.createElement("button"); btn.type = "button"; btn.textContent = tr("Load this program"); btn.disabled = true; card.appendChild(btn);
  }
  function shMsg(text, kind){ const m = $("sh-msg"); m.textContent = text; m.className = "msg" + (kind ? " " + kind : ""); }
  // The issue form's address: every field prefilled from the form, plus the #p= link, the file name and the runtime.
  function shareUrl(f, link){
    const p = new URLSearchParams();
    p.set("template", SHARE_TEMPLATE);
    p.set("title", "Share a program: " + f.title);
    p.set("name", slug($("io-name").value));
    p.set("category", GALLERY_GROUPS[f.category] || f.category);  // the dropdown's label, as it appears in the form
    p.set("description", f.desc);
    p.set("tip", f.tip);
    p.set("author", f.author);
    p.set("runtime", RUNTIME_VERSION);
    p.set("link", link);
    return REPO_URL + "/issues/new?" + p.toString();
  }
  async function buildShareUrl(){
    const f = shareFields();
    if (!f.title || !f.desc || !f.tip || !f.author) return "";
    const link = await programLink().catch(() => "");
    return link ? shareUrl(f, link) : "";
  }
  window.__shareUrl = () => buildShareUrl();  // for the tests
  function wireShare(){
    registerDrawer("share", ["share-prog"], () => { fillShareCategory(); shareCard(); $("sh-title").focus(); });
    $("share-prog").onclick = () => toggleDrawer("share");
    SHARE_FIELDS.forEach(id => $(id).addEventListener("input", shareCard));
    $("sh-open").onclick = async () => {
      const f = shareFields();
      if (!f.title || !f.desc || !f.tip || !f.author) { shMsg(tr("Fill in the title, a description, a tip and your name first."), "bad"); return; }
      const link = await programLink().catch(() => "");
      if (!link) { shMsg(tr("This browser can't pack a link (no CompressionStream); copy the block file instead."), "bad"); return; }
      shMsg("", "");
      window.open(shareUrl(f, link), "_blank", "noopener");
    };
  }
  wireShare();
