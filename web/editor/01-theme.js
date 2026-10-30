  // 01-theme.js: Colours and Blockly's theme.
  /* ---------- Colours and theme ---------- */
  const HUES = {
    events:"#D9A21B", control:"#E07B24", operators:"#4E9E3A", text:"#2F9A7A", variables:"#E0583A",
    lists:"#C2413B", procedures:"#D04F7E", draft:"#3E7BFA", claude:"#5B5BD6", review:"#8A55D6",
    you:"#1E94A8", output:"#2E9E5E", time:"#5F7F96", pictures:"#B4469E", memory:"#8C5A2B", files:"#556B8D", records:"#3B8A8C", ha:"#2C7FB8", agent:"#6E7F1A", tools:"#8A7A14", conn:"#C2185B", homey:"#2E8B57"
  };
  function shade(hex, amt){
    const n = parseInt(hex.slice(1), 16);
    let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    const f = c => Math.round(amt < 0 ? c * (1 + amt) : c + (255 - c) * amt);
    return "#" + [f(r), f(g), f(b)].map(x => x.toString(16).padStart(2, "0")).join("");
  }
  const style = (hex, hat) => Object.assign({ colourPrimary:hex, colourSecondary:shade(hex, .35), colourTertiary:shade(hex, -.25) }, hat ? { hat:"cap" } : {});
  const blockStyles = {
    events_hat:style(HUES.events, true), events:style(HUES.events), time:style(HUES.time), control:style(HUES.control), operators:style(HUES.operators), text:style(HUES.text),
    draft:style(HUES.draft), claude:style(HUES.claude), review:style(HUES.review), you:style(HUES.you), output:style(HUES.output), pictures:style(HUES.pictures), memory:style(HUES.memory), files:style(HUES.files), records:style(HUES.records), ha:style(HUES.ha), ha_hat:style(HUES.ha, true),
    agent:style(HUES.agent), tools:style(HUES.tools), conn:style(HUES.conn), conn_hat:style(HUES.conn, true), homey:style(HUES.homey), homey_hat:style(HUES.homey, true),
    loop_blocks:style(HUES.control), logic_blocks:style(HUES.operators), math_blocks:style(HUES.operators),
    text_blocks:style(HUES.text), list_blocks:style(HUES.lists), variable_blocks:style(HUES.variables),
    variable_dynamic_blocks:style(HUES.variables), procedure_blocks:style(HUES.procedures), hat_blocks:style(HUES.events, true)
  };
  const categoryStyles = {};
  Object.keys(HUES).forEach(k => categoryStyles[k] = { colour:HUES[k] });
  categoryStyles.search = { colour:"#9AA0B8" };
  function makeTheme(dark){
    return Blockly.Theme.defineTheme(dark ? "rb-dark" : "rb-light", {
      base: Blockly.Themes.Classic, blockStyles, categoryStyles,
      componentStyles: dark ? {
        workspaceBackgroundColour:"#1B1E2A", toolboxBackgroundColour:"#161925", toolboxForegroundColour:"#E9EBF3",
        flyoutBackgroundColour:"#22263A", flyoutForegroundColour:"#E9EBF3", flyoutOpacity:0.96,
        scrollbarColour:"#3A3F55", insertionMarkerColour:"#FFFFFF", insertionMarkerOpacity:0.3, cursorColour:"#7C93FF"
      } : {
        workspaceBackgroundColour:"#FFFFFF", toolboxBackgroundColour:"#F3F4F8", toolboxForegroundColour:"#1B1E2B",
        flyoutBackgroundColour:"#EBEDF4", flyoutForegroundColour:"#1B1E2B", flyoutOpacity:0.96,
        scrollbarColour:"#C9CDDB", insertionMarkerColour:"#000000", insertionMarkerOpacity:0.2, cursorColour:"#2F4BDB"
      },
      fontStyle:{ family:'"Atkinson Hyperlegible", system-ui, sans-serif' + (window.ST_I18N && window.ST_I18N.font ? ', "' + window.ST_I18N.font + '"' : ""), weight:"bold", size:12 },
      startHats:true
    });
  }
  function isDark(){
    const t = document.documentElement.getAttribute("data-theme");
    if (t === "dark") return true;
    if (t === "light") return false;
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

