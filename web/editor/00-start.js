  // 00-start.js: The editor's opening: shared limits and small helpers ($, STORE_KEY, MAX_*). Every file below runs inside the same function, so names declared in one are seen by the rest.
(function(){
  const $ = id => document.getElementById(id);
  const STORE_KEY = "reflection-blocks-program-v3";
  const MAX_AI_CALLS = 60, MAX_STEPS = 20000, MAX_DEPTH = 60, MAX_SCRIPTS = 100, MAX_LIVE = 30;

