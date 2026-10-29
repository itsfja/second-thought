"""End-to-end tests of the page and exported programs in every language."""
from e2e.common import *  # noqa: F401,F403
from e2e.sources import PY_MARK  # noqa: E402


UNTRANSLATED = {"rb_use_model.TIER", "rb_with_model.TIER"}  # model names stay as they are


# Blockly's own words that the palette shows: its built-in blocks (if, repeat, maths, logic, text, lists, variables,
# My Blocks) and the right-click menu. A language Blockly has no msg file for supplies all of these in "blocklyMsg".
BLOCKLY_MSGS = """ADD_COMMENT CHANGE_VALUE_TITLE CLEAN_UP COLLAPSED_WARNINGS_WARNING COLLAPSE_ALL COLLAPSE_BLOCK
CONTROLS_FLOW_STATEMENTS_OPERATOR_BREAK CONTROLS_FLOW_STATEMENTS_OPERATOR_CONTINUE CONTROLS_FLOW_STATEMENTS_TOOLTIP_BREAK
CONTROLS_FLOW_STATEMENTS_TOOLTIP_CONTINUE CONTROLS_FLOW_STATEMENTS_WARNING CONTROLS_FOREACH_TITLE CONTROLS_FOREACH_TOOLTIP
CONTROLS_FOR_TITLE CONTROLS_FOR_TOOLTIP CONTROLS_IF_ELSEIF_TOOLTIP CONTROLS_IF_ELSE_TOOLTIP CONTROLS_IF_IF_TOOLTIP
CONTROLS_IF_MSG_ELSE CONTROLS_IF_MSG_ELSEIF CONTROLS_IF_MSG_IF CONTROLS_IF_TOOLTIP_1 CONTROLS_IF_TOOLTIP_2 CONTROLS_IF_TOOLTIP_3
CONTROLS_IF_TOOLTIP_4 CONTROLS_REPEAT_INPUT_DO CONTROLS_REPEAT_TITLE CONTROLS_REPEAT_TOOLTIP CONTROLS_WHILEUNTIL_OPERATOR_UNTIL
CONTROLS_WHILEUNTIL_OPERATOR_WHILE CONTROLS_WHILEUNTIL_TOOLTIP_UNTIL CONTROLS_WHILEUNTIL_TOOLTIP_WHILE DELETE_ALL_BLOCKS
DELETE_BLOCK DELETE_VARIABLE DELETE_VARIABLE_CONFIRMATION DELETE_X_BLOCKS DISABLE_BLOCK DUPLICATE_BLOCK DUPLICATE_COMMENT
ENABLE_BLOCK EXPAND_ALL EXPAND_BLOCK EXTERNAL_INPUTS HELP INLINE_INPUTS LISTS_CREATE_EMPTY_TITLE LISTS_CREATE_EMPTY_TOOLTIP
LISTS_CREATE_WITH_CONTAINER_TITLE_ADD LISTS_CREATE_WITH_CONTAINER_TOOLTIP LISTS_CREATE_WITH_INPUT_WITH
LISTS_CREATE_WITH_ITEM_TOOLTIP LISTS_CREATE_WITH_TOOLTIP LISTS_GET_INDEX_FIRST LISTS_GET_INDEX_FROM_END
LISTS_GET_INDEX_FROM_START LISTS_GET_INDEX_GET LISTS_GET_INDEX_GET_REMOVE LISTS_GET_INDEX_LAST LISTS_GET_INDEX_RANDOM
LISTS_GET_INDEX_REMOVE LISTS_GET_INDEX_TOOLTIP_GET_FIRST LISTS_GET_INDEX_TOOLTIP_GET_FROM LISTS_GET_INDEX_TOOLTIP_GET_LAST
LISTS_GET_INDEX_TOOLTIP_GET_RANDOM LISTS_GET_INDEX_TOOLTIP_GET_REMOVE_FIRST LISTS_GET_INDEX_TOOLTIP_GET_REMOVE_FROM
LISTS_GET_INDEX_TOOLTIP_GET_REMOVE_LAST LISTS_GET_INDEX_TOOLTIP_GET_REMOVE_RANDOM LISTS_GET_INDEX_TOOLTIP_REMOVE_FIRST
LISTS_GET_INDEX_TOOLTIP_REMOVE_FROM LISTS_GET_INDEX_TOOLTIP_REMOVE_LAST LISTS_GET_INDEX_TOOLTIP_REMOVE_RANDOM
LISTS_INDEX_FROM_END_TOOLTIP LISTS_INDEX_FROM_START_TOOLTIP LISTS_INLIST LISTS_ISEMPTY_TITLE LISTS_ISEMPTY_TOOLTIP
LISTS_LENGTH_TITLE LISTS_LENGTH_TOOLTIP LISTS_SET_INDEX_INPUT_TO LISTS_SET_INDEX_INSERT LISTS_SET_INDEX_SET
LISTS_SET_INDEX_TOOLTIP_INSERT_FIRST LISTS_SET_INDEX_TOOLTIP_INSERT_FROM LISTS_SET_INDEX_TOOLTIP_INSERT_LAST
LISTS_SET_INDEX_TOOLTIP_INSERT_RANDOM LISTS_SET_INDEX_TOOLTIP_SET_FIRST LISTS_SET_INDEX_TOOLTIP_SET_FROM
LISTS_SET_INDEX_TOOLTIP_SET_LAST LISTS_SET_INDEX_TOOLTIP_SET_RANDOM LOGIC_BOOLEAN_FALSE LOGIC_BOOLEAN_TOOLTIP
LOGIC_BOOLEAN_TRUE LOGIC_COMPARE_TOOLTIP_EQ LOGIC_COMPARE_TOOLTIP_GT LOGIC_COMPARE_TOOLTIP_GTE LOGIC_COMPARE_TOOLTIP_LT
LOGIC_COMPARE_TOOLTIP_LTE LOGIC_COMPARE_TOOLTIP_NEQ LOGIC_NEGATE_TITLE LOGIC_NEGATE_TOOLTIP LOGIC_OPERATION_AND
LOGIC_OPERATION_OR LOGIC_OPERATION_TOOLTIP_AND LOGIC_OPERATION_TOOLTIP_OR LOGIC_TERNARY_CONDITION LOGIC_TERNARY_IF_FALSE
LOGIC_TERNARY_IF_TRUE LOGIC_TERNARY_TOOLTIP MATH_ARITHMETIC_TOOLTIP_ADD MATH_ARITHMETIC_TOOLTIP_DIVIDE
MATH_ARITHMETIC_TOOLTIP_MINUS MATH_ARITHMETIC_TOOLTIP_MULTIPLY MATH_ARITHMETIC_TOOLTIP_POWER MATH_CHANGE_TITLE
MATH_CHANGE_TOOLTIP MATH_MODULO_TITLE MATH_MODULO_TOOLTIP MATH_NUMBER_TOOLTIP MATH_RANDOM_INT_TITLE MATH_RANDOM_INT_TOOLTIP
MATH_ROUND_OPERATOR_ROUND MATH_ROUND_OPERATOR_ROUNDDOWN MATH_ROUND_OPERATOR_ROUNDUP MATH_ROUND_TOOLTIP NEW_NUMBER_VARIABLE
NEW_STRING_VARIABLE NEW_VARIABLE NEW_VARIABLE_TITLE NEW_VARIABLE_TYPE_TITLE PROCEDURES_ALLOW_STATEMENTS
PROCEDURES_BEFORE_PARAMS PROCEDURES_CALLNORETURN_TOOLTIP PROCEDURES_CALLRETURN_TOOLTIP PROCEDURES_CALL_BEFORE_PARAMS
PROCEDURES_CALL_DISABLED_DEF_WARNING PROCEDURES_CREATE_DO PROCEDURES_DEFNORETURN_COMMENT PROCEDURES_DEFNORETURN_PROCEDURE
PROCEDURES_DEFNORETURN_TITLE PROCEDURES_DEFNORETURN_TOOLTIP PROCEDURES_DEFRETURN_RETURN PROCEDURES_DEFRETURN_TOOLTIP
PROCEDURES_DEF_DUPLICATE_WARNING PROCEDURES_HIGHLIGHT_DEF PROCEDURES_IFRETURN_TOOLTIP PROCEDURES_IFRETURN_WARNING
PROCEDURES_MUTATORARG_TITLE PROCEDURES_MUTATORARG_TOOLTIP PROCEDURES_MUTATORCONTAINER_TITLE PROCEDURES_MUTATORCONTAINER_TOOLTIP
REDO REMOVE_COMMENT RENAME_VARIABLE RENAME_VARIABLE_TITLE TEXT_CHANGECASE_OPERATOR_LOWERCASE TEXT_CHANGECASE_OPERATOR_TITLECASE
TEXT_CHANGECASE_OPERATOR_UPPERCASE TEXT_CHANGECASE_TOOLTIP TEXT_CREATE_JOIN_ITEM_TOOLTIP TEXT_CREATE_JOIN_TITLE_JOIN
TEXT_CREATE_JOIN_TOOLTIP TEXT_ISEMPTY_TITLE TEXT_ISEMPTY_TOOLTIP TEXT_JOIN_TITLE_CREATEWITH TEXT_JOIN_TOOLTIP
TEXT_LENGTH_TITLE TEXT_LENGTH_TOOLTIP TEXT_TEXT_TOOLTIP UNDO UNNAMED_KEY VARIABLES_DEFAULT_NAME VARIABLES_GET_CREATE_SET
VARIABLES_GET_TOOLTIP VARIABLES_SET VARIABLES_SET_CREATE_GET VARIABLES_SET_TOOLTIP VARIABLE_ALREADY_EXISTS
VARIABLE_ALREADY_EXISTS_FOR_ANOTHER_TYPE VARIABLE_ALREADY_EXISTS_FOR_A_PARAMETER""".split()


def blockly_english():
    """Blockly's own English messages, from its msg/en.js."""
    src = (VENDOR / "blockly/package/msg/en.js").read_text(encoding="utf-8")
    return {k: json.loads('"' + v + '"') for k, v in re.findall(r'Blockly\.Msg\["(\w+)"\] = "((?:[^"\\]|\\.)*)"', src)}


def same_export(files):
    """An export's files with what differs between any two exports taken out: the date, the blocks' random ids, the
    note an example opens with (a comment on its first block, written in the page's language), and the words the
    program prints in that language (EXPORT_LANGUAGE and EXPORT_WORDS, and the language line in its settings)."""
    out = {}
    for k, v in files.items():
        v = "\n".join(l for l in v.split("\n") if "Exported from Second Thought on" not in l and not l.startswith("; language = en"))
        v = re.sub(r"# The language this program prints in.*?\n}\n\n", "", v, flags=re.S)
        if PY_MARK in v:
            code, rest = v.split(PY_MARK, 1)
            b64 = "".join(l[2:] for l in rest.split("# BLOCKS:", 1)[1].split("\n") if l.startswith("# "))
            blocks = json.loads(base64.b64decode(b64).decode("utf-8"))
            strip = lambda o: {k_: strip(x) for k_, x in o.items() if k_ not in ("id", "icons")} if isinstance(o, dict) else [strip(x) for x in o] if isinstance(o, list) else o  # noqa: E731
            v = (code, strip(blocks))
        out[k] = v
    return out


# Calls whose first argument the page shows through tr(): its words are what a translation needs.
SHOWN_BY = ["tr", "addStep", "askStep", "askJSON", "waitForYou", "setStatus", "connNote", ".done", "libMsg", "showBanner", "offerChoice", ("ioMsg", 1)]


def code_texts(page):
    """The texts in the page's code that reach tr(): the first argument of each call in SHOWN_BY, when it is a text
    or a choice of texts (cond ? "a" : "b"). An argument joined from parts ("Homey: " + name) isn't a text to translate."""
    js = page[page.index('id="community-gallery"'):]
    found = set()
    for name in SHOWN_BY:
        name, which = name if isinstance(name, tuple) else (name, 0)  # (name, n): the nth argument is the shown one
        pattern = (r"\." + name[1:] if name.startswith(".") else r"(?<![\w.])" + name) + r"\("
        for m in re.finditer(pattern, js):
            i, depth, arg, quote, n = m.end(), 0, [], None, 0
            while i < len(js):
                c = js[i]
                if quote:
                    if c == "\\":
                        arg.append(js[i:i + 2]); i += 2; continue
                    if c == quote:
                        quote = None
                elif c in "\"'`":
                    quote = c
                elif c in "([{":
                    depth += 1
                elif c in ")]}":
                    if depth == 0:
                        break
                    depth -= 1
                elif c == "," and depth == 0:
                    if n == which:
                        break
                    n, arg = n + 1, []
                    i += 1
                    continue
                arg.append(c); i += 1
            if n != which:
                continue
            arg = "".join(arg)
            bare = re.sub(r'"(?:[^"\\]|\\.)*"', '""', arg)
            if "+" in bare or not arg.lstrip().startswith(('"', "(", "{")) and "?" not in bare:
                continue
            # Only the texts it can show: the whole argument, or a choice after ? or : (not those in a condition).
            found |= {json.loads('"' + t + '"') for t in re.findall(r'(?:[?:]|\|\|)\s*"((?:[^"\\]|\\.)*)"|^\s*"((?:[^"\\]|\\.)*)"', arg) for t in t if t}
    return {t for t in found if re.search(r"[A-Za-z]", t)}


async def i18n_tests():
    """Every language has every block's words, and a program is the same whatever language its blocks are shown in."""
    print("Languages")
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        async def page(lang=None):
            pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            await pg.route("**/*", route)
            # Only the first load: after that, the page's own choice (the picker) must stand.
            await pg.add_init_script(MOCK + (f";try{{if(!sessionStorage.getItem('lang-set')){{localStorage.setItem('second-thought-language','{lang}');"
                                             "sessionStorage.setItem('lang-set','1')}}catch(e){}" if lang else ""))
            await pg.goto("http://test/")
            await pg.wait_for_timeout(1500)
            return pg, errors

        en, en_errors = await page()
        info = await en.evaluate("window.__i18n()")
        page_info = await en.evaluate("window.__pageI18n()")
        examples = await en.evaluate("window.__examples()")
        starters = await en.evaluate("window.__starters()")
        # Every text the page's code shows through tr() (directly, or as a step name, a step's label or the status), as written in the source.
        tr_texts = code_texts(PAGE)
        page_needs = set(page_info["keys"]) | set(page_info["categories"]) | tr_texts | set(await en.evaluate("window.__runWords()"))
        check(len(page_info["keys"]) > 60 and "Run" in page_info["keys"] and "Step: on" in tr_texts,
              f"the page lists its own words for translators ({len(page_info['keys'])} in the page, {len(tr_texts)} set by code)")
        check(info["lang"] == "en" and info["langs"], f"the page has {len(info['langs'])} translation(s) of the block palette, and English when none is chosen")
        for code, t in info["langs"].items():
            problems = []
            for d in info["defs"]:
                mine = t["blocks"].get(d["type"], {})
                for k, v in d.items():
                    if re.fullmatch(r"message\d+", k) or k == "tooltip":
                        if k not in mine:
                            problems.append(f"{d['type']}.{k} missing")
                        elif k != "tooltip" and sorted(re.findall(r"%\d+", v)) != sorted(re.findall(r"%\d+", mine[k])):
                            problems.append(f"{d['type']}.{k} has different %N placeholders")
                for k, args in d.items():
                    if re.fullmatch(r"args\d+", k):
                        for a in args:
                            if a.get("type") == "field_dropdown" and isinstance(a.get("options"), list) and f"{d['type']}.{a['name']}" not in UNTRANSLATED:
                                labels = t["options"].get(f"{d['type']}.{a['name']}", {})
                                problems += [f"{d['type']}.{a['name']}={o[1]} missing" for o in a["options"]
                                             if isinstance(o[0], str) and o[0] != o[1] and o[1] not in labels]
            known = {d["type"] for d in info["defs"]}
            problems += [f"{b} isn't a block" for b in t["blocks"] if b not in known]
            problems += [f"category {c} missing" for c in info["categories"] if c not in t["categories"]]
            problems += [f"label {x!r} missing" for x in info["labels"] if x not in t["labels"]]
            if t.get("blockly") and not (VENDOR / "blockly/package/msg" / (t["blockly"] + ".js")).exists():
                problems.append(f"Blockly has no msg/{t['blockly']}.js")
            if "blocklyMsg" in t:
                en_msg, bm = blockly_english(), t["blocklyMsg"]
                own = [k for k in BLOCKLY_MSGS if not (isinstance(bm.get(k), str) and bm[k].strip())]
                own += [f"{k} isn't one of Blockly's palette words" for k in bm if k not in BLOCKLY_MSGS]
                own += [f"{k} has different %N placeholders" for k in bm if k in en_msg
                        and sorted(re.findall(r"%\d+", en_msg[k])) != sorted(re.findall(r"%\d+", bm[k]))]
                check(not own, f"{t.get('name', code)} ({code}) brings its own words for all {len(BLOCKLY_MSGS)} of Blockly's palette messages"
                      + (f": {own[:8]}" if own else ""))
            check(not problems, f"{t.get('name', code)} ({code}) has every block's words, tooltip and choices, with matching placeholders"
                  + (f": {problems[:8]}" if problems else ""))
            if "starters" in t:
                missing = sorted(set(starters) - set(t["starters"]))
                extra = sorted(set(t["starters"]) - set(starters))
                check(not missing and not extra, f"{t.get('name', code)} ({code}) has the words in every palette block, and no others"
                      + (f": missing {missing[:6]}" if missing else "") + (f"; not in the palette {extra[:6]}" if extra else ""))
            if "examples" in t:
                want = {e["key"] for e in examples}
                lacking = sorted(k for k in want if not all((t["examples"].get(k) or {}).get(f) for f in ("title", "desc", "tip")))
                extra = sorted(set(t["examples"]) - want)
                check(not lacking and not extra, f"{t.get('name', code)} ({code}) has every example's title, description and tip, and no others"
                      + (f": missing {lacking[:6]}" if lacking else "") + (f"; not examples {extra[:6]}" if extra else ""))
            if "page" in t:
                missing = sorted(page_needs - set(t["page"]))
                stale = sorted(set(t["page"]) - page_needs)
                check(not missing and not stale, f"{t.get('name', code)} ({code}) has every one of the page's own words, and none it doesn't use"
                      + (f": missing {missing[:6]}" if missing else "") + (f"; not on the page {stale[:6]}" if stale else ""))

        for code in info["langs"]:
            pg, errors = await page(code)
            got = await pg.evaluate("""() => { const ws = Blockly.getMainWorkspace(), b = ws.newBlock('rb_start'), w = ws.newBlock('rb_wait');
                const r = { lang:window.ST_LANG, start:b.toString(), wait:w.getField('UNIT').getText(), cat:ws.getToolbox().getToolboxItems()[0].getName(), ifmsg:Blockly.Msg.CONTROLS_IF_MSG_IF };
                b.dispose(); w.dispose(); return r; }""")
            t = info["langs"][code]
            check(got["lang"] == code and got["start"] == t["blocks"]["rb_start"]["message0"] and got["cat"] == t["categories"]["Events"]
                  and got["wait"] == t["options"]["rb_wait.UNIT"]["s"] and got["ifmsg"] not in ("if", None),
                  f"with {code} chosen, blocks, choices, categories and Blockly's own blocks are in {t.get('name', code)} ({got})")
            if "blocklyMsg" in t:
                own = await pg.evaluate("""(bm) => { const ws = Blockly.getMainWorkspace(), r = ws.newBlock('controls_repeat_ext'), l = ws.newBlock('lists_length');
                    const out = { differ:Object.keys(bm).filter(k => Blockly.Msg[k] !== bm[k]), repeat:r.toString(), length:l.toString() };
                    r.dispose(); l.dispose(); return out; }""", t["blocklyMsg"])
                check(not own["differ"] and own["repeat"].startswith(t["blocklyMsg"]["CONTROLS_REPEAT_TITLE"].split("%1")[0].strip()),
                      f"with {code} chosen, Blockly's own blocks use the language's own words ({own})")
            if t.get("font"):
                _, sample, script, _ = FONTS[t["font"]]
                f = await pg.evaluate("""async ([font, sample, script]) => { await document.fonts.load('bold 12px "' + font + '"', sample);
                    const ws = Blockly.getMainWorkspace();
                    const text = [...document.querySelectorAll('.blocklyText')].map(e => e.textContent).join(' ');
                    return { link:!!document.querySelector('link[href*="family=' + font.replace(/ /g, '+') + '"]'),
                             loaded:document.fonts.check('bold 12px "' + font + '"', sample),
                             signs:new RegExp(script, 'u').test(text), page:getComputedStyle(document.body).fontFamily.includes(font),
                             blocks:ws.getTheme().fontStyle.family.includes(font) }; }""", [t["font"], sample, script])
                english = await en.evaluate("() => [...document.querySelectorAll('link')].some(l => /fonts\\.googleapis\\.com\\/css2\\?family=Noto/.test(l.href))")
                check(all(f.values()) and not english,
                      f"with {code} chosen, the page loads {t['font']} and its blocks show the signs; English doesn't load it ({f}, english: {english})")
            want = t.get("dir", "ltr")
            dirs = await pg.evaluate("""() => ({ page:document.documentElement.dir || 'ltr', blocks:Blockly.getMainWorkspace().RTL,
                toolbox:getComputedStyle(document.querySelector('.blocklyToolboxDiv') || document.body).direction,
                code:getComputedStyle(document.getElementById('io-paste')).direction, log:getComputedStyle(document.body).direction })""")
            check(dirs["page"] == want and dirs["blocks"] == (want == "rtl") and dirs["log"] == want and dirs["code"] == "ltr",
                  f"with {code} chosen, the page and its blocks run {'right to left' if want == 'rtl' else 'left to right'}, and code stays left to right ({dirs})")
            same = []
            for ex in ("review", "a_inbox", "ha_doorbell"):
                for pg_ in (en, pg):
                    await pg_.select_option("#example", ex)
                    await pg_.click("#load")
                a, b = [{f["name"]: f["text"] for f in await x.evaluate("window.__exportFiles()")} for x in (en, pg)]
                same.append(same_export(a) == same_export(b))
            check(all(same), f"the same programs export exactly the same files whether their blocks are shown in English or {code} ({same})")
            if "page" in t:
                P = t["page"]
                shown = await pg.evaluate("""() => ({ missing:window.__pageI18n().missing, lang:document.documentElement.lang,
                    run:document.getElementById('run').textContent, load:document.getElementById('load').textContent,
                    step:document.getElementById('step-toggle').textContent, find:document.getElementById('block-search').placeholder,
                    group:document.querySelector('#gal-body h3').textContent, opt:document.querySelector('#example optgroup').label,
                    hint:document.querySelector('#bk .hint').innerHTML })""")
                check(not shown["missing"] and shown["lang"] == code and shown["run"] == P["Run"] and shown["load"] == P["Load"]
                      and shown["step"] == P["Step: off"] and shown["find"] == P["Find a block…"] and shown["group"] == P["Writing"]
                      and shown["opt"] == P["Writing"] and "<b>" in shown["hint"],
                      f"with {code} chosen, the page's buttons, panels and example groups are in {t.get('name', code)} ({shown})")
                await pg.click("#step-toggle")
                on = await pg.text_content("#step-toggle")
                await pg.click("#step-toggle")
                await pg.click("#bk-toggle")
                await pg.select_option("#bk-1", "quick")
                bk = await pg.text_content("#bk-toggle")
                await pg.select_option("#bk-1", "")
                await pg.click("#bk-toggle")
                check(on == P["Step: on"] and bk == P["Backups ({n})"].replace("{n}", "1"),
                      f"labels the page changes as you go are in {t.get('name', code)} too ({on!r}, {bk!r})")
                if "starters" in t:
                    texts = await pg.evaluate("""() => { const out = [];
                        const walk = items => items.forEach(it => { if (it.kind === 'block' && it.type === 'rb_say') out.push(it.inputs.TEXT.shadow.fields.TEXT); if (it.contents) walk(it.contents); });
                        walk(Blockly.getMainWorkspace().options.languageTree.contents); return out; }""")
                    check(t["starters"]["Hello"] in texts, f"with {code} chosen, the words already in the palette's blocks are in {t.get('name', code)} ({texts})")
                if "examples" in t:
                    E = t["examples"]["review"]
                    await pg.select_option("#example", "review")
                    await pg.click("#load")
                    shown = await pg.evaluate("""() => ({ desc:document.getElementById('ex-desc').textContent,
                        option:document.querySelector('#example option[value="review"]').textContent,
                        card:document.querySelector('.gal-card[data-key="review"] h4').textContent,
                        note:Blockly.getMainWorkspace().getTopBlocks(true)[0].getCommentText() })""")
                    check(shown["option"] == E["title"] and shown["card"] == E["title"] and E["desc"] in shown["desc"]
                          and P["Try: {tip}"].replace("{tip}", E["tip"]) in shown["desc"] and shown["note"].startswith(E["title"]) and E["tip"] in shown["note"],
                          f"with {code} chosen, the examples' titles, descriptions and tips are in {t.get('name', code)} ({shown['option']!r}, {shown['desc'][:80]!r})")
                if "python" in t:
                    W = t["python"]
                    await pg.select_option("#example", "review")
                    await pg.click("#load")
                    files = {f["name"]: f["text"] for f in await pg.evaluate("window.__exportFiles()")}
                    en_files = {f["name"]: f["text"] for f in await en.evaluate("window.__exportFiles()")}
                    prog = next(n for n in files if n.endswith(".py"))
                    check(f'EXPORT_LANGUAGE = "{code}"' in files[prog] and "EXPORT_WORDS = {" in files[prog] and "language = en" in files["second-thought.ini"]
                          and "EXPORT_WORDS = {" not in next(v for k, v in en_files.items() if k.endswith(".py")),
                          f"a program exported with the page in {code} carries its words (and one exported in English doesn't)"
)
                    with tempfile.TemporaryDirectory() as tmp:
                        for n, text in files.items():
                            pathlib.Path(tmp, n).write_text(text, encoding="utf-8")
                        env = {k: v for k, v in os.environ.items() if not k.endswith(("_API_KEY", "_TOKEN")) and not k.startswith("RB_")}
                        # UTF-8 out, as the other runs of exported programs here: a Windows pipe's own code page can't always show every letter.
                        env.update(RB_APPROVE="no", SECOND_THOUGHT_INI=str(pathlib.Path(tmp, "second-thought.ini")), PYTHONIOENCODING="utf-8")
                        outs = {}
                        for lang_, args in (("", []), ("en", []), ("", ["--doctor"])):
                            r = subprocess.run([sys.executable, prog] + args, cwd=tmp, env=dict(env, **({"RB_LANGUAGE": lang_} if lang_ else {})),
                                               capture_output=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=120)
                            outs[(lang_, tuple(args))] = r.stdout
                    said, english, doctor = outs[("", ())], outs[("en", ())], outs[("", ("--doctor",))]
                    check(W["Task set"] in said and W["\n✖ Run stopped: {msg}"].split("{msg}")[0].strip() in said
                          and W["Claude needs a key. Put ANTHROPIC_API_KEY = your-key {where_keys} (https://console.anthropic.com)."].split("{where_keys}")[0] in said,
                          f"the exported program prints its run log and errors in {t.get('name', code)} ({said.strip()[-160:]!r})")
                    check("Task set" in english and "Run stopped: Claude needs a key" in english, f"language = en switches it back to English ({english.strip()[-120:]!r})")
                    check(W["Only reading: nothing is sent, posted, switched or charged.\n"].strip() in doctor and "  FAIL  " in doctor,
                          f"--doctor speaks {t.get('name', code)} too, keeping ok, FAIL and NOTE as they are ({doctor.strip()[:120]!r})")
                    if t.get("font") and FONTS[t["font"]][3]:
                        # A script terminals can't show (Linear B, cuneiform): the terminal gets its transcription, in Latin letters only.
                        odd = sorted({ch for ch in said + doctor if ch.isalpha() and not unicodedata.name(ch, "").startswith("LATIN")})
                        check(not odd and all(not c.isalpha() or unicodedata.name(c, "").startswith("LATIN") for c in W["Task set"]),
                              f"the exported program prints {t.get('name', code)} in transcription, with no letters outside Latin script ({odd[:10]}; {W['Task set']!r})")
                done_word = P["done in {time}"].split("{time}")[0]
                await pg.select_option("#example", "review")
                await pg.click("#load")
                status = await run_program(pg)
                check(status.startswith(done_word), f"a program still runs with the page in {code} ({status})")
                await pg.select_option("#example", "interview")
                await pg.click("#load")
                status = await run_program(pg)
                log = await pg.evaluate("""() => ({ names:[...document.querySelectorAll('.step-name')].map(x => x.textContent),
                    pills:[...document.querySelectorAll('.pill')].map(x => x.textContent), states:[...document.querySelectorAll('.pill')].map(x => x.dataset.state || '') })""")
                check(status.startswith(done_word) and P["Question for you"] in log["names"] and P["Write a first draft"] in log["names"]
                      and P["Result"] in log["names"] and P["done"] in log["pills"] and P["answered"] in log["pills"]
                      and "done" in log["states"] and "running" not in log["states"] and not any(x in ("done", "running", "answered") for x in log["pills"]),
                      f"the run log's steps, labels and status are in {t.get('name', code)}, and the page still tracks each step in English ({status}; {log['names'][:5]}; {log['pills'][:5]})")
                await load_state(pg, {"blocks": {"languageVersion": 0, "blocks": [{"type": "rb_start", "x": 30, "y": 30, "next": {"block": {"type": "rb_generate"}}}]}})
                await pg.click("#run")
                await pg.wait_for_function("document.getElementById('run') && !document.getElementById('run').disabled", timeout=15000)
                bodies = await pg.eval_on_selector_all(".step-body", "e => e.map(x => x.innerText)")
                check(any(P["Add a 'set task to' block before this step."] in b for b in bodies),
                      f"what the run log says inside a step, such as why a run stopped, is in {t.get('name', code)} ({bodies[-1:]})")
                await pg.click("#io-toggle")
                await paste(pg, (ROOT / "gallery" / "rye-news-telegram.json").read_text(encoding="utf-8"))
                await pg.click("#io-load-paste")
                msg = await pg.text_content("#io-import-msg")
                await pg.click("#io-toggle")
                await pg.click("#mem-toggle")
                where = await pg.text_content("#mem-where")
                await pg.click("#mem-toggle")
                wanted = P["It can {things}."].replace("{things}", P["send Telegram messages"])
                loaded = re.escape(P["Loaded \u201c{name}\u201d ({n} blocks)."]).replace(re.escape("{name}"), ".+").replace(re.escape("{n}"), r"\d+")
                check(re.match(loaded, msg) and wanted in msg
                      and P["Exported to Python, it asks you before its first run."] in msg and where in P.values(),
                      f"the page's messages, and what a program can do, are in {t.get('name', code)} ({msg!r}; {where!r})")
            await pg.select_option("#example", "brainstorm")
            await pg.click("#load")
            n = await pg.evaluate("Blockly.getMainWorkspace().getAllBlocks(false).length")
            await pg.select_option("#lang", "en")
            await pg.wait_for_load_state("load")
            await pg.wait_for_timeout(1500)
            back = await pg.evaluate("[window.ST_LANG, Blockly.getMainWorkspace().getAllBlocks(false).length, document.documentElement.dir || 'ltr', Blockly.getMainWorkspace().RTL]")
            check(back == ["en", n, "ltr", False], f"switching the blocks' language keeps the program on the canvas, left to right again in English ({back}, {n} blocks before)")
            check(not errors, f"no page errors in {code}" + (f": {errors[:2]}" if errors else ""))
            await pg.close()
        check(not en_errors, "no page errors in English")
        await browser.close()
