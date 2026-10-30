  // 04-examples.js: Building example programs: the helpers the example library uses.
  /* ---------- Example programs ---------- */
  const st = (o) => ({ block:o });
  const sh = (type, fields) => ({ shadow:{ type, fields } });
  const tx = t => sh("text", { TEXT:t });
  const lt = t => sh("rb_longtext", { TEXT:t });
  const nm = n => sh("math_number", { NUM:n });
  const blk = (type, fields, inputs, next, extra) => Object.assign({ type }, fields ? { fields } : {}, inputs ? { inputs } : {}, next ? { next:st(next) } : {}, extra || {});
  const chain = (...bs) => { for (let i = bs.length - 2; i >= 0; i--) bs[i].next = st(bs[i + 1]); return bs[0]; };
  const getv = id => ({ block:{ type:"variables_get", fields:{ VAR:{ id } } } });
  const setv = (id, value) => ({ type:"variables_set", fields:{ VAR:{ id } }, inputs:{ VALUE:value } });
  const progMulti = (vars, tops) => ({ variables:vars.map(([id, name]) => ({ id, name })), blocks:{ languageVersion:0, blocks:tops.map(([x, y, top]) => Object.assign({ x, y }, top)) } });
  const prog = (vars, top) => ({ variables:vars.map(([id, name]) => ({ id, name })), blocks:{ languageVersion:0, blocks:[Object.assign({ x:30, y:30 }, top)] } });

  const EXAMPLES = {
    review: () => prog([], chain(
      blk("rb_start"),
      blk("rb_task", null, { TEXT:lt("Explain what autolyse is in sourdough baking, for a home baker's reference page.\nCover what it is, why bakers use it, and how long to rest the dough.") }),
      blk("rb_generate"),
      blk("rb_reflect", null, { CRITERIA:lt("accurate and specific; beginner friendly, jargon explained; under 200 words"), ROUNDS:nm(3), FIX:st(blk("rb_revise")) }),
      blk("rb_result")
    )),
    brainstorm: () => prog([["v_ideas","ideas"],["v_idea","idea"],["v_best","best"],["v_bestScore","best score"],["v_s","score"]], chain(
      blk("rb_start"),
      setv("v_ideas", { block:blk("rb_ask_list", null, { TEXT:tx("6 catchy headlines for a beginner's guide to sourdough autolyse") }) }),
      setv("v_best", tx("")),
      setv("v_bestScore", nm(0)),
      blk("controls_forEach", { VAR:{ id:"v_idea" } }, { LIST:getv("v_ideas"), DO:st(chain(
        setv("v_s", { block:blk("rb_score", null, { TEXT:getv("v_idea"), CRITERIA:tx("clear, catchy, accurate, under 10 words") }) }),
        blk("rb_say", null, { TEXT:{ block:{ type:"text_join", extraState:{ itemCount:3 }, inputs:{ ADD0:getv("v_s"), ADD1:tx("/10  "), ADD2:getv("v_idea") } } } }),
        blk("controls_if", null, {
          IF0:{ block:{ type:"logic_compare", fields:{ OP:"GT" }, inputs:{ A:getv("v_s"), B:getv("v_bestScore") } } },
          DO0:st(chain(setv("v_bestScore", getv("v_s")), setv("v_best", getv("v_idea"))))
        })
      )) }),
      blk("rb_finish_with", null, { TEXT:getv("v_best") })
    )),
    interview: () => prog([], chain(
      blk("rb_start"),
      blk("rb_ask_me", null, { TEXT:tx("What should I write about, and for whom?") }),
      blk("rb_task", null, { TEXT:{ block:{ type:"rb_answer" } } }),
      blk("rb_generate"),
      blk("controls_whileUntil", { MODE:"UNTIL" }, {
        BOOL:{ block:blk("rb_approve", null, { TEXT:{ block:{ type:"rb_draft" } } }) },
        DO:st(chain(
          blk("rb_ask_me", null, { TEXT:tx("What should change?") }),
          blk("rb_rework", null, { TEXT:{ block:{ type:"rb_answer" } } })
        ))
      }),
      blk("rb_result")
    )),
    gemini: () => prog([], chain(
      blk("rb_start"),
      blk("rb_task", null, { TEXT:lt("Explain what autolyse is in sourdough baking, for a home baker's reference page.") }),
      blk("rb_generate"),
      blk("controls_repeat_ext", null, { TIMES:nm(3), DO:st(chain(
        blk("rb_with_model", { TIER:"gemini-default" }, { DO:st(blk("rb_review", null, { CRITERIA:lt("accurate and specific; beginner friendly, jargon explained; under 200 words") })) }),
        blk("controls_if", null, { IF0:{ block:{ type:"rb_passed" } }, DO0:st(blk("controls_flow_statements", { FLOW:"BREAK" })) }),
        blk("rb_revise")
      )) }),
      blk("rb_result")
    )),
    files: () => prog([["v_doc","document"],["v_sum","summary"]], chain(
      blk("rb_start"),
      setv("v_doc", { block:blk("rb_file_choose") }),
      blk("rb_retry", null, { TIMES:nm(3), DO:st(
        setv("v_sum", { block:blk("rb_ask", null, { TEXT:{ block:{ type:"text_join", extraState:{ itemCount:2 }, inputs:{
          ADD0:lt("Summarise this document in five bullet points, then list any action items.\n\n"), ADD1:getv("v_doc") } } } }) })
      ) }),
      blk("rb_add_result", null, { TEXT:getv("v_sum") }),
      blk("rb_try", null, {
        DO:st(blk("rb_file_save", { EXT:"md" }, { VALUE:{ block:{ type:"rb_result_text" } }, NAME:tx("summary") })),
        FAIL:st(blk("rb_say", null, { TEXT:{ block:{ type:"text_join", extraState:{ itemCount:2 }, inputs:{ ADD0:tx("Couldn't save the file: "), ADD1:{ block:{ type:"rb_error" } } } } } }))
      }),
      blk("rb_result")
    )),
    memory: () => prog([["v_ideas","ideas"],["v_pick","headline"]], chain(
      blk("rb_start"),
      blk("controls_if", null, {
        IF0:{ block:blk("rb_mem_has", null, { NAME:tx("last run") }) },
        DO0:st(blk("rb_say", null, { TEXT:{ block:{ type:"text_join", extraState:{ itemCount:2 }, inputs:{ ADD0:tx("Last run: "), ADD1:{ block:blk("rb_mem_get", null, { NAME:tx("last run") }) } } } } }))
      }),
      setv("v_ideas", { block:blk("rb_ask_list", null, { TEXT:{ block:{ type:"text_join", extraState:{ itemCount:2 }, inputs:{
        ADD0:lt("5 catchy headlines for a sourdough baking blog post. Each must be different in topic from all of these earlier ones:\n"),
        ADD1:{ block:blk("rb_mem_get", null, { NAME:tx("used headlines") }) } } } } }) }),
      setv("v_pick", { block:{ type:"lists_getIndex", fields:{ MODE:"GET", WHERE:"FIRST" }, inputs:{ VALUE:getv("v_ideas") } } }),
      blk("rb_mem_add", { KIND:"permanent" }, { VALUE:getv("v_pick"), NAME:tx("used headlines") }),
      blk("rb_mem_set", { KIND:"permanent" }, { VALUE:{ block:blk("rb_now", { PART:"datetime" }) }, NAME:tx("last run") }),
      blk("rb_mem_set_for", { UNIT:"d" }, { VALUE:getv("v_pick"), NAME:tx("today's headline"), N:nm(1) }),
      blk("rb_finish_with", null, { TEXT:getv("v_pick") })
    )),
    pictures: () => prog([["v_pic","picture"],["v_notes","notes"]], chain(
      blk("rb_start"),
      setv("v_pic", { block:blk("rb_img_draw", null, { TEXT:lt("A cross-section of a sourdough loaf showing an open, airy crumb and a dark blistered crust. Flat illustration, warm colours, no text.") }) }),
      blk("rb_img_show", null, { IMG:getv("v_pic") }),
      blk("controls_repeat_ext", null, { TIMES:nm(2), DO:st(chain(
        setv("v_notes", { block:blk("rb_img_ask", null, { TEXT:lt("You are an illustration editor. List the 3 changes that would most improve this picture, one short line each."), IMG:getv("v_pic") }) }),
        setv("v_pic", { block:blk("rb_img_change", null, { IMG:getv("v_pic"), TEXT:{ block:{ type:"variables_get", fields:{ VAR:{ id:"v_notes" } } } } }) }),
        blk("rb_img_show", null, { IMG:getv("v_pic") })
      )) }),
      blk("rb_add_result", null, { TEXT:getv("v_pic") }),
      blk("rb_result")
    )),
    parallel: () => progMulti([], [
      [30, 30, chain(
        blk("rb_start"),
        blk("rb_task", null, { TEXT:lt("Explain what autolyse is in sourdough baking, for a home baker's reference page") }),
        blk("rb_generate"),
        blk("rb_add_result", null, { TEXT:{ block:{ type:"rb_draft" } } }),
        blk("rb_broadcast_wait", null, { MSG:tx("get feedback") }),
        blk("rb_result")
      )],
      [640, 30, chain(
        blk("rb_receive", { MSG:"get feedback" }),
        blk("rb_add_result", null, { TEXT:{ block:{ type:"text_join", extraState:{ itemCount:2 }, inputs:{
          ADD0:tx("Accuracy check: "),
          ADD1:{ block:blk("rb_ask", null, { TEXT:{ block:{ type:"text_join", extraState:{ itemCount:2 }, inputs:{
            ADD0:tx("In two sentences, point out any factual errors in this text, or say it is accurate:\n\n"), ADD1:{ block:{ type:"rb_draft" } } } } } }) }
        } } } })
      )],
      [640, 340, chain(
        blk("rb_receive", { MSG:"get feedback" }),
        blk("rb_add_result", null, { TEXT:{ block:{ type:"text_join", extraState:{ itemCount:2 }, inputs:{
          ADD0:tx("Beginner check: "),
          ADD1:{ block:blk("rb_ask", null, { TEXT:{ block:{ type:"text_join", extraState:{ itemCount:2 }, inputs:{
            ADD0:tx("In two sentences, suggest the single change that would most help a beginner understand this text:\n\n"), ADD1:{ block:{ type:"rb_draft" } } } } } }) }
        } } } })
      )]
    ]),
    translate: () => prog([["v_lang","language"]], chain(
      blk("rb_start"),
      blk("rb_task", null, { TEXT:lt("Write a 3-sentence welcome for a sourdough recipe website") }),
      blk("rb_generate"),
      blk("rb_add_result", null, { TEXT:{ block:{ type:"text_join", extraState:{ itemCount:2 }, inputs:{ ADD0:tx("English: "), ADD1:{ block:{ type:"rb_draft" } } } } } }),
      blk("controls_forEach", { VAR:{ id:"v_lang" } }, {
        LIST:{ block:{ type:"lists_create_with", extraState:{ itemCount:2 }, inputs:{ ADD0:tx("French"), ADD1:tx("Spanish") } } },
        DO:st(blk("rb_add_result", null, { TEXT:{ block:{ type:"text_join", extraState:{ itemCount:3 }, inputs:{
          ADD0:getv("v_lang"), ADD1:tx(": "),
          ADD2:{ block:blk("rb_rewrite", null, { TEXT:{ block:{ type:"rb_draft" } }, HOW:{ block:{ type:"text_join", extraState:{ itemCount:2 }, inputs:{ ADD0:tx("translate into "), ADD1:getv("v_lang") } } } }) }
        } } } }))
      }),
      blk("rb_result")
    ))
  };


