  // 07-format.js: Block file format versions and their migrations.
  // ----- Block file format -----
  // Block files say which version of the blocks' shapes they were saved with ("version"). When a block's fields or inputs
  // change shape, bump FORMAT_VERSION and add MIGRATIONS[the old version]: a function that turns a program saved with that
  // version into one for the next. Every way a program loads runs them: imports, exported Python, saved programs, the
  // gallery, and what the page kept from last time. CONTRIBUTING.md: changing a block's shape needs a migration.
  let FORMAT_VERSION = 1;
  let MIGRATIONS = {};
  // { state, from }: the program brought up to FORMAT_VERSION, and the version it was saved with. A program from a newer
  // page can't be read safely, so that throws.
  function migrateProgram(state, from){
    let v = Math.max(1, Math.floor(Number(from)) || 1);
    const start = v;
    if (v > FORMAT_VERSION) throw new Error(tr("This program was saved by a newer Second Thought (block format {theirs}; this page reads up to {ours}). Open it on the newest page.", { theirs:v, ours:FORMAT_VERSION }));
    if (v < FORMAT_VERSION) state = JSON.parse(JSON.stringify(state));
    while (v < FORMAT_VERSION) { state = MIGRATIONS[v](state) || state; v++; }
    return { state, from:start };
  }
  window.__setFormat = (version, migrations) => { FORMAT_VERSION = version; MIGRATIONS = migrations || {}; };  // for the tests
  const GALLERY_GROUPS = { github:"Community: GitHub", coding:"Community: code and data", news:"Community: news", money:"Community: money",
    calendar:"Community: calendar and email", home:"Community: home and baking", learning:"Community: teaching", odds:"Community: odds and ends" };
  window.__galleryGroups = Object.values(GALLERY_GROUPS);  // every group's name is a page word, used or not yet
  const COMMUNITY_GROUPS = Object.keys(GALLERY_GROUPS).filter(k => GALLERY.some(g => (g.category || "odds") === k)).map(k => GALLERY_GROUPS[k]);
  EXAMPLE_CATEGORIES.splice(EXAMPLE_CATEGORIES.indexOf("Research") + 1, 0, ...COMMUNITY_GROUPS);
  GALLERY.forEach(g => EXAMPLE_LIST.push({ key:g.key, cat:GALLERY_GROUPS[g.category] || GALLERY_GROUPS.odds, title:g.title, desc:g.description, tip:g.tip, author:g.author,
    runtime:g.runtime, file:g.file, community:true, build:() => migrateProgram(JSON.parse(JSON.stringify(g.program)), g.version).state }));
  EXAMPLE_LIST.forEach(e => { EXAMPLES[e.key] = e.build; });
  window.__exampleStates = () => Object.keys(EXAMPLES).map(k => [k, EXAMPLES[k]()]);  // for the tests
  // The examples' titles, descriptions and tips in the page's language ("examples" in i18n/<language>.json, by key).
  // Shared gallery programs keep the words their authors wrote.
  window.__examples = () => EXAMPLE_LIST.filter(e => !e.community).map(e => ({ key:e.key, cat:e.cat, title:e.en ? e.en.title : e.title,
    desc:e.en ? e.en.desc : e.desc, tip:e.en ? e.en.tip : e.tip }));
  if (window.ST_I18N && I18N.examples) EXAMPLE_LIST.forEach(e => {
    const t = !e.community && I18N.examples[e.key];
    if (t) { e.en = { title:e.title, desc:e.desc, tip:e.tip }; Object.assign(e, { title:t.title || e.title, desc:t.desc || e.desc, tip:t.tip || e.tip }); }
  });
  const exampleByKey = k => EXAMPLE_LIST.find(e => e.key === k);
  /* Every example opens with a note on its first block saying what it does and what to try. */
  function exampleState(key){
    const e = exampleByKey(key), state = EXAMPLES[key]();
    const first = state.blocks.blocks[0];
    if (e && first && !first.icons) first.icons = { comment:{ text:(e.community ? tr("{title} (shared by {author})", { title:e.title, author:e.author }) : e.title) + "\n\n" + e.desc + "\n\n" + tr("Try: {tip}", { tip:e.tip }), pinned:false, height:150, width:300 } };
    return state;
  }
  // What a program in a saved state can do, worked out the same way as programCapabilities, without loading it.
  function stateCapabilities(state){
    const w = new Blockly.Workspace();
    try {
      Blockly.serialization.workspaces.load(state, w);
      const got = new Set(w.getAllBlocks(false).map(blockCapability).filter(Boolean));
      return CAPABILITIES.filter(c => got.has(c[0]));
    } finally { w.dispose(); }
  }
  window.__gallery = () => GALLERY.map(g => ({ key:g.key, file:g.file, title:g.title, unknown:unknownTypes(g.program),
    can:stateCapabilities(g.program).map(c => c[0]), card:(document.querySelector('.gal-card[data-key="' + g.key + '"]') || {}).innerText || "" }));
  const communityCaps = {};
  function communityCanText(e){
    if (!(e.key in communityCaps)) communityCaps[e.key] = stateCapabilities(e.build());
    return capabilitySentence(communityCaps[e.key]) || tr("It only uses your models: it doesn't connect to anything else.");
  }

