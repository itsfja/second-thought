#!/usr/bin/env node
/* What tools/pages.py needs for the gallery's web pages (#438), from the editor's own code (tools/export.cjs's page):
   for each gallery file, its Python as the page exports it, what it can do as the page works it out, and its blocks as
   an outline. Prints JSON: [{ file, python, can:[capability ids], outline:[[depth, words], ...] }, ...].

    node tools/gallery_data.cjs gallery/*.json
*/
"use strict";
const fs = require("fs"), path = require("path");
const { loadPage } = require("./export.cjs");

const page = loadPage("en");
const out = [];
for (const file of process.argv.slice(2)) {
  const text = fs.readFileSync(file, "utf8");
  const name = JSON.parse(text).name || path.basename(file, ".json");
  const python = page.__exportBlockFile(text, name);
  out.push({ file:path.basename(file), python, can:[...page.__capabilityCheck().program], outline:page.__programOutline() });
}
process.stdout.write(JSON.stringify(out));
