  // 23-connections.js: the Connections list in Settings (#446): one checkbox per service; the turned-on services show
  // as sections inside the Connections category of the palette (the logic is in 03-toolbox.js, visibleToolbox()).
  /* ---------- The Connections drawer ---------- */
  (function connDrawer(){
    const list = $("conn-list");
    serviceCats().forEach(c => {
      const lab = document.createElement("label");
      lab.className = "conn-item";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = enabledServices().has(c.service);
      cb.setAttribute("data-service", c.service);
      cb.addEventListener("change", () => {
        const en = enabledServices();
        if (cb.checked) en.add(c.service); else en.delete(c.service);
        saveEnabled(en);
        applyToolbox();
      });
      const name = document.createElement("span");
      name.textContent = catName(c.name);  // a palette category's own words
      lab.appendChild(cb);
      lab.appendChild(name);
      list.appendChild(lab);
    });
    registerDrawer("conn", ["conn-toggle"], () => $("conn-title").focus());
    $("conn-toggle").onclick = () => toggleDrawer("conn");
  })();
